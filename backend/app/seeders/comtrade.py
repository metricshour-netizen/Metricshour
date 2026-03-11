"""
Seed bilateral trade pairs from UN Comtrade API (comtradeapi.un.org).

Coverage: all countries with UN M49 numeric codes (~200 reporters).
Data: annual export flows for latest available year (tries 2023, falls back to 2022).
Each reporter fetched separately → top 15 trading partners stored per country.

No API key required for basic access (unlimited calls, up to 500 records/call).
Optional: register for a free key at https://comtradedeveloper.un.org/ for higher
record limits (100k/call) and 500 calls/day quota.

Run:  python seed.py --only comtrade
      python seed.py --only comtrade --refresh   (re-fetch all, including existing)

Idempotent — safe to re-run. Skips countries with existing 2022+ data unless
--refresh is passed.
"""

import logging
import os
import time

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Country, TradePair

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL = "https://comtradeapi.un.org/data/v1/get/C/A/HS"
PREFERRED_YEAR = 2023
FALLBACK_YEAR = 2022
TOP_N_PARTNERS = 15     # top trading partners to keep per country
REQUEST_DELAY = 1.2     # seconds between calls — stays well under rate limit


def _fetch_exports(reporter_m49: int, year: int, api_key: str | None) -> list[dict]:
    """Fetch annual export rows for one reporter → all partners."""
    url = f"{BASE_URL}/{year}/{reporter_m49}"
    headers = {}
    if api_key:
        headers["Ocp-Apim-Subscription-Key"] = api_key
    params = {
        "cmdCode": "TOTAL",
        "flowCode": "X",
        "partner2Code": 0,
        "customsCode": "C00",
        "motCode": 0,
        "includeDesc": "true",
        "maxRecords": 500,  # free-tier limit; key holders get 100k
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 404:
            return []
        if resp.status_code == 429:
            log.warning("Rate limited — sleeping 60s then retrying")
            time.sleep(60)
            return _fetch_exports(reporter_m49, year, api_key)
        resp.raise_for_status()
        return resp.json().get("data", []) or []
    except Exception as exc:
        log.warning("Failed M49=%s year=%s: %s", reporter_m49, year, exc)
        return []


def seed_comtrade(db: Session, api_key: str | None = None, refresh: bool = False) -> None:
    countries = db.query(Country).all()
    if not countries:
        raise RuntimeError("No countries in DB. Run the country seeder first.")

    # M49 numeric code → internal country id
    m49_to_id: dict[int, int] = {}
    for c in countries:
        if c.numeric_code:
            try:
                m49_to_id[int(c.numeric_code)] = c.id
            except (ValueError, TypeError):
                pass

    id_to_country: dict[int, Country] = {c.id: c for c in countries}
    log.info("Loaded %d countries with M49 codes", len(m49_to_id))

    # Determine which reporters to process
    if refresh:
        reporters = [c for c in countries if c.numeric_code]
    else:
        existing_exporters = set(
            row[0] for row in db.execute(
                select(TradePair.exporter_id).where(TradePair.year >= 2022).distinct()
            ).all()
        )
        reporters = [
            c for c in countries
            if c.numeric_code and c.id not in existing_exporters
        ]

    log.info(
        "Processing %d reporters (skipping %d with existing data)",
        len(reporters),
        len(countries) - len(reporters),
    )

    # Accumulate: (exporter_id, importer_id) → (exports_usd, year)
    export_map: dict[tuple[int, int], tuple[float, int]] = {}

    for i, country in enumerate(reporters):
        m49 = int(country.numeric_code)
        log.info("[%d/%d] %s (M49=%d)", i + 1, len(reporters), country.name, m49)

        rows = _fetch_exports(m49, PREFERRED_YEAR, api_key)
        actual_year = PREFERRED_YEAR
        if not rows:
            rows = _fetch_exports(m49, FALLBACK_YEAR, api_key)
            actual_year = FALLBACK_YEAR

        if not rows:
            log.info("  No data — skipping")
            time.sleep(REQUEST_DELAY)
            continue

        # Strip world aggregates (partnerCode 0, 837, 838, 839, 849, 899) and self
        AGGREGATE_CODES = {0, 837, 838, 839, 849, 899, 472, 473, 568, 577, 636, 637, 697, 728}
        bilateral = [
            r for r in rows
            if r.get("partnerCode") not in AGGREGATE_CODES
            and r.get("partnerCode") != m49
            and r.get("primaryValue") is not None
            and r["primaryValue"] > 0
        ]

        bilateral.sort(key=lambda r: r["primaryValue"], reverse=True)
        bilateral = bilateral[:TOP_N_PARTNERS]

        for row in bilateral:
            partner_id = m49_to_id.get(row["partnerCode"])
            if not partner_id:
                continue
            export_map[(country.id, partner_id)] = (float(row["primaryValue"]), actual_year)

        log.info("  %d partners", len(bilateral))
        time.sleep(REQUEST_DELAY)

    # Upsert trade_pairs
    pairs_upserted = 0
    for (exp_id, imp_id), (exports_usd, year) in export_map.items():
        imports_usd = export_map.get((imp_id, exp_id), (None, None))[0]

        if imports_usd is not None:
            trade_value = exports_usd + imports_usd
            balance = exports_usd - imports_usd
        else:
            trade_value = exports_usd
            balance = exports_usd

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
    log.info("Comtrade seed complete — %d trade pairs upserted.", pairs_upserted)


def run(api_key: str = None, refresh: bool = False) -> None:
    if not api_key:
        api_key = os.environ.get("COMTRADE_API_KEY") or None  # None = no-auth free tier
    if api_key:
        log.info("Using COMTRADE_API_KEY (500 calls/day, 100k records/call)")
    else:
        log.info("No COMTRADE_API_KEY — using free no-auth tier (unlimited calls, 500 records/call)")
    db = SessionLocal()
    try:
        seed_comtrade(db, api_key=api_key, refresh=refresh)
    finally:
        db.close()
