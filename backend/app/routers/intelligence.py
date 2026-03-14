"""
Intelligence router.

GET /api/intelligence/spotlight  — adaptive insight cards (3-hr Redis cache)
GET /api/summaries/{entity_type}/{entity_code}  — page summary (50-100 words)
POST /api/summaries/refresh  — internal: trigger summary regeneration (admin only)
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.limiter import limiter

from app.config import settings
from app.database import get_db
from app.models.asset import Asset, StockCountryRevenue
from app.models.country import Country, CountryIndicator, TradePair
from app.models.summary import PageSummary, PageInsight
from app.routers.auth import get_admin_user
from app.storage import get_redis

log = logging.getLogger(__name__)
router = APIRouter()

SPOTLIGHT_KEY_TPL = "intelligence:spotlight:v2:{hour}"
SPOTLIGHT_TTL = 4_200  # 70 min


# ── Spotlight generation ───────────────────────────────────────────────────────

SPOTLIGHT_KEY = "intelligence:spotlight:v2:{hour}"
SPOTLIGHT_TTL = 4_200  # 70 min — covers hour boundary cleanly


def _build_spotlight(db: Session) -> list[dict[str, Any]]:
    """
    Build adaptive spotlight cards from multiple data sources.
    Hour-seeded shuffle ensures different ordering each hour.
    """
    import random as _rnd
    now = datetime.now(timezone.utc)
    hour_seed = int(now.strftime('%Y%m%d%H'))
    rng = _rnd.Random(hour_seed)

    cards: list[dict[str, Any]] = []

    # ── 1. AI insights from page_insights ─────────────────────────────────
    insight_rows = db.execute(text("""
        SELECT pi.entity_type, pi.entity_code, pi.summary, pi.generated_at,
               COALESCE(a.market_cap_usd, 0) AS market_cap,
               COALESCE(c.is_g20, FALSE) AS is_g20
        FROM page_insights pi
        LEFT JOIN assets a ON pi.entity_type = 'stock'
                           AND a.symbol = pi.entity_code
                           AND a.asset_type = 'stock'
        LEFT JOIN countries c ON pi.entity_type = 'country'
                              AND c.code = pi.entity_code
        WHERE pi.generated_at >= NOW() - INTERVAL '72 hours'
          AND pi.entity_type IN ('stock', 'country', 'trade', 'commodity')
          AND pi.summary IS NOT NULL
        ORDER BY pi.generated_at DESC
        LIMIT 400
    """)).fetchall()

    by_type: dict[str, list] = {}
    for row in insight_rows:
        by_type.setdefault(row.entity_type, []).append(row)

    def _first_sentence(text: str, max_len: int = 130) -> str:
        import re as _re
        m = _re.search(r'\. [A-Z]', text)
        s = (text[:m.start() + 1] if m else text.split('\n')[0]).strip()
        return s[:max_len - 3] + '...' if len(s) > max_len else s

    def _insight_card(row: Any) -> dict:
        s = _first_sentence(row.summary or '')
        if row.entity_type == 'stock':
            return {'id': f'ins-stock-{row.entity_code.lower()}',
                    'type': 'stock_insight', 'tag': row.entity_code,
                    'dot': '#10b981', 'border': '#064e3b',
                    'text': s, 'subtext': 'AI · Stock Analysis',
                    'link': f'/stocks/{row.entity_code.lower()}',
                    'generated_at': row.generated_at.isoformat()}
        if row.entity_type == 'country':
            return {'id': f'ins-country-{row.entity_code.lower()}',
                    'type': 'country_insight', 'tag': row.entity_code,
                    'dot': '#60a5fa', 'border': '#1e3a5f',
                    'text': s, 'subtext': 'AI · Macro Analysis',
                    'link': f'/countries/{row.entity_code.lower()}',
                    'generated_at': row.generated_at.isoformat()}
        if row.entity_type == 'trade':
            parts = row.entity_code.split('-')
            slug = row.entity_code.lower()
            tag = f'{parts[0]}↔{parts[1]}' if len(parts) == 2 else row.entity_code
            return {'id': f'ins-trade-{slug}',
                    'type': 'trade_insight', 'tag': tag,
                    'dot': '#f59e0b', 'border': '#78350f',
                    'text': s, 'subtext': 'AI · Trade Analysis',
                    'link': f'/trade/{slug}',
                    'generated_at': row.generated_at.isoformat()}
        if row.entity_type == 'commodity':
            return {'id': f'ins-comm-{row.entity_code.lower()}',
                    'type': 'commodity_insight', 'tag': row.entity_code,
                    'dot': '#a78bfa', 'border': '#4c1d95',
                    'text': s, 'subtext': 'AI · Commodity Analysis',
                    'link': f'/commodities/{row.entity_code.lower()}',
                    'generated_at': row.generated_at.isoformat()}
        return {}

    type_quotas = {'stock': 6, 'country': 6, 'trade': 6, 'commodity': 3}
    for t, quota in type_quotas.items():
        pool = by_type.get(t, [])
        if t == 'stock':
            pool = sorted(pool, key=lambda r: r.market_cap or 0, reverse=True)[:40]
        elif t == 'country':
            g20 = [r for r in pool if r.is_g20]
            rest = [r for r in pool if not r.is_g20]
            pool = g20[:30] + rest[:10]
        else:
            pool = pool[:60]
        if pool:
            picked = rng.sample(pool, min(quota, len(pool)))
            cards.extend([c for c in (_insight_card(r) for r in picked) if c])

    # ── 2. Geo revenue cards ───────────────────────────────────────────────
    geo_rows = db.execute(text("""
        SELECT a.symbol, r.revenue_pct, r.fiscal_year,
               hq.flag_emoji AS hq_flag,
               c.name AS country_name, c.flag_emoji AS country_flag,
               c.code AS country_code
        FROM stock_country_revenues r
        JOIN assets a ON r.asset_id = a.id
        JOIN countries c ON r.country_id = c.id
        LEFT JOIN countries hq ON a.country_id = hq.id
        WHERE r.revenue_pct >= 8.0
          AND a.asset_type = 'stock'
          AND a.market_cap_usd >= 5e9
        ORDER BY a.market_cap_usd DESC
        LIMIT 80
    """)).fetchall()

    seen_geo: set[str] = set()
    geo_pool: list[dict] = []
    for row in geo_rows:
        key = f'{row.symbol}-{row.country_code}'
        if key in seen_geo:
            continue
        seen_geo.add(key)
        geo_pool.append({
            'id': f'geo-{row.symbol.lower()}-{row.country_code.lower()}',
            'type': 'geo_revenue', 'tag': row.symbol,
            'dot': '#10b981', 'border': '#064e3b',
            'text': f'{row.symbol} earns {row.revenue_pct:.0f}% revenue from {row.country_flag or ""} {row.country_name}',
            'subtext': f'FY{row.fiscal_year} · SEC EDGAR',
            'link': f'/stocks/{row.symbol.lower()}',
            'generated_at': datetime.now(timezone.utc).isoformat(),
        })
    if geo_pool:
        cards.extend(rng.sample(geo_pool, min(4, len(geo_pool))))

    # ── 3. Macro signals ───────────────────────────────────────────────────
    macro_rows = db.execute(text("""
        SELECT DISTINCT ON (c.code, ci.indicator)
               c.name, c.flag_emoji, c.code,
               ci.indicator, ci.value, ci.period_date
        FROM country_indicators ci
        JOIN countries c ON ci.country_id = c.id
        WHERE c.is_g20 = true
          AND ci.indicator IN ('gdp_growth_pct', 'inflation_pct', 'interest_rate_pct')
          AND ci.value IS NOT NULL
        ORDER BY c.code, ci.indicator, ci.period_date DESC
    """)).fetchall()

    macro_pool: list[dict] = []
    for row in macro_rows:
        if row.indicator == 'gdp_growth_pct':
            if abs(row.value) < 1.0:
                continue
            text_str = f'{row.flag_emoji or ""} {row.name} GDP growth {row.value:+.1f}%'
            dot, border = '#10b981', '#064e3b'
        elif row.indicator == 'inflation_pct':
            if row.value < 3.5:
                continue
            text_str = f'{row.flag_emoji or ""} {row.name} inflation {row.value:.1f}%'
            dot, border = '#f59e0b', '#78350f'
        elif row.indicator == 'interest_rate_pct':
            if row.value < 4.0:
                continue
            text_str = f'{row.flag_emoji or ""} {row.name} rate {row.value:.2f}%'
            dot, border = '#60a5fa', '#1e3a5f'
        else:
            continue
        macro_pool.append({
            'id': f'macro-{row.code.lower()}-{row.indicator}',
            'type': 'macro', 'tag': row.code,
            'dot': dot, 'border': border,
            'text': text_str,
            'subtext': f'World Bank · {row.period_date.year if row.period_date else "latest"}',
            'link': f'/countries/{row.code.lower()}',
            'generated_at': datetime.now(timezone.utc).isoformat(),
        })
    if macro_pool:
        cards.extend(rng.sample(macro_pool, min(3, len(macro_pool))))

    # ── Final shuffle + cap ────────────────────────────────────────────────
    rng.shuffle(cards)
    return cards[:24]




# ── Summary generation ─────────────────────────────────────────────────────────

def _country_summary(code: str, db: Session) -> str | None:
    country = db.query(Country).filter(Country.code == code.upper()).first()
    if not country:
        return None

    # Fetch latest indicators
    indicators: dict[str, float] = {}
    rows = (
        db.query(CountryIndicator)
        .filter(CountryIndicator.country_id == country.id)
        .filter(CountryIndicator.indicator.in_([
            "gdp_usd", "gdp_growth_pct", "inflation_pct",
            "interest_rate_pct", "unemployment_pct", "population",
        ]))
        .order_by(CountryIndicator.period_date.desc())
        .limit(30)
        .all()
    )
    seen_ind: set[str] = set()
    for r in rows:
        if r.indicator not in seen_ind:
            indicators[r.indicator] = r.value
            seen_ind.add(r.indicator)

    gdp = indicators.get("gdp_usd")
    growth = indicators.get("gdp_growth_pct")
    inflation = indicators.get("inflation_pct")
    rate = indicators.get("interest_rate_pct")
    unemployment = indicators.get("unemployment_pct")

    def fmt_gdp(v: float | None) -> str:
        if v is None:
            return "N/A"
        if v >= 1e12:
            return f"${v/1e12:.1f}T"
        if v >= 1e9:
            return f"${v/1e9:.0f}B"
        return f"${v/1e6:.0f}M"

    groups = []
    if country.is_g7:
        groups.append("G7")
    if country.is_g20:
        groups.append("G20")
    if country.is_eu:
        groups.append("EU")
    if country.is_nato:
        groups.append("NATO")
    if country.is_brics:
        groups.append("BRICS")
    if country.is_opec:
        groups.append("OPEC")
    group_str = ", ".join(groups[:3]) if groups else "the UN"

    # Infer development status if not explicitly set
    dev_label = country.development_status
    if not dev_label:
        if country.is_g7 or country.is_oecd or country.income_level == "high":
            dev_label = "developed"
        elif country.income_level in ("low", "lower_middle"):
            dev_label = "developing"
        else:
            dev_label = "emerging"

    parts = [
        f"{country.name} ({country.code}) is a {dev_label} economy"
        f" with a GDP of {fmt_gdp(gdp)}.",
    ]
    if growth is not None:
        parts.append(f"GDP growth stands at {growth:.1f}%")
        if inflation is not None:
            parts[-1] += f" with inflation at {inflation:.1f}%."
        else:
            parts[-1] += "."
    if rate is not None:
        parts.append(f"The central bank interest rate is {rate:.2f}%.")
    if unemployment is not None:
        parts.append(f"Unemployment is {unemployment:.1f}%.")
    parts.append(
        f"A member of {group_str}, {country.name} uses the {country.currency_name or country.currency_code or 'local currency'}."
    )

    return " ".join(parts)


def _stock_summary(symbol: str, db: Session) -> str | None:
    asset = db.query(Asset).filter(Asset.symbol == symbol.upper()).first()
    if not asset:
        return None

    hq_country = db.query(Country).filter(Country.id == asset.country_id).first() if asset.country_id else None

    def fmt_cap(v: float | None) -> str:
        if v is None:
            return "N/A"
        if v >= 1e12:
            return f"${v/1e12:.1f}T"
        if v >= 1e9:
            return f"${v/1e9:.0f}B"
        return f"${v/1e6:.0f}M"

    revenues = (
        db.query(StockCountryRevenue, Country)
        .join(Country, StockCountryRevenue.country_id == Country.id)
        .filter(StockCountryRevenue.asset_id == asset.id)
        .order_by(StockCountryRevenue.revenue_pct.desc())
        .limit(5)
        .all()
    )

    hq_str = f" headquartered in {hq_country.name}" if hq_country else ""
    parts = [
        f"{asset.name} ({asset.symbol}) is a {fmt_cap(asset.market_cap_usd)} market cap"
        f" {asset.sector or 'company'}{hq_str}.",
    ]

    if revenues:
        top_rev, top_country = revenues[0]
        parts.append(
            f"It derives {top_rev.revenue_pct:.0f}% of revenue from"
            f" {top_country.flag_emoji or ''} {top_country.name}"
            f" (FY{top_rev.fiscal_year} · SEC EDGAR)."
        )
        if len(revenues) >= 2:
            second_rev, second_country = revenues[1]
            parts.append(
                f"The second-largest market is {second_country.name}"
                f" at {second_rev.revenue_pct:.0f}%."
            )

    return " ".join(parts)


def _commodity_summary(symbol: str, db: Session) -> str | None:
    asset = db.query(Asset).filter(
        Asset.symbol == symbol.upper(), Asset.asset_type == "commodity"
    ).first()
    if not asset:
        return None
    # Simple template fallback for on-the-fly (full AI version runs via Celery)
    return (
        f"{asset.name} ({asset.symbol}) is a globally traded commodity tracked on MetricsHour. "
        f"Price history, supply and demand dynamics, and related macro indicators are "
        f"updated continuously from market data providers."
    )


def _index_summary(symbol: str, db: Session) -> str | None:
    asset = db.query(Asset).filter(
        Asset.symbol == symbol.upper(), Asset.asset_type == "index"
    ).first()
    if not asset:
        return None
    region = asset.sector or "global"
    return (
        f"{asset.name} ({asset.symbol}) is a major {region} stock market index tracked on MetricsHour. "
        f"It reflects the aggregate performance of its constituent companies and is a key benchmark "
        f"for institutional and retail investors. Price history, daily changes, and related macro data "
        f"are updated from market data providers."
    )


def _trade_summary(pair: str, db: Session) -> str | None:
    parts = pair.upper().split("-")
    if len(parts) != 2:
        return None
    code_a, code_b = parts

    country_a = db.query(Country).filter(Country.code == code_a).first()
    country_b = db.query(Country).filter(Country.code == code_b).first()
    if not country_a or not country_b:
        return None

    trade = (
        db.query(TradePair)
        .filter(TradePair.exporter_id == country_a.id)
        .filter(TradePair.importer_id == country_b.id)
        .order_by(TradePair.year.desc())
        .first()
    )
    if not trade:
        # Try reverse direction
        trade = (
            db.query(TradePair)
            .filter(TradePair.exporter_id == country_b.id)
            .filter(TradePair.importer_id == country_a.id)
            .order_by(TradePair.year.desc())
            .first()
        )
        if trade:
            country_a, country_b = country_b, country_a

    if not trade:
        return (
            f"{country_a.name} and {country_b.name} are bilateral trade partners tracked by MetricsHour."
            f" Trade data is sourced from WTO and IMF reports."
        )

    def fmt_usd(v: float | None) -> str:
        if v is None:
            return "N/A"
        if abs(v) >= 1e12:
            return f"${abs(v)/1e12:.1f}T"
        if abs(v) >= 1e9:
            return f"${abs(v)/1e9:.0f}B"
        return f"${abs(v)/1e6:.0f}M"

    balance_word = "surplus" if (trade.balance_usd or 0) >= 0 else "deficit"
    products: list[str] = []
    if trade.top_export_products:
        products = [p.get("name", "") for p in trade.top_export_products[:3] if p.get("name")]

    parts_text = [
        f"{country_a.name} exported {fmt_usd(trade.exports_usd)} to {country_b.name}"
        f" in {trade.year}, running a {fmt_usd(trade.balance_usd)} {balance_word}.",
    ]
    if products:
        parts_text.append(f"Top exports include {', '.join(products)}.")
    if trade.exporter_gdp_share_pct:
        parts_text.append(
            f"Bilateral trade represents {trade.exporter_gdp_share_pct:.1f}%"
            f" of {country_a.name}'s GDP."
        )

    return " ".join(parts_text)


# ── API endpoints ──────────────────────────────────────────────────────────────

@router.get("/intelligence/spotlight")
@limiter.limit("30/minute")
def get_spotlight(
    request: Request,
    db: Session = Depends(get_db),
    country: str | None = None,  # ISO2 code hint from frontend (e.g. "US")
) -> list[dict]:
    """
    Returns adaptive insight cards — cached per hour, personalised by visitor country.
    Falls back to live DB generation if Redis unavailable.
    """
    import random as _rnd

    now = datetime.now(timezone.utc)
    hour = now.strftime('%Y%m%d%H')
    # Country suffix makes cache per-region (top 10 countries; rest share "default")
    country_key = (country or '').upper()[:2] or 'default'
    cache_key = SPOTLIGHT_KEY_TPL.format(hour=hour) + f':{country_key}'

    try:
        r = get_redis()
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        log.warning("Redis unavailable for spotlight read — falling back to DB")

    cards = _build_spotlight(db)

    # ── Location personalisation ─────────────────────────────────────────────
    # Boost cards related to the visitor's country to the front
    if country_key not in ('', 'default'):
        cc = country_key.lower()
        related = [c for c in cards if
                   cc in c.get('id', '') or
                   cc in c.get('link', '') or
                   cc in c.get('tag', '').lower()]
        rest = [c for c in cards if c not in related]
        cards = related[:4] + rest  # put up to 4 local cards first

    # ── Time-of-day weighting ────────────────────────────────────────────────
    # During US market hours (13–21 UTC) boost stock insights to front
    # During Asian hours (00–08 UTC) boost APAC country/trade cards
    hour_int = now.hour
    if 13 <= hour_int <= 21:
        # US market hours — push stock_insight and geo_revenue forward
        stock_cards = [c for c in cards if c.get('type') in ('stock_insight', 'geo_revenue')]
        other = [c for c in cards if c not in stock_cards]
        rng2 = _rnd.Random(int(hour) + 1)
        rng2.shuffle(other)
        cards = stock_cards[:6] + other
    elif 0 <= hour_int <= 8:
        # Asian hours — push APAC country/trade cards forward
        apac = {'CN', 'JP', 'KR', 'AU', 'IN', 'SG', 'HK', 'TW', 'ID', 'TH'}
        apac_cards = [c for c in cards if any(cc in c.get('id', '').upper() for cc in apac)]
        other = [c for c in cards if c not in apac_cards]
        rng2 = _rnd.Random(int(hour) + 2)
        rng2.shuffle(other)
        cards = apac_cards[:5] + other

    try:
        r = get_redis()
        r.setex(cache_key, SPOTLIGHT_TTL, json.dumps(cards))
    except Exception:
        log.warning("Redis unavailable for spotlight write")

    return cards


SUMMARY_TYPES = ("country", "stock", "commodity", "trade", "index")
INSIGHT_TYPES = ("country_insight", "stock_insight", "commodity_insight", "trade_insight", "index_insight")
ALL_ENTITY_TYPES = SUMMARY_TYPES + INSIGHT_TYPES


@router.get("/summaries/{entity_type}/{entity_code}")
@limiter.limit("60/minute")
def get_summary(request: Request, entity_type: str, entity_code: str, db: Session = Depends(get_db)) -> dict:
    """
    Returns page summary or daily insight. Reads from page_summaries table.
    For summaries: on-the-fly fallback generation if not cached.
    For insights: returns 404 if not yet generated (generated by daily Celery task).
    entity_type: country | stock | commodity | trade | country_insight | stock_insight | commodity_insight
    """
    entity_type = entity_type.lower()
    entity_code = entity_code.upper()

    if entity_type not in ALL_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"entity_type must be one of: {', '.join(ALL_ENTITY_TYPES)}"
        )

    existing = (
        db.query(PageSummary)
        .filter(PageSummary.entity_type == entity_type)
        .filter(PageSummary.entity_code == entity_code)
        .first()
    )
    if existing:
        return {
            "entity_type": entity_type,
            "entity_code": entity_code,
            "summary": existing.summary,
            "generated_at": existing.generated_at.isoformat(),
        }

    # Insights are only available after the daily Celery task runs — don't generate on-the-fly
    if entity_type in INSIGHT_TYPES:
        raise HTTPException(status_code=404, detail="Insight not yet generated — check back after 5am UTC")

    # Generate summary on-the-fly and persist
    summary_text: str | None = None
    if entity_type == "country":
        summary_text = _country_summary(entity_code, db)
    elif entity_type == "stock":
        summary_text = _stock_summary(entity_code, db)
    elif entity_type == "commodity":
        summary_text = _commodity_summary(entity_code, db)
    elif entity_type == "index":
        summary_text = _index_summary(entity_code, db)
    elif entity_type == "trade":
        summary_text = _trade_summary(entity_code, db)

    if not summary_text:
        raise HTTPException(status_code=404, detail="Entity not found")

    now = datetime.now(timezone.utc)
    record = PageSummary(
        entity_type=entity_type,
        entity_code=entity_code,
        summary=summary_text,
        generated_at=now,
    )
    db.add(record)
    db.commit()

    return {
        "entity_type": entity_type,
        "entity_code": entity_code,
        "summary": summary_text,
        "generated_at": now.isoformat(),
    }


INSIGHT_ENTITY_TYPES = ("country", "stock", "commodity", "trade", "index")


@router.get("/insights/{entity_type}/{entity_code}")
@limiter.limit("60/minute")
def get_insights(
    request: Request,
    entity_type: str,
    entity_code: str,
    limit: int = 30,
    db: Session = Depends(get_db),
) -> list:
    """
    Returns most recent insights for an entity, most recent first.
    Default limit=2 (today + yesterday). Pass limit=N for admin/API use.
    entity_type: country | stock | commodity | trade | index
    """
    entity_type = entity_type.lower()
    entity_code = entity_code.upper()
    limit = max(1, min(limit, 90))  # clamp 1–90

    if entity_type not in INSIGHT_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"entity_type must be one of: {', '.join(INSIGHT_ENTITY_TYPES)}"
        )

    rows = (
        db.query(PageInsight)
        .filter(PageInsight.entity_type == entity_type)
        .filter(PageInsight.entity_code == entity_code)
        .order_by(PageInsight.generated_at.desc())
        .limit(limit)
        .all()
    )
    return [{"summary": r.summary, "generated_at": r.generated_at.isoformat()} for r in rows]


@router.post("/summaries/refresh")
def refresh_summaries(
    entity_type: str | None = None,
    _admin=Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    """Admin: delete cached summaries/insights so they regenerate. Pass entity_type to scope deletion."""
    q = db.query(PageSummary)
    if entity_type:
        q = q.filter(PageSummary.entity_type == entity_type)
    deleted = q.delete()
    db.commit()

    try:
        # Clear all v2 spotlight keys (hour-based)
        for key in get_redis().scan_iter("intelligence:spotlight:v2:*"):
            get_redis().delete(key)
    except Exception:
        pass

    return {"deleted": deleted, "spotlight_cleared": True, "note": "Summaries regenerate at 2am UTC; insights at 5am UTC"}
