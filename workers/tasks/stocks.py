"""
Stock price ingestion — Tiingo IEX (primary, real-time OHLCV) + yfinance fallback.
Runs every 15 minutes during market hours.
Tiingo IEX batches up to 100 tickers per call — ~5 calls for 465 US stocks.
"""

import logging
import time
from datetime import datetime, timezone

import requests
import yfinance as yf

# yfinance logs internal per-ticker errors at ERROR level before our except blocks run.
# We handle missing tickers ourselves, so suppress yfinance's own noisy output.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.config import settings
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price
from tasks.market_hours import is_trading_day

log = logging.getLogger(__name__)

TIINGO_HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': f'Token {settings.tiingo_api_key}',
}

# Reject any single-period price change > this threshold (bad ticks)
MAX_STOCK_SPIKE_PCT = 15.0
CHUNK_SIZE = 100  # Tiingo IEX accepts up to 100 symbols per call

# Exchanges we track via IEX (US only)
US_EXCHANGES = {'NASDAQ', 'NYSE', 'NYSE ARCA', 'NYSE MKT', 'AMEX', 'BATS'}


def _fetch_tiingo_iex(symbols: list[str]) -> dict[str, dict]:
    """
    Fetch latest IEX quotes for a batch of US symbols via Tiingo.
    Returns {symbol: {open, high, low, close, volume}}. Skips failures quietly.
    """
    result: dict[str, dict] = {}
    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i:i + CHUNK_SIZE]
        try:
            resp = requests.get(
                'https://api.tiingo.com/iex/',
                params={'tickers': ','.join(chunk)},
                headers=TIINGO_HEADERS,
                timeout=20,
            )
            resp.raise_for_status()
            for row in resp.json():
                sym = row.get('ticker', '').upper()
                close = row.get('tngoLast') or row.get('last')
                if sym and close:
                    result[sym] = {
                        'open':   row.get('open'),
                        'high':   row.get('high'),
                        'low':    row.get('low'),
                        'close':  float(close),
                        'volume': row.get('volume'),
                    }
        except Exception:
            log.warning('Tiingo IEX batch %d-%d failed', i, i + CHUNK_SIZE)
    return result


def _fetch_yfinance(symbols: list[str]) -> dict[str, tuple[float | None, float]]:
    """yfinance fallback. Returns {symbol: (open_price, close_price)}."""
    result: dict[str, tuple[float | None, float]] = {}
    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i:i + CHUNK_SIZE]
        try:
            tickers = chunk if len(chunk) > 1 else chunk * 2
            df = yf.download(tickers, period='2d', interval='1d',
                             group_by='ticker', progress=False, threads=True)
            for sym in chunk:
                try:
                    close = df[sym]['Close'].dropna()
                    open_ = df[sym]['Open'].dropna()
                    if not close.empty:
                        open_val = float(open_.iloc[-1]) if not open_.empty else None
                        result[sym] = (open_val, float(close.iloc[-1]))
                except (KeyError, IndexError, TypeError):
                    pass
        except Exception:
            log.exception('yfinance batch %d-%d failed', i, i + CHUNK_SIZE)
    return result


def _upsert_prices(
    db,
    symbol_to_asset: dict,
    prices: dict[str, dict | tuple | float],
    now: datetime,
) -> int:
    asset_ids = [symbol_to_asset[s].id for s in prices if s in symbol_to_asset]
    last_prices: dict[int, float] = {}
    for aid in asset_ids:
        last = db.execute(
            select(Price.close).where(Price.asset_id == aid).order_by(Price.timestamp.desc()).limit(1)
        ).scalar()
        if last is not None:
            last_prices[aid] = last

    rows = []
    for sym, price_data in prices.items():
        if sym not in symbol_to_asset:
            continue

        if isinstance(price_data, dict):
            open_val  = price_data.get('open')
            high_val  = price_data.get('high')
            low_val   = price_data.get('low')
            close_val = float(price_data['close'])
            vol_val   = price_data.get('volume')
        elif isinstance(price_data, tuple):
            open_val, close_val = price_data
            high_val = low_val = vol_val = None
            close_val = float(close_val)
        else:
            open_val = high_val = low_val = vol_val = None
            close_val = float(price_data)

        asset = symbol_to_asset[sym]
        if asset.id in last_prices and last_prices[asset.id] > 0:
            chg = abs((close_val - last_prices[asset.id]) / last_prices[asset.id]) * 100
            if chg > MAX_STOCK_SPIKE_PCT:
                log.warning(
                    'Stock spike rejected: %s new=%.4f prev=%.4f chg=%.1f%%',
                    sym, close_val, last_prices[asset.id], chg,
                )
                continue
        rows.append({
            'asset_id': asset.id,
            'timestamp': now,
            'interval': '1d',
            'open': open_val, 'high': high_val, 'low': low_val,
            'close': close_val,
            'volume': vol_val,
            'fetched_at': datetime.now(timezone.utc),
        })
    if not rows:
        return 0
    stmt = pg_insert(Price).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint='uq_price_asset_time_interval',
        set_={
            'close':      stmt.excluded.close,
            'open':       stmt.excluded.open,
            'high':       stmt.excluded.high,
            'low':        stmt.excluded.low,
            'volume':     stmt.excluded.volume,
            'fetched_at': stmt.excluded.fetched_at,
        },
    )
    db.execute(stmt)
    return len(rows)


@app.task(name='tasks.stocks.fetch_stock_prices', bind=True, max_retries=3)
def fetch_stock_prices(self):
    db = SessionLocal()
    try:
        assets = db.execute(
            select(Asset).where(
                Asset.asset_type == AssetType.stock,
                Asset.is_active == True,
                Asset.exchange.in_(US_EXCHANGES),
            )
        ).scalars().all()
        symbol_to_asset = {a.symbol: a for a in assets}
        symbols = list(symbol_to_asset.keys())

        if not symbols:
            return

        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        if not is_trading_day(now):
            log.debug('Stock fetch skipped — weekend')
            return

        # Primary: Tiingo IEX — real-time OHLCV, batched 100/call
        iex_prices = _fetch_tiingo_iex(symbols)

        # Fallback: yfinance for anything IEX didn't return
        missed = [s for s in symbols if s not in iex_prices]
        yf_prices: dict[str, tuple[float | None, float]] = {}
        if missed:
            yf_prices = _fetch_yfinance(missed)

        prices: dict[str, dict | tuple | float] = {**iex_prices, **yf_prices}
        count = _upsert_prices(db, symbol_to_asset, prices, now)
        db.commit()
        log.info(
            'Stocks: upserted %d/%d prices (tiingo_iex=%d, yfinance=%d)',
            count, len(symbols), len(iex_prices), len(yf_prices),
        )

    except Exception as exc:
        db.rollback()
        log.exception('Stock price fetch failed')
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
