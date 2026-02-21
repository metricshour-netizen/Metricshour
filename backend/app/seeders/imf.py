"""
Seed country indicators from IMF DataMapper API (free, no API key required).

Covers: government debt, budget balance, external debt, current account, interest rate.
IMF WEO data has better coverage than World Bank for fiscal indicators — especially
for G20/G7/OECD countries where WB has gaps.

API docs: https://www.imf.org/external/datamapper/api/v1/
Idempotent — safe to run multiple times.

Run: python seed.py --only imf
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

IMF_BASE = "https://www.imf.org/external/datamapper/api/v1"

# IMF DataMapper indicator code → our internal indicator name
# All WEO indicators sourced from: https://www.imf.org/external/datamapper/
IMF_INDICATORS: dict[str, str] = {
    # FISCAL
    "GGXWDG_NGDP":  "government_debt_gdp_pct",    # General Govt Gross Debt (% GDP) — WEO
    "GGXCNL_NGDP":  "budget_balance_gdp_pct",     # Net Lending/Borrowing (% GDP) — WEO
    # EXTERNAL
    "BCA_NGDPD":    "current_account_gdp_pct",     # Current Account Balance (% GDP) — WEO
    "NGDP_D":       "external_debt_gdp_pct",        # We'll skip if no data (BPM6)
    # GROWTH / INFLATION — better recency than WB for some countries
    "NGDP_RPCH":    "gdp_growth_pct",               # Real GDP Growth (%) — WEO
    "PCPIPCH":      "inflation_pct",                 # CPI Inflation avg (%) — WEO
    "LUR":          "unemployment_pct",              # Unemployment Rate (%) — WEO
}

# IMF uses ISO alpha-3 codes for most countries, matching our code3 column.
# A handful of IMF codes differ from ISO — map those here.
IMF_TO_ISO3: dict[str, str] = {
    "UVK": "XKX",   # Kosovo (IMF code → our code3 from REST Countries)
    "WBG": "PSE",   # West Bank and Gaza → Palestinian territories
    "TMP": "TLS",   # Timor-Leste old code
}

# Years to import — include WEO projections for current year (they're labeled as estimates)
YEAR_START = 2015
YEAR_END = 2024


def _fetch_imf_indicator(code: str) -> dict[str, dict[int, float]]:
    """
    Fetch all countries for one IMF DataMapper indicator.
    Returns: {iso3_code: {year: value}}
    """
    url = f"{IMF_BASE}/{code}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # Structure: {"values": {"INDICATOR_CODE": {"USA": {"2015": X, ...}, ...}}}
        values_outer = data.get("values", {})
        if not values_outer:
            log.warning(f"IMF {code}: no 'values' key in response")
            return {}
        # The outer key is the indicator code (might differ from what we passed)
        country_data = next(iter(values_outer.values()), {})
        return {
            imf_code: {
                int(yr): float(val)
                for yr, val in year_vals.items()
                if val is not None and YEAR_START <= int(yr) <= YEAR_END
            }
            for imf_code, year_vals in country_data.items()
            if isinstance(year_vals, dict)
        }
    except Exception as exc:
        log.warning(f"IMF fetch failed for {code}: {exc}")
        return {}


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


def seed_imf(db: Session) -> None:
    # Build code3 → country_id map
    countries = db.query(Country).all()
    if not countries:
        raise RuntimeError("No countries in DB. Run the country seeder first.")

    # Primary lookup by ISO alpha-3
    code3_map: dict[str, int] = {c.code3: c.id for c in countries}

    def resolve_id(imf_code: str) -> int | None:
        iso3 = IMF_TO_ISO3.get(imf_code, imf_code)
        return code3_map.get(iso3)

    total_rows = 0

    # --- WEO indicators ---
    for imf_code, our_name in IMF_INDICATORS.items():
        # Skip external_debt_gdp_pct — IMF DataMapper NGDP_D is nominal GDP deflator, wrong field
        # We'll skip and let WB fill it
        if imf_code == "NGDP_D":
            continue

        log.info(f"IMF DataMapper: fetching {imf_code} → {our_name}...")
        country_data = _fetch_imf_indicator(imf_code)

        rows: list[dict] = []
        for imf_country_code, year_vals in country_data.items():
            country_id = resolve_id(imf_country_code)
            if not country_id:
                continue  # IMF regional aggregates (e.g. "G20", "WORLD") — skip
            for year, value in year_vals.items():
                rows.append({
                    "country_id": country_id,
                    "indicator": our_name,
                    "value": value,
                    "period_date": date(year, 1, 1),
                    "period_type": "annual",
                    "source": "imf_weo",
                })

        _upsert_rows(db, rows)
        total_rows += len(rows)
        log.info(f"  Upserted {len(rows)} rows for {our_name}")
        time.sleep(0.5)

    log.info(f"IMF seed complete. Total rows upserted: {total_rows}")


def run() -> None:
    db = SessionLocal()
    try:
        seed_imf(db)
    finally:
        db.close()


if __name__ == "__main__":
    run()
