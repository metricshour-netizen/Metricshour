from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.limiter import limiter
from app.models import Asset, AssetType, Country, Price, StockCountryRevenue
from app.storage import cache_get, cache_set

router = APIRouter(prefix="/assets", tags=["assets"])


def _market_open(asset: Asset) -> bool:
    """Return True if the asset's primary exchange is currently in regular trading hours."""
    if asset.asset_type in (AssetType.crypto, AssetType.fx):
        return True  # 24/7 markets
    if asset.asset_type not in (AssetType.stock, AssetType.etf, AssetType.index):
        return False
    now = datetime.now(timezone.utc)
    wd = now.weekday()   # 0=Mon … 6=Sun
    m = now.hour * 60 + now.minute
    ex = (asset.exchange or '').upper()
    if ex in ('NYSE', 'NASDAQ', 'NYSE ARCA', 'NYSE MKT', 'AMEX', 'BATS'):
        return wd < 5 and 13 * 60 + 30 <= m < 21 * 60
    if ex == 'LSE':
        return wd < 5 and 8 * 60 <= m < 16 * 60 + 30
    if ex in ('SHG', 'SHE', 'SSE'):  # Shanghai / Shenzhen — morning + afternoon session (UTC)
        return wd < 5 and (1 * 60 + 30 <= m < 3 * 60 + 30 or 5 * 60 <= m < 7 * 60)
    if ex in ('NGX', 'NSE'):  # Nigerian Exchange — 10:00–14:30 WAT = 09:00–13:30 UTC
        return wd < 5 and 9 * 60 <= m < 13 * 60 + 30
    return False


@router.get("")
@limiter.limit("60/minute")
def list_assets(
    request: Request,
    type: str | None = None,
    sector: str | None = None,
    country_code: str | None = None,
    exchange: str | None = None,
    ids: str | None = None,
    limit: int = Query(default=2000, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[dict]:
    # ID-scoped fetches bypass cache (specific set of assets)
    if ids:
        id_list = [int(i) for i in ids.split(',') if i.strip().isdigit()]
        if not id_list:
            return []
        assets = db.execute(
            select(Asset).where(Asset.id.in_(id_list), Asset.is_active == True)
        ).scalars().all()
        # preserve requested order
        id_order = {aid: i for i, aid in enumerate(id_list)}
        assets = sorted(assets, key=lambda a: id_order.get(a.id, 999))
        country_ids = {a.country_id for a in assets if a.country_id}
        country_map = {}
        if country_ids:
            for c in db.execute(select(Country).where(Country.id.in_(country_ids))).scalars().all():
                country_map[c.id] = c
        asset_ids = [a.id for a in assets]
        price_map = {}
        if asset_ids:
            for p in db.execute(
                select(Price).where(Price.asset_id.in_(asset_ids), Price.interval == "1d")
                .order_by(Price.timestamp.desc())
            ).scalars().all():
                if p.asset_id not in price_map:
                    price_map[p.asset_id] = p
        result = []
        for a in assets:
            row = _asset_summary(a, country_map.get(a.country_id) if a.country_id else None)
            row["price"] = _price_dict(price_map[a.id]) if a.id in price_map else None
            result.append(row)
        return result

    # country_code/exchange-scoped queries are never cached (too many combinations)
    cache_key = f"assets:list:v4:{type or 'all'}:{sector or 'all'}" if not country_code and not exchange else None
    if cache_key:
        cached = cache_get(cache_key)
        if cached is not None:
            return cached[offset:offset + limit]

    query = (
        select(Asset)
        .where(Asset.is_active == True)
        .order_by(Asset.market_cap_usd.desc().nullslast(), Asset.symbol)
    )

    if type:
        try:
            query = query.where(Asset.asset_type == AssetType(type))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid type '{type}'. Use: stock, crypto, commodity, fx, etf, index, bond")

    if sector:
        query = query.where(Asset.sector == sector)

    if exchange:
        query = query.where(Asset.exchange == exchange.upper())

    if country_code:
        # Join to Country and filter by ISO code (case-insensitive)
        hq_country = db.execute(
            select(Country).where(Country.code == country_code.upper())
        ).scalar_one_or_none()
        if hq_country:
            query = query.where(Asset.country_id == hq_country.id)
        else:
            return []

    assets = db.execute(query).scalars().all()

    # Batch-load HQ countries to avoid N+1
    country_ids = {a.country_id for a in assets if a.country_id}
    countries: dict[int, Country] = {}
    if country_ids:
        rows = db.execute(select(Country).where(Country.id.in_(country_ids))).scalars().all()
        countries = {c.id: c for c in rows}

    # Batch-load latest 1d price per asset to get open/close for change_pct
    asset_ids = [a.id for a in assets]
    prices: dict[int, Price] = {}
    if asset_ids:
        latest_ts_sq = (
            select(Price.asset_id, func.max(Price.timestamp).label("max_ts"))
            .where(Price.asset_id.in_(asset_ids), Price.interval == "1d")
            .group_by(Price.asset_id)
            .subquery()
        )
        price_rows = db.execute(
            select(Price).join(
                latest_ts_sq,
                (Price.asset_id == latest_ts_sq.c.asset_id) &
                (Price.timestamp == latest_ts_sq.c.max_ts)
            ).where(Price.interval == "1d")
        ).scalars().all()
        prices = {p.asset_id: p for p in price_rows}

    result = []
    for a in assets:
        row = _asset_summary(a, countries.get(a.country_id))
        p = prices.get(a.id)
        row["price"] = _price_dict(p) if p else None
        result.append(row)

    if cache_key:
        cache_set(cache_key, result, ttl_seconds=300)
    return result[offset:offset + limit]


@router.get("/{symbol}/prices")
@limiter.limit("120/minute")
def get_asset_prices(
    request: Request,
    symbol: str,
    interval: str = "15m",
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[dict]:
    asset = db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.is_active == True)
    ).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    rows = db.execute(
        select(Price)
        .where(Price.asset_id == asset.id, Price.interval == interval)
        .order_by(Price.timestamp.asc())
        .limit(limit)
    ).scalars().all()

    # Fall back to any interval if none found for the requested one
    if not rows:
        rows = db.execute(
            select(Price)
            .where(Price.asset_id == asset.id)
            .order_by(Price.timestamp.asc())
            .limit(limit)
        ).scalars().all()

    return [
        {
            "t": p.timestamp.isoformat(),
            "o": p.open,
            "h": p.high,
            "l": p.low,
            "c": p.close,
            "v": p.volume,
        }
        for p in rows
    ]


_SECTOR_META: dict[str, dict] = {
    "technology": {
        "name": "Technology",
        "description": "Software, semiconductors, hardware, and IT services companies driving the digital economy.",
        "icon": "💻",
    },
    "healthcare": {
        "name": "Healthcare",
        "description": "Pharmaceuticals, biotechnology, medical devices, and healthcare service providers.",
        "icon": "🏥",
    },
    "financials": {
        "name": "Financials",
        "description": "Banks, asset managers, insurance, and capital markets institutions.",
        "icon": "🏦",
    },
    "industrials": {
        "name": "Industrials",
        "description": "Aerospace, defense, machinery, construction, and transportation companies.",
        "icon": "🏭",
    },
    "energy": {
        "name": "Energy",
        "description": "Oil, gas, refining, pipelines, and diversified energy producers.",
        "icon": "⚡",
    },
    "consumer-discretionary": {
        "name": "Consumer Discretionary",
        "description": "Retail, automotive, luxury goods, hospitality, and leisure companies.",
        "icon": "🛍️",
    },
    "consumer-staples": {
        "name": "Consumer Staples",
        "description": "Food, beverages, household products, and everyday essential goods.",
        "icon": "🛒",
    },
    "communication-services": {
        "name": "Communication Services",
        "description": "Social media, streaming, telecom, and interactive entertainment platforms.",
        "icon": "📡",
    },
    "materials": {
        "name": "Materials",
        "description": "Mining, chemicals, construction materials, and specialty materials.",
        "icon": "⛏️",
    },
    "real-estate": {
        "name": "Real Estate",
        "description": "REITs, property developers, and real estate services.",
        "icon": "🏢",
    },
    "utilities": {
        "name": "Utilities",
        "description": "Electric, gas, and water utilities providing essential services.",
        "icon": "💡",
    },
}

# Canonical name → slug lookup for deep-link injection
SECTOR_SLUG_MAP: dict[str, str] = {meta["name"]: slug for slug, meta in _SECTOR_META.items()}


@router.get("/sectors")
@limiter.limit("60/minute")
def list_sectors(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    cached = cache_get("api:sectors:list:v1")
    if cached is not None:
        return cached

    rows = db.execute(
        select(Asset.sector, func.count().label("stock_count"), func.sum(Asset.market_cap_usd).label("total_cap"))
        .where(Asset.asset_type == AssetType.stock, Asset.is_active == True, Asset.sector.isnot(None))
        .group_by(Asset.sector)
        .order_by(func.sum(Asset.market_cap_usd).desc().nullslast())
    ).all()

    result = []
    for row in rows:
        slug = SECTOR_SLUG_MAP.get(row.sector)
        if not slug:
            continue  # skip index/ETF pseudo-sectors
        meta = _SECTOR_META[slug]
        result.append({
            "slug": slug,
            "name": meta["name"],
            "description": meta["description"],
            "icon": meta["icon"],
            "stock_count": row.stock_count,
            "total_market_cap_usd": row.total_cap,
        })

    cache_set("api:sectors:list:v1", result, ttl_seconds=3600)
    return result


@router.get("/sectors/{slug}")
@limiter.limit("60/minute")
def get_sector(request: Request, slug: str, db: Session = Depends(get_db)) -> dict:
    meta = _SECTOR_META.get(slug)
    if not meta:
        raise HTTPException(status_code=404, detail="Sector not found")

    cache_key = f"api:sector:{slug}:v1"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    sector_name = meta["name"]

    assets = db.execute(
        select(Asset)
        .where(Asset.sector == sector_name, Asset.asset_type == AssetType.stock, Asset.is_active == True)
        .order_by(Asset.market_cap_usd.desc().nullslast())
    ).scalars().all()

    # Batch-load countries
    country_ids = {a.country_id for a in assets if a.country_id}
    countries: dict[int, Country] = {}
    if country_ids:
        rows = db.execute(select(Country).where(Country.id.in_(country_ids))).scalars().all()
        countries = {c.id: c for c in rows}

    # Batch-load latest prices
    asset_ids = [a.id for a in assets]
    prices: dict[int, Price] = {}
    if asset_ids:
        latest_ts_sq = (
            select(Price.asset_id, func.max(Price.timestamp).label("max_ts"))
            .where(Price.asset_id.in_(asset_ids), Price.interval == "1d")
            .group_by(Price.asset_id)
            .subquery()
        )
        price_rows = db.execute(
            select(Price).join(
                latest_ts_sq,
                (Price.asset_id == latest_ts_sq.c.asset_id) &
                (Price.timestamp == latest_ts_sq.c.max_ts)
            ).where(Price.interval == "1d")
        ).scalars().all()
        prices = {p.asset_id: p for p in price_rows}

    # Top countries by exposure (aggregate revenue pct across all sector stocks)
    country_exposure: dict[int, dict] = {}
    if asset_ids:
        rev_rows = db.execute(
            select(StockCountryRevenue, Country)
            .join(Country, StockCountryRevenue.country_id == Country.id)
            .where(StockCountryRevenue.asset_id.in_(asset_ids))
        ).all()
        for rev, cty in rev_rows:
            if cty.id not in country_exposure:
                country_exposure[cty.id] = {"code": cty.code, "name": cty.name, "flag": cty.flag_emoji, "total_pct": 0.0, "stock_count": 0}
            country_exposure[cty.id]["total_pct"] += rev.revenue_pct
            country_exposure[cty.id]["stock_count"] += 1

    top_countries = sorted(country_exposure.values(), key=lambda x: x["total_pct"], reverse=True)[:10]

    stock_list = []
    for a in assets:
        country = countries.get(a.country_id) if a.country_id else None
        price = prices.get(a.id)
        s = _asset_summary(a, country)
        s["price"] = _price_dict(price) if price else None
        stock_list.append(s)

    total_cap = sum(a.market_cap_usd or 0 for a in assets)

    result = {
        "slug": slug,
        "name": meta["name"],
        "description": meta["description"],
        "icon": meta["icon"],
        "stock_count": len(assets),
        "total_market_cap_usd": total_cap,
        "stocks": stock_list,
        "top_countries": top_countries,
    }

    cache_set(cache_key, result, ttl_seconds=3600)
    return result


@router.get("/{symbol}")
@limiter.limit("120/minute")
def get_asset(request: Request, symbol: str, db: Session = Depends(get_db)) -> dict:
    cache_key = f"api:asset:{symbol.upper()}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    asset = db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.is_active == True)
    ).scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # HQ country
    country: Country | None = None
    if asset.country_id:
        country = db.execute(
            select(Country).where(Country.id == asset.country_id)
        ).scalar_one_or_none()

    # Latest daily price
    latest_price = db.execute(
        select(Price)
        .where(Price.asset_id == asset.id, Price.interval == "1d")
        .order_by(Price.timestamp.desc())
        .limit(1)
    ).scalar_one_or_none()

    # Geographic revenue breakdown (stocks only) — most recent year, desc by pct
    revenues: list[dict] = []
    if asset.asset_type == AssetType.stock:
        rev_rows = db.execute(
            select(StockCountryRevenue, Country)
            .join(Country, StockCountryRevenue.country_id == Country.id)
            .where(StockCountryRevenue.asset_id == asset.id)
            .order_by(
                StockCountryRevenue.fiscal_year.desc(),
                StockCountryRevenue.revenue_pct.desc(),
            )
        ).all()

        # Deduplicate — keep only most recent fiscal year per country
        seen: set[int] = set()
        for rev, cty in rev_rows:
            if cty.id not in seen:
                seen.add(cty.id)
                revenues.append({
                    "country": {
                        "code": cty.code,
                        "name": cty.name,
                        "flag": cty.flag_emoji,
                    },
                    "revenue_pct": rev.revenue_pct,
                    "revenue_usd": rev.revenue_usd,
                    "fiscal_year": rev.fiscal_year,
                })

    result = _asset_summary(asset, country)
    result["price"] = _price_dict(latest_price) if latest_price else None
    result["country_revenues"] = revenues
    result["market_open"] = _market_open(asset)

    # Prices are updated every 15min — cache for 15min so data is never stale
    cache_set(cache_key, result, ttl_seconds=900)
    return result


def _price_dict(p: Price) -> dict:
    """Serialize a Price row including computed change_pct from open/close."""
    chg = None
    if p.open and p.open > 0 and p.close is not None and p.close != p.open:
        chg = round((p.close - p.open) / p.open * 100, 4)
    return {
        "close": p.close,
        "open": p.open,
        "high": p.high,
        "low": p.low,
        "change_pct": chg,
        "timestamp": p.timestamp.isoformat(),
        "fetched_at": p.fetched_at.isoformat() if p.fetched_at else None,
    }


def _asset_summary(asset: Asset, country: Country | None) -> dict:
    return {
        "id": asset.id,
        "symbol": asset.symbol,
        "name": asset.name,
        "asset_type": asset.asset_type.value,
        "exchange": asset.exchange,
        "currency": asset.currency,
        "sector": asset.sector,
        "industry": asset.industry,
        "market_cap_usd": asset.market_cap_usd,
        "base_currency": asset.base_currency,
        "quote_currency": asset.quote_currency,
        "country": {
            "code": country.code,
            "name": country.name,
            "flag": country.flag_emoji,
        } if country else None,
    }


@router.get("/{symbol}/prices/download")
@limiter.limit("20/minute")
def download_asset_prices(
    request: Request,
    symbol: str,
    interval: str = "1d",
    limit: int = Query(default=365, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Download price history as CSV."""
    import csv, io
    from fastapi.responses import StreamingResponse

    asset = db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.is_active == True)
    ).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    rows = db.execute(
        select(Price)
        .where(Price.asset_id == asset.id, Price.interval == interval)
        .order_by(Price.timestamp.desc())
        .limit(limit)
    ).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "open", "high", "low", "close", "volume", "interval", "symbol", "source_credit"])
    for p in rows:
        writer.writerow([
            p.timestamp.date(), p.open, p.high, p.low, p.close, p.volume,
            interval, asset.symbol, "MetricsHour (metricshour.com)",
        ])

    output.seek(0)
    filename = f"{symbol.lower()}-prices-{interval}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
