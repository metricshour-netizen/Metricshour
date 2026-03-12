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
from app.models.asset import Asset, AssetType, Price, StockCountryRevenue
from app.models.country import Country, TradePair, CountryIndicator
from app.models.summary import PageSummary
from app.models.feed import BlogPost

router = APIRouter()

BASE = "https://metricshour.com"

# lastmod = today for pages that update frequently, None for static pages
_TODAY = date.today().isoformat()

STATIC_ROUTES = [
    (f"{BASE}/",              "1.0", "daily",   _TODAY),
    (f"{BASE}/markets/",      "0.9", "daily",   _TODAY),
    (f"{BASE}/stocks/",       "0.9", "daily",   _TODAY),
    (f"{BASE}/countries/",    "0.9", "weekly",  _TODAY),
    (f"{BASE}/compare/",      "0.7", "weekly",  _TODAY),
    (f"{BASE}/trade/",        "0.9", "weekly",  _TODAY),
    (f"{BASE}/commodities/",  "0.8", "daily",   _TODAY),
    (f"{BASE}/feed/",         "0.8", "hourly",  _TODAY),
    (f"{BASE}/blog/",         "0.7", "weekly",  _TODAY),
    (f"{BASE}/pricing/",      "0.7", "monthly", _TODAY),
    (f"{BASE}/about/",        "0.6", "monthly", _TODAY),
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

    # Stocks → /stocks/{symbol} — only stocks with price OR revenue data (avoid thin content)
    stocks_with_prices = {
        row[0] for row in db.execute(
            select(Asset.symbol)
            .join(Price, Price.asset_id == Asset.id)
            .where(Asset.asset_type == AssetType.stock, Asset.is_active == True)
            .distinct()
        )
    }
    stocks_with_revenue = {
        row[0] for row in db.execute(
            select(Asset.symbol)
            .join(StockCountryRevenue, StockCountryRevenue.asset_id == Asset.id)
            .where(Asset.asset_type == AssetType.stock, Asset.is_active == True)
            .distinct()
        )
    }
    stocks_with_content = stocks_with_prices | stocks_with_revenue
    for (symbol,) in db.execute(
        select(Asset.symbol).where(
            Asset.symbol.isnot(None),
            Asset.asset_type == AssetType.stock,
            Asset.is_active == True,
        )
    ):
        if symbol not in stocks_with_content:
            continue  # skip stocks with no price + no revenue data — thin content
        lm = lastmod_map.get(("stock_insight", symbol)) or lastmod_map.get(("stock", symbol))
        entries.append(_url(f"{BASE}/stocks/{symbol.lower()}/", "0.7", "daily", lm))

    # Indices → /indices/{symbol}  (all active index assets)
    for (symbol,) in db.execute(
        select(Asset.symbol).where(
            Asset.asset_type == AssetType.index,
            Asset.is_active == True,
            Asset.symbol.isnot(None),
        )
    ):
        lm = lastmod_map.get(("index_insight", symbol)) or lastmod_map.get(("index", symbol)) or _TODAY
        entries.append(_url(f"{BASE}/indices/{symbol.lower()}/", "0.6", "daily", lm))

    # Commodities → /commodities/{symbol}  (only those with actual price data)
    commodity_symbols_with_prices = {
        row[0] for row in db.execute(
            select(Asset.symbol)
            .join(Price, Price.asset_id == Asset.id)
            .where(Asset.asset_type == AssetType.commodity, Asset.is_active == True)
            .distinct()
        )
    }
    for (symbol,) in db.execute(
        select(Asset.symbol).where(
            Asset.asset_type == AssetType.commodity,
            Asset.is_active == True,
            Asset.symbol.isnot(None),
        )
    ):
        if symbol not in commodity_symbols_with_prices:
            continue  # skip commodities with no price data — thin content penalty risk
        entries.append(_url(f"{BASE}/commodities/{symbol.lower()}/", "0.7", "daily", _TODAY))

    # Countries → /countries/{code}
    for (code,) in db.execute(select(Country.code).where(Country.code.isnot(None))):
        lm = lastmod_map.get(("country_insight", code)) or lastmod_map.get(("country", code))
        entries.append(_url(f"{BASE}/countries/{code.lower()}/", "0.7", "weekly", lm))

    # Trade pairs → /trade/{exp}-{imp}
    # DB stores both directions (A→B and B→A); include only one per relationship.
    # Only include pairs with actual bilateral data (exports_usd populated) to avoid thin-content pages.
    Exporter = aliased(Country)
    Importer = aliased(Country)
    seen_trade_pairs: set[tuple[str, str]] = set()
    for (exp_id, imp_id, exp_code, imp_code) in db.execute(
        select(TradePair.exporter_id, TradePair.importer_id, Exporter.code, Importer.code)
        .select_from(TradePair)
        .join(Exporter, TradePair.exporter_id == Exporter.id)
        .join(Importer, TradePair.importer_id == Importer.id)
        .where(TradePair.exports_usd.isnot(None))
        .distinct()
    ):
        if not exp_code or not imp_code:
            continue
        canonical_key = (min(exp_id, imp_id), max(exp_id, imp_id))
        if canonical_key in seen_trade_pairs:
            continue
        seen_trade_pairs.add(canonical_key)
        pair_code = f"{exp_code}-{imp_code}"
        lm = lastmod_map.get(("trade_insight", pair_code)) or lastmod_map.get(("trade", pair_code))
        entries.append(_url(f"{BASE}/trade/{exp_code.lower()}-{imp_code.lower()}/", "0.6", "daily", lm))

    # Blog posts → /blog/{slug}/
    blog_posts = db.execute(
        select(BlogPost.slug, BlogPost.published_at)
        .where(BlogPost.status == "published")  # BlogStatus.published
        .order_by(BlogPost.published_at.desc())
    ).all()
    for post in blog_posts:
        lm = post.published_at.date().isoformat() if post.published_at else _TODAY
        entries.append(_url(f"{BASE}/blog/{post.slug}/", "0.7", "monthly", lm))

    # Compare pages → /compare/{a}-vs-{b}
    # Only include pairs where BOTH countries have GDP data (avoids thin content).
    # Canonical order: alphabetically by country code (matches frontend redirect logic).
    countries_with_gdp: set[str] = {
        row[0] for row in db.execute(
            select(Country.code)
            .join(CountryIndicator, CountryIndicator.country_id == Country.id)
            .where(CountryIndicator.indicator == "gdp_usd", Country.code.isnot(None))
            .distinct()
        )
    }
    # Emit G20 × G20 pairs only (380 pairs max) — broad enough for long-tail, tight enough to avoid spam
    g20_with_gdp = [
        code for (code,) in db.execute(
            select(Country.code).where(Country.is_g20 == True, Country.code.isnot(None))
        )
        if code in countries_with_gdp
    ]
    seen_compare: set[tuple[str, str]] = set()
    for i, ca in enumerate(sorted(g20_with_gdp)):
        for cb in sorted(g20_with_gdp)[i + 1:]:
            key = (min(ca, cb), max(ca, cb))
            if key in seen_compare:
                continue
            seen_compare.add(key)
            a_lower, b_lower = key[0].lower(), key[1].lower()
            entries.append(_url(f"{BASE}/compare/{a_lower}-vs-{b_lower}/", "0.5", "weekly", _TODAY))

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
