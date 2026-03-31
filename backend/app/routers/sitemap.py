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

STATIC_ROUTE_TEMPLATES = [
    (f"{BASE}/",              "1.0", "daily"),
    (f"{BASE}/markets/",      "0.9", "daily"),
    (f"{BASE}/stocks/",       "0.9", "daily"),
    (f"{BASE}/sectors/",      "0.8", "weekly"),
    (f"{BASE}/countries/",    "0.9", "weekly"),
    (f"{BASE}/compare/",      "0.7", "weekly"),
    (f"{BASE}/trade/",        "0.9", "weekly"),
    (f"{BASE}/commodities/",  "0.8", "daily"),
    (f"{BASE}/indices/",      "0.7", "daily"),
    (f"{BASE}/feed/",         "0.8", "hourly"),
    (f"{BASE}/blog/",         "0.8", "weekly"),
    (f"{BASE}/faq/",          "0.6", "monthly"),
    (f"{BASE}/pricing/",      "0.7", "monthly"),
    (f"{BASE}/about/",        "0.6", "monthly"),
    (f"{BASE}/privacy/",      "0.3", "yearly"),
    (f"{BASE}/terms/",        "0.3", "yearly"),
]

SECTOR_SLUGS = [
    "technology", "healthcare", "financials", "industrials", "energy",
    "consumer-discretionary", "consumer-staples", "communication-services",
    "materials", "real-estate", "utilities",
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


@router.api_route("/sitemap.xml", methods=["GET", "HEAD"], include_in_schema=False)
def sitemap(db: Session = Depends(get_db)):
    # Compute today's date fresh per request so lastmod is never stale
    today = date.today().isoformat()

    # Pull actual last-updated timestamps from page_summaries so Google sees
    # accurate lastmod per URL instead of a bulk-same timestamp.
    # Key: (entity_type, entity_code) → "YYYY-MM-DD"
    lastmod_map: dict[tuple, str] = {}
    for row in db.execute(
        select(PageSummary.entity_type, PageSummary.entity_code, PageSummary.generated_at)
    ):
        lastmod_map[(row.entity_type, row.entity_code)] = row.generated_at.strftime("%Y-%m-%d")

    entries: list[str] = [_url(loc, pri, freq, today) for loc, pri, freq in STATIC_ROUTE_TEMPLATES]

    # Sector pages → /sectors/{slug}
    for slug in SECTOR_SLUGS:
        entries.append(_url(f"{BASE}/sectors/{slug}/", "0.7", "weekly", today))

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
        lm = lastmod_map.get(("stock_insight", symbol)) or lastmod_map.get(("stock", symbol)) or today
        entries.append(_url(f"{BASE}/stocks/{symbol.lower()}/", "0.7", "daily", lm))

    # Indices → /indices/{symbol}  (all active index assets)
    for (symbol,) in db.execute(
        select(Asset.symbol).where(
            Asset.asset_type == AssetType.index,
            Asset.is_active == True,
            Asset.symbol.isnot(None),
        )
    ):
        lm = lastmod_map.get(("index_insight", symbol)) or lastmod_map.get(("index", symbol)) or today
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
        lm = lastmod_map.get(("commodity_insight", symbol)) or lastmod_map.get(("commodity", symbol)) or today
        entries.append(_url(f"{BASE}/commodities/{symbol.lower()}/", "0.7", "daily", lm))

    # Countries → /countries/{code}
    # Only include countries that actually have indicator data (excludes ~19 placeholder rows)
    countries_with_data: set[int] = {
        row[0] for row in db.execute(
            select(CountryIndicator.country_id).distinct()
        )
    }
    for (country_id, code) in db.execute(
        select(Country.id, Country.code).where(Country.code.isnot(None))
    ):
        if country_id not in countries_with_data:
            continue
        lm = lastmod_map.get(("country_insight", code)) or lastmod_map.get(("country", code)) or today
        entries.append(_url(f"{BASE}/countries/{code.lower()}/", "0.7", "weekly", lm))

    # Trade pairs → /trade/{exp}-{imp}
    # DB stores both directions (A→B and B→A); include only one per relationship.
    # Only include pairs with ≥$1B trade volume — removes ~1,200 obscure micro-pairs
    # (e.g. Seychelles-Ireland, Senegal-Guinea-Bissau) that Google won't index due to
    # thin content and zero search demand. All economically significant relationships
    # (including Africa ↔ major economies) exceed this threshold.
    Exporter = aliased(Country)
    Importer = aliased(Country)
    seen_trade_pairs: set[tuple[str, str]] = set()
    for (exp_id, imp_id, exp_code, imp_code) in db.execute(
        select(TradePair.exporter_id, TradePair.importer_id, Exporter.code, Importer.code)
        .select_from(TradePair)
        .join(Exporter, TradePair.exporter_id == Exporter.id)
        .join(Importer, TradePair.importer_id == Importer.id)
        .where(TradePair.exports_usd >= 1_000_000_000)
        .distinct()
    ):
        if not exp_code or not imp_code:
            continue
        canonical_key = (min(exp_id, imp_id), max(exp_id, imp_id))
        if canonical_key in seen_trade_pairs:
            continue
        seen_trade_pairs.add(canonical_key)
        pair_code = f"{exp_code}-{imp_code}"
        rev_code = f"{imp_code}-{exp_code}"
        lm = (lastmod_map.get(("trade_insight", pair_code)) or lastmod_map.get(("trade", pair_code))
              or lastmod_map.get(("trade_insight", rev_code)) or lastmod_map.get(("trade", rev_code))
              or today)
        entries.append(_url(f"{BASE}/trade/{exp_code.lower()}-{imp_code.lower()}/", "0.6", "daily", lm))

    # Blog posts → /blog/{slug}/
    blog_posts = db.execute(
        select(BlogPost.slug, BlogPost.published_at, BlogPost.updated_at)
        .where(BlogPost.status == "published")  # BlogStatus.published
        .order_by(BlogPost.published_at.desc())
    ).all()
    for post in blog_posts:
        # Use whichever is more recent: updated_at or published_at
        dates = [d for d in (post.published_at, post.updated_at) if d is not None]
        lm = max(dates).date().isoformat() if dates else today
        entries.append(_url(f"{BASE}/blog/{post.slug}/", "0.8", "weekly", lm))

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
            entries.append(_url(f"{BASE}/compare/{a_lower}-vs-{b_lower}/", "0.5", "weekly", today))

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
            "Cache-Control": "public, max-age=3600, s-maxage=3600, stale-while-revalidate=86400",
        },
    )


@router.api_route("/robots.txt", methods=["GET", "HEAD"])
def robots_txt() -> Response:
    """Serve robots.txt from the API so Sitemap directive isn't overridden by Cloudflare managed content."""
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "\n"
        "# AI scrapers — no training, no generative AI input\n"
        "User-agent: GPTBot\n"
        "Disallow: /\n"
        "\n"
        "User-agent: ClaudeBot\n"
        "Disallow: /\n"
        "\n"
        "User-agent: Google-Extended\n"
        "Disallow: /\n"
        "\n"
        "User-agent: CCBot\n"
        "Disallow: /\n"
        "\n"
        "User-agent: Bytespider\n"
        "Disallow: /\n"
        "\n"
        f"Sitemap: https://api.metricshour.com/sitemap.xml\n"
    )
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Cache-Control": "public, max-age=86400"},
    )
