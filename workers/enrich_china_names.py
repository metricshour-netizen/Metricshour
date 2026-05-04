"""
One-time script to backfill proper English company names for China A-shares.

The original import stored the ticker code as the name (e.g. "600000" instead of
"Shanghai Pudong Development Bank"). This script fetches the real name from the
Tiingo metadata endpoint and updates the DB.

Run from workers/ with the venv active:
    python3 enrich_china_names.py

Safe to re-run — skips assets whose name no longer looks like a raw ticker code.
"""
import logging
import re
import sys
import time

import requests
from sqlalchemy import select, update

sys.path.insert(0, '/root/metricshour/backend')

from app.config import settings
from app.database import SessionLocal
from app.models.asset import Asset, AssetType

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

HEADERS = {
    'Authorization': f'Token {settings.tiingo_api_key}',
    'Content-Type': 'application/json',
}
_TICKER_CODE_RE = re.compile(r'^\d{5,6}(\.SH|\.SZ|\.SS)?$')
_RATE_DELAY = 0.15  # 150ms between Tiingo calls


def _looks_like_code(name: str) -> bool:
    return bool(_TICKER_CODE_RE.match(name.strip()))


def _tiingo_name(symbol: str) -> str | None:
    """Fetch the company name from Tiingo's daily metadata endpoint."""
    url = f'https://api.tiingo.com/tiingo/daily/{symbol}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get('name') or None
        if r.status_code == 404:
            return None
        log.warning('Tiingo %s → HTTP %d', symbol, r.status_code)
        return None
    except Exception as e:
        log.warning('Tiingo %s error: %s', symbol, e)
        return None


def main():
    db = SessionLocal()
    try:
        # Find all China A-shares where the name still looks like a raw ticker code
        assets = db.execute(
            select(Asset).where(
                Asset.asset_type == AssetType.stock,
                Asset.exchange.in_(['SHG', 'SHE', 'SSE']),
                Asset.is_active == True,
            )
        ).scalars().all()

        to_update = [a for a in assets if _looks_like_code(a.name)]
        log.info('%d China A-shares need name enrichment', len(to_update))

        updated = 0
        failed = 0
        for asset in to_update:
            time.sleep(_RATE_DELAY)
            name = _tiingo_name(asset.symbol)
            if name and not _looks_like_code(name):
                db.execute(
                    update(Asset).where(Asset.id == asset.id).values(name=name)
                )
                log.info('✓ %s → %s', asset.symbol, name)
                updated += 1
            else:
                # Tiingo doesn't have a better name — keep as-is but log it
                log.warning('✗ %s no name from Tiingo (raw: %r)', asset.symbol, name)
                failed += 1

            if updated % 50 == 0 and updated > 0:
                db.commit()
                log.info('Committed %d updates so far', updated)

        db.commit()
        log.info('Done — %d updated, %d skipped/no-name', updated, failed)

    finally:
        db.close()


if __name__ == '__main__':
    main()
