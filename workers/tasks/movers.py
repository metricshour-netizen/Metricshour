"""
Detect stocks with intraday price moves > 3% and write to Redis.

Key: moving:{SYMBOL}   Value: {symbol, name, direction, pct_change, price_open, price_current, triggered_at}
TTL: 48 hours (auto-expires even if stock never reverts)

Also maintains a Redis SET "moving_tickers" so the sitemap can enumerate active movers.
Runs every 15 minutes during US market hours.
"""
import logging
from datetime import datetime, timezone

from celery_app import app
from app.database import SessionLocal
from app.storage import get_redis

log = logging.getLogger(__name__)

_THRESHOLD = 3.0  # percent
_TTL = 172_800    # 48 hours


@app.task(name='tasks.movers.detect_movers', ignore_result=True)
def detect_movers():
    from sqlalchemy import text as sa_text

    db = SessionLocal()
    redis = get_redis()
    try:
        rows = db.execute(sa_text("""
            SELECT DISTINCT ON (a.symbol)
                a.symbol,
                a.name,
                p.open   AS price_open,
                p.close  AS price_close
            FROM assets a
            JOIN prices p ON p.asset_id = a.id
            WHERE a.asset_type = 'stock'
              AND a.is_active = true
              AND p.interval = '1d'
              AND p.open IS NOT NULL
              AND p.open > 0
              AND p.close IS NOT NULL
            ORDER BY a.symbol, p.timestamp DESC
        """)).mappings().all()

        for r in rows:
            sym = r['symbol']
            pct = (r['price_close'] - r['price_open']) / r['price_open'] * 100

            if abs(pct) >= _THRESHOLD:
                payload = {
                    'symbol': sym,
                    'name': r['name'],
                    'direction': 'up' if pct > 0 else 'down',
                    'pct_change': round(abs(pct), 2),
                    'price_open': round(r['price_open'], 2),
                    'price_current': round(r['price_close'], 2),
                    'triggered_at': datetime.now(timezone.utc).isoformat(),
                }
                redis.setex(f'moving:{sym}', _TTL, __import__('json').dumps(payload))
                redis.sadd('moving_tickers', sym)
                redis.expire('moving_tickers', _TTL)
            else:
                # Reverted within 3% — remove
                redis.delete(f'moving:{sym}')
                redis.srem('moving_tickers', sym)

        log.info('detect_movers: scanned %d stocks', len(rows))
    except Exception as exc:
        log.error('detect_movers failed: %s', exc)
    finally:
        db.close()
