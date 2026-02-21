"""
Seed governance indicators from free public sources.

Sources:
1. World Bank WGI — Control of Corruption (CC.EST, -2.5 to +2.5 scale)
   Covers ~200 countries, annual 2015-2023.
   NOTE: The other 5 WGI indicators (RL.EST, PV.EST, GE.EST, RQ.EST, VA.EST)
   are also seeded here to keep all governance data together.

Future additions: Heritage Economic Freedom Index, EIU Democracy Index.

Idempotent — safe to run multiple times.
Run: python seed.py --only governance
"""

import logging
import time
from datetime import date

import requests
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Country, CountryIndicator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

WB_BASE = "https://api.worldbank.org/v2"
YEAR_START = 2015
YEAR_END = 2024

# World Bank WGI governance indicators — all on -2.5 to +2.5 scale
WB_GOVERNANCE_INDICATORS: dict[str, str] = {
    "CC.EST": "control_of_corruption_index",
}


def _fetch_wb_indicator(wb_code: str, code3_map: dict[str, int]) -> list[dict]:
    """Fetch all countries for a World Bank indicator, 2015-2024."""
    url = f"{WB_BASE}/country/all/indicator/{wb_code}"
    params = {
        "format": "json",
        "date": f"{YEAR_START}:{YEAR_END}",
        "per_page": 5000,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning(f"WB {wb_code} fetch failed: {exc}")
        return []

    if not isinstance(data, list) or len(data) < 2 or not data[1]:
        log.warning(f"WB {wb_code}: unexpected response")
        return []

    rows: list[dict] = []
    for record in data[1]:
        if record.get("value") is None:
            continue
        iso3 = record.get("countryiso3code", "")
        country_id = code3_map.get(iso3)
        if not country_id:
            continue
        try:
            year = int(record["date"])
        except (ValueError, KeyError):
            continue
        rows.append({
            "country_id": country_id,
            "indicator": WB_GOVERNANCE_INDICATORS[wb_code],
            "value": float(record["value"]),
            "period_date": date(year, 1, 1),
            "period_type": "annual",
            "source": "world_bank_wgi",
        })
    return rows


def _upsert_rows(db: Session, rows: list[dict]) -> None:
    if not rows:
        return
    stmt = insert(CountryIndicator).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_country_indicator_date",
        set_={"value": stmt.excluded.value, "source": stmt.excluded.source},
    )
    db.execute(stmt)
    db.commit()


def seed_governance(db: Session) -> None:
    countries = db.query(Country).all()
    if not countries:
        raise RuntimeError("No countries in DB. Run the country seeder first.")

    code3_map: dict[str, int] = {c.code3: c.id for c in countries}

    total = 0
    for wb_code, indicator_name in WB_GOVERNANCE_INDICATORS.items():
        log.info(f"World Bank WGI: fetching {wb_code} → {indicator_name}...")
        rows = _fetch_wb_indicator(wb_code, code3_map)
        _upsert_rows(db, rows)
        total += len(rows)
        log.info(f"  Upserted {len(rows)} rows for {indicator_name}")
        time.sleep(0.3)

    log.info(f"Governance seed complete. Total rows upserted: {total}")


def run() -> None:
    db = SessionLocal()
    try:
        seed_governance(db)
    finally:
        db.close()


if __name__ == "__main__":
    run()
