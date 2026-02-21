from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.database import get_db
from app.models import Country, CountryIndicator, TradePair, StockCountryRevenue, Asset
from app.storage import kv_json_get, kv_json_set

router = APIRouter(prefix="/countries", tags=["countries"])


@router.get("")
def list_countries(
    region: str | None = None,
    is_g20: bool | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    # Key encodes filters so different combos are cached separately
    cache_key = f"countries:list:{region or 'all'}:{is_g20}"
    cached = kv_json_get(cache_key)
    if cached is not None:
        return cached

    query = select(Country).order_by(Country.name)

    if region:
        query = query.where(Country.region == region)
    if is_g20 is not None:
        query = query.where(Country.is_g20 == is_g20)

    countries = db.execute(query).scalars().all()
    result = [_country_summary(c) for c in countries]

    # Country list changes very rarely — cache for 1 hour
    kv_json_set(cache_key, result, ttl_seconds=3600)
    return result


@router.get("/{code}")
def get_country(code: str, db: Session = Depends(get_db)) -> dict:
    country = db.execute(
        select(Country).where(Country.code == code.upper())
    ).scalar_one_or_none()

    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    # Latest value for each indicator
    indicators = db.execute(
        select(CountryIndicator)
        .where(CountryIndicator.country_id == country.id)
        .order_by(CountryIndicator.indicator, CountryIndicator.period_date.desc())
    ).scalars().all()

    # Deduplicate — keep only the most recent per indicator
    latest: dict[str, float] = {}
    for row in indicators:
        if row.indicator not in latest:
            latest[row.indicator] = row.value

    return {**_country_summary(country), "indicators": latest}


def _country_summary(c: Country) -> dict:
    return {
        "id": c.id,
        "code": c.code,
        "code3": c.code3,
        "name": c.name,
        "name_official": c.name_official,
        "capital": c.capital_city,
        "flag": c.flag_emoji,
        "slug": c.slug,
        "region": c.region,
        "subregion": c.subregion,
        "currency_code": c.currency_code,
        "currency_symbol": c.currency_symbol,
        "income_level": c.income_level,
        "development_status": c.development_status,
        "is_g7": c.is_g7,
        "is_g20": c.is_g20,
        "is_eu": c.is_eu,
        "is_nato": c.is_nato,
        "is_opec": c.is_opec,
        "is_brics": c.is_brics,
        "credit_rating_sp": c.credit_rating_sp,
        "credit_rating_moodys": c.credit_rating_moodys,
        "major_exports": c.major_exports,
        "natural_resources": c.natural_resources,
        "groupings": _groupings(c),
    }


@router.get("/{code}/gdp-history")
def get_gdp_history(code: str, db: Session = Depends(get_db)) -> list[dict]:
    country = db.execute(
        select(Country).where(Country.code == code.upper())
    ).scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    rows = db.execute(
        select(CountryIndicator)
        .where(CountryIndicator.country_id == country.id, CountryIndicator.indicator == "gdp_usd")
        .order_by(CountryIndicator.period_date)
    ).scalars().all()

    return [{"year": r.period_date.year, "gdp": r.value} for r in rows]


@router.get("/{code}/stocks")
def get_country_stocks(code: str, db: Session = Depends(get_db)) -> list[dict]:
    country = db.execute(
        select(Country).where(Country.code == code.upper())
    ).scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    rows = db.execute(
        select(StockCountryRevenue, Asset)
        .join(Asset, StockCountryRevenue.asset_id == Asset.id)
        .where(StockCountryRevenue.country_id == country.id)
        .order_by(StockCountryRevenue.fiscal_year.desc(), StockCountryRevenue.revenue_pct.desc())
    ).all()

    seen: set[int] = set()
    result = []
    for rev, asset in rows:
        if asset.id not in seen:
            seen.add(asset.id)
            result.append({
                "symbol": asset.symbol,
                "name": asset.name,
                "sector": asset.sector,
                "market_cap_usd": asset.market_cap_usd,
                "revenue_pct": rev.revenue_pct,
                "fiscal_year": rev.fiscal_year,
            })
    return result


@router.get("/{code}/trade-partners")
def get_trade_partners(code: str, db: Session = Depends(get_db)) -> list[dict]:
    country = db.execute(
        select(Country).where(Country.code == code.upper())
    ).scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    pairs = db.execute(
        select(TradePair)
        .where(or_(TradePair.exporter_id == country.id, TradePair.importer_id == country.id))
        .order_by(TradePair.trade_value_usd.desc())
        .limit(20)
    ).scalars().all()

    partner_ids = {
        (p.importer_id if p.exporter_id == country.id else p.exporter_id)
        for p in pairs
    }
    partners: dict[int, Country] = {}
    if partner_ids:
        rows = db.execute(select(Country).where(Country.id.in_(partner_ids))).scalars().all()
        partners = {c.id: c for c in rows}

    result = []
    for p in pairs:
        is_exporter = p.exporter_id == country.id
        partner_id = p.importer_id if is_exporter else p.exporter_id
        partner = partners.get(partner_id)
        if not partner:
            continue
        exports = p.exports_usd if is_exporter else p.imports_usd
        imports = p.imports_usd if is_exporter else p.exports_usd
        result.append({
            "partner": {"code": partner.code, "name": partner.name, "flag": partner.flag_emoji},
            "exports_usd": exports,
            "imports_usd": imports,
            "balance_usd": (exports or 0) - (imports or 0),
            "trade_value_usd": p.trade_value_usd,
        })
    return result


def _groupings(c: Country) -> list[str]:
    groups = []
    if c.is_g7:
        groups.append("G7")
    if c.is_g20:
        groups.append("G20")
    if c.is_eu:
        groups.append("EU")
    if c.is_eurozone:
        groups.append("Eurozone")
    if c.is_nato:
        groups.append("NATO")
    if c.is_opec:
        groups.append("OPEC")
    if c.is_brics:
        groups.append("BRICS")
    if c.is_asean:
        groups.append("ASEAN")
    if c.is_oecd:
        groups.append("OECD")
    if c.is_commonwealth:
        groups.append("Commonwealth")
    return groups
