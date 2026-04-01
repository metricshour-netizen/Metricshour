"""
Stock price ingestion — Marketstack (primary, EOD) + yfinance fallback.
Runs every 15 minutes but Marketstack is called at most ONCE per trading day
via a Redis cache key. yfinance handles intraday updates.
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
CHUNK_SIZE = 100  # Marketstack accepts up to 100 symbols per call

# Set to True if Marketstack key is confirmed invalid — skips all calls silently
_marketstack_disabled = False

# Redis cache key: set after a successful EOD fetch so we call Marketstack
# exactly once per trading day instead of on every 15-min task run.
_MS_CACHE_KEY_PREFIX = 'marketstack:eod:fetched:'
_MS_CACHE_TTL = 6 * 3600  # 6h — expires well before next day's window


def _ms_cache_key(date_str: str) -> str:
    return f'{_MS_CACHE_KEY_PREFIX}{date_str}'


def _already_fetched_today(date_str: str) -> bool:
    """Returns True if we already have a successful Marketstack EOD fetch for today."""
    try:
        from app.storage import get_redis
        r = get_redis()
        return r.exists(_ms_cache_key(date_str)) == 1
    except Exception:
        return False  # Redis unavailable — allow the fetch


def _mark_fetched_today(date_str: str) -> None:
    try:
        from app.storage import get_redis
        r = get_redis()
        r.setex(_ms_cache_key(date_str), _MS_CACHE_TTL, '1')
    except Exception:
        pass


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
        data = resp.json()
        if resp.status_code == 401 or data.get('error', {}).get('code') == 'invalid_access_key':
            log.warning('Marketstack API key invalid — falling back to yfinance for all symbols')
            _marketstack_disabled = True
            return False
    except Exception:
        pass
    return True


def _fetch_marketstack(symbols: list[str]) -> dict[str, dict]:
    """
    Fetch latest EOD OHLCV for a batch of symbols via Marketstack.
    Returns {symbol: {open, high, low, close, volume}}. Skips failures quietly.
    Batches in chunks of CHUNK_SIZE to stay within per-request limits.
    """
    if _marketstack_disabled or not MARKETSTACK_KEY:
        return {}

    result: dict[str, dict] = {}
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
                close = row.get('adj_close') or row.get('close')
                if sym and close:
                    result[sym] = {
                        'open':   row.get('adj_open') or row.get('open'),
                        'high':   row.get('adj_high') or row.get('high'),
                        'low':    row.get('adj_low') or row.get('low'),
                        'close':  float(close),
                        'volume': row.get('adj_volume') or row.get('volume'),
                    }
        except Exception:
            log.warning('Marketstack batch %d-%d failed', i, i + CHUNK_SIZE)

    return result


def _fetch_yfinance(symbols: list[str]) -> dict[str, tuple[float | None, float]]:
    """yfinance fallback. Returns {symbol: (open_price, close_price)}."""
    result: dict[str, tuple[float | None, float]] = {}
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
                    open_ = df[sym]['Open'].dropna()
                    if not close.empty:
                        open_val = float(open_.iloc[-1]) if not open_.empty else None
                        result[sym] = (open_val, float(close.iloc[-1]))
                except (KeyError, IndexError, TypeError):
                    pass
        except Exception:
            log.exception(f'yfinance batch {i}-{i+CHUNK_SIZE} failed')
    return result


def _upsert_prices(
    db,
    symbol_to_asset: dict,
    prices: dict[str, dict | tuple | float],
    now: datetime,
) -> int:
    """
    Upsert daily prices.
    Accepts three price formats:
      - dict: {open, high, low, close, volume}   (Marketstack full OHLCV)
      - tuple: (open, close)                      (yfinance)
      - float: close only                         (legacy)
    Timestamp must already be day-truncated by the caller.
    On conflict, updates all OHLCV fields so Marketstack data enriches yfinance rows.
    """
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
        })
    if not rows:
        return 0
    stmt = pg_insert(Price).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint='uq_price_asset_time_interval',
        set_={
            'close':  stmt.excluded.close,
            'open':   stmt.excluded.open,
            'high':   stmt.excluded.high,
            'low':    stmt.excluded.low,
            'volume': stmt.excluded.volume,
        },
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

        # Truncate to day-start so every run upserts the same daily row
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_str = now.strftime('%Y-%m-%d')

        # Skip entirely on weekends — no exchange has settled EOD data
        if not is_trading_day(now):
            log.debug('Stock fetch skipped — weekend')
            return

        # Probe Marketstack key on first run — disables globally if invalid
        if not _marketstack_disabled and MARKETSTACK_KEY:
            _check_marketstack_key()

        # Primary: Marketstack EOD — called once per trading day (after US close 21:00 UTC).
        # A Redis cache key prevents redundant calls on the 12 subsequent 15-min task runs.
        ms_prices: dict[str, dict] = {}
        if should_call_marketstack_eod(now) and not _already_fetched_today(today_str):
            ms_prices = _fetch_marketstack(symbols)
            if ms_prices:
                _mark_fetched_today(today_str)
                log.info('Marketstack EOD: fetched %d/%d symbols, cached for today', len(ms_prices), len(symbols))

        # Fallback / intraday: yfinance covers anything Marketstack missed and
        # keeps prices updating throughout the trading day.
        missed = [s for s in symbols if s not in ms_prices]
        yf_prices: dict[str, tuple[float | None, float]] = {}
        if missed:
            yf_prices = _fetch_yfinance(missed)

        prices: dict[str, dict | tuple | float] = {**ms_prices, **yf_prices}
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
