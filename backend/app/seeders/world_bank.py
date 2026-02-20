"""
Seed country indicators from World Bank API (free, no key required).
Fetches all countries per indicator in one request — ~40 API calls total.
Idempotent — safe to run multiple times.

Run: python -m app.seeders.world_bank
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
DATE_RANGE = "2015:2024"
PER_PAGE = 20000  # large enough for all countries × years in one page

# Maps World Bank indicator code → our internal indicator name
# Format: "WB_CODE": ("our_name", "source_period_type")
INDICATORS: dict[str, tuple[str, str]] = {
    # --- DEMOGRAPHICS ---
    "SP.POP.TOTL":          ("population",                  "annual"),
    "SP.POP.GROW":          ("population_growth_pct",        "annual"),
    "SP.URB.TOTL.IN.ZS":   ("urban_population_pct",         "annual"),
    "SP.POP.DPND":          ("dependency_ratio",             "annual"),
    "SP.DYN.LE00.IN":       ("life_expectancy",              "annual"),
    "SP.DYN.TFRT.IN":       ("fertility_rate",               "annual"),
    "SP.DYN.CBRT.IN":       ("birth_rate",                   "annual"),
    "SP.DYN.CDRT.IN":       ("death_rate",                   "annual"),
    "SP.DYN.IMRT.IN":       ("infant_mortality_per_1000",    "annual"),
    "SM.POP.NETM":          ("net_migration",                "annual"),
    "EN.POP.DNST":          ("population_density",           "annual"),

    # --- ECONOMY ---
    "NY.GDP.MKTP.CD":       ("gdp_usd",                     "annual"),
    "NY.GDP.PCAP.CD":       ("gdp_per_capita_usd",          "annual"),
    "NY.GDP.MKTP.PP.CD":    ("gdp_ppp_usd",                 "annual"),
    "NY.GDP.PCAP.PP.CD":    ("gdp_per_capita_ppp_usd",      "annual"),
    "NY.GDP.MKTP.KD.ZG":    ("gdp_growth_pct",              "annual"),
    "NV.AGR.TOTL.ZS":       ("gdp_agriculture_pct",         "annual"),
    "NV.IND.TOTL.ZS":       ("gdp_industry_pct",            "annual"),
    "NV.SRV.TOTL.ZS":       ("gdp_services_pct",            "annual"),
    "NV.IND.MANF.ZS":       ("gdp_manufacturing_pct",       "annual"),

    # --- MONETARY / INFLATION ---
    "FP.CPI.TOTL.ZG":       ("inflation_pct",               "annual"),
    "FR.INR.RINR":          ("real_interest_rate_pct",      "annual"),
    "FM.LBL.BMNY.GD.ZS":   ("money_supply_m2_gdp_pct",     "annual"),

    # --- EXTERNAL ---
    "FI.RES.TOTL.CD":       ("foreign_reserves_usd",        "annual"),
    "BN.CAB.XOKA.GD.ZS":   ("current_account_gdp_pct",     "annual"),
    "BX.KLT.DINV.WD.GD.ZS":("fdi_inflows_gdp_pct",         "annual"),
    "BX.KLT.DINV.CD.WD":   ("fdi_inflows_usd",             "annual"),
    "DT.DOD.DECT.GD.ZS":   ("external_debt_gdp_pct",       "annual"),
    "DT.DOD.DECT.CD":       ("external_debt_usd",           "annual"),
    "BX.TRF.PWKR.DT.GD.ZS":("remittances_gdp_pct",         "annual"),  # the overlooked one
    "BX.TRF.PWKR.CD.DT":   ("remittances_received_usd",    "annual"),

    # --- TRADE ---
    "NE.EXP.GNFS.CD":       ("exports_usd",                 "annual"),
    "NE.IMP.GNFS.CD":       ("imports_usd",                 "annual"),

    # --- FISCAL ---
    "GC.DOD.TOTL.GD.ZS":   ("government_debt_gdp_pct",     "annual"),
    "GC.BAL.CASH.GD.ZS":   ("budget_balance_gdp_pct",      "annual"),
    "GC.TAX.TOTL.GD.ZS":   ("tax_revenue_gdp_pct",         "annual"),
    "MS.MIL.XPND.GD.ZS":   ("military_spending_gdp_pct",   "annual"),
    "SE.XPD.TOTL.GD.ZS":   ("education_spending_gdp_pct",  "annual"),
    "SH.XPD.CHEX.GD.ZS":   ("healthcare_spending_gdp_pct", "annual"),

    # --- LABOR ---
    "SL.UEM.TOTL.ZS":       ("unemployment_pct",            "annual"),
    "SL.UEM.1524.ZS":       ("youth_unemployment_pct",      "annual"),  # often 3× higher
    "SL.TLF.CACT.ZS":       ("labor_participation_pct",     "annual"),
    "SL.TLF.CACT.FE.ZS":   ("female_labor_participation_pct", "annual"),

    # --- SOCIAL / HUMAN DEVELOPMENT ---
    "SI.POV.GINI":          ("gini_coefficient",            "annual"),
    "SI.POV.DDAY":          ("poverty_rate_pct",            "annual"),
    "SE.ADT.LITR.ZS":       ("literacy_rate_pct",           "annual"),
    "IT.NET.USER.ZS":       ("internet_penetration_pct",    "annual"),
    "IT.CEL.SETS.P2":       ("mobile_subscriptions_per_100","annual"),
    "SH.MED.BEDS.ZS":       ("hospital_beds_per_1000",      "annual"),
    "SH.MED.PHYS.ZS":       ("doctors_per_1000",            "annual"),

    # --- ENVIRONMENT ---
    "EN.ATM.CO2E.KT":       ("co2_emissions_mt",            "annual"),
    "EN.ATM.CO2E.PC":       ("co2_per_capita_t",            "annual"),
    "EG.ELC.RNEW.ZS":       ("renewable_energy_pct",        "annual"),
    "AG.LND.FRST.ZS":       ("forest_cover_pct",            "annual"),

    # --- INNOVATION ---
    "GB.XPD.RSDV.GD.ZS":   ("rd_spending_gdp_pct",         "annual"),
    "IP.PAT.RESD":          ("patent_applications",         "annual"),

    # --- TOURISM ---
    "ST.INT.ARVL":          ("tourist_arrivals",            "annual"),
    "ST.INT.RCPT.CD":       ("tourism_revenue_usd",         "annual"),
}


def _fetch_indicator(wb_code: str) -> list[dict]:
    """Fetch all countries for one indicator, returning raw WB records."""
    url = f"{WB_BASE}/country/all/indicator/{wb_code}"
    params = {
        "format": "json",
        "date": DATE_RANGE,
        "per_page": PER_PAGE,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # WB returns [metadata, [records]] — check structure
        if not isinstance(data, list) or len(data) < 2:
            return []
        return data[1] or []
    except Exception as exc:
        log.warning(f"Failed to fetch {wb_code}: {exc}")
        return []


def _parse_records(
    records: list[dict],
    our_name: str,
    period_type: str,
    country_code_map: dict[str, int],
) -> list[dict]:
    """Convert raw WB records to CountryIndicator rows."""
    rows = []
    for rec in records:
        if rec.get("value") is None:
            continue

        # WB uses alpha-3 in countryiso3code (e.g. "USA", "DEU")
        iso3 = rec.get("countryiso3code", "")
        country_id = country_code_map.get(iso3)
        if not country_id:
            continue  # aggregate regions (e.g. "1W" for World) — skip

        try:
            year = int(rec["date"])
        except (ValueError, KeyError):
            continue

        rows.append({
            "country_id": country_id,
            "indicator": our_name,
            "value": float(rec["value"]),
            "period_date": date(year, 1, 1),
            "period_type": period_type,
            "source": "world_bank",
        })
    return rows


def _upsert_rows(db: Session, rows: list[dict]) -> None:
    if not rows:
        return
    stmt = insert(CountryIndicator).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_country_indicator_date",
        set_={"value": stmt.excluded.value},
    )
    db.execute(stmt)
    db.commit()


def seed_world_bank(db: Session) -> None:
    # Build country_code → id map so we can look up by ISO alpha-2
    countries = db.query(Country).all()
    if not countries:
        raise RuntimeError("No countries in DB. Run the country seeder first.")

    country_code_map: dict[str, int] = {c.code3: c.id for c in countries}
    log.info(f"Loaded {len(country_code_map)} countries from DB")

    total_rows = 0

    for wb_code, (our_name, period_type) in INDICATORS.items():
        log.info(f"Fetching {wb_code} → {our_name}...")
        records = _fetch_indicator(wb_code)
        rows = _parse_records(records, our_name, period_type, country_code_map)
        _upsert_rows(db, rows)
        total_rows += len(rows)
        log.info(f"  Upserted {len(rows)} rows")
        time.sleep(0.5)  # be polite to the API

    log.info(f"World Bank seed complete. Total rows: {total_rows}")


def run() -> None:
    db = SessionLocal()
    try:
        seed_world_bank(db)
    finally:
        db.close()


if __name__ == "__main__":
    run()
