"""
Stock price ingestion — Marketstack (primary, EOD + intraday) + yfinance fallback.
Runs every 15 minutes.

Marketstack handles global exchanges and is available 24/7 for EOD data.
yfinance used as fallback when Marketstack misses a symbol.
"""

import logging
import os
from datetime import datetime, timezone

import requests
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

MARKETSTACK_KEY = os.environ.get('MARKETSTACK_API_KEY', '')
MARKETSTACK_URL = 'http://api.marketstack.com/v1'
CHUNK_SIZE = 50   # marketstack accepts up to 100 symbols per call; 50 is safe


def _fetch_marketstack(symbols: list[str]) -> dict[str, float]:
    """
    Fetch latest EOD close prices for a batch of symbols via Marketstack.
    Returns {symbol: close_price}. Skips symbols that fail quietly.
    """
    if not MARKETSTACK_KEY:
        return {}

    result: dict[str, float] = {}
    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i:i + CHUNK_SIZE]
        try:
            resp = requests.get(
                f'{MARKETSTACK_URL}/eod/latest',
                params={
                    'access_key': MARKETSTACK_KEY,
                    'symbols': ','.join(chunk),
                    'limit': len(chunk),
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            for row in data.get('data', []):
                sym = row.get('symbol', '').split('.')[0]  # strip exchange suffix
                if sym and row.get('close'):
                    result[sym] = float(row['close'])
        except Exception:
            log.warning(f'Marketstack batch {i}-{i+CHUNK_SIZE} failed', exc_info=True)

    return result


def _fetch_yfinance(symbols: list[str]) -> dict[str, float]:
    """yfinance fallback for symbols Marketstack doesn't cover."""
    result: dict[str, float] = {}
    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i:i + CHUNK_SIZE]
        try:
            if len(chunk) == 1:
                df = yf.download(chunk[0], period='2d', interval='1d', progress=False)
                if not df.empty:
                    close = df['Close'].dropna()
                    if not close.empty:
                        result[chunk[0]] = float(close.iloc[-1])
            else:
                df = yf.download(chunk, period='2d', interval='1d',
                                 group_by='ticker', progress=False, threads=True)
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


def _upsert_prices(db, symbol_to_asset: dict, prices: dict[str, float], now: datetime) -> int:
    rows = [
        {
            'asset_id': symbol_to_asset[sym].id,
            'timestamp': now,
            'interval': '1d',
            'open': None, 'high': None, 'low': None,
            'close': price,
            'volume': None,
        }
        for sym, price in prices.items()
        if sym in symbol_to_asset
    ]
    if not rows:
        return 0
    stmt = pg_insert(Price).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint='uq_price_asset_time_interval',
        set_={'close': stmt.excluded.close},
    )
    db.execute(stmt)
    return len(rows)


@app.task(name='tasks.stocks.fetch_stock_prices', bind=True, max_retries=3)
def fetch_stock_prices(self):
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

        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        # Primary: Marketstack
        prices = _fetch_marketstack(symbols)

        # Fallback: yfinance for anything Marketstack missed
        missed = [s for s in symbols if s not in prices]
        if missed:
            fallback = _fetch_yfinance(missed)
            prices.update(fallback)

        count = _upsert_prices(db, symbol_to_asset, prices, now)
        db.commit()
        log.info(f'Stocks: upserted {count}/{len(symbols)} prices (marketstack={len(prices)-len(missed)}, yf={len(prices)-count+count-len(missed)})')

    except Exception as exc:
        db.rollback()
        log.exception('Stock price fetch failed')
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
