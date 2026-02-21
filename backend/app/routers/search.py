from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import Country, Asset

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(q: str = "", db: Session = Depends(get_db)) -> dict:
    if not q or len(q.strip()) < 2:
        return {"countries": [], "assets": []}

    term = q.strip()

    countries = db.execute(
        select(Country)
        .where(Country.name.ilike(f"%{term}%") | Country.code.ilike(f"%{term}%"))
        .order_by(Country.is_g20.desc(), Country.name)
        .limit(5)
    ).scalars().all()

    assets = db.execute(
        select(Asset)
        .where(
            Asset.is_active == True,
            Asset.symbol.ilike(f"%{term}%") | Asset.name.ilike(f"%{term}%"),
        )
        .order_by(Asset.market_cap_usd.desc().nullslast())
        .limit(5)
    ).scalars().all()

    return {
        "countries": [
            {"code": c.code, "name": c.name, "flag": c.flag_emoji, "type": "country"}
            for c in countries
        ],
        "assets": [
            {
                "symbol": a.symbol,
                "name": a.name,
                "sector": a.sector,
                "asset_type": a.asset_type.value,
                "type": "asset",
            }
            for a in assets
        ],
    }
