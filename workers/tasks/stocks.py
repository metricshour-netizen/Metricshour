"""
Stock price ingestion — yfinance (free, no key required).
Runs every 15 minutes during NYSE market hours (Mon-Fri ~14:30-21:00 UTC).
"""

import logging
from datetime import datetime, timezone

import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

CHUNK_SIZE = 50  # yfinance handles up to ~50 symbols well per batch


def _is_market_hours() -> bool:
    """Approximate NYSE hours: Mon-Fri, 14:30-21:00 UTC."""
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    return (now.hour == 14 and now.minute >= 30) or (15 <= now.hour < 21)


def _fetch_latest_closes(symbols: list[str]) -> dict[str, float]:
    """Fetch latest 15m close price for each symbol via yfinance."""
    result: dict[str, float] = {}

    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i:i + CHUNK_SIZE]
        try:
            if len(chunk) == 1:
                df = yf.download(chunk[0], period='1d', interval='15m', progress=False)
                if not df.empty:
                    close = df['Close'].dropna()
                    if not close.empty:
                        result[chunk[0]] = float(close.iloc[-1])
            else:
                df = yf.download(
                    chunk, period='1d', interval='15m',
                    group_by='ticker', progress=False, threads=True,
                )
                for sym in chunk:
                    try:
                        close = df[sym]['Close'].dropna()
                        if not close.empty:
                            result[sym] = float(close.iloc[-1])
                    except (KeyError, IndexError):
                        pass
        except Exception:
            log.exception(f'yfinance batch {i}-{i+CHUNK_SIZE} failed')

    return result


@app.task(name='tasks.stocks.fetch_stock_prices', bind=True, max_retries=3)
def fetch_stock_prices(self):
    if not _is_market_hours():
        return 'skipped: outside market hours'

    db = SessionLocal()
    try:
        assets = (
            db.query(Asset)
            .filter(Asset.asset_type == AssetType.stock, Asset.is_active == True)
            .all()
        )
        symbol_to_asset = {a.symbol: a for a in assets}
        symbols = list(symbol_to_asset.keys())

        if not symbols:
            return

        prices = _fetch_latest_closes(symbols)
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        rows = [
            {
                'asset_id': symbol_to_asset[sym].id,
                'timestamp': now,
                'interval': '15m',
                'open': None,
                'high': None,
                'low': None,
                'close': price,
                'volume': None,
            }
            for sym, price in prices.items()
            if sym in symbol_to_asset
        ]

        if rows:
            stmt = pg_insert(Price).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_price_asset_time_interval',
                set_={'close': stmt.excluded.close},
            )
            db.execute(stmt)
            db.commit()
            log.info(f'Stocks: upserted {len(rows)}/{len(symbols)} prices')

    except Exception as exc:
        db.rollback()
        log.exception('Stock price fetch failed')
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
