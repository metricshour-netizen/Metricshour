from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import Asset, AssetType, Country, Price, StockCountryRevenue
from app.storage import kv_json_get, kv_json_set

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
def list_assets(
    type: str | None = None,
    sector: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    # Key encodes filters so different combos are cached separately
    cache_key = f"assets:list:{type or 'all'}:{sector or 'all'}"
    cached = kv_json_get(cache_key)
    if cached is not None:
        return cached

    query = (
        select(Asset)
        .where(Asset.is_active == True)
        .order_by(Asset.market_cap_usd.desc().nullslast(), Asset.symbol)
    )

    if type:
        try:
            query = query.where(Asset.asset_type == AssetType(type))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid type '{type}'. Use: stock, crypto, commodity, fx")

    if sector:
        query = query.where(Asset.sector == sector)

    assets = db.execute(query).scalars().all()

    # Batch-load HQ countries to avoid N+1
    country_ids = {a.country_id for a in assets if a.country_id}
    countries: dict[int, Country] = {}
    if country_ids:
        rows = db.execute(select(Country).where(Country.id.in_(country_ids))).scalars().all()
        countries = {c.id: c for c in rows}

    result = [_asset_summary(a, countries.get(a.country_id)) for a in assets]

    # Asset list changes at most every 15 min (price ingestion) — cache for 5 min
    kv_json_set(cache_key, result, ttl_seconds=300)
    return result


@router.get("/{symbol}")
def get_asset(symbol: str, db: Session = Depends(get_db)) -> dict:
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
    result["price"] = {
        "close": latest_price.close,
        "open": latest_price.open,
        "high": latest_price.high,
        "low": latest_price.low,
        "timestamp": latest_price.timestamp.isoformat(),
    } if latest_price else None
    result["country_revenues"] = revenues

    return result


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
