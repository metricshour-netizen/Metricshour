"""
Crypto price ingestion via Tiingo crypto/prices endpoint.
GET /tiingo/crypto/prices without startDate returns the latest bar with full OHLCV.
Tiingo limit: 5 tickers per request, so we batch across 10 calls for 50 coins.
Runs every 1 minute, 24/7.
"""

import logging
import time
import requests
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.config import settings
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

TIINGO_HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': f'Token {settings.tiingo_api_key}',
}

# Maps our DB symbol -> Tiingo ticker (lowercase, quote currency appended)
SYMBOL_TO_TIINGO: dict[str, str] = {
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

TIINGO_TO_SYMBOL = {v: k for k, v in SYMBOL_TO_TIINGO.items()}

BATCH_SIZE = 5  # Tiingo limit: 5 tickers per request


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


@app.task(name='tasks.crypto.fetch_crypto_prices', bind=True, max_retries=3)
def fetch_crypto_prices(self):
    db = SessionLocal()
    try:
        assets = db.execute(
            select(Asset).where(Asset.asset_type == AssetType.crypto, Asset.is_active == True)
        ).scalars().all()
        symbol_to_asset = {a.symbol: a for a in assets}

        # Build list of (symbol, tiingo_ticker) pairs for assets we track
        pairs = [
            (sym, SYMBOL_TO_TIINGO[sym])
            for sym in symbol_to_asset
            if sym in SYMBOL_TO_TIINGO
        ]
        if not pairs:
            return

        now_minute = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        now_day = now_minute.replace(hour=0, minute=0)
        fetched = datetime.now(timezone.utc)

        rows_1m = []
        rows_1d = []

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

            time.sleep(0.1)

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
                    'open': stmt.excluded.open,
                    'high': stmt.excluded.high,
                    'low': stmt.excluded.low,
                    'close': stmt.excluded.close,
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
        log.warning('Crypto fetch failed (%s), retrying in %ds', exc, countdown)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()
