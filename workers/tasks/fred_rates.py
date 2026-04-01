"""
FRED rates fetcher — public CSV endpoint, no API key required.
Fetches yield curve, Fed funds rate, CPI, M2, jobless claims, mortgage rates.

Source: https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}
Stores into macro_series table. Runs daily at 6:30am UTC.
"""

import csv
import logging
from datetime import date, datetime, timedelta
from io import StringIO

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.macro import MacroSeries

log = logging.getLogger(__name__)

FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"

# series_id → (display_name, category, period_type)
FRED_SERIES: dict[str, tuple[str, str, str]] = {
    # Yield curve
    "DGS3MO": ("3-Month Treasury Yield",        "yield_curve", "daily"),
    "DGS2":   ("2-Year Treasury Yield",          "yield_curve", "daily"),
    "DGS5":   ("5-Year Treasury Yield",          "yield_curve", "daily"),
    "DGS10":  ("10-Year Treasury Yield",         "yield_curve", "daily"),
    "DGS30":  ("30-Year Treasury Yield",         "yield_curve", "daily"),
    "T10Y2Y": ("10Y-2Y Term Spread",             "yield_curve", "daily"),
    # Interest rates
    "DFF":          ("Fed Funds Rate",              "rates", "daily"),
    "MORTGAGE30US": ("30-Year Mortgage Rate",       "rates", "weekly"),
    "DFII10":       ("10-Year Real Rate (TIPS)",    "rates", "daily"),
    # Inflation
    "CPIAUCSL": ("CPI (All Urban Consumers)",    "inflation", "monthly"),
    "CPILFESL": ("Core CPI (ex Food & Energy)",  "inflation", "monthly"),
    "PCEPI":    ("PCE Price Index",              "inflation", "monthly"),
    # Money supply
    "M2SL": ("M2 Money Supply",                  "money", "monthly"),
    # Labor
    "ICSA":   ("Initial Jobless Claims",         "labor", "weekly"),
    "UNRATE": ("Unemployment Rate",              "labor", "monthly"),
}

# How many days back to fetch on first run (subsequent runs only need recent data)
LOOKBACK_DAYS = 365 * 5  # 5 years for charts


def _fetch_series(series_id: str, since: date | None = None) -> list[tuple[date, float]]:
    """Download FRED CSV and return (date, value) pairs, skipping missing values."""
    url = FRED_BASE.format(series_id)
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        log.warning("FRED fetch failed for %s: %s", series_id, e)
        return []

    rows: list[tuple[date, float]] = []
    reader = csv.DictReader(StringIO(resp.text))
    fieldnames = reader.fieldnames or []
    # FRED CSV uses "observation_date" as the date column; value column is the series_id
    date_col = "observation_date" if "observation_date" in fieldnames else "DATE"
    value_col = series_id if series_id in fieldnames else "VALUE"
    for row in reader:
        try:
            d = date.fromisoformat(row[date_col])
            v = row.get(value_col, "").strip()
            if v == "." or not v:  # FRED uses "." for missing
                continue
            if since and d < since:
                continue
            rows.append((d, float(v)))
        except (ValueError, KeyError):
            continue
    return rows


def _upsert_rows(db, series_id: str, name: str, category: str, period_type: str,
                  rows: list[tuple[date, float]]) -> int:
    if not rows:
        return 0
    values = [
        {
            "series_id": series_id,
            "name": name,
            "category": category,
            "period_type": period_type,
            "period_date": d,
            "value": v,
            "source": "fred",
        }
        for d, v in rows
    ]
    stmt = pg_insert(MacroSeries).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_macro_series_date",
        set_={"value": stmt.excluded.value, "name": stmt.excluded.name},
    )
    db.execute(stmt)
    return len(values)


@app.task(name="fred_rates.fetch_all", bind=True, max_retries=2)
def fetch_fred_rates(self):
    """Fetch all FRED series and store in macro_series. Runs daily 6:30am UTC."""
    db = SessionLocal()
    try:
        from sqlalchemy import select, func
        total = 0
        for series_id, (name, category, period_type) in FRED_SERIES.items():
            # Check how far back we already have data
            latest_row = db.execute(
                select(MacroSeries.period_date)
                .where(MacroSeries.series_id == series_id)
                .order_by(MacroSeries.period_date.desc())
                .limit(1)
            ).scalar_one_or_none()

            if latest_row is None:
                since = date.today() - timedelta(days=LOOKBACK_DAYS)
            else:
                # Re-fetch from 30 days before latest to catch revisions
                since = latest_row - timedelta(days=30)

            rows = _fetch_series(series_id, since=since)
            n = _upsert_rows(db, series_id, name, category, period_type, rows)
            total += n
            log.info("FRED %s: upserted %d rows", series_id, n)

        db.commit()
        log.info("FRED fetch complete — %d total rows upserted across %d series",
                 total, len(FRED_SERIES))
        return {"series": len(FRED_SERIES), "rows": total}
    except Exception as exc:
        db.rollback()
        log.error("FRED fetch error: %s", exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
