"""
China A-share price ingestion — Tiingo daily endpoint.
Runs daily at 09:00 UTC (SHG/SHE close at ~07:00 UTC).
Limited to 300 stocks to keep API calls manageable.
"""

import logging
import time
import requests
from datetime import datetime, timezone, date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.config import settings
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

TIINGO_HEADERS = {
    'Authorization': f'Token {settings.tiingo_api_key}',
    'Content-Type': 'application/json',
}
CHINA_EXCHANGES = {'SHE', 'SHG'}
RATE_LIMIT_DELAY = 0.1  # 100ms between calls → ~10 calls/sec → 300 stocks in ~30s


@app.task(name='tasks.china_stocks.fetch_china_prices', bind=True, max_retries=3)
def fetch_china_prices(self):
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
        today = date.today().isoformat()
        start = (date.today() - timedelta(days=5)).isoformat()
        fetched = datetime.now(timezone.utc)
        rows = []
        errors = 0

        for ticker, asset in symbol_to_asset.items():
            try:
                resp = requests.get(
                    f'https://api.tiingo.com/tiingo/daily/{ticker}/prices',
                    params={'startDate': start, 'endDate': today},
                    headers=TIINGO_HEADERS,
                    timeout=8,
                )
                if resp.status_code in (404, 400):
                    continue
                resp.raise_for_status()
                price_data = resp.json()
                if not price_data:
                    continue

                latest = price_data[-1]
                ts_raw = latest.get('date', '')
                ts = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
                day_ts = ts.replace(hour=0, minute=0, second=0, microsecond=0)

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
                errors += 1
                log.debug('China stock %s error: %s', ticker, e)
            finally:
                time.sleep(RATE_LIMIT_DELAY)

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
            log.info('China A-shares: upserted %d prices (%d errors) for %d stocks', len(rows), errors, len(assets))

    except Exception as exc:
        db.rollback()
        log.warning('China stock fetch failed: %s', exc)
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
