"""
IEX intraday real-time quotes — Tiingo IEX endpoint.
Runs every 1 minute during US market hours only.
Stores tngoLast as 1m close price for all active US stocks.
"""

import logging
import os
import requests
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price
from tasks.market_hours import is_us_market_open

log = logging.getLogger(__name__)

TIINGO_KEY = os.environ.get('TIINGO_API_KEY', '')
TIINGO_HEADERS = {
    'Authorization': f'Token {TIINGO_KEY}',
    'Content-Type': 'application/json',
}
CHUNK_SIZE = 100  # IEX accepts up to 100 tickers per request
US_EXCHANGES = {'NASDAQ', 'NYSE', 'NYSE ARCA', 'NYSE MKT', 'AMEX', 'BATS'}


@app.task(name='tasks.iex_intraday.fetch_intraday_quotes', bind=True, max_retries=2)
def fetch_intraday_quotes(self):
    if not TIINGO_KEY:
        return
    if not is_us_market_open():
        return

    db = SessionLocal()
    try:
        assets = db.execute(
            select(Asset).where(
                Asset.asset_type == AssetType.stock,
                Asset.is_active == True,
                Asset.currency == 'USD',
            )
        ).scalars().all()

        # Only US-listed stocks
        us_assets = [a for a in assets if a.exchange in US_EXCHANGES]
        if not us_assets:
            return

        symbol_to_asset = {a.symbol: a for a in us_assets}
        symbols = list(symbol_to_asset.keys())

        now_minute = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        fetched = datetime.now(timezone.utc)
        rows = []

        for i in range(0, len(symbols), CHUNK_SIZE):
            chunk = symbols[i:i + CHUNK_SIZE]
            try:
                resp = requests.get(
                    'https://api.tiingo.com/iex/',
                    params={'tickers': ','.join(chunk)},
                    headers=TIINGO_HEADERS,
                    timeout=15,
                )
                resp.raise_for_status()
                for item in resp.json():
                    ticker = item.get('ticker', '').upper()
                    last = item.get('tngoLast')
                    if not ticker or last is None:
                        continue
                    asset = symbol_to_asset.get(ticker)
                    if not asset:
                        continue
                    rows.append({
                        'asset_id': asset.id,
                        'timestamp': now_minute,
                        'interval': '1m',
                        'open': item.get('open'),
                        'high': item.get('high'),
                        'low': item.get('low'),
                        'close': last,
                        'volume': item.get('volume'),
                        'fetched_at': fetched,
                    })
            except Exception as e:
                log.warning('IEX chunk %d-%d failed: %s', i, i + CHUNK_SIZE, e)

        if rows:
            stmt = pg_insert(Price).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_price_asset_time_interval',
                set_={
                    'close': stmt.excluded.close,
                    'open': stmt.excluded.open,
                    'high': stmt.excluded.high,
                    'low': stmt.excluded.low,
                    'volume': stmt.excluded.volume,
                    'fetched_at': stmt.excluded.fetched_at,
                },
            )
            db.execute(stmt)
            db.commit()
            log.info('IEX intraday: upserted %d 1m prices', len(rows))

    except Exception as exc:
        db.rollback()
        log.warning('IEX intraday fetch failed: %s', exc)
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
