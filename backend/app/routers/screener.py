"""
Stock screener — filter S&P 500 stocks by geographic revenue exposure, sector, and market cap.

GET /api/screener            — paginated, filterable stock list
GET /api/screener/sectors    — distinct sectors for filter UI
GET /api/screener/export     — CSV export of current filtered results
GET /api/screener/revenue-history/{symbol}  — multi-year revenue breakdown for macro chart
"""
import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.storage import cache_get, cache_set

router = APIRouter(prefix="/screener", tags=["screener"])

CACHE_TTL = 900  # 15 minutes

# EM country codes (MSCI Emerging Markets universe)
_EM_CODES = (
    'CN','IN','BR','MX','RU','ZA','KR','TW','ID','TH','MY','PH','CL','CO',
    'PE','TR','EG','QA','AE','SA','AR','NG','PK','VN','BD','PL','HU','CZ',
    'RO','GR','UA','KZ',
)
_EM_LIST = ", ".join(f"'{c}'" for c in _EM_CODES)


def _build_query(
    china_max: float | None,
    china_min: float | None,
    us_min: float | None,
    us_max: float | None,
    eu_min: float | None,
    eu_max: float | None,
    japan_min: float | None,
    japan_max: float | None,
    india_min: float | None,
    india_max: float | None,
    em_min: float | None,
    em_max: float | None,
    sector: str | None,
    market_cap_min: float | None,
    market_cap_max: float | None,
    country_code: str | None,
    sort_by: str,
    sort_dir: str,
    limit: int,
    offset: int,
) -> tuple[str, dict]:
    base_sql = f"""
    WITH latest_year AS (
        SELECT asset_id, MAX(fiscal_year) AS fy
        FROM stock_country_revenues
        GROUP BY asset_id
    ),
    revenue_pivot AS (
        SELECT
            scr.asset_id,
            MAX(CASE WHEN c.code = 'CN' THEN scr.revenue_pct END)              AS china_pct,
            MAX(CASE WHEN c.code = 'US' THEN scr.revenue_pct END)              AS us_pct,
            COALESCE(SUM(CASE WHEN c.is_eu  = true THEN scr.revenue_pct END), 0) AS eu_pct,
            MAX(CASE WHEN c.code = 'JP' THEN scr.revenue_pct END)              AS japan_pct,
            MAX(CASE WHEN c.code = 'IN' THEN scr.revenue_pct END)              AS india_pct,
            COALESCE(SUM(CASE WHEN c.code IN ({_EM_LIST}) THEN scr.revenue_pct END), 0) AS em_pct,
            COUNT(DISTINCT scr.country_id)                                     AS country_count,
            MAX(scr.fiscal_year)                                               AS fiscal_year
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
        COALESCE(rp.eu_pct, 0)       AS eu_pct,
        COALESCE(rp.japan_pct, 0)    AS japan_pct,
        COALESCE(rp.india_pct, 0)    AS india_pct,
        COALESCE(rp.em_pct, 0)       AS em_pct,
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
    if eu_min is not None:
        conditions.append("COALESCE(rp.eu_pct, 0) >= :eu_min")
        params["eu_min"] = eu_min
    if eu_max is not None:
        conditions.append("COALESCE(rp.eu_pct, 0) <= :eu_max")
        params["eu_max"] = eu_max
    if japan_min is not None:
        conditions.append("COALESCE(rp.japan_pct, 0) >= :japan_min")
        params["japan_min"] = japan_min
    if japan_max is not None:
        conditions.append("COALESCE(rp.japan_pct, 0) <= :japan_max")
        params["japan_max"] = japan_max
    if india_min is not None:
        conditions.append("COALESCE(rp.india_pct, 0) >= :india_min")
        params["india_min"] = india_min
    if india_max is not None:
        conditions.append("COALESCE(rp.india_pct, 0) <= :india_max")
        params["india_max"] = india_max
    if em_min is not None:
        conditions.append("COALESCE(rp.em_pct, 0) >= :em_min")
        params["em_min"] = em_min
    if em_max is not None:
        conditions.append("COALESCE(rp.em_pct, 0) <= :em_max")
        params["em_max"] = em_max
    if sector:
        conditions.append("a.sector = :sector")
        params["sector"] = sector
    if market_cap_min is not None:
        conditions.append("a.market_cap_usd >= :market_cap_min")
        params["market_cap_min"] = market_cap_min * 1_000_000_000
    if market_cap_max is not None:
        conditions.append("a.market_cap_usd <= :market_cap_max")
        params["market_cap_max"] = market_cap_max * 1_000_000_000
    if country_code:
        conditions.append("""
            EXISTS (
                SELECT 1 FROM stock_country_revenues scr2
                JOIN countries c2 ON c2.id = scr2.country_id
                WHERE scr2.asset_id = a.id AND UPPER(c2.code) = UPPER(:country_code)
                  AND scr2.revenue_pct > 0
            )
        """)
        params["country_code"] = country_code

    if conditions:
        base_sql += " AND " + " AND ".join(conditions)

    valid_sorts = {
        "market_cap": "a.market_cap_usd",
        "china_pct": "china_pct",
        "us_pct": "us_pct",
        "eu_pct": "eu_pct",
        "japan_pct": "japan_pct",
        "india_pct": "india_pct",
        "em_pct": "em_pct",
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
    china_max, china_min, us_min, us_max,
    eu_min, eu_max, japan_min, japan_max, india_min, india_max, em_min, em_max,
    sector, market_cap_min, market_cap_max, country_code,
) -> tuple[str, dict]:
    sql, params = _build_query(
        china_max, china_min, us_min, us_max,
        eu_min, eu_max, japan_min, japan_max, india_min, india_max, em_min, em_max,
        sector, market_cap_min, market_cap_max, country_code,
        "market_cap", "DESC", 10000, 0,
    )
    count_sql = f"SELECT COUNT(*) FROM ({sql.split('ORDER BY')[0]}) sub"
    params.pop("limit", None)
    params.pop("offset", None)
    return count_sql, params


def _row_to_dict(r: Any) -> dict:
    mcap = r["market_cap_usd"]
    return {
        "symbol": r["symbol"],
        "name": r["name"],
        "sector": r["sector"],
        "market_cap_usd": mcap,
        "market_cap_b": round(mcap / 1_000_000_000, 1) if mcap else None,
        "china_pct": round(r["china_pct"] or 0, 1),
        "us_pct": round(r["us_pct"] or 0, 1),
        "eu_pct": round(r["eu_pct"] or 0, 1),
        "japan_pct": round(r["japan_pct"] or 0, 1),
        "india_pct": round(r["india_pct"] or 0, 1),
        "em_pct": round(r["em_pct"] or 0, 1),
        "country_count": r["country_count"] or 0,
        "fiscal_year": r["fiscal_year"],
        "has_revenue_data": r["has_revenue_data"],
    }


def _filter_params(
    china_max, china_min, us_min, us_max,
    eu_min, eu_max, japan_min, japan_max, india_min, india_max, em_min, em_max,
    sector, market_cap_min, market_cap_max, country_code,
    sort_by, sort_dir, limit, offset,
):
    return dict(
        china_max=china_max, china_min=china_min,
        us_min=us_min, us_max=us_max,
        eu_min=eu_min, eu_max=eu_max,
        japan_min=japan_min, japan_max=japan_max,
        india_min=india_min, india_max=india_max,
        em_min=em_min, em_max=em_max,
        sector=sector, market_cap_min=market_cap_min, market_cap_max=market_cap_max,
        country_code=country_code, sort_by=sort_by, sort_dir=sort_dir,
        limit=limit, offset=offset,
    )


@router.get("")
def screener(
    china_max: float | None    = Query(default=None, ge=0, le=100),
    china_min: float | None    = Query(default=None, ge=0, le=100),
    us_min: float | None       = Query(default=None, ge=0, le=100),
    us_max: float | None       = Query(default=None, ge=0, le=100),
    eu_min: float | None       = Query(default=None, ge=0, le=100),
    eu_max: float | None       = Query(default=None, ge=0, le=100),
    japan_min: float | None    = Query(default=None, ge=0, le=100),
    japan_max: float | None    = Query(default=None, ge=0, le=100),
    india_min: float | None    = Query(default=None, ge=0, le=100),
    india_max: float | None    = Query(default=None, ge=0, le=100),
    em_min: float | None       = Query(default=None, ge=0, le=100),
    em_max: float | None       = Query(default=None, ge=0, le=100),
    sector: str | None         = Query(default=None),
    market_cap_min: float | None = Query(default=None, ge=0),
    market_cap_max: float | None = Query(default=None, ge=0),
    country_code: str | None   = Query(default=None, max_length=2),
    sort_by: str  = Query(default="market_cap", pattern="^(market_cap|china_pct|us_pct|eu_pct|japan_pct|india_pct|em_pct|symbol|sector|country_count)$"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int    = Query(default=50, ge=1, le=200),
    offset: int   = Query(default=0, ge=0),
    db: Session   = Depends(get_db),
) -> dict[str, Any]:
    no_filters = all(v is None for v in [
        china_max, china_min, us_min, us_max,
        eu_min, eu_max, japan_min, japan_max, india_min, india_max, em_min, em_max,
        market_cap_min, market_cap_max,
    ]) and not sector and not country_code
    cache_key = f"screener:v2:{sort_by}:{sort_dir}:{limit}:{offset}" if no_filters else None
    if cache_key:
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

    sql, params = _build_query(
        china_max, china_min, us_min, us_max,
        eu_min, eu_max, japan_min, japan_max, india_min, india_max, em_min, em_max,
        sector, market_cap_min, market_cap_max, country_code,
        sort_by, sort_dir, limit, offset,
    )
    rows = db.execute(text(sql), params).mappings().all()
    results = [_row_to_dict(r) for r in rows]

    count_sql, count_params = _count_query(
        china_max, china_min, us_min, us_max,
        eu_min, eu_max, japan_min, japan_max, india_min, india_max, em_min, em_max,
        sector, market_cap_min, market_cap_max, country_code,
    )
    total = db.execute(text(count_sql), count_params).scalar() or 0

    out = {
        "results": results,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": _filter_params(
            china_max, china_min, us_min, us_max,
            eu_min, eu_max, japan_min, japan_max, india_min, india_max, em_min, em_max,
            sector, market_cap_min, market_cap_max, country_code,
            sort_by, sort_dir, limit, offset,
        ),
    }

    if cache_key:
        cache_set(cache_key, out, ttl_seconds=CACHE_TTL)
    return out


@router.get("/export")
def screener_export(
    china_max: float | None    = Query(default=None, ge=0, le=100),
    china_min: float | None    = Query(default=None, ge=0, le=100),
    us_min: float | None       = Query(default=None, ge=0, le=100),
    us_max: float | None       = Query(default=None, ge=0, le=100),
    eu_min: float | None       = Query(default=None, ge=0, le=100),
    eu_max: float | None       = Query(default=None, ge=0, le=100),
    japan_min: float | None    = Query(default=None, ge=0, le=100),
    japan_max: float | None    = Query(default=None, ge=0, le=100),
    india_min: float | None    = Query(default=None, ge=0, le=100),
    india_max: float | None    = Query(default=None, ge=0, le=100),
    em_min: float | None       = Query(default=None, ge=0, le=100),
    em_max: float | None       = Query(default=None, ge=0, le=100),
    sector: str | None         = Query(default=None),
    market_cap_min: float | None = Query(default=None, ge=0),
    market_cap_max: float | None = Query(default=None, ge=0),
    country_code: str | None   = Query(default=None, max_length=2),
    sort_by: str  = Query(default="market_cap", pattern="^(market_cap|china_pct|us_pct|eu_pct|japan_pct|india_pct|em_pct|symbol|sector|country_count)$"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session   = Depends(get_db),
):
    sql, params = _build_query(
        china_max, china_min, us_min, us_max,
        eu_min, eu_max, japan_min, japan_max, india_min, india_max, em_min, em_max,
        sector, market_cap_min, market_cap_max, country_code,
        sort_by, sort_dir, 2000, 0,
    )
    rows = db.execute(text(sql), params).mappings().all()

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "symbol", "name", "sector", "market_cap_b",
        "china_pct", "us_pct", "eu_pct", "japan_pct", "india_pct", "em_pct",
        "country_count", "fiscal_year",
    ])
    writer.writeheader()
    for r in rows:
        mcap = r["market_cap_usd"]
        writer.writerow({
            "symbol": r["symbol"],
            "name": r["name"],
            "sector": r["sector"] or "",
            "market_cap_b": round(mcap / 1_000_000_000, 1) if mcap else "",
            "china_pct": round(r["china_pct"] or 0, 1),
            "us_pct": round(r["us_pct"] or 0, 1),
            "eu_pct": round(r["eu_pct"] or 0, 1),
            "japan_pct": round(r["japan_pct"] or 0, 1),
            "india_pct": round(r["india_pct"] or 0, 1),
            "em_pct": round(r["em_pct"] or 0, 1),
            "country_count": r["country_count"] or 0,
            "fiscal_year": r["fiscal_year"] or "",
        })

    from datetime import date
    filename = f"metricshour-screener-{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/revenue-history/{symbol}")
def revenue_history(symbol: str, db: Session = Depends(get_db)):
    """Multi-year geographic revenue breakdown for a stock — used for macro risk chart."""
    cache_key = f"screener:rev-history:{symbol.upper()}:v1"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    rows = db.execute(text("""
        SELECT
            scr.fiscal_year,
            MAX(CASE WHEN c.code = 'CN' THEN scr.revenue_pct END) AS china_pct,
            MAX(CASE WHEN c.code = 'US' THEN scr.revenue_pct END) AS us_pct,
            COALESCE(SUM(CASE WHEN c.is_eu = true THEN scr.revenue_pct END), 0) AS eu_pct
        FROM stock_country_revenues scr
        JOIN assets a      ON a.id = scr.asset_id
        JOIN countries c   ON c.id = scr.country_id
        WHERE UPPER(a.symbol) = UPPER(:symbol)
          AND a.asset_type = 'stock'
          AND scr.fiscal_quarter IS NULL
        GROUP BY scr.fiscal_year
        ORDER BY scr.fiscal_year ASC
    """), {"symbol": symbol.upper()}).mappings().all()

    result = [
        {
            "year": r["fiscal_year"],
            "china_pct": round(r["china_pct"] or 0, 1),
            "us_pct": round(r["us_pct"] or 0, 1),
            "eu_pct": round(r["eu_pct"] or 0, 1),
        }
        for r in rows
    ]

    cache_set(cache_key, result, ttl_seconds=3600 * 6)
    return result


@router.get("/sectors")
def screener_sectors(db: Session = Depends(get_db)) -> list[str]:
    cached = cache_get("screener:sectors:v1")
    if cached is not None:
        return cached
    rows = db.execute(text(
        "SELECT DISTINCT sector FROM assets WHERE asset_type='stock' AND is_active=true AND sector IS NOT NULL ORDER BY sector"
    )).scalars().all()
    result = list(rows)
    cache_set("screener:sectors:v1", result, ttl_seconds=3600)
    return result
