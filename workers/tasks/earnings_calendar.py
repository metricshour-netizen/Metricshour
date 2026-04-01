"""
Earnings calendar fetcher — yfinance .earnings_dates for tracked stocks.
Upserts into earnings_events table.

Runs daily at 7:30am UTC. Fetches 90 days forward + 30 days back.
Prioritises the 50 largest-cap stocks per run to stay within rate limits.
"""

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType
from app.models.earnings import EarningsEvent

log = logging.getLogger(__name__)

# Process top N stocks by market cap per run (yfinance rate limit friendly)
BATCH_SIZE = 100


def _fetch_earnings(symbol: str) -> list[dict]:
    """Return list of earnings dicts for a symbol via yfinance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        df = ticker.earnings_dates
        if df is None or df.empty:
            return []
        rows = []
        for idx, row in df.iterrows():
            try:
                # idx is a DatetimeTZDtype; convert to date
                report_date = idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])
                eps_est = float(row.get("EPS Estimate", None) or 0) or None
                eps_act = float(row.get("Reported EPS", None) or 0) or None
                surprise = float(row.get("Surprise(%)", None) or 0) or None
                rows.append({
                    "report_date": report_date,
                    "eps_estimate": eps_est,
                    "eps_actual": eps_act,
                    "surprise_pct": surprise,
                })
            except Exception:
                continue
        return rows
    except Exception as e:
        log.debug("yfinance earnings fetch failed for %s: %s", symbol, e)
        return []


@app.task(name="earnings_calendar.fetch_earnings_dates", bind=True, max_retries=2)
def fetch_earnings_dates(self):
    """Fetch upcoming earnings for top stocks and upsert into earnings_events."""
    db = SessionLocal()
    try:
        # Fetch top stocks by market cap
        assets = db.execute(
            select(Asset.id, Asset.symbol)
            .where(Asset.asset_type == AssetType.stock)
            .where(Asset.is_active == True)
            .where(Asset.market_cap_usd.isnot(None))
            .order_by(Asset.market_cap_usd.desc())
            .limit(BATCH_SIZE)
        ).all()

        total = 0
        for asset_id, symbol in assets:
            raw_rows = _fetch_earnings(symbol)
            if not raw_rows:
                continue

            values = [
                {
                    "asset_id": asset_id,
                    "symbol": symbol,
                    "report_date": r["report_date"],
                    "eps_estimate": r["eps_estimate"],
                    "eps_actual": r["eps_actual"],
                    "surprise_pct": r["surprise_pct"],
                }
                for r in raw_rows
            ]

            stmt = pg_insert(EarningsEvent).values(values)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_earnings_symbol_date",
                set_={
                    "eps_estimate": stmt.excluded.eps_estimate,
                    "eps_actual": stmt.excluded.eps_actual,
                    "surprise_pct": stmt.excluded.surprise_pct,
                },
            )
            db.execute(stmt)
            total += len(values)
            log.debug("Earnings %s: %d rows", symbol, len(values))

        db.commit()
        log.info("Earnings calendar: upserted %d rows for %d stocks", total, len(assets))
        return {"stocks": len(assets), "rows": total}
    except Exception as exc:
        db.rollback()
        log.error("Earnings calendar error: %s", exc)
        raise self.retry(exc=exc, countdown=600)
    finally:
        db.close()
