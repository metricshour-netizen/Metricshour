"""
OECD SDMX API — economic indicators for 38 OECD member countries.
Source: https://data.oecd.org/api/
Runs weekly on Sunday at 1am UTC.

No API key. Commercial use permitted.

Key datasets:
  - MEI: Main Economic Indicators (industrial production, interest rates, leading indicators)
  - MEI_CLI: Composite Leading Indicators
  - MONTHLY_TRADE: Merchandise trade flows (monthly)
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

OECD_BASE = "https://stats.oecd.org/restsdmx/sdmx.ashx/GetData"

# OECD country codes (ISO alpha-2, but OECD uses alpha-3 for API)
# OECD 3-letter → ISO 2-letter for our DB
OECD_TO_ISO2: dict[str, str] = {
    "AUS": "AU", "AUT": "AT", "BEL": "BE", "CAN": "CA", "CHL": "CL",
    "COL": "CO", "CZE": "CZ", "DNK": "DK", "EST": "EE", "FIN": "FI",
    "FRA": "FR", "DEU": "DE", "GRC": "GR", "HUN": "HU", "ISL": "IS",
    "IRL": "IE", "ISR": "IL", "ITA": "IT", "JPN": "JP", "KOR": "KR",
    "LVA": "LV", "LTU": "LT", "LUX": "LU", "MEX": "MX", "NLD": "NL",
    "NZL": "NZ", "NOR": "NO", "POL": "PL", "PRT": "PT", "SVK": "SK",
    "SVN": "SI", "ESP": "ES", "SWE": "SE", "CHE": "CH", "TUR": "TR",
    "GBR": "GB", "USA": "US", "CRI": "CR",
}

# OECD API queries: (dataset, series_key, measure_concept, our_indicator, period_type)
# Each query fetches all OECD countries for one indicator
QUERIES: list[dict] = [
    # Composite Leading Indicator (normalised)
    {
        "dataset": "MEI_CLI",
        "key": "LOLITOAA.{country}.IXOBSA.M",
        "indicator": "oecd_cli",
        "period_type": "monthly",
        "description": "Composite Leading Indicator",
    },
    # Industrial Production Index
    {
        "dataset": "MEI",
        "key": "{country}.PRINTO01.IXOBSA.M",
        "indicator": "oecd_industrial_production",
        "period_type": "monthly",
        "description": "Industrial Production Index",
    },
    # Short-term interest rate (3-month)
    {
        "dataset": "MEI",
        "key": "{country}.IR3TIB01.ST.M",
        "indicator": "oecd_short_term_rate",
        "period_type": "monthly",
        "description": "3-month interest rate",
    },
    # Long-term interest rate (10yr govt bond)
    {
        "dataset": "MEI",
        "key": "{country}.IRLTLT01.ST.M",
        "indicator": "oecd_long_term_rate",
        "period_type": "monthly",
        "description": "10-year government bond yield",
    },
    # CPI (Consumer Price Index, all items)
    {
        "dataset": "MEI",
        "key": "{country}.CPALTT01.IXNBSA.M",
        "indicator": "oecd_cpi_index",
        "period_type": "monthly",
        "description": "CPI All Items Index",
    },
    # Unemployment rate (monthly)
    {
        "dataset": "MEI",
        "key": "{country}.LRUNTTTT.STSA.M",
        "indicator": "oecd_unemployment_monthly",
        "period_type": "monthly",
        "description": "Harmonised unemployment rate",
    },
    # Retail Trade (volume)
    {
        "dataset": "MEI",
        "key": "{country}.SLRTTO01.IXOBSA.M",
        "indicator": "oecd_retail_trade",
        "period_type": "monthly",
        "description": "Retail trade volume index",
    },
    # Merchandise imports value
    {
        "dataset": "MEI",
        "key": "{country}.XTIMVA01.STSA.M",
        "indicator": "oecd_imports_monthly_usd",
        "period_type": "monthly",
        "description": "Imports value USD",
    },
    # Merchandise exports value
    {
        "dataset": "MEI",
        "key": "{country}.XTEXVA01.STSA.M",
        "indicator": "oecd_exports_monthly_usd",
        "period_type": "monthly",
        "description": "Exports value USD",
    },
]

ALL_OECD = "+".join(OECD_TO_ISO2.keys())


def _fetch_oecd_json(dataset: str, key: str) -> list[dict]:
    """
    Fetch OECD SDMX data as JSON. Returns list of {country_code3, period, value}.
    Uses all OECD countries in one request.
    """
    series_key = key.replace("{country}", ALL_OECD)
    url = f"{OECD_BASE}/{dataset}/{series_key}/all"
    params = {"format": "json", "startTime": "2018-01", "endTime": "2099-12"}

    try:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
    except Exception:
        log.exception(f"OECD fetch failed: {dataset}/{key}")
        return []

    # OECD JSON structure: data.dataSets[0].series, data.structure.dimensions
    try:
        structure = data["structure"]
        dimensions = structure["dimensions"]["series"]
        # Find location dimension index
        loc_dim = next((d for d in dimensions if d["id"] in ("LOCATION", "COUNTRY")), None)
        if not loc_dim:
            return []
        loc_idx = dimensions.index(loc_dim)
        loc_values = loc_dim["values"]  # list of {id: "USA", ...}

        time_periods = structure["dimensions"]["observation"][0]["values"]
        # [{id: "2023-01", name: "January 2023"}, ...]

        series_data = data["dataSets"][0]["series"]
        results = []

        for series_key_str, series_obj in series_data.items():
            key_parts = series_key_str.split(":")
            loc_code = loc_values[int(key_parts[loc_idx])]["id"]
            observations = series_obj.get("observations", {})

            for obs_idx_str, obs_values in observations.items():
                if obs_values[0] is None:
                    continue
                period_id = time_periods[int(obs_idx_str)]["id"]  # e.g. "2023-01"
                results.append({
                    "country_code3": loc_code,
                    "period": period_id,
                    "value": float(obs_values[0]),
                })

        return results
    except (KeyError, IndexError, ValueError):
        log.exception(f"OECD parse error: {dataset}")
        return []


def _period_to_date(period: str) -> tuple[date, str]:
    """Convert '2023-01' or '2023-Q1' to (date, period_type)."""
    if "-Q" in period:
        year, q = period.split("-Q")
        month = (int(q) - 1) * 3 + 1
        return date(int(year), month, 1), "quarterly"
    if len(period) == 7 and "-" in period:
        year, month = period.split("-")
        return date(int(year), int(month), 1), "monthly"
    return date(int(period), 1, 1), "annual"


@app.task(name='tasks.oecd_update.update_oecd_data', bind=True, max_retries=2)
def update_oecd_data(self):
    """Refresh OECD economic indicators for all 38 member countries. Runs weekly."""
    db = SessionLocal()
    try:
        iso2_map: dict[str, int] = {
            c.code: c.id
            for c in db.query(Country.code, Country.id).all()
        }
        total_upserted = 0

        for query in QUERIES:
            rows = _fetch_oecd_json(query["dataset"], query["key"])
            if not rows:
                log.warning(f"OECD: no data for {query['indicator']}")
                time.sleep(2)
                continue

            batch = []
            for row in rows:
                iso2 = OECD_TO_ISO2.get(row["country_code3"])
                if not iso2:
                    continue
                country_id = iso2_map.get(iso2)
                if not country_id:
                    continue

                pd, period_type = _period_to_date(row["period"])
                if pd.year < 2018:
                    continue

                batch.append({
                    "country_id": country_id,
                    "indicator": query["indicator"],
                    "value": row["value"],
                    "period_date": pd,
                    "period_type": period_type,
                    "source": "oecd",
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
                log.info(f"OECD: {query['indicator']} — {len(batch)} rows upserted")

            time.sleep(1)  # OECD is rate-limit-free but be polite

        log.info(f"OECD update complete — {total_upserted} total rows")
        return f"ok: {total_upserted} rows"

    except Exception as exc:
        db.rollback()
        log.exception("OECD update failed")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
