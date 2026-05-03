"""
Earnings calendar fetcher — yfinance .earnings_dates for tracked stocks.
Upserts into earnings_events table. Then backfills revenue_actual from
Tiingo fundamentals income statements for past quarters.

Runs daily at 7:30am UTC.
"""

import logging
import os
from datetime import date, timedelta

import requests
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType
from app.models.earnings import EarningsEvent

log = logging.getLogger(__name__)

BATCH_SIZE = 100
TIINGO_KEY = os.environ.get("TIINGO_API_KEY", "")


def _fetch_tiingo_revenue(symbol: str) -> dict[str, float]:
    """Return {date_str: revenue} from Tiingo quarterly income statements.
    date_str is ISO date of the statement period end — matched ±45 days to report_date.
    """
    if not TIINGO_KEY:
        return {}
    try:
        url = f"https://api.tiingo.com/tiingo/fundamentals/{symbol.lower()}/statements"
        r = requests.get(url, params={"token": TIINGO_KEY, "startDate": "2022-01-01"}, timeout=10)
        if r.status_code != 200:
            return {}
        data = r.json()
        result: dict[str, float] = {}
        for entry in data:
            period_end = entry.get("date", "")[:10]
            # income statement is nested under statementData.incomeStatement list
            stmts = entry.get("statementData", {}).get("incomeStatement", [])
            for row in stmts:
                if row.get("dataCode") == "revenue" and row.get("value") is not None:
                    result[period_end] = float(row["value"])
                    break
        return result
    except Exception as e:
        log.debug("Tiingo revenue fetch failed for %s: %s", symbol, e)
        return {}


def _match_revenue(revenue_map: dict[str, float], report_date: date) -> float | None:
    """Find a revenue value whose period-end date is within 45 days of report_date."""
    best: float | None = None
    best_delta = 999
    for ds, rev in revenue_map.items():
        try:
            d = date.fromisoformat(ds)
        except ValueError:
            continue
        delta = abs((d - report_date).days)
        if delta <= 45 and delta < best_delta:
            best_delta = delta
            best = rev
    return best


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

        # Backfill revenue_actual from Tiingo for rows that have eps_actual but no revenue
        if TIINGO_KEY:
            rev_updated = 0
            rows_needing_rev = db.execute(
                select(EarningsEvent.id, EarningsEvent.symbol, EarningsEvent.report_date)
                .where(EarningsEvent.eps_actual.isnot(None))
                .where(EarningsEvent.revenue_actual.is_(None))
                .limit(500)
            ).all()

            seen_symbols: dict[str, dict[str, float]] = {}
            for ev_id, ev_symbol, ev_date in rows_needing_rev:
                if ev_symbol not in seen_symbols:
                    seen_symbols[ev_symbol] = _fetch_tiingo_revenue(ev_symbol)
                rev = _match_revenue(seen_symbols[ev_symbol], ev_date)
                if rev is not None:
                    db.execute(
                        update(EarningsEvent)
                        .where(EarningsEvent.id == ev_id)
                        .values(revenue_actual=rev)
                    )
                    rev_updated += 1

            db.commit()
            log.info("Earnings calendar: backfilled revenue_actual for %d rows", rev_updated)

        return {"stocks": len(assets), "rows": total}
    except Exception as exc:
        db.rollback()
        log.error("Earnings calendar error: %s", exc)
        raise self.retry(exc=exc, countdown=600)
    finally:
        db.close()
