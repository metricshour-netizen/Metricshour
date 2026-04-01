"""
Crypto price ingestion — CoinGecko free API (no key required).
Runs every 1 minute, 24/7.
"""

import logging
import requests
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

# Maps our DB symbol → CoinGecko ID
COINGECKO_IDS: dict[str, str] = {
    'BTC':   'bitcoin',
    'ETH':   'ethereum',
    'BNB':   'binancecoin',
    'SOL':   'solana',
    'XRP':   'ripple',
    'DOGE':  'dogecoin',
    'ADA':   'cardano',
    'AVAX':  'avalanche-2',
    'DOT':   'polkadot',
    'LINK':  'chainlink',
    'LTC':   'litecoin',
    'BCH':   'bitcoin-cash',
    'UNI':   'uniswap',
    'ATOM':  'cosmos',
    'XLM':   'stellar',
    'NEAR':  'near',
    'FIL':   'filecoin',
    'ICP':   'internet-computer',
    'HBAR':  'hedera-hashgraph',
    'VET':   'vechain',
    'ALGO':  'algorand',
    'XTZ':   'tezos',
    'EOS':   'eos',
    'SAND':  'the-sandbox',
    'MANA':  'decentraland',
    'THETA': 'theta-token',
    'AXS':   'axie-infinity',
    'GRT':   'the-graph',
    'FTM':   'fantom',
    'FLOW':  'flow',
    'ZEC':   'zcash',
    'DASH':  'dash',
    'WAVES': 'waves',
    'ENJ':   'enjincoin',
    'BAT':   'basic-attention-token',
    'ICX':   'icon',
    'QTUM':  'qtum',
    'ZIL':   'zilliqa',
    'ONT':   'ontology',
    'CRV':   'curve-dao-token',
    'LDO':   'lido-dao',
    'ARB':   'arbitrum',
    'OP':    'optimism',
    'APT':   'aptos',
    'INJ':   'injective-protocol',
    'RUNE':  'thorchain',
    'KAVA':  'kava',
    'CHZ':   'chiliz',
    'EGLD':  'elrond-erd-2',
    'MNT':   'mantle',
}

ID_TO_SYMBOL = {v: k for k, v in COINGECKO_IDS.items()}


@app.task(name='tasks.crypto.fetch_crypto_prices', bind=True, max_retries=3)
def fetch_crypto_prices(self):
    db = SessionLocal()
    try:
        assets = db.execute(
            select(Asset).where(Asset.asset_type == AssetType.crypto, Asset.is_active == True)
        ).scalars().all()
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
                'include_24hr_change': 'true',
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        now_minute = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        now_day = now_minute.replace(hour=0, minute=0)

        rows_1m = []
        rows_1d = []
        for cg_id, vals in data.items():
            sym = ID_TO_SYMBOL.get(cg_id)
            if not sym or sym not in symbol_to_asset:
                continue
            close = vals['usd']
            change_pct = vals.get('usd_24h_change')
            # Reconstruct 24h-ago price as a proxy for today's open
            open_val = close / (1 + change_pct / 100) if change_pct is not None else None

            rows_1m.append({
                'asset_id': symbol_to_asset[sym].id,
                'timestamp': now_minute,
                'interval': '1m',
                'open': None, 'high': None, 'low': None,
                'close': close,
                'volume': vals.get('usd_24h_vol'),
            })
            rows_1d.append({
                'asset_id': symbol_to_asset[sym].id,
                'timestamp': now_day,
                'interval': '1d',
                'open': open_val, 'high': None, 'low': None,
                'close': close,
                'volume': vals.get('usd_24h_vol'),
            })

        if rows_1m:
            stmt = pg_insert(Price).values(rows_1m)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_price_asset_time_interval',
                set_={'close': stmt.excluded.close, 'volume': stmt.excluded.volume},
            )
            db.execute(stmt)

        if rows_1d:
            stmt = pg_insert(Price).values(rows_1d)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_price_asset_time_interval',
                set_={'close': stmt.excluded.close, 'volume': stmt.excluded.volume, 'open': stmt.excluded.open},
            )
            db.execute(stmt)

        db.commit()
        log.info(f'Crypto: upserted {len(rows_1m)} 1m + {len(rows_1d)} 1d prices')

    except Exception as exc:
        db.rollback()
        # Back off longer on rate limit errors
        import requests as req_mod
        countdown = 120 if isinstance(exc, req_mod.exceptions.HTTPError) and exc.response is not None and exc.response.status_code == 429 else 30
        log.warning('Crypto price fetch failed (%s), retrying in %ds', exc, countdown)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()
