"""
Intelligence router.

GET /api/intelligence/spotlight  — adaptive insight cards (3-hr Redis cache)
GET /api/summaries/{entity_type}/{entity_code}  — page summary (50-100 words)
POST /api/summaries/refresh  — internal: trigger summary regeneration (admin only)
"""
import json
import logging
import ssl
from datetime import datetime, timezone
from typing import Any

import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.asset import Asset, StockCountryRevenue
from app.models.country import Country, CountryIndicator, TradePair
from app.models.summary import PageSummary
from app.routers.auth import get_admin_user

log = logging.getLogger(__name__)
router = APIRouter()

SPOTLIGHT_KEY = "intelligence:spotlight:v1"
SPOTLIGHT_TTL = 10_800  # 3 hours


# ── Redis helper ───────────────────────────────────────────────────────────────

def _redis():
    return redis_lib.from_url(
        settings.redis_url,
        ssl_cert_reqs=ssl.CERT_NONE,
        decode_responses=True,
    )


# ── Spotlight generation ───────────────────────────────────────────────────────

def _build_spotlight(db: Session) -> list[dict[str, Any]]:
    """
    Build adaptive spotlight cards from live DB data.
    Returns up to 8 cards ordered by revenue_pct DESC.
    """
    rows = (
        db.execute(
            text("""
                SELECT
                    a.symbol, a.name, a.sector, a.market_cap_usd,
                    r.revenue_pct, r.fiscal_year,
                    hq.flag_emoji AS hq_flag, hq.code AS hq_code,
                    c.name AS country_name, c.flag_emoji AS country_flag, c.code AS country_code
                FROM stock_country_revenues r
                JOIN assets a ON r.asset_id = a.id
                JOIN countries c ON r.country_id = c.id
                LEFT JOIN countries hq ON a.country_id = hq.id
                WHERE r.revenue_pct >= 5.0
                  AND a.asset_type = 'stock'
                ORDER BY r.revenue_pct DESC
                LIMIT 40
            """)
        ).fetchall()
    )

    seen: set[str] = set()
    cards = []
    for row in rows:
        key = f"{row.symbol}-{row.country_code}"
        if key in seen:
            continue
        seen.add(key)

        cards.append({
            "id": f"geo-{row.symbol.lower()}-{row.country_code.lower()}",
            "type": "geo_revenue",
            "text": f"{row.symbol} earns {row.revenue_pct:.0f}% revenue from {row.country_flag or ''} {row.country_name}",
            "subtext": f"FY{row.fiscal_year} · SEC EDGAR",
            "flag_hq": row.hq_flag or "🌐",
            "flag_country": row.country_flag or "",
            "symbol": row.symbol,
            "country_code": row.country_code.lower(),
            "revenue_pct": round(row.revenue_pct, 1),
            "link": f"/stocks/{row.symbol}",
            "link_country": f"/countries/{row.country_code.lower()}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })

        if len(cards) >= 8:
            break

    return cards


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
        .filter(CountryIndicator.indicator_name.in_([
            "gdp_usd", "gdp_growth_pct", "inflation_pct",
            "interest_rate_pct", "unemployment_pct", "population",
        ]))
        .order_by(CountryIndicator.year.desc())
        .limit(30)
        .all()
    )
    seen_ind: set[str] = set()
    for r in rows:
        if r.indicator_name not in seen_ind:
            indicators[r.indicator_name] = r.value
            seen_ind.add(r.indicator_name)

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

    parts = [
        f"{country.name} ({country.code}) is a {country.development_status or 'developing'} economy"
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
def get_spotlight(db: Session = Depends(get_db)) -> list[dict]:
    """
    Returns adaptive insight cards. Cached in Redis for 3 hours.
    Falls back to live DB generation if Redis unavailable.
    """
    try:
        r = _redis()
        cached = r.get(SPOTLIGHT_KEY)
        if cached:
            return json.loads(cached)
    except Exception:
        log.warning("Redis unavailable for spotlight read — falling back to DB")

    cards = _build_spotlight(db)

    try:
        r = _redis()
        r.setex(SPOTLIGHT_KEY, SPOTLIGHT_TTL, json.dumps(cards))
    except Exception:
        log.warning("Redis unavailable for spotlight write")

    return cards


@router.get("/summaries/{entity_type}/{entity_code}")
def get_summary(entity_type: str, entity_code: str, db: Session = Depends(get_db)) -> dict:
    """
    Returns page summary. Reads from page_summaries table.
    If not yet generated, builds one on-the-fly and caches it.
    """
    entity_type = entity_type.lower()
    entity_code = entity_code.upper()

    if entity_type not in ("country", "stock", "trade"):
        raise HTTPException(status_code=400, detail="entity_type must be country, stock, or trade")

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

    # Generate on-the-fly and persist
    summary_text: str | None = None
    if entity_type == "country":
        summary_text = _country_summary(entity_code, db)
    elif entity_type == "stock":
        summary_text = _stock_summary(entity_code, db)
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


@router.post("/summaries/refresh")
def refresh_summaries(
    entity_type: str | None = None,
    _admin=Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    """Admin: delete cached summaries so they regenerate on next request."""
    q = db.query(PageSummary)
    if entity_type:
        q = q.filter(PageSummary.entity_type == entity_type)
    deleted = q.delete()
    db.commit()

    # Also clear spotlight cache
    try:
        _redis().delete(SPOTLIGHT_KEY)
    except Exception:
        pass

    return {"deleted": deleted, "spotlight_cleared": True}
