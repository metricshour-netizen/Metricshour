from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import Country, Asset
from app.config import settings

router = APIRouter(prefix="/search", tags=["search"])

try:
    import meilisearch as _meili
    _MEILI_AVAILABLE = True
except ImportError:
    _MEILI_AVAILABLE = False


def _meili_search(q: str) -> dict | None:
    """Search via Meilisearch. Returns None if unavailable or on error."""
    if not _MEILI_AVAILABLE or not settings.meili_master_key:
        return None
    try:
        client = _meili.Client(settings.meili_url, settings.meili_master_key)
        countries_res = client.index("countries").search(q, {
            "limit": 5,
            "sort": ["is_g20:desc", "name:asc"],
        })
        assets_res = client.index("assets").search(q, {
            "limit": 5,
            "filter": "is_active = true",
            "sort": ["market_cap_usd:desc"],
        })
        return {
            "countries": [
                {"code": h["code"], "name": h["name"], "flag": h.get("flag_emoji", ""), "type": "country"}
                for h in countries_res["hits"]
            ],
            "assets": [
                {
                    "symbol": h["symbol"],
                    "name": h["name"],
                    "sector": h.get("sector") or None,
                    "asset_type": h["asset_type"],
                    "type": "asset",
                }
                for h in assets_res["hits"]
            ],
        }
    except Exception:
        return None


def _pg_search(q: str, db: Session) -> dict:
    """Fallback: plain Postgres ilike search."""
    term = q.strip()[:100]
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


@router.get("")
def search(q: str = Query(default="", max_length=100), db: Session = Depends(get_db)) -> dict:
    if not q or len(q.strip()) < 2:
        return {"countries": [], "assets": []}

    result = _meili_search(q.strip())
    if result is not None:
        return result
    return _pg_search(q.strip(), db)
