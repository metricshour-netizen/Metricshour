"""
Crypto price ingestion — CoinGecko free API (no key required).
Runs every 1 minute, 24/7.
"""

import logging
import requests
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

# Maps our DB symbol → CoinGecko ID
COINGECKO_IDS: dict[str, str] = {
    'BTC':  'bitcoin',
    'ETH':  'ethereum',
    'BNB':  'binancecoin',
    'SOL':  'solana',
    'XRP':  'ripple',
    'DOGE': 'dogecoin',
    'ADA':  'cardano',
    'AVAX': 'avalanche-2',
    'DOT':  'polkadot',
    'LINK': 'chainlink',
}

ID_TO_SYMBOL = {v: k for k, v in COINGECKO_IDS.items()}


@app.task(name='tasks.crypto.fetch_crypto_prices', bind=True, max_retries=3)
def fetch_crypto_prices(self):
    db = SessionLocal()
    try:
        assets = (
            db.query(Asset)
            .filter(Asset.asset_type == AssetType.crypto, Asset.is_active == True)
            .all()
        )
        symbol_to_asset = {a.symbol: a for a in assets}

        ids = [COINGECKO_IDS[s] for s in symbol_to_asset if s in COINGECKO_IDS]
        if not ids:
            return

        resp = requests.get(
            'https://api.coingecko.com/api/v3/simple/price',
            params={
                'ids': ','.join(ids),
                'vs_currencies': 'usd',
                'include_24hr_vol': 'true',
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        rows = []
        for cg_id, vals in data.items():
            sym = ID_TO_SYMBOL.get(cg_id)
            if not sym or sym not in symbol_to_asset:
                continue
            rows.append({
                'asset_id': symbol_to_asset[sym].id,
                'timestamp': now,
                'interval': '1m',
                'open': None,
                'high': None,
                'low': None,
                'close': vals['usd'],
                'volume': vals.get('usd_24h_vol'),
            })

        if rows:
            stmt = pg_insert(Price).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_price_asset_time_interval',
                set_={'close': stmt.excluded.close, 'volume': stmt.excluded.volume},
            )
            db.execute(stmt)
            db.commit()
            log.info(f'Crypto: upserted {len(rows)} prices')

    except Exception as exc:
        db.rollback()
        log.exception('Crypto price fetch failed')
        raise self.retry(exc=exc, countdown=10)
    finally:
        db.close()
