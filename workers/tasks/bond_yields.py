"""
Government bond yield ingestion — FRED CSV API (no API key required).
Runs daily at 6:30am UTC, after markets close.

FRED series used:
  US02Y  → DGS2         (US Treasury 2-Year Constant Maturity, daily)
  DE10Y  → IRLTLT01DEM156N  (Germany Long-Term Govt Bond Yields, monthly)
  GB10Y  → IRLTLT01GBM156N  (UK Long-Term Govt Bond Yields, monthly)
  FR10Y  → IRLTLT01FRM156N  (France Long-Term Govt Bond Yields, monthly)
  IT10Y  → IRLTLT01ITM156N  (Italy Long-Term Govt Bond Yields, monthly)
  JP10Y  → IRLTLT01JPM156N  (Japan Long-Term Govt Bond Yields, monthly)

US 5Y/10Y/30Y are already handled by yfinance in indices.py (^FVX/^TNX/^TYX).
"""

import csv
import logging
from datetime import datetime, timezone
from io import StringIO

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# Maps our DB symbol → FRED series ID
FRED_BOND_MAP: dict[str, str] = {
    "US02Y": "DGS2",
    "DE10Y": "IRLTLT01DEM156N",
    "GB10Y": "IRLTLT01GBM156N",
    "FR10Y": "IRLTLT01FRM156N",
    "IT10Y": "IRLTLT01ITM156N",
    "JP10Y": "IRLTLT01JPM156N",
}

TIMEOUT = 30
HEADERS = {"User-Agent": "MetricsHour/1.0"}


def _fetch_latest_yield(fred_series: str) -> float | None:
    """Fetch the most recent non-null value from a FRED CSV series."""
    try:
        resp = requests.get(
            FRED_BASE, params={"id": fred_series}, timeout=TIMEOUT, headers=HEADERS
        )
        resp.raise_for_status()
        reader = csv.reader(StringIO(resp.text))
        next(reader)  # skip header row
        latest: float | None = None
        for row in reader:
            if len(row) < 2:
                continue
            val = row[1].strip()
            if val and val != ".":  # FRED uses "." for missing values
                try:
                    latest = float(val)
                except ValueError:
                    pass
        return latest
    except Exception:
        log.exception("FRED fetch failed for %s", fred_series)
        return None


@app.task(name="tasks.bond_yields.fetch_bond_yields", bind=True, max_retries=3)
def fetch_bond_yields(self):
    """Fetch government bond yields from FRED and upsert into prices table."""
    db = SessionLocal()
    try:
        assets = (
            db.query(Asset)
            .filter(
                Asset.asset_type == AssetType.bond,
                Asset.symbol.in_(list(FRED_BOND_MAP.keys())),
                Asset.is_active == True,
            )
            .all()
        )
        if not assets:
            log.info("No FRED bond assets active — skipping")
            return

        symbol_to_asset = {a.symbol: a for a in assets}
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        rows = []

        for db_sym, fred_series in FRED_BOND_MAP.items():
            if db_sym not in symbol_to_asset:
                continue
            yield_pct = _fetch_latest_yield(fred_series)
            if yield_pct is None:
                log.warning("No FRED data returned for %s (%s)", db_sym, fred_series)
                continue
            asset = symbol_to_asset[db_sym]
            rows.append({
                "asset_id": asset.id,
                "timestamp": now,
                "interval": "1d",
                "open": None,
                "high": None,
                "low": None,
                "close": yield_pct,
                "volume": None,
            })
            log.info("Bond yield: %s = %.4f%% (FRED:%s)", db_sym, yield_pct, fred_series)

        if rows:
            stmt = pg_insert(Price).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_price_asset_time_interval",
                set_={"close": stmt.excluded.close},
            )
            db.execute(stmt)
            db.commit()
            log.info("Bond yields: upserted %d rows", len(rows))

    except Exception as exc:
        db.rollback()
        log.exception("Bond yield fetch failed")
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
