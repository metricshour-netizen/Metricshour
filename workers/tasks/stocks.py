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

# yfinance logs internal per-ticker errors at ERROR level before our except blocks run.
# We handle missing tickers ourselves, so suppress yfinance's own noisy output.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price
from tasks.market_hours import is_trading_day, should_call_marketstack_eod

log = logging.getLogger(__name__)

MARKETSTACK_KEY = os.environ.get('MARKETSTACK_API_KEY', '')

# Reject any single-period price change > this threshold (bad yfinance/Marketstack ticks)
MAX_STOCK_SPIKE_PCT = 15.0
MARKETSTACK_URL = 'http://api.marketstack.com/v1'
CHUNK_SIZE = 50   # marketstack accepts up to 100 symbols per call; 50 is safe

# Set to True if Marketstack key is confirmed invalid — skips all calls silently
_marketstack_disabled = False


def _check_marketstack_key() -> bool:
    """Probe Marketstack with a single symbol. Disables globally on 401/invalid_access_key."""
    global _marketstack_disabled
    if not MARKETSTACK_KEY:
        _marketstack_disabled = True
        return False
    try:
        resp = requests.get(
            f'{MARKETSTACK_URL}/eod/latest',
            params={'access_key': MARKETSTACK_KEY, 'symbols': 'AAPL', 'limit': 1},
            timeout=10,
        )
        if resp.status_code == 401 or resp.json().get('error', {}).get('code') == 'invalid_access_key':
            log.warning('Marketstack API key invalid — falling back to yfinance for all symbols')
            _marketstack_disabled = True
            return False
    except Exception:
        pass
    return True


def _fetch_marketstack(symbols: list[str]) -> dict[str, float]:
    """
    Fetch latest EOD close prices for a batch of symbols via Marketstack.
    Returns {symbol: close_price}. Skips symbols that fail quietly.
    """
    if _marketstack_disabled or not MARKETSTACK_KEY:
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
            log.warning(f'Marketstack batch {i}-{i+CHUNK_SIZE} failed')

    return result


def _fetch_yfinance(symbols: list[str]) -> dict[str, float]:
    """yfinance fallback for symbols Marketstack doesn't cover."""
    result: dict[str, float] = {}
    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i:i + CHUNK_SIZE]
        try:
            # Force multi-ticker path so df[sym] always returns a clean sub-DataFrame
            tickers = chunk if len(chunk) > 1 else chunk * 2
            df = yf.download(tickers, period='2d', interval='1d',
                             group_by='ticker', progress=False, threads=True)
            for sym in chunk:
                try:
                    close = df[sym]['Close'].dropna()
                    if not close.empty:
                        result[sym] = float(close.iloc[-1])
                except (KeyError, IndexError, TypeError):
                    pass
        except Exception:
            log.exception(f'yfinance batch {i}-{i+CHUNK_SIZE} failed')
    return result


def _upsert_prices(db, symbol_to_asset: dict, prices: dict[str, float], now: datetime) -> int:
    # Fetch last known price per asset for spike guard
    asset_ids = [symbol_to_asset[s].id for s in prices if s in symbol_to_asset]
    last_prices: dict[int, float] = {}
    for aid in asset_ids:
        last = db.execute(
            select(Price.close).where(Price.asset_id == aid).order_by(Price.timestamp.desc()).limit(1)
        ).scalar()
        if last is not None:
            last_prices[aid] = last

    rows = []
    for sym, price in prices.items():
        if sym not in symbol_to_asset:
            continue
        asset = symbol_to_asset[sym]
        if asset.id in last_prices and last_prices[asset.id] > 0:
            chg = abs((price - last_prices[asset.id]) / last_prices[asset.id]) * 100
            if chg > MAX_STOCK_SPIKE_PCT:
                log.warning(
                    'Stock spike rejected: %s new=%.4f prev=%.4f chg=%.1f%%',
                    sym, price, last_prices[asset.id], chg,
                )
                continue
        rows.append({
            'asset_id': asset.id,
            'timestamp': now,
            'interval': '1d',
            'open': None, 'high': None, 'low': None,
            'close': price,
            'volume': None,
        })
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
        assets = db.execute(
            select(Asset).where(Asset.asset_type == AssetType.stock, Asset.is_active == True)
        ).scalars().all()
        symbol_to_asset = {a.symbol: a for a in assets}
        symbols = list(symbol_to_asset.keys())

        if not symbols:
            return

        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        # Skip entirely on weekends — no exchange has settled EOD data
        if not is_trading_day(now):
            log.debug('Stock fetch skipped — weekend')
            return

        # Probe Marketstack key on first run — disables globally if invalid
        if not _marketstack_disabled and MARKETSTACK_KEY:
            _check_marketstack_key()

        # Primary: Marketstack — only call after US close (21:00 UTC) when EOD
        # data is fresh. During market hours /eod/latest returns yesterday's close,
        # so calling it every 15 min is pure waste.
        ms_prices: dict[str, float] = {}
        if should_call_marketstack_eod(now):
            ms_prices = _fetch_marketstack(symbols)

        # Fallback / intraday: yfinance covers anything Marketstack missed and
        # keeps prices updating throughout the trading day.
        missed = [s for s in symbols if s not in ms_prices]
        yf_prices: dict[str, float] = {}
        if missed:
            yf_prices = _fetch_yfinance(missed)

        prices = {**ms_prices, **yf_prices}
        count = _upsert_prices(db, symbol_to_asset, prices, now)
        db.commit()
        log.info(
            'Stocks: upserted %d/%d prices (marketstack=%d, yfinance=%d)',
            count, len(symbols), len(ms_prices), len(yf_prices),
        )

    except Exception as exc:
        db.rollback()
        log.exception('Stock price fetch failed')
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
