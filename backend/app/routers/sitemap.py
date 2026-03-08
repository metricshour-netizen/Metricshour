"""
GET /sitemap.xml — served from FastAPI backend (no Cloudflare Bot Fight Mode).

Cloudflare Bot Fight Mode blocks Googlebot/Bingbot on the Pages origin
(metricshour.com), so robots.txt points here instead:
  Sitemap: https://api.metricshour.com/sitemap.xml

Generates the sitemap dynamically from the database, with Cache-Control so
Cloudflare caches it at the edge for 1 hour.
"""
from datetime import date
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import select

from sqlalchemy.orm import aliased

from app.database import get_db
from app.models.asset import Asset
from app.models.country import Country, TradePair
from app.models.summary import PageSummary

router = APIRouter()

BASE = "https://metricshour.com"

# lastmod = today for pages that update frequently, None for static pages
_TODAY = date.today().isoformat()

STATIC_ROUTES = [
    (f"{BASE}/",              "1.0", "daily",   _TODAY),
    (f"{BASE}/markets/",      "0.9", "daily",   _TODAY),
    (f"{BASE}/stocks/",       "0.9", "daily",   _TODAY),
    (f"{BASE}/countries/",    "0.9", "weekly",  _TODAY),
    (f"{BASE}/trade/",        "0.9", "weekly",  _TODAY),
    (f"{BASE}/commodities/",  "0.8", "daily",   _TODAY),
    (f"{BASE}/pricing/",      "0.7", "monthly", None),
    (f"{BASE}/about/",        "0.6", "monthly", None),
]


def _url(loc: str, priority: str, changefreq: str, lastmod: str | None = None) -> str:
    lastmod_tag = f"    <lastmod>{lastmod}</lastmod>\n" if lastmod else ""
    return (
        f"  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"{lastmod_tag}"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        f"  </url>"
    )


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap(db: Session = Depends(get_db)):
    # Pull actual last-updated timestamps from page_summaries so Google sees
    # accurate lastmod per URL instead of a bulk-same timestamp.
    # Key: (entity_type, entity_code) → "YYYY-MM-DD"
    lastmod_map: dict[tuple, str] = {}
    for row in db.execute(
        select(PageSummary.entity_type, PageSummary.entity_code, PageSummary.generated_at)
    ):
        lastmod_map[(row.entity_type, row.entity_code)] = row.generated_at.strftime("%Y-%m-%d")

    entries: list[str] = [_url(loc, pri, freq, lm) for loc, pri, freq, lm in STATIC_ROUTES]

    # Assets → /stocks/{symbol}
    for (symbol,) in db.execute(select(Asset.symbol).where(Asset.symbol.isnot(None))):
        # Use the insight timestamp if available, else summary
        lm = lastmod_map.get(("stock_insight", symbol)) or lastmod_map.get(("stock", symbol))
        entries.append(_url(f"{BASE}/stocks/{symbol}/", "0.7", "daily", lm))

    # Countries → /countries/{code}
    for (code,) in db.execute(select(Country.code).where(Country.code.isnot(None))):
        lm = lastmod_map.get(("country_insight", code)) or lastmod_map.get(("country", code))
        entries.append(_url(f"{BASE}/countries/{code.lower()}/", "0.7", "weekly", lm))

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
            pair_code = f"{exp_code}-{imp_code}"
            lm = lastmod_map.get(("trade_insight", pair_code)) or lastmod_map.get(("trade", pair_code))
            entries.append(_url(f"{BASE}/trade/{exp_code.lower()}-{imp_code.lower()}/", "0.6", "daily", lm))

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>"
    )

    return Response(
        content=xml,
        media_type="application/xml",
        headers={
            "Content-Type": "application/xml; charset=utf-8",
            "Cache-Control": "public, max-age=3600, s-maxage=3600",
        },
    )
