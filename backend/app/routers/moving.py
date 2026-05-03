"""
GET /api/stocks/{ticker}/moving  — why-is-X-moving page data
GET /api/movers                  — list active movers (sitemap)

Redis is used when available (written by Celery detect_movers task).
Falls back to live DB query so the page works before the first Celery run.
"""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.storage import get_redis

log = logging.getLogger(__name__)
router = APIRouter()

_THRESHOLD = 3.0


def _redis_moving(ticker: str) -> dict | None:
    try:
        raw = get_redis().get(f'moving:{ticker}')
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _db_moving(ticker: str, db: Session) -> dict | None:
    """Compute move data live from the prices table (same formula as _price_dict)."""
    row = db.execute(text("""
        SELECT a.symbol, a.name, p.open, p.close
        FROM assets a
        JOIN prices p ON p.asset_id = a.id
        WHERE UPPER(a.symbol) = :ticker
          AND a.asset_type = 'stock'
          AND p.interval = '1d'
          AND p.open IS NOT NULL AND p.open > 0
          AND p.close IS NOT NULL
        ORDER BY p.timestamp DESC
        LIMIT 1
    """), {'ticker': ticker}).mappings().first()

    if not row:
        return None
    pct = (row['close'] - row['open']) / row['open'] * 100
    if abs(pct) < _THRESHOLD:
        return None
    return {
        'symbol': row['symbol'],
        'name': row['name'],
        'direction': 'up' if pct > 0 else 'down',
        'pct_change': round(abs(pct), 2),
        'price_open': round(row['open'], 2),
        'price_current': round(row['close'], 2),
        'triggered_at': datetime.now(timezone.utc).isoformat(),
    }


@router.get('/api/stocks/{ticker}/moving')
def stock_moving(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.upper()

    data = _redis_moving(ticker) or _db_moving(ticker, db)
    if not data:
        raise HTTPException(status_code=404, detail='Stock is not currently moving')

    insight_row = db.execute(text("""
        SELECT summary, generated_at
        FROM page_insights
        WHERE entity_type IN ('stock_insight', 'stock')
          AND entity_code = :ticker
        ORDER BY generated_at DESC
        LIMIT 1
    """), {'ticker': ticker}).mappings().first()

    rev_rows = db.execute(text("""
        SELECT c.code, c.name, c.flag, scr.revenue_pct, scr.fiscal_year,
               ci_gdp.value AS gdp_growth,
               ci_inf.value AS inflation
        FROM stock_country_revenues scr
        JOIN assets a    ON a.id = scr.asset_id
        JOIN countries c ON c.id = scr.country_id
        LEFT JOIN country_indicators ci_gdp
            ON ci_gdp.country_id = c.id AND ci_gdp.indicator = 'gdp_growth_pct'
            AND ci_gdp.year = (SELECT MAX(year) FROM country_indicators
                               WHERE country_id = c.id AND indicator = 'gdp_growth_pct')
        LEFT JOIN country_indicators ci_inf
            ON ci_inf.country_id = c.id AND ci_inf.indicator = 'inflation_pct'
            AND ci_inf.year = (SELECT MAX(year) FROM country_indicators
                               WHERE country_id = c.id AND indicator = 'inflation_pct')
        WHERE UPPER(a.symbol) = :ticker AND a.asset_type = 'stock'
          AND scr.fiscal_year = (
              SELECT MAX(scr2.fiscal_year) FROM stock_country_revenues scr2
              WHERE scr2.asset_id = a.id
          )
        ORDER BY scr.revenue_pct DESC
        LIMIT 3
    """), {'ticker': ticker}).mappings().all()

    return {
        **data,
        'insight': {
            'summary': insight_row['summary'],
            'generated_at': insight_row['generated_at'].isoformat(),
        } if insight_row else None,
        'top_revenues': [
            {
                'code': r['code'],
                'name': r['name'],
                'flag': r['flag'],
                'revenue_pct': round(r['revenue_pct'], 1),
                'fiscal_year': r['fiscal_year'],
                'gdp_growth': round(r['gdp_growth'], 1) if r['gdp_growth'] is not None else None,
                'inflation': round(r['inflation'], 1) if r['inflation'] is not None else None,
            }
            for r in rev_rows
        ],
    }


@router.get('/api/movers')
def list_movers():
    try:
        redis = get_redis()
        members = redis.smembers('moving_tickers')
        result = []
        for sym_bytes in members:
            sym = sym_bytes.decode() if isinstance(sym_bytes, bytes) else sym_bytes
            raw = redis.get(f'moving:{sym}')
            if raw:
                d = json.loads(raw)
                result.append({'symbol': sym, 'direction': d.get('direction'), 'pct_change': d.get('pct_change')})
        return result
    except Exception:
        return []
