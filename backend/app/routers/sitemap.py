"""
GET /sitemap.xml — served from FastAPI backend (no Cloudflare Bot Fight Mode).

Cloudflare Bot Fight Mode blocks Googlebot/Bingbot on the Pages origin
(metricshour.com), so robots.txt points here instead:
  Sitemap: https://api.metricshour.com/sitemap.xml

Generates the sitemap dynamically from the database, with Cache-Control so
Cloudflare caches it at the edge for 1 hour.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import select

from sqlalchemy.orm import aliased

from app.database import get_db
from app.models.asset import Asset
from app.models.country import Country, TradePair

router = APIRouter()

BASE = "https://metricshour.com"

STATIC_ROUTES = [
    (f"{BASE}/",             "1.0", "daily"),
    (f"{BASE}/markets",      "0.9", "daily"),
    (f"{BASE}/stocks",       "0.9", "daily"),
    (f"{BASE}/countries",    "0.9", "weekly"),
    (f"{BASE}/trade",        "0.9", "weekly"),
    (f"{BASE}/commodities",  "0.8", "daily"),
    (f"{BASE}/feed",         "0.7", "daily"),
    (f"{BASE}/pricing",      "0.6", "monthly"),
]


def _url(loc: str, priority: str, changefreq: str) -> str:
    return (
        f"  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        f"  </url>"
    )


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap(db: Session = Depends(get_db)):
    entries: list[str] = [_url(*r) for r in STATIC_ROUTES]

    # Assets → /stocks/{symbol}
    for (symbol,) in db.execute(select(Asset.symbol).where(Asset.symbol.isnot(None))):
        entries.append(_url(f"{BASE}/stocks/{symbol}", "0.7", "daily"))

    # Countries → /countries/{code}
    for (code,) in db.execute(select(Country.code).where(Country.code.isnot(None))):
        entries.append(_url(f"{BASE}/countries/{code.lower()}", "0.7", "weekly"))

    # Trade pairs → /trade/{exp}-{imp}
    Exporter = aliased(Country)
    Importer = aliased(Country)
    for (exp_code, imp_code) in db.execute(
        select(Exporter.code, Importer.code)
        .select_from(TradePair)
        .join(Exporter, TradePair.exporter_id == Exporter.id)
        .join(Importer, TradePair.importer_id == Importer.id)
        .distinct()
    ):
        if exp_code and imp_code:
            entries.append(_url(f"{BASE}/trade/{exp_code.lower()}-{imp_code.lower()}", "0.6", "monthly"))

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>"
    )

    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600, s-maxage=3600"},
    )
