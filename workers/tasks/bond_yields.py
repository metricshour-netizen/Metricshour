"""
Government bond yield ingestion — US Treasury XML API (no API key required).
Runs daily at 6:30am UTC, after markets close.

Sources:
  US02Y  → home.treasury.gov DailyTreasuryYieldCurveRateData (BC_2YEAR field)

US 5Y/10Y/30Y are handled by yfinance in indices.py (^FVX/^TNX/^TYX).
EU/JP sovereign bonds (DE10Y, GB10Y, FR10Y, IT10Y, JP10Y) are inactive —
no accessible free data source is available from the server.
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

TREASURY_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/"
    "interest-rates/pages/xml"
)
TIMEOUT = 20
HEADERS = {"User-Agent": "MetricsHour/1.0"}

# Namespaces used in Treasury XML
_NS = "http://schemas.microsoft.com/ado/2007/08/dataservices"
_NS_M = "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"


def _fetch_us02y() -> float | None:
    """Fetch the most recent US 2-Year Treasury yield from Treasury.gov XML."""
    from datetime import date

    ym = date.today().strftime("%Y%m")
    try:
        resp = requests.get(
            TREASURY_URL,
            params={"data": "daily_treasury_yield_curve", "field_tdr_date_value_month": ym},
            timeout=TIMEOUT,
            headers=HEADERS,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        latest: float | None = None
        # Entries are ordered oldest→newest; iterate all BC_2YEAR elements, keep last
        for el in root.iter(f"{{{_NS}}}BC_2YEAR"):
            if el.text:
                try:
                    latest = float(el.text)
                except ValueError:
                    pass
        return latest
    except Exception:
        log.exception("Treasury.gov fetch failed for US02Y")
        return None


# Maps our DB symbol → fetch function
BOND_FETCHERS: dict[str, callable] = {
    "US02Y": _fetch_us02y,
}


@app.task(name="tasks.bond_yields.fetch_bond_yields", bind=True, max_retries=3)
def fetch_bond_yields(self):
    """Fetch government bond yields from official sources and upsert into prices table."""
    db = SessionLocal()
    try:
        assets = (
            db.query(Asset)
            .filter(
                Asset.asset_type == AssetType.bond,
                Asset.symbol.in_(list(BOND_FETCHERS.keys())),
                Asset.is_active == True,
            )
            .all()
        )
        if not assets:
            log.info("No bond assets active for yield fetching — skipping")
            return

        symbol_to_asset = {a.symbol: a for a in assets}
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        rows = []

        for sym, fetch_fn in BOND_FETCHERS.items():
            if sym not in symbol_to_asset:
                continue
            yield_pct = fetch_fn()
            if yield_pct is None:
                log.warning("No yield data returned for %s", sym)
                continue
            asset = symbol_to_asset[sym]
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
            log.info("Bond yield: %s = %.4f%%", sym, yield_pct)

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
