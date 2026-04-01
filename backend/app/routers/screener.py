"""
Stock screener — filter S&P 500 stocks by geographic revenue exposure, sector, and market cap.

GET /api/screener   — paginated, filterable stock list with China/US revenue %
GET /api/screener/sectors  — distinct sectors for filter UI
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.storage import cache_get, cache_set

router = APIRouter(prefix="/screener", tags=["screener"])

# Cache TTL for screener results (15 min — revenue data changes daily at most)
CACHE_TTL = 900


def _build_query(
    china_max: float | None,
    china_min: float | None,
    us_min: float | None,
    us_max: float | None,
    sector: str | None,
    market_cap_min: float | None,
    market_cap_max: float | None,
    country_code: str | None,
    sort_by: str,
    sort_dir: str,
    limit: int,
    offset: int,
) -> tuple[str, dict]:
    """Build parameterised screener SQL. Returns (sql, params)."""

    # Pivot China% and US% in a subquery, then filter in the outer query
    base_sql = """
    WITH latest_year AS (
        SELECT asset_id, MAX(fiscal_year) AS fy
        FROM stock_country_revenues
        GROUP BY asset_id
    ),
    revenue_pivot AS (
        SELECT
            scr.asset_id,
            MAX(CASE WHEN c.code = 'CN' THEN scr.revenue_pct END)  AS china_pct,
            MAX(CASE WHEN c.code = 'US' THEN scr.revenue_pct END)  AS us_pct,
            COUNT(DISTINCT scr.country_id)                          AS country_count,
            MAX(scr.fiscal_year)                                    AS fiscal_year
        FROM stock_country_revenues scr
        JOIN latest_year ly ON ly.asset_id = scr.asset_id AND ly.fy = scr.fiscal_year
        JOIN countries c    ON c.id = scr.country_id
        GROUP BY scr.asset_id
    )
    SELECT
        a.id,
        a.symbol,
        a.name,
        a.sector,
        a.market_cap_usd,
        COALESCE(rp.china_pct, 0)    AS china_pct,
        COALESCE(rp.us_pct, 0)       AS us_pct,
        COALESCE(rp.country_count, 0) AS country_count,
        rp.fiscal_year,
        CASE WHEN rp.asset_id IS NOT NULL THEN true ELSE false END AS has_revenue_data
    FROM assets a
    LEFT JOIN revenue_pivot rp ON rp.asset_id = a.id
    WHERE a.asset_type = 'stock' AND a.is_active = true
    """

    conditions = []
    params: dict[str, Any] = {}

    if china_max is not None:
        conditions.append("COALESCE(rp.china_pct, 0) <= :china_max")
        params["china_max"] = china_max
    if china_min is not None:
        conditions.append("COALESCE(rp.china_pct, 0) >= :china_min")
        params["china_min"] = china_min
    if us_min is not None:
        conditions.append("COALESCE(rp.us_pct, 0) >= :us_min")
        params["us_min"] = us_min
    if us_max is not None:
        conditions.append("COALESCE(rp.us_pct, 0) <= :us_max")
        params["us_max"] = us_max
    if sector:
        conditions.append("a.sector = :sector")
        params["sector"] = sector
    if market_cap_min is not None:
        conditions.append("a.market_cap_usd >= :market_cap_min")
        params["market_cap_min"] = market_cap_min * 1_000_000_000
    if market_cap_max is not None:
        conditions.append("a.market_cap_usd <= :market_cap_max")
        params["market_cap_max"] = market_cap_max * 1_000_000_000

    # Country exposure filter — must have >0% revenue from that country
    if country_code:
        conditions.append("""
            EXISTS (
                SELECT 1 FROM stock_country_revenues scr2
                JOIN countries c2 ON c2.id = scr2.country_id
                WHERE scr2.asset_id = a.id AND UPPER(c2.code) = UPPER(:country_code) AND scr2.revenue_pct > 0
            )
        """)
        params["country_code"] = country_code

    if conditions:
        base_sql += " AND " + " AND ".join(conditions)

    # Validated sort columns (prevent SQL injection)
    valid_sorts = {
        "market_cap": "a.market_cap_usd",
        "china_pct": "china_pct",
        "us_pct": "us_pct",
        "symbol": "a.symbol",
        "sector": "a.sector",
        "country_count": "country_count",
    }
    order_col = valid_sorts.get(sort_by, "a.market_cap_usd")
    direction = "ASC" if sort_dir.upper() == "ASC" else "DESC"
    nulls = "NULLS LAST" if direction == "DESC" else "NULLS FIRST"

    base_sql += f" ORDER BY {order_col} {direction} {nulls}"
    base_sql += " LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    return base_sql, params


def _count_query(
    china_max: float | None,
    china_min: float | None,
    us_min: float | None,
    us_max: float | None,
    sector: str | None,
    market_cap_min: float | None,
    market_cap_max: float | None,
    country_code: str | None,
) -> tuple[str, dict]:
    """Same filters as main query but returns COUNT(*)."""
    sql, params = _build_query(
        china_max, china_min, us_min, us_max, sector,
        market_cap_min, market_cap_max, country_code,
        "market_cap", "DESC", 10000, 0,
    )
    # Wrap in COUNT
    count_sql = f"SELECT COUNT(*) FROM ({sql.split('ORDER BY')[0]}) sub"
    # Remove pagination params
    params.pop("limit", None)
    params.pop("offset", None)
    return count_sql, params


@router.get("")
def screener(
    china_max: float | None = Query(default=None, ge=0, le=100, description="Max China revenue %"),
    china_min: float | None = Query(default=None, ge=0, le=100, description="Min China revenue %"),
    us_min: float | None    = Query(default=None, ge=0, le=100, description="Min US revenue %"),
    us_max: float | None    = Query(default=None, ge=0, le=100, description="Max US revenue %"),
    sector: str | None      = Query(default=None, description="GICS sector name"),
    market_cap_min: float | None = Query(default=None, ge=0, description="Min market cap (billions USD)"),
    market_cap_max: float | None = Query(default=None, ge=0, description="Max market cap (billions USD)"),
    country_code: str | None     = Query(default=None, max_length=2, description="Must have revenue exposure to this country (ISO2)"),
    sort_by: str  = Query(default="market_cap", pattern="^(market_cap|china_pct|us_pct|symbol|sector|country_count)$"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int    = Query(default=50, ge=1, le=200),
    offset: int   = Query(default=0, ge=0),
    db: Session   = Depends(get_db),
) -> dict[str, Any]:
    # Cache key — only for unfiltered default request
    # Use `is None` checks — 0 is a valid filter value (e.g. china_max=0)
    no_filters = all(v is None for v in [china_max, china_min, us_min, us_max,
                                          market_cap_min, market_cap_max]) and not sector and not country_code
    cache_key = f"screener:v1:{sort_by}:{sort_dir}:{limit}:{offset}" if no_filters else None
    if cache_key:
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

    sql, params = _build_query(
        china_max, china_min, us_min, us_max, sector,
        market_cap_min, market_cap_max, country_code,
        sort_by, sort_dir, limit, offset,
    )

    rows = db.execute(text(sql), params).mappings().all()

    results = []
    for r in rows:
        mcap = r["market_cap_usd"]
        results.append({
            "symbol": r["symbol"],
            "name": r["name"],
            "sector": r["sector"],
            "market_cap_usd": mcap,
            "market_cap_b": round(mcap / 1_000_000_000, 1) if mcap else None,
            "china_pct": round(r["china_pct"] or 0, 1),
            "us_pct": round(r["us_pct"] or 0, 1),
            "country_count": r["country_count"] or 0,
            "fiscal_year": r["fiscal_year"],
            "has_revenue_data": r["has_revenue_data"],
        })

    # Count total matching (use simple approach — count result rows before limit)
    count_sql, count_params = _count_query(
        china_max, china_min, us_min, us_max, sector,
        market_cap_min, market_cap_max, country_code,
    )
    total = db.execute(text(count_sql), count_params).scalar() or 0

    out = {
        "results": results,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "china_max": china_max,
            "china_min": china_min,
            "us_min": us_min,
            "us_max": us_max,
            "sector": sector,
            "market_cap_min": market_cap_min,
            "market_cap_max": market_cap_max,
            "country_code": country_code,
        },
    }

    if cache_key:
        cache_set(cache_key, out, ttl_seconds=CACHE_TTL)
    return out


@router.get("/sectors")
def screener_sectors(db: Session = Depends(get_db)) -> list[str]:
    """Return distinct sectors for filter UI."""
    cached = cache_get("screener:sectors:v1")
    if cached is not None:
        return cached

    rows = db.execute(text(
        "SELECT DISTINCT sector FROM assets WHERE asset_type='stock' AND is_active=true AND sector IS NOT NULL ORDER BY sector"
    )).scalars().all()
    result = list(rows)
    cache_set("screener:sectors:v1", result, ttl_seconds=3600)
    return result
