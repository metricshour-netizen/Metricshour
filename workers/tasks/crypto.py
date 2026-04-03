"""
<<<<<<< HEAD
Crypto price ingestion — Tiingo crypto API.
Runs every 2 minutes, 24/7.
"""

import logging
import os
=======
Crypto price ingestion — Tiingo crypto/prices endpoint.
GET /tiingo/crypto/prices without startDate returns the latest bar with full OHLCV.
Tiingo limit: 5 tickers per request, so we batch across 10 calls for 50 coins.
Runs every 1 minute, 24/7.
"""

import logging
import time
>>>>>>> 8e1707a (feat: Tiingo integration — news, crypto OHLC, IEX intraday, China A-shares)
import requests
from datetime import datetime, timezone, date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.config import settings
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

<<<<<<< HEAD
TIINGO_KEY = os.environ.get('TIINGO_API_KEY', '')
TIINGO_HEADERS = {
    'Authorization': f'Token {TIINGO_KEY}',
    'Content-Type': 'application/json',
}

# Maps our DB symbol → Tiingo ticker (symbol + "usd")
TIINGO_TICKERS: dict[str, str] = {
=======
TIINGO_HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': f'Token {settings.tiingo_api_key}',
}

# Maps our DB symbol → Tiingo ticker (lowercase, quote currency appended)
SYMBOL_TO_TIINGO: dict[str, str] = {
>>>>>>> 8e1707a (feat: Tiingo integration — news, crypto OHLC, IEX intraday, China A-shares)
    'BTC':   'btcusd',
    'ETH':   'ethusd',
    'BNB':   'bnbusd',
    'SOL':   'solusd',
    'XRP':   'xrpusd',
    'DOGE':  'dogeusd',
    'ADA':   'adausd',
    'AVAX':  'avaxusd',
    'DOT':   'dotusd',
    'LINK':  'linkusd',
    'LTC':   'ltcusd',
    'BCH':   'bchusd',
    'UNI':   'uniusd',
    'ATOM':  'atomusd',
    'XLM':   'xlmusd',
    'NEAR':  'nearusd',
    'FIL':   'filusd',
    'ICP':   'icpusd',
    'HBAR':  'hbarusd',
    'VET':   'vetusd',
    'ALGO':  'algousd',
    'XTZ':   'xtzusd',
    'EOS':   'eosusd',
    'SAND':  'sandusd',
    'MANA':  'manausd',
    'THETA': 'thetausd',
    'AXS':   'axsusd',
    'GRT':   'grtusd',
    'FTM':   'ftmusd',
    'FLOW':  'flowusd',
    'ZEC':   'zecusd',
    'DASH':  'dashusd',
    'WAVES': 'wavesusd',
    'ENJ':   'enjusd',
    'BAT':   'batusd',
    'ICX':   'icxusd',
    'QTUM':  'qtumusd',
    'ZIL':   'zilusd',
    'ONT':   'ontusd',
    'CRV':   'crvusd',
    'LDO':   'ldousd',
    'ARB':   'arbusd',
    'OP':    'opusd',
    'APT':   'aptusd',
    'INJ':   'injusd',
    'RUNE':  'runeusd',
    'KAVA':  'kavausd',
    'CHZ':   'chzusd',
    'EGLD':  'egldusd',
    'MNT':   'mntusd',
}

<<<<<<< HEAD
TICKER_TO_SYMBOL = {v: k for k, v in TIINGO_TICKERS.items()}
=======
TIINGO_TO_SYMBOL = {v: k for k, v in SYMBOL_TO_TIINGO.items()}

BATCH_SIZE = 5  # Tiingo limit: 5 tickers per request


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]
>>>>>>> 8e1707a (feat: Tiingo integration — news, crypto OHLC, IEX intraday, China A-shares)


@app.task(name='tasks.crypto.fetch_crypto_prices', bind=True, max_retries=3)
def fetch_crypto_prices(self):
    if not TIINGO_KEY:
        log.warning('TIINGO_API_KEY not set — skipping crypto fetch')
        return

    db = SessionLocal()
    try:
        assets = db.execute(
            select(Asset).where(Asset.asset_type == AssetType.crypto, Asset.is_active == True)
        ).scalars().all()
        symbol_to_asset = {a.symbol: a for a in assets}

<<<<<<< HEAD
        tiingo_tickers = [TIINGO_TICKERS[s] for s in symbol_to_asset if s in TIINGO_TICKERS]
        if not tiingo_tickers:
            return

        tickers_param = ','.join(tiingo_tickers)

        # ── Real-time top-of-book ───────────────────────────────────────────────
        resp = requests.get(
            'https://api.tiingo.com/tiingo/crypto/top',
            params={'tickers': tickers_param},
            headers=TIINGO_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        top_data = {item['ticker']: item for item in resp.json()}

        # ── Daily OHLC ─────────────────────────────────────────────────────────
        today = date.today().isoformat()
        resp_daily = requests.get(
            'https://api.tiingo.com/tiingo/crypto/prices',
            params={'tickers': tickers_param, 'startDate': today, 'resampleFreq': '1day'},
            headers=TIINGO_HEADERS,
            timeout=15,
        )
        resp_daily.raise_for_status()
        # Returns: [{ticker, baseCurrency, quoteCurrency, priceData: [{date, open, high, low, close, volume, volumeNotional}]}]
        daily_map: dict[str, dict] = {}
        for item in resp_daily.json():
            if item.get('priceData'):
                daily_map[item['ticker']] = item['priceData'][-1]  # most recent day

=======
        # Build list of (symbol, tiingo_ticker) pairs for assets we track
        pairs = [
            (sym, SYMBOL_TO_TIINGO[sym])
            for sym in symbol_to_asset
            if sym in SYMBOL_TO_TIINGO
        ]
        if not pairs:
            return

>>>>>>> 8e1707a (feat: Tiingo integration — news, crypto OHLC, IEX intraday, China A-shares)
        now_minute = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        now_day = now_minute.replace(hour=0, minute=0)
        fetched = datetime.now(timezone.utc)

        rows_1m = []
        rows_1d = []
<<<<<<< HEAD

        for tiingo_ticker, book in top_data.items():
            sym = TICKER_TO_SYMBOL.get(tiingo_ticker)
            if not sym or sym not in symbol_to_asset:
                continue

            book_data = book.get('topOfBookData', [{}])[0]
            close = book_data.get('lastPrice')
            if close is None:
                continue

            rows_1m.append({
                'asset_id': symbol_to_asset[sym].id,
                'timestamp': now_minute,
                'interval': '1m',
                'open': None, 'high': None, 'low': None,
                'close': close,
                'volume': book_data.get('lastSizeNotional'),  # USD-denominated volume
                'fetched_at': fetched,
            })
=======

        for batch in _chunks(pairs, BATCH_SIZE):
            tiingo_tickers = [t for _, t in batch]
            resp = requests.get(
                'https://api.tiingo.com/tiingo/crypto/prices',
                params={'tickers': ','.join(tiingo_tickers)},
                headers=TIINGO_HEADERS,
                timeout=15,
            )
            resp.raise_for_status()

            for item in resp.json():
                tiingo_ticker = item.get('ticker', '').lower()
                sym = TIINGO_TO_SYMBOL.get(tiingo_ticker)
                if not sym or sym not in symbol_to_asset:
                    continue

                price_data = item.get('priceData', [])
                if not price_data:
                    continue
                latest = price_data[0]

                close = latest.get('close')
                if close is None:
                    continue

                asset_id = symbol_to_asset[sym].id
                rows_1m.append({
                    'asset_id': asset_id,
                    'timestamp': now_minute,
                    'interval': '1m',
                    'open': None, 'high': None, 'low': None,
                    'close': close,
                    'volume': latest.get('volumeNotional'),
                    'fetched_at': fetched,
                })
                rows_1d.append({
                    'asset_id': asset_id,
                    'timestamp': now_day,
                    'interval': '1d',
                    'open': latest.get('open'),
                    'high': latest.get('high'),
                    'low': latest.get('low'),
                    'close': close,
                    'volume': latest.get('volumeNotional'),
                    'fetched_at': fetched,
                })

            # Small delay between batches to avoid hammering the API
            time.sleep(0.1)
>>>>>>> 8e1707a (feat: Tiingo integration — news, crypto OHLC, IEX intraday, China A-shares)

            # Daily OHLC — use Tiingo daily data if available, else reconstruct
            daily = daily_map.get(tiingo_ticker)
            if daily:
                rows_1d.append({
                    'asset_id': symbol_to_asset[sym].id,
                    'timestamp': now_day,
                    'interval': '1d',
                    'open': daily.get('open'),
                    'high': daily.get('high'),
                    'low': daily.get('low'),
                    'close': daily.get('close') or close,
                    'volume': daily.get('volumeNotional'),
                    'fetched_at': fetched,
                })
            else:
                rows_1d.append({
                    'asset_id': symbol_to_asset[sym].id,
                    'timestamp': now_day,
                    'interval': '1d',
                    'open': None, 'high': None, 'low': None,
                    'close': close,
                    'volume': None,
                    'fetched_at': fetched,
                })

        if rows_1m:
            stmt = pg_insert(Price).values(rows_1m)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_price_asset_time_interval',
                set_={'close': stmt.excluded.close, 'volume': stmt.excluded.volume, 'fetched_at': stmt.excluded.fetched_at},
            )
            db.execute(stmt)

        if rows_1d:
            stmt = pg_insert(Price).values(rows_1d)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_price_asset_time_interval',
                set_={
<<<<<<< HEAD
                    'close': stmt.excluded.close,
                    'open': stmt.excluded.open,
                    'high': stmt.excluded.high,
                    'low': stmt.excluded.low,
=======
                    'open': stmt.excluded.open,
                    'high': stmt.excluded.high,
                    'low': stmt.excluded.low,
                    'close': stmt.excluded.close,
>>>>>>> 8e1707a (feat: Tiingo integration — news, crypto OHLC, IEX intraday, China A-shares)
                    'volume': stmt.excluded.volume,
                    'fetched_at': stmt.excluded.fetched_at,
                },
            )
            db.execute(stmt)

        db.commit()
        log.info('Crypto (Tiingo): upserted %d 1m + %d 1d prices', len(rows_1m), len(rows_1d))

    except Exception as exc:
        db.rollback()
        countdown = 120 if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None and exc.response.status_code == 429 else 30
<<<<<<< HEAD
        log.warning('Crypto price fetch failed (%s), retrying in %ds', exc, countdown)
=======
        log.warning('Crypto fetch failed (%s), retrying in %ds', exc, countdown)
>>>>>>> 8e1707a (feat: Tiingo integration — news, crypto OHLC, IEX intraday, China A-shares)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()
