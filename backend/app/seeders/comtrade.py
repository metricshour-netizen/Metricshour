"""
Seed bilateral trade pairs using two free sources:
  1. World Bank WITS API (primary — no key, no rate limit, ISO3 codes)
  2. UN Comtrade public preview API (fallback — M49 numeric codes, ~100 req/hr limit)

WITS covers ~180 countries. Comtrade fills the remainder (Serbia, DR Congo, etc.).

Run:  python seed.py --only comtrade
      python seed.py --only comtrade --refresh   (re-fetch all including existing)

Idempotent — safe to re-run. Skips countries with existing 2022+ data unless
--refresh is passed.
"""

import logging
import time
import xml.etree.ElementTree as ET

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import SessionLocal
from app.models import Country, TradePair

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

WITS_BASE = "https://wits.worldbank.org/API/V1/SDMX/V21/datasource/tradestats-trade"
COMTRADE_BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
YEARS = [2023, 2022, 2021]
TOP_N_PARTNERS = 50
REQUEST_DELAY = 0.5        # WITS has no strict rate limit
COMTRADE_DELAY = 1.5       # Comtrade public ~100 req/hr — stay safe


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


def _fetch_comtrade_api(m49: int, year: int) -> dict[int, float]:
    """
    Fallback: UN Comtrade public preview API → {partner_m49: value_usd}.
    Uses M49 numeric codes. partnerCode=0 is the world total — skip it.
    """
    url = (
        f"{COMTRADE_BASE}?reporterCode={m49}&period={year}"
        f"&cmdCode=TOTAL&flowCode=X"
    )
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "MetricsHour/1.0"})
        if resp.status_code in (400, 404, 429):
            return {}
        resp.raise_for_status()
        data = resp.json().get("data", [])
        result: dict[int, float] = {}
        for row in data:
            partner_m49 = row.get("partnerCode")
            value = row.get("primaryValue")
            if partner_m49 and partner_m49 != 0 and value and float(value) > 0:
                m49_int = int(partner_m49)
                if m49_int not in result or float(value) > result[m49_int]:
                    result[m49_int] = float(value)
        return result
    except Exception as exc:
        log.warning("Comtrade API failed m49=%s year=%s: %s", m49, year, exc)
        return {}


def seed_comtrade(db: Session, refresh: bool = False) -> None:
    countries = db.query(Country).all()
    if not countries:
        raise RuntimeError("No countries in DB. Run the country seeder first.")

    iso3_to_id: dict[str, int] = {c.code3: c.id for c in countries if c.code3}
    m49_to_id: dict[int, int] = {
        int(c.numeric_code): c.id
        for c in countries
        if c.numeric_code and str(c.numeric_code).isdigit()
    }
    id_to_country: dict[int, Country] = {c.id: c for c in countries}
    log.info("Loaded %d countries (%d with M49 codes)", len(iso3_to_id), len(m49_to_id))

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
            # WITS has no data — try UN Comtrade API (uses M49 numeric code)
            m49 = int(country.numeric_code) if country.numeric_code and str(country.numeric_code).isdigit() else None
            if m49:
                log.info("  WITS empty — trying UN Comtrade API (M49=%s)", m49)
                comtrade_exports: dict[int, float] = {}
                for year in YEARS:
                    comtrade_exports = _fetch_comtrade_api(m49, year)
                    if comtrade_exports:
                        actual_year = year
                        break
                    time.sleep(COMTRADE_DELAY)

                if comtrade_exports:
                    # Convert M49 partner codes to DB ids
                    ranked_m49 = sorted(comtrade_exports.items(), key=lambda x: -x[1])
                    added = 0
                    for partner_m49, value in ranked_m49:
                        if added >= TOP_N_PARTNERS:
                            break
                        partner_id = m49_to_id.get(partner_m49)
                        if not partner_id or partner_id == country.id:
                            continue
                        export_map[(country.id, partner_id)] = (value, actual_year)
                        added += 1
                    log.info("  Comtrade: %d partners (year %s)", added, actual_year)
                    time.sleep(COMTRADE_DELAY)
                    continue
                else:
                    log.info("  No data in Comtrade either — skipping")
            else:
                log.info("  No M49 code — skipping")
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
                # Only overwrite imports_usd if the incoming value is not null
                "imports_usd": func.coalesce(stmt.excluded.imports_usd, TradePair.imports_usd),
                "balance_usd": stmt.excluded.balance_usd,
                "data_source": stmt.excluded.data_source,
                # Preserve existing products if incoming arrays are empty/null
                "top_export_products": func.coalesce(stmt.excluded.top_export_products, TradePair.top_export_products),
                "top_import_products": func.coalesce(stmt.excluded.top_import_products, TradePair.top_import_products),
            },
        )
        db.execute(stmt)
        pairs_upserted += 1

        if pairs_upserted % 200 == 0:
            db.commit()
            log.info("Committed %d pairs so far…", pairs_upserted)

    db.commit()
    log.info("Comtrade/WITS seed complete — %d trade pairs upserted.", pairs_upserted)


def fill_missing_imports(db: Session, year: int = 2023) -> None:
    """
    Second pass: for trade_pair rows where imports_usd is null, fetch the importer's
    WITS import data and backfill it. Runs ~1 WITS request per unique importer country.
    """
    countries = db.query(Country).all()
    iso3_to_id: dict[str, int] = {c.code3: c.id for c in countries if c.code3}
    id_to_iso3: dict[int, str] = {c.id: c.code3 for c in countries if c.code3}

    # All pairs for this year with missing imports_usd
    null_pairs = db.execute(
        select(TradePair).where(TradePair.imports_usd.is_(None), TradePair.year == year)
    ).scalars().all()

    if not null_pairs:
        log.info("No pairs with null imports_usd for year %d — nothing to do.", year)
        return

    log.info("Found %d pairs with null imports_usd for %d.", len(null_pairs), year)

    # Group by importer so we make one WITS request per importer country
    from collections import defaultdict
    by_importer: dict[int, list[TradePair]] = defaultdict(list)
    for p in null_pairs:
        by_importer[p.importer_id].append(p)

    updated = 0
    for i, (imp_id, pairs) in enumerate(by_importer.items()):
        iso3 = id_to_iso3.get(imp_id)
        if not iso3:
            continue

        log.info("[%d/%d] Fetching imports for %s (%d pairs to fill)", i + 1, len(by_importer), iso3, len(pairs))
        # "imports of country B" = what B imports from all partners
        imports_by_partner: dict[str, float] = _fetch_bilateral(iso3, year, "imports")
        if not imports_by_partner:
            # Try prior year
            imports_by_partner = _fetch_bilateral(iso3, year - 1, "imports")

        if not imports_by_partner:
            log.info("  No WITS import data for %s — skipping", iso3)
            time.sleep(REQUEST_DELAY)
            continue

        for p in pairs:
            exp_iso3 = id_to_iso3.get(p.exporter_id)
            if not exp_iso3:
                continue
            imports_val = imports_by_partner.get(exp_iso3)
            if imports_val is None:
                continue

            # Update this pair with the recovered imports_usd
            balance = (p.exports_usd or 0) - imports_val
            trade_value = (p.exports_usd or 0) + imports_val
            p.imports_usd = imports_val
            p.balance_usd = balance
            p.trade_value_usd = trade_value
            updated += 1

        db.commit()
        time.sleep(REQUEST_DELAY)

    log.info("fill_missing_imports complete — %d pairs updated.", updated)


def run(refresh: bool = False) -> None:
    db = SessionLocal()
    try:
        seed_comtrade(db, refresh=refresh)
        # Second pass: backfill imports_usd for pairs that were seeded before their
        # partner country was processed (order-dependent gap in the first pass).
        for year in YEARS:
            fill_missing_imports(db, year=year)
    finally:
        db.close()
