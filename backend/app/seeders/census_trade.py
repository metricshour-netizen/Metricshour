"""
Seed 2023 US bilateral trade data from US Census Bureau International Trade API.
Upserts new year=2023 rows for all 18 US bilateral pairs (both directions).
Product breakdown carried forward from 2022 UN Comtrade seed (mix is stable year-to-year).
Idempotent — safe to re-run.

Source: US Census Bureau — api.census.gov/data/timeseries/intltrade
Run: python seed.py --only census_trade
"""

import logging
import urllib.request
import json
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy import select as sa_select

from app.database import SessionLocal
from app.models import Country, TradePair
from app.models.country import CountryIndicator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Census Bureau CTY_CODE for each ISO-2 G20 partner
CENSUS_CTY_MAP: dict[str, str] = {
    "CA": "1220",
    "MX": "2010",
    "BR": "3510",
    "AR": "3570",
    "GB": "4120",
    "FR": "4279",
    "DE": "4280",
    "RU": "4621",
    "IT": "4759",
    "TR": "4890",
    "SA": "5170",
    "IN": "5330",
    "ID": "5600",
    "CN": "5700",
    "JP": "5880",
    "AU": "6021",
    "ZA": "7910",
    "KR": "5800",
}

BASE = "https://api.census.gov/data/timeseries/intltrade"
YEAR = 2023


def _fetch(endpoint: str, cty_code: str, value_field: str) -> float | None:
    url = (
        f"{BASE}/{endpoint}/enduse"
        f"?get=CTY_CODE,CTY_NAME,{value_field}&YEAR={YEAR}&MONTH=12&CTY_CODE={cty_code}"
    )
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        if len(data) < 2:
            return None
        return float(data[1][2])
    except Exception as e:
        log.warning(f"Census API failed for {endpoint} CTY={cty_code}: {e}")
        return None


def seed_census_trade(db: Session) -> int:
    # country code → id
    rows = db.execute(sa_select(Country.id, Country.code)).all()
    country_map: dict[str, int] = {r.code: r.id for r in rows}

    # GDP map for gdp_share calculation
    gdp_rows = db.execute(
        sa_select(CountryIndicator.country_id, CountryIndicator.value)
        .where(CountryIndicator.indicator == "gdp_usd")
        .order_by(CountryIndicator.period_date.desc())
    ).all()
    gdp_map: dict[int, float] = {}
    for r in gdp_rows:
        if r.country_id not in gdp_map:
            gdp_map[r.country_id] = r.value

    def gdp_share(code: str, trade_usd: float) -> float | None:
        cid = country_map.get(code)
        gdp = gdp_map.get(cid) if cid else None
        if gdp and gdp > 0:
            return round((trade_usd / gdp) * 100, 2)
        return None

    # Carry forward product data from existing 2022 US pairs
    us_id = country_map.get("US")
    products_2022: dict[tuple[int, int], dict] = {}
    if us_id:
        existing = db.execute(
            sa_select(TradePair)
            .where(
                TradePair.year == 2022,
                (TradePair.exporter_id == us_id) | (TradePair.importer_id == us_id),
            )
        ).scalars().all()
        for p in existing:
            products_2022[(p.exporter_id, p.importer_id)] = {
                "top_export_products": p.top_export_products,
                "top_import_products": p.top_import_products,
            }

    records: list[dict] = []
    us_id_check = country_map.get("US")
    if not us_id_check:
        log.error("US not found in countries table — cannot seed Census trade data")
        return 0

    for iso, cty_code in CENSUS_CTY_MAP.items():
        partner_id = country_map.get(iso)
        if not partner_id:
            log.warning(f"Skipping {iso}: not found in DB")
            continue

        exports_raw = _fetch("exports", cty_code, "ALL_VAL_YR")
        imports_raw = _fetch("imports", cty_code, "GEN_VAL_YR")

        if exports_raw is None or imports_raw is None:
            log.warning(f"Incomplete Census data for US-{iso}, skipping")
            continue

        exports_usd = exports_raw
        imports_usd = imports_raw
        trade_value = exports_usd + imports_usd
        balance = exports_usd - imports_usd

        # Forward: US → partner
        fwd_prods = products_2022.get((us_id_check, partner_id), {})
        records.append({
            "exporter_id": us_id_check,
            "importer_id": partner_id,
            "year": YEAR,
            "trade_value_usd": trade_value,
            "exports_usd": exports_usd,
            "imports_usd": imports_usd,
            "balance_usd": balance,
            "top_export_products": fwd_prods.get("top_export_products"),
            "top_import_products": fwd_prods.get("top_import_products"),
            "exporter_gdp_share_pct": gdp_share("US", trade_value),
            "importer_gdp_share_pct": gdp_share(iso, trade_value),
            "data_source": "US Census Bureau 2023",
        })

        # Reverse: partner → US
        rev_prods = products_2022.get((partner_id, us_id_check), {})
        records.append({
            "exporter_id": partner_id,
            "importer_id": us_id_check,
            "year": YEAR,
            "trade_value_usd": trade_value,
            "exports_usd": imports_usd,
            "imports_usd": exports_usd,
            "balance_usd": -balance,
            "top_export_products": rev_prods.get("top_export_products"),
            "top_import_products": rev_prods.get("top_import_products"),
            "exporter_gdp_share_pct": gdp_share(iso, trade_value),
            "importer_gdp_share_pct": gdp_share("US", trade_value),
            "data_source": "US Census Bureau 2023",
        })

        log.info(f"US-{iso}: exports=${exports_usd/1e9:.1f}B imports=${imports_usd/1e9:.1f}B")

    if not records:
        log.warning("No Census trade records to insert")
        return 0

    stmt = pg_insert(TradePair).values(records)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_trade_pair_year",
        set_={
            col: stmt.excluded[col]
            for col in records[0].keys()
            if col not in ("exporter_id", "importer_id", "year")
        },
    )
    db.execute(stmt)
    db.commit()
    log.info(f"Upserted {len(records)} Census trade records ({len(records)//2} unique US pairs × 2 directions)")

    # Bust trade cache for all affected US pairs so fresh 2023 data is served immediately
    try:
        from app.storage import cache_del
        for iso in CENSUS_CTY_MAP:
            cache_del(f"api:trade:v2:US:{iso}")
            cache_del(f"api:trade:v2:{iso}:US")
        log.info("Cache busted for all US bilateral trade pairs")
    except Exception as e:
        log.warning(f"Cache bust failed (non-fatal): {e}")

    return len(records)


def run() -> None:
    db = SessionLocal()
    try:
        total = seed_census_trade(db)
        log.info(f"Done. {total} trade pair records in database.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
