"""
Why is X moving — endpoint for stocks with significant intraday price moves.

GET /api/stocks/{ticker}/moving
  Returns move data + intelligence insights + top revenue countries.
  Returns 404 if the stock is not currently moving (>3% from open).

GET /api/movers
  Returns list of currently-moving ticker symbols (for sitemap).
"""
import json
import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends

from app.database import get_db
from app.storage import get_redis

log = logging.getLogger(__name__)
router = APIRouter()


def _get_moving_data(ticker: str) -> dict | None:
    redis = get_redis()
    raw = redis.get(f'moving:{ticker.upper()}')
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


@router.get('/api/stocks/{ticker}/moving')
def stock_moving(ticker: str, db: Session = Depends(get_db)):
    """Return move data + context for a currently-moving stock. 404 if not moving."""
    ticker = ticker.upper()
    data = _get_moving_data(ticker)
    if not data:
        raise HTTPException(status_code=404, detail='Stock is not currently moving')

    # Pull latest AI insight for this stock
    insight_row = db.execute(text("""
        SELECT summary, generated_at
        FROM page_insights
        WHERE entity_type IN ('stock_insight', 'stock')
          AND entity_code = :ticker
        ORDER BY generated_at DESC
        LIMIT 1
    """), {'ticker': ticker}).mappings().first()

    # Pull top 3 revenue countries with basic macro context
    rev_rows = db.execute(text("""
        SELECT
            c.code, c.name, c.flag,
            scr.revenue_pct, scr.fiscal_year,
            ci_gdp.value    AS gdp_growth,
            ci_inf.value    AS inflation
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
            'summary': insight_row['summary'] if insight_row else None,
            'generated_at': insight_row['generated_at'].isoformat() if insight_row else None,
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
    """Return all currently-moving stock tickers (used by sitemap)."""
    redis = get_redis()
    members = redis.smembers('moving_tickers')
    result = []
    for sym_bytes in members:
        sym = sym_bytes.decode() if isinstance(sym_bytes, bytes) else sym_bytes
        raw = redis.get(f'moving:{sym}')
        if raw:
            try:
                d = json.loads(raw)
                result.append({'symbol': sym, 'direction': d.get('direction'), 'pct_change': d.get('pct_change')})
            except Exception:
                pass
    return result
