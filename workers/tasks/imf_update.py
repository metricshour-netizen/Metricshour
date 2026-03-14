"""
IMF DataMapper API — forecasts for 190+ countries.
Source: https://www.imf.org/external/datamapper/api/v1/
Runs monthly on the 1st at 5am UTC.

No API key. Commercial use permitted (public IMF data).

Key indicators: GDP growth, inflation, unemployment, current account,
government debt, fiscal balance, interest rates.
"""

import logging
import time
from datetime import date

import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.country import Country, CountryIndicator

log = logging.getLogger(__name__)

IMF_BASE = "https://www.imf.org/external/datamapper/api/v1"

# IMF indicator code → (our indicator name, period_type)
# IMF DataMapper provides annual forecasts (current year + 5yr horizon)
IMF_INDICATORS: dict[str, tuple[str, str]] = {
    "NGDP_RPCH":    ("imf_gdp_growth_pct",          "annual"),   # Real GDP growth %
    "NGDPD":        ("imf_gdp_usd_bn",               "annual"),   # GDP, USD billions
    "NGDPDPC":      ("imf_gdp_per_capita_usd",       "annual"),   # GDP per capita, USD
    "PPPPC":        ("imf_gdp_ppp_per_capita",       "annual"),   # GDP per capita, PPP
    "PCPIPCH":      ("imf_inflation_pct",             "annual"),   # CPI inflation %
    "LUR":          ("imf_unemployment_pct",          "annual"),   # Unemployment rate %
    "BCA_NGDPD":    ("imf_current_account_pct_gdp",  "annual"),   # Current account % GDP
    "GGXWDG_NGDP":  ("imf_govt_gross_debt_pct_gdp",  "annual"),   # General govt gross debt % GDP
    "GGXCNL_NGDP":  ("imf_fiscal_balance_pct_gdp",   "annual"),   # Net lending/borrowing % GDP
    "GGX_NGDP":     ("imf_govt_expenditure_pct_gdp", "annual"),   # Govt expenditure % GDP
    "GGREV_NGDP":   ("imf_govt_revenue_pct_gdp",     "annual"),   # Govt revenue % GDP
    "FPCPITOTLZG":  ("imf_inflation_forecast_pct",   "annual"),   # Inflation forecast
    "TM_RPCH":      ("imf_import_growth_pct",         "annual"),   # Import growth %
    "TX_RPCH":      ("imf_export_growth_pct",         "annual"),   # Export growth %
    "LP":           ("imf_population_mn",             "annual"),   # Population, millions
}

# IMF uses ISO 3-letter codes (mostly standard, some exceptions)
# Exceptions to standard alpha-3:
IMF_CODE_REMAP: dict[str, str] = {
    "UVK": "XK",   # Kosovo (non-standard)
    "WBG": "PS",   # West Bank & Gaza
    "CZR": "CZ",   # Czech Republic (old IMF code)
    "SVK": "SK",   # Slovakia
}


def _fetch_imf_indicator(imf_code: str) -> dict[str, dict[int, float]]:
    """
    Fetch one IMF indicator for all countries.
    Returns {imf_country_code: {year: value}}.
    """
    url = f"{IMF_BASE}/{imf_code}"
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        values = data.get("values", {}).get(imf_code, {})
        return {
            country: {int(yr): float(val) for yr, val in years.items() if val is not None}
            for country, years in values.items()
        }
    except Exception:
        log.exception(f"IMF fetch failed: {imf_code}")
        return {}


def _build_code_maps(db) -> tuple[dict[str, int], dict[str, int]]:
    """Build ISO2 and ISO3 → country_id maps."""
    countries = db.execute(select(Country.code, Country.code3, Country.id)).all()
    iso2 = {c.code: c.id for c in countries}
    iso3 = {c.code3: c.id for c in countries if c.code3}
    return iso2, iso3


@app.task(name='tasks.imf_update.update_imf_data', bind=True, max_retries=2, time_limit=1800)
def update_imf_data(self):
    """Refresh IMF forecasts for all countries. Runs monthly on the 1st."""
    db = SessionLocal()
    try:
        iso2_map, iso3_map = _build_code_maps(db)
        total_upserted = 0

        for imf_code, (indicator_name, period_type) in IMF_INDICATORS.items():
            country_data = _fetch_imf_indicator(imf_code)
            if not country_data:
                time.sleep(1)
                continue

            batch = []
            for imf_country_code, year_values in country_data.items():
                # Map IMF country code → our DB id (try ISO3 first, then remap)
                mapped_code = IMF_CODE_REMAP.get(imf_country_code, imf_country_code)
                country_id = iso3_map.get(mapped_code) or iso2_map.get(mapped_code)
                if not country_id:
                    continue

                for year, value in year_values.items():
                    if year < 2015:
                        continue
                    batch.append({
                        "country_id": country_id,
                        "indicator": indicator_name,
                        "value": value,
                        "period_date": date(year, 1, 1),
                        "period_type": period_type,
                        "source": "imf",
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
                log.info(f"IMF: {indicator_name} — {len(batch)} rows upserted")

            time.sleep(0.5)

        log.info(f"IMF update complete — {total_upserted} total rows")

        # Fire macro alert check instantly — users get alerted the moment new data lands
        if total_upserted > 0:
            from tasks.macro_alert_checker import check_macro_alerts
            check_macro_alerts.apply_async(countdown=5)
            log.info("Macro alert check queued after IMF update")

        return f"ok: {total_upserted} rows"

    except Exception as exc:
        db.rollback()
        log.exception("IMF update failed")
        raise self.retry(exc=exc, countdown=600)
    finally:
        db.close()
