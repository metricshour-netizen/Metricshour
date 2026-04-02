"""
China A-share price ingestion — Tiingo daily endpoint.
Runs daily at 09:00 UTC (SHG/SHE close at ~07:00 UTC).
Fetches EOD prices for all active SHE/SHG stocks.
"""

import logging
import os
import requests
from datetime import datetime, timezone, date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

TIINGO_KEY = os.environ.get('TIINGO_API_KEY', '')
TIINGO_HEADERS = {
    'Authorization': f'Token {TIINGO_KEY}',
    'Content-Type': 'application/json',
}
CHINA_EXCHANGES = {'SHE', 'SHG'}
CHUNK_SIZE = 50  # fetch 50 tickers at a time


@app.task(name='tasks.china_stocks.fetch_china_prices', bind=True, max_retries=3)
def fetch_china_prices(self):
    if not TIINGO_KEY:
        return

    db = SessionLocal()
    try:
        assets = db.execute(
            select(Asset).where(
                Asset.asset_type == AssetType.stock,
                Asset.is_active == True,
                Asset.exchange.in_(CHINA_EXCHANGES),
            )
        ).scalars().all()

        if not assets:
            log.info('No Chinese A-share assets found in DB')
            return

        symbol_to_asset = {a.symbol: a for a in assets}
        symbols = list(symbol_to_asset.keys())

        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=3)).isoformat()  # 3-day window to catch Mon after weekend
        fetched = datetime.now(timezone.utc)
        rows = []

        for i in range(0, len(symbols), CHUNK_SIZE):
            chunk = symbols[i:i + CHUNK_SIZE]
            for ticker in chunk:
                try:
                    resp = requests.get(
                        f'https://api.tiingo.com/tiingo/daily/{ticker}/prices',
                        params={'startDate': yesterday, 'endDate': today},
                        headers=TIINGO_HEADERS,
                        timeout=10,
                    )
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    price_data = resp.json()
                    if not price_data:
                        continue

                    latest = price_data[-1]
                    ts = datetime.fromisoformat(latest['date'].replace('Z', '+00:00'))
                    day_ts = ts.replace(hour=0, minute=0, second=0, microsecond=0)
                    asset = symbol_to_asset.get(ticker)
                    if not asset:
                        continue

                    rows.append({
                        'asset_id': asset.id,
                        'timestamp': day_ts,
                        'interval': '1d',
                        'open': latest.get('adjOpen') or latest.get('open'),
                        'high': latest.get('adjHigh') or latest.get('high'),
                        'low': latest.get('adjLow') or latest.get('low'),
                        'close': latest.get('adjClose') or latest.get('close'),
                        'volume': latest.get('volume'),
                        'fetched_at': fetched,
                    })
                except Exception as e:
                    log.debug('China stock %s price fetch error: %s', ticker, e)

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
            log.info('China A-shares: upserted %d 1d prices for %d stocks', len(rows), len(assets))

    except Exception as exc:
        db.rollback()
        log.warning('China stock fetch failed: %s', exc)
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
