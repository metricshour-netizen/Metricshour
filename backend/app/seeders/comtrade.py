"""
Seed bilateral trade pairs from World Bank WITS API (free, no key required).

Endpoint: https://wits.worldbank.org/API/V1/SDMX/V21/datasource/tradestats-trade
- Free, no auth, no rate limiting
- SDMX XML format — parsed with xml.etree.ElementTree
- Values in thousands USD (multiplied by 1000 before storing)
- Annual data, exports + imports per reporter country

Coverage: all countries with ISO3 codes in our DB (~200 reporters).
Data: latest available year (tries 2023, falls back to 2022, then 2021).
Each reporter → top 15 partners stored.

Run:  python seed.py --only comtrade
      python seed.py --only comtrade --refresh   (re-fetch all including existing)

Idempotent — safe to re-run. Skips countries with existing 2022+ data unless
--refresh is passed.
"""

import logging
import os
import time
import xml.etree.ElementTree as ET

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Country, TradePair

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

WITS_BASE = "https://wits.worldbank.org/API/V1/SDMX/V21/datasource/tradestats-trade"
YEARS = [2023, 2022, 2021]
TOP_N_PARTNERS = 15
REQUEST_DELAY = 0.5  # WITS has no strict rate limit


def _fetch_bilateral(iso3: str, year: int, flow: str) -> dict[str, float]:
    """
    Fetch bilateral trade for one country/year/flow.
    flow: 'exports' or 'imports'
    Returns dict of {partner_iso3: value_usd}.
    """
    indicator = "XPRT-TRD-VL" if flow == "exports" else "MPRT-TRD-VL"
    url = (
        f"{WITS_BASE}/reporter/{iso3}/year/{year}"
        f"/partner/ALL/product/Total/indicator/{indicator}"
    )
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code in (404, 400):
            return {}
        resp.raise_for_status()
        return _parse_wits_xml(resp.text)
    except Exception as exc:
        log.warning("WITS failed %s %s %s: %s", iso3, year, flow, exc)
        return {}


def _parse_wits_xml(xml_text: str) -> dict[str, float]:
    """Parse SDMX XML → {partner_iso3: value_usd}. Values in thousands USD → USD."""
    result: dict[str, float] = {}
    try:
        root = ET.fromstring(xml_text)
        for series in root.iter():
            if not series.tag.endswith("}Series") and series.tag != "Series":
                continue
            partner = series.attrib.get("PARTNER", "")
            # Skip non-country partners (aggregates are 3+ chars but not ISO3, or known codes)
            if not partner or len(partner) != 3 or partner in ("WLD", "ECS", "SSF", "SAS", "EAS", "NAC", "LCN", "MEA", "EUU", "HIC", "LMC", "LIC", "UMC", "MIC", "OHI"):
                continue
            for obs in series:
                if obs.tag.endswith("}Obs") or obs.tag == "Obs":
                    val = obs.attrib.get("OBS_VALUE")
                    if val:
                        try:
                            usd = float(val) * 1000  # WITS values are in thousands USD
                            if usd > 0:
                                # Keep highest value if multiple obs per partner
                                if partner not in result or usd > result[partner]:
                                    result[partner] = usd
                        except ValueError:
                            pass
    except ET.ParseError as exc:
        log.warning("XML parse error: %s", exc)
    return result


def seed_comtrade(db: Session, refresh: bool = False) -> None:
    countries = db.query(Country).all()
    if not countries:
        raise RuntimeError("No countries in DB. Run the country seeder first.")

    iso3_to_id: dict[str, int] = {c.code3: c.id for c in countries if c.code3}
    id_to_country: dict[int, Country] = {c.id: c for c in countries}
    log.info("Loaded %d countries", len(iso3_to_id))

    if refresh:
        reporters = [c for c in countries if c.code3]
    else:
        existing_exporters = set(
            row[0] for row in db.execute(
                select(TradePair.exporter_id).where(TradePair.year >= 2021).distinct()
            ).all()
        )
        reporters = [c for c in countries if c.code3 and c.id not in existing_exporters]

    log.info(
        "Processing %d reporters (skipping %d with existing data)",
        len(reporters),
        len(countries) - len(reporters),
    )

    # Accumulate: (exporter_id, importer_id) → (exports_usd, year)
    export_map: dict[tuple[int, int], tuple[float, int]] = {}

    for i, country in enumerate(reporters):
        iso3 = country.code3
        log.info("[%d/%d] %s (%s)", i + 1, len(reporters), country.name, iso3)

        exports: dict[str, float] = {}
        actual_year = None
        for year in YEARS:
            exports = _fetch_bilateral(iso3, year, "exports")
            if exports:
                actual_year = year
                break
            time.sleep(REQUEST_DELAY)

        if not exports:
            log.info("  No data — skipping")
            continue

        # Keep top N partners that exist in our DB
        ranked = sorted(exports.items(), key=lambda x: -x[1])
        added = 0
        for partner_iso3, value in ranked:
            if added >= TOP_N_PARTNERS:
                break
            partner_id = iso3_to_id.get(partner_iso3)
            if not partner_id or partner_id == country.id:
                continue
            export_map[(country.id, partner_id)] = (value, actual_year)
            added += 1

        log.info("  %d partners (year %s)", added, actual_year)
        time.sleep(REQUEST_DELAY)

    # Upsert trade_pairs
    pairs_upserted = 0
    for (exp_id, imp_id), (exports_usd, year) in export_map.items():
        imports_usd = export_map.get((imp_id, exp_id), (None, None))[0]

        trade_value = (exports_usd or 0) + (imports_usd or 0) if imports_usd else exports_usd
        balance = (exports_usd or 0) - (imports_usd or 0) if imports_usd else exports_usd

        stmt = pg_insert(TradePair).values(
            exporter_id=exp_id,
            importer_id=imp_id,
            year=year,
            trade_value_usd=trade_value,
            exports_usd=exports_usd,
            imports_usd=imports_usd,
            balance_usd=balance,
            data_source=f"UN Comtrade {year}",
            top_export_products=None,
            top_import_products=None,
            exporter_gdp_share_pct=None,
            importer_gdp_share_pct=None,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_trade_pair_year",
            set_={
                "trade_value_usd": stmt.excluded.trade_value_usd,
                "exports_usd": stmt.excluded.exports_usd,
                "imports_usd": stmt.excluded.imports_usd,
                "balance_usd": stmt.excluded.balance_usd,
                "data_source": stmt.excluded.data_source,
            },
        )
        db.execute(stmt)
        pairs_upserted += 1

        if pairs_upserted % 200 == 0:
            db.commit()
            log.info("Committed %d pairs so far…", pairs_upserted)

    db.commit()
    log.info("Comtrade/WITS seed complete — %d trade pairs upserted.", pairs_upserted)


def run(refresh: bool = False) -> None:
    db = SessionLocal()
    try:
        seed_comtrade(db, refresh=refresh)
    finally:
        db.close()
