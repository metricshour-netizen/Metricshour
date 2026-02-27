"""
World Bank daily data refresh — all 196 countries, 50+ indicators.
Runs daily at 6am UTC. Fetches the most recent available year.

World Bank API: https://api.worldbank.org/v2/ — free, no key required.
"""

import logging
import time
from datetime import date

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.country import Country, CountryIndicator

log = logging.getLogger(__name__)

WB_BASE = "https://api.worldbank.org/v2"
PER_PAGE = 20000  # enough for all countries × 10 years in one page

# Maps World Bank indicator code → (our indicator name, period_type)
INDICATORS: dict[str, tuple[str, str]] = {
    # Demographics
    "SP.POP.TOTL":          ("population",                  "annual"),
    "SP.POP.GROW":          ("population_growth_pct",        "annual"),
    "SP.URB.TOTL.IN.ZS":   ("urban_population_pct",         "annual"),
    "SP.DYN.LE00.IN":       ("life_expectancy",              "annual"),
    "SP.DYN.TFRT.IN":       ("fertility_rate",               "annual"),
    "EN.POP.DNST":          ("population_density",           "annual"),

    # Economy
    "NY.GDP.MKTP.CD":       ("gdp_usd",                     "annual"),
    "NY.GDP.PCAP.CD":       ("gdp_per_capita_usd",          "annual"),
    "NY.GDP.MKTP.KD.ZG":   ("gdp_growth_pct",               "annual"),
    "NY.GDP.MKTP.PP.CD":   ("gdp_ppp_usd",                  "annual"),
    "NY.GDP.PCAP.PP.CD":   ("gdp_per_capita_ppp",           "annual"),
    "NV.AGR.TOTL.ZS":      ("agriculture_pct_gdp",          "annual"),
    "NV.IND.TOTL.ZS":      ("industry_pct_gdp",             "annual"),
    "NV.SRV.TOTL.ZS":      ("services_pct_gdp",             "annual"),
    "NE.CON.PRVT.ZS":      ("household_consumption_pct_gdp", "annual"),
    "NE.GDI.TOTL.ZS":      ("gross_investment_pct_gdp",     "annual"),

    # Monetary
    "FP.CPI.TOTL.ZG":      ("inflation_pct",                "annual"),
    "FR.INR.LEND":         ("interest_rate_pct",            "annual"),  # Lending interest rate
    "FR.INR.RINR":         ("real_interest_rate_pct",       "annual"),
    "FM.LBL.BMNY.GD.ZS":  ("money_supply_m2_gdp_pct",      "annual"),

    # External / BoP
    "BN.CAB.XOKA.GD.ZS":  ("current_account_gdp_pct",      "annual"),
    "FI.RES.TOTL.CD":      ("foreign_reserves_usd",         "annual"),
    "BX.KLT.DINV.CD.WD":  ("fdi_inflows_usd",              "annual"),
    "BX.KLT.DINV.WD.GD.ZS":("fdi_inflows_gdp_pct",         "annual"),
    "DT.DOD.DECT.CD":      ("external_debt_usd",            "annual"),
    "BX.TRF.PWKR.CD.DT":  ("remittances_received_usd",     "annual"),
    "BX.TRF.PWKR.DT.GD.ZS":("remittances_gdp_pct",         "annual"),

    # Trade
    "NE.EXP.GNFS.CD":      ("exports_usd",                  "annual"),
    "NE.IMP.GNFS.CD":      ("imports_usd",                  "annual"),

    # Fiscal
    "GC.DOD.TOTL.GD.ZS":  ("government_debt_gdp_pct",      "annual"),
    "GC.BAL.CASH.GD.ZS":  ("budget_balance_gdp_pct",       "annual"),
    "GC.TAX.TOTL.GD.ZS":  ("tax_revenue_gdp_pct",          "annual"),
    "MS.MIL.XPND.GD.ZS":  ("military_spending_gdp_pct",    "annual"),
    "SE.XPD.TOTL.GD.ZS":  ("education_spending_gdp_pct",   "annual"),
    "SH.XPD.CHEX.GD.ZS":  ("healthcare_spending_gdp_pct",  "annual"),

    # Labour
    "SL.UEM.TOTL.ZS":      ("unemployment_pct",             "annual"),
    "SL.UEM.1524.ZS":      ("youth_unemployment_pct",       "annual"),
    "SL.TLF.CACT.ZS":      ("labor_participation_pct",      "annual"),
    "SL.TLF.CACT.FE.ZS":  ("female_labor_participation_pct", "annual"),

    # Social
    "SI.POV.GINI":         ("gini_coefficient",             "annual"),
    "SI.POV.DDAY":         ("poverty_rate_pct",             "annual"),
    "SE.ADT.LITR.ZS":      ("literacy_rate_pct",            "annual"),
    "IT.NET.USER.ZS":      ("internet_penetration_pct",     "annual"),
    "SP.DYN.IMRT.IN":      ("infant_mortality_per_1000",    "annual"),
    "SH.MED.BEDS.ZS":      ("hospital_beds_per_1000",       "annual"),
    "SH.MED.PHYS.ZS":      ("doctors_per_1000",             "annual"),

    # Environment
    "EG.ELC.RNEW.ZS":      ("renewable_energy_pct",         "annual"),
    "AG.LND.FRST.ZS":      ("forest_cover_pct",             "annual"),

    # Innovation
    "GB.XPD.RSDV.GD.ZS":  ("rd_spending_gdp_pct",          "annual"),
    "IP.PAT.RESD":         ("patent_applications",          "annual"),

    # Tourism
    "ST.INT.ARVL":         ("tourist_arrivals",             "annual"),
    "ST.INT.RCPT.CD":      ("tourism_revenue_usd",          "annual"),
}


def _fetch_indicator(wb_code: str, date_range: str = "2018:2024") -> list[dict]:
    """Fetch all countries for one WB indicator. Returns list of {country_code, year, value}."""
    url = f"{WB_BASE}/country/all/indicator/{wb_code}"
    params = {
        "format": "json",
        "per_page": PER_PAGE,
        "date": date_range,
        "mrv": 5,  # most recent 5 values
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not data or len(data) < 2 or not data[1]:
            return []
        return [
            {
                "country_code": row["country"]["id"],  # ISO 2-letter
                "year": int(row["date"]),
                "value": row["value"],
            }
            for row in data[1]
            if row.get("value") is not None
        ]
    except Exception:
        log.exception(f"WB fetch failed: {wb_code}")
        return []


@app.task(name='tasks.world_bank_update.update_world_bank', bind=True, max_retries=2)
def update_world_bank(self):
    """Refresh World Bank indicators for all 196 countries. Runs daily."""
    db = SessionLocal()
    try:
        # Build ISO-2 → country_id map once
        countries = db.query(Country.code, Country.id).all()
        code_to_id: dict[str, int] = {c.code: c.id for c in countries}

        total_upserted = 0

        for wb_code, (indicator_name, period_type) in INDICATORS.items():
            rows = _fetch_indicator(wb_code)
            if not rows:
                log.warning(f"WB: no data for {wb_code}")
                time.sleep(0.5)
                continue

            batch = []
            for row in rows:
                country_id = code_to_id.get(row["country_code"])
                if not country_id:
                    continue
                batch.append({
                    "country_id": country_id,
                    "indicator": indicator_name,
                    "value": float(row["value"]),
                    "period_date": date(row["year"], 1, 1),
                    "period_type": period_type,
                    "source": "world_bank",
                })

            if batch:
                stmt = pg_insert(CountryIndicator).values(batch)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_country_indicator_date",
                    set_={"value": stmt.excluded.value, "source": stmt.excluded.source},
                )
                db.execute(stmt)
                db.commit()
                total_upserted += len(batch)
                log.info(f"WB: {indicator_name} — {len(batch)} rows upserted")

            time.sleep(0.3)  # be polite to the WB API

        log.info(f"World Bank update complete — {total_upserted} total rows")
        return f"ok: {total_upserted} rows"

    except Exception as exc:
        db.rollback()
        log.exception("World Bank update failed")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
