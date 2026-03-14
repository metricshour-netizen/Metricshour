"""
Trade data update — WITS bulk download (annual) + UN Comtrade API (quarterly).
Source: https://wits.worldbank.org/data/public/
Runs annually on Jan 15 at 2am UTC for full refresh.
Also runs quarterly (Apr/Jul/Oct 1st) for recent-year Comtrade updates.

WITS: ~500MB CSV, all countries × all countries, annual trade flows.
Comtrade: API for recent quarters not yet in WITS bulk.

No API key required for either. Commercial use permitted.
"""

import csv
import gzip
import io
import logging
import time
from datetime import date

import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.country import Country, TradePair

log = logging.getLogger(__name__)

# WITS bulk download — annual merchandise trade (UNCTAD/Comtrade based)
# URL pattern: all reporters × all partners, HS commodity level, USD thousands
WITS_BULK_BASE = "https://wits.worldbank.org/data/public/WITS_Trade_Summary"
WITS_FILE_URL = "https://wits.worldbank.org/data/public/WITS_Trade_Summary.zip"

# UN Comtrade API v2 (no key for limited requests, reasonable for quarterly updates)
COMTRADE_BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"

# Minimum trade value to store (USD) — filter out noise
MIN_TRADE_USD = 100_000


def _build_iso3_map(db) -> tuple[dict[str, int], dict[str, str]]:
    """
    Returns:
        iso3_to_id: {alpha3: country_db_id}
        iso2_to_id: {alpha2: country_db_id}
    """
    countries = db.execute(select(Country.code, Country.code3, Country.id)).all()
    iso3 = {c.code3: c.id for c in countries if c.code3}
    iso2 = {c.code: c.id for c in countries}
    return iso3, iso2


def _fetch_wits_bulk(year: int) -> list[dict]:
    """
    Download WITS trade summary CSV for a given year.
    Returns list of {reporter_iso3, partner_iso3, trade_value_usd, exports_usd, imports_usd}.

    WITS CSV columns (approximate):
      Reporter ISO3, Partner ISO3, Year, TradeFlowCode, TradeValue (USD thousands)
    """
    url = f"https://wits.worldbank.org/API/V1/SDMX/V21/datasource/tradestats-trade/reporter/all/year/{year}/partner/all/product/Total/indicator/XPRT-TRD-VL+MPRT-TRD-VL?format=csvformat"

    try:
        log.info(f"WITS: fetching {year} trade matrix...")
        r = requests.get(url, timeout=120, stream=True)
        r.raise_for_status()
    except Exception:
        log.exception(f"WITS bulk download failed for {year}")
        return []

    records: dict[tuple, dict] = {}  # (reporter, partner) → {exports, imports}

    try:
        content = r.content
        # Handle gzip or plain CSV
        if content[:2] == b'\x1f\x8b':
            content = gzip.decompress(content)

        reader = csv.DictReader(io.StringIO(content.decode("utf-8", errors="replace")))
        for row in reader:
            reporter = (row.get("Reporter ISO3") or row.get("ReporterISO") or "").strip().upper()
            partner = (row.get("Partner ISO3") or row.get("PartnerISO") or "").strip().upper()
            indicator = (row.get("Indicator") or row.get("IndicatorCode") or "").strip()
            try:
                value_usd = float(row.get("Value") or 0) * 1000  # WITS reports in USD thousands
            except (ValueError, TypeError):
                continue

            if not reporter or not partner or partner in ("WLD", "ALL"):
                continue
            if value_usd < MIN_TRADE_USD:
                continue

            key = (reporter, partner)
            if key not in records:
                records[key] = {"reporter": reporter, "partner": partner, "exports": 0.0, "imports": 0.0}

            if "XPRT" in indicator or "EXP" in indicator:
                records[key]["exports"] += value_usd
            elif "MPRT" in indicator or "IMP" in indicator:
                records[key]["imports"] += value_usd

    except Exception:
        log.exception("WITS CSV parse failed")
        return []

    return [
        {
            "reporter_iso3": v["reporter"],
            "partner_iso3": v["partner"],
            "exports_usd": v["exports"],
            "imports_usd": v["imports"],
            "trade_value_usd": v["exports"] + v["imports"],
        }
        for v in records.values()
        if v["exports"] + v["imports"] > MIN_TRADE_USD
    ]


def _fetch_comtrade_recent(year: int, iso3_to_id: dict[str, int]) -> list[dict]:
    """
    Fetch recent-year bilateral trade from UN Comtrade public API.
    Used for years not yet in WITS bulk download.
    """
    # Get top 50 reporters by trade volume (major economies only for API quota)
    major_reporters = [
        "USA", "CHN", "DEU", "GBR", "FRA", "JPN", "CAN", "ITA", "NLD", "KOR",
        "BEL", "IND", "MEX", "AUS", "ESP", "CHE", "RUS", "BRA", "AUT", "SWE",
        "POL", "NOR", "DNK", "FIN", "THA", "MYS", "SGP", "IDN", "ZAF", "SAU",
        "ARE", "TUR", "ARG", "CHL", "COL", "PER", "PHL", "VNM", "PAK", "BGD",
    ]

    all_rows = []
    for reporter in major_reporters:
        url = f"{COMTRADE_BASE}/{reporter}/all"
        params = {"period": str(year), "format": "JSON", "maxRecords": 500}
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 429:
                log.warning("Comtrade rate limit hit, backing off 60s")
                time.sleep(60)
                continue
            r.raise_for_status()
            data = r.json()
            entries = data.get("data", [])
            for e in entries:
                partner = e.get("partnerCode") or e.get("ptCode") or ""
                if not partner or partner in ("0", "896", "899"):  # world/unspecified
                    continue
                fob = float(e.get("primaryValue") or e.get("TradeValue") or 0)
                if fob < MIN_TRADE_USD:
                    continue
                flow = str(e.get("flowCode") or e.get("rgCode") or "")
                all_rows.append({
                    "reporter": reporter,
                    "partner_code": str(partner),
                    "value": fob,
                    "flow": "X" if flow in ("X", "1") else "M",
                })
            time.sleep(0.5)
        except Exception:
            log.warning(f"Comtrade: failed for {reporter}/{year}")
            time.sleep(2)
            continue

    # Aggregate by (reporter, partner)
    aggregated: dict[tuple, dict] = {}
    for row in all_rows:
        key = (row["reporter"], row["partner_code"])
        if key not in aggregated:
            aggregated[key] = {"exports": 0.0, "imports": 0.0}
        if row["flow"] == "X":
            aggregated[key]["exports"] += row["value"]
        else:
            aggregated[key]["imports"] += row["value"]

    return [
        {
            "reporter_iso3": k[0],
            "partner_iso3": k[1],
            "exports_usd": v["exports"],
            "imports_usd": v["imports"],
            "trade_value_usd": v["exports"] + v["imports"],
        }
        for k, v in aggregated.items()
        if v["exports"] + v["imports"] > MIN_TRADE_USD
    ]


def _upsert_trade_rows(db, rows: list[dict], year: int, iso3_to_id: dict, iso2_to_id: dict) -> int:
    """Convert raw trade rows to DB records and upsert. Returns row count."""
    batch = []
    for row in rows:
        # Try ISO3 first, then ISO2
        exp_id = iso3_to_id.get(row["reporter_iso3"]) or iso2_to_id.get(row["reporter_iso3"])
        imp_id = iso3_to_id.get(row["partner_iso3"]) or iso2_to_id.get(row["partner_iso3"])
        if not exp_id or not imp_id or exp_id == imp_id:
            continue

        exports = row.get("exports_usd", 0.0) or 0.0
        imports = row.get("imports_usd", 0.0) or 0.0
        total = exports + imports

        batch.append({
            "exporter_id": exp_id,
            "importer_id": imp_id,
            "year": year,
            "trade_value_usd": total,
            "exports_usd": exports if exports > 0 else None,
            "imports_usd": imports if imports > 0 else None,
            "balance_usd": exports - imports if exports > 0 and imports > 0 else None,
            "top_export_products": None,
            "top_import_products": None,
            "exporter_gdp_share_pct": None,
            "importer_gdp_share_pct": None,
        })

    if not batch:
        return 0

    # Process in chunks to avoid huge single statements
    chunk_size = 1000
    total_inserted = 0
    for i in range(0, len(batch), chunk_size):
        chunk = batch[i:i + chunk_size]
        stmt = pg_insert(TradePair).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_trade_pair_year",
            set_={
                "trade_value_usd": stmt.excluded.trade_value_usd,
                "exports_usd": stmt.excluded.exports_usd,
                "imports_usd": stmt.excluded.imports_usd,
                "balance_usd": stmt.excluded.balance_usd,
            },
        )
        db.execute(stmt)
        db.commit()
        total_inserted += len(chunk)

    return total_inserted


@app.task(name='tasks.trade_update.update_trade_data_annual', bind=True, max_retries=1)
def update_trade_data_annual(self):
    """
    Full WITS trade matrix refresh — runs annually on Jan 15.
    Downloads last 2 complete years from WITS.
    """
    db = SessionLocal()
    try:
        iso3_map, iso2_map = _build_iso3_map(db)
        current_year = date.today().year
        total = 0

        for year in [current_year - 2, current_year - 1]:
            rows = _fetch_wits_bulk(year)
            if not rows:
                log.warning(f"WITS: no rows for {year}, trying Comtrade fallback")
                rows = _fetch_comtrade_recent(year, iso3_map)

            if rows:
                n = _upsert_trade_rows(db, rows, year, iso3_map, iso2_map)
                total += n
                log.info(f"Trade: {year} — {n} pairs upserted ({len(rows)} raw rows)")
            else:
                log.warning(f"Trade: no data for {year}")

        return f"ok: {total} trade pairs upserted"

    except Exception as exc:
        db.rollback()
        log.exception("Annual trade update failed")
        raise self.retry(exc=exc, countdown=600)
    finally:
        db.close()


@app.task(name='tasks.trade_update.update_trade_data_quarterly', bind=True, max_retries=2)
def update_trade_data_quarterly(self):
    """
    Quarterly Comtrade update for current year — runs Apr/Jul/Oct 1st at 3am UTC.
    Uses Comtrade API for recent data not yet in WITS bulk.
    """
    db = SessionLocal()
    try:
        iso3_map, iso2_map = _build_iso3_map(db)
        current_year = date.today().year

        rows = _fetch_comtrade_recent(current_year, iso3_map)
        if not rows:
            log.warning(f"Comtrade: no rows for {current_year}")
            return "ok: no rows"

        n = _upsert_trade_rows(db, rows, current_year, iso3_map, iso2_map)
        log.info(f"Trade quarterly: {current_year} — {n} pairs upserted")
        return f"ok: {n} trade pairs"

    except Exception as exc:
        db.rollback()
        log.exception("Quarterly trade update failed")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
