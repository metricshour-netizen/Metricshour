from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import Country, CountryIndicator

router = APIRouter(prefix="/countries", tags=["countries"])


@router.get("")
def list_countries(
    region: str | None = None,
    is_g20: bool | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = select(Country).order_by(Country.name)

    if region:
        query = query.where(Country.region == region)
    if is_g20 is not None:
        query = query.where(Country.is_g20 == is_g20)

    countries = db.execute(query).scalars().all()
    return [_country_summary(c) for c in countries]


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
