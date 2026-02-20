from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import TradePair, Country

router = APIRouter(prefix="/trade", tags=["trade"])


@router.get("")
def list_trade_pairs(
    exporter: str | None = None,
    importer: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = (
        select(TradePair)
        .order_by(TradePair.trade_value_usd.desc())
        .limit(100)
    )

    if exporter:
        exp = db.execute(
            select(Country.id).where(Country.code == exporter.upper())
        ).scalar_one_or_none()
        if exp:
            query = query.where(TradePair.exporter_id == exp)

    if importer:
        imp = db.execute(
            select(Country.id).where(Country.code == importer.upper())
        ).scalar_one_or_none()
        if imp:
            query = query.where(TradePair.importer_id == imp)

    pairs = db.execute(query).scalars().all()

    # Batch-load countries
    country_ids = {p.exporter_id for p in pairs} | {p.importer_id for p in pairs}
    countries: dict[int, Country] = {}
    if country_ids:
        rows = db.execute(select(Country).where(Country.id.in_(country_ids))).scalars().all()
        countries = {c.id: c for c in rows}

    return [_pair_summary(p, countries) for p in pairs]


@router.get("/{exporter_code}/{importer_code}")
def get_trade_pair(
    exporter_code: str,
    importer_code: str,
    db: Session = Depends(get_db),
) -> dict:
    exp = db.execute(
        select(Country).where(Country.code == exporter_code.upper())
    ).scalar_one_or_none()

    imp = db.execute(
        select(Country).where(Country.code == importer_code.upper())
    ).scalar_one_or_none()

    if not exp or not imp:
        raise HTTPException(status_code=404, detail="Country not found")

    pair = db.execute(
        select(TradePair)
        .where(TradePair.exporter_id == exp.id, TradePair.importer_id == imp.id)
        .order_by(TradePair.year.desc())
        .limit(1)
    ).scalar_one_or_none()

    countries = {exp.id: exp, imp.id: imp}

    return {
        "exporter": _country_ref(exp),
        "importer": _country_ref(imp),
        "trade_data": _pair_summary(pair, countries) if pair else None,
    }


def _pair_summary(pair: TradePair, countries: dict[int, Country]) -> dict:
    exp = countries.get(pair.exporter_id)
    imp = countries.get(pair.importer_id)
    return {
        "id": pair.id,
        "year": pair.year,
        "exporter": _country_ref(exp) if exp else None,
        "importer": _country_ref(imp) if imp else None,
        "trade_value_usd": pair.trade_value_usd,
        "exports_usd": pair.exports_usd,
        "imports_usd": pair.imports_usd,
        "balance_usd": pair.balance_usd,
        "exporter_gdp_share_pct": pair.exporter_gdp_share_pct,
        "importer_gdp_share_pct": pair.importer_gdp_share_pct,
        "top_export_products": pair.top_export_products or [],
        "top_import_products": pair.top_import_products or [],
    }


def _country_ref(c: Country) -> dict:
    return {"code": c.code, "name": c.name, "flag": c.flag_emoji}
