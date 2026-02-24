"""
Page summary + spotlight refresh tasks.

generate_page_summaries  — runs daily at 2am UTC
  Loops all countries, stocks, and trade pairs, generates 50-100 word
  templated summaries and upserts them into page_summaries table.

refresh_spotlight        — runs every 3 hours
  Rebuilds the adaptive intelligence spotlight cards and caches them
  in Redis (TTL = 3 hours). These power the homepage insight cards.
"""
import json
import logging
import ssl
from datetime import datetime, timezone

import redis as redis_lib
from sqlalchemy import text

from celery_app import app
from app.database import SessionLocal
from app.models.country import Country, CountryIndicator, TradePair
from app.models.asset import Asset, StockCountryRevenue
from app.models.summary import PageSummary

log = logging.getLogger(__name__)

SPOTLIGHT_KEY = "intelligence:spotlight:v1"
SPOTLIGHT_TTL = 10_800  # 3 hours


def _get_redis():
    from app.config import settings
    return redis_lib.from_url(
        settings.redis_url,
        ssl_cert_reqs=ssl.CERT_NONE,
        decode_responses=True,
    )


# ── Template helpers ───────────────────────────────────────────────────────────

def _fmt_gdp(v):
    if v is None:
        return "N/A"
    if v >= 1e12:
        return f"${v/1e12:.1f}T"
    if v >= 1e9:
        return f"${v/1e9:.0f}B"
    return f"${v/1e6:.0f}M"


def _fmt_usd(v):
    if v is None:
        return "N/A"
    a = abs(v)
    if a >= 1e12:
        return f"${a/1e12:.1f}T"
    if a >= 1e9:
        return f"${a/1e9:.0f}B"
    return f"${a/1e6:.0f}M"


def _country_summary_text(country: Country, db) -> str:
    indicators: dict[str, float] = {}
    rows = (
        db.query(CountryIndicator)
        .filter(CountryIndicator.country_id == country.id)
        .filter(CountryIndicator.indicator_name.in_([
            "gdp_usd", "gdp_growth_pct", "inflation_pct",
            "interest_rate_pct", "unemployment_pct",
        ]))
        .order_by(CountryIndicator.year.desc())
        .limit(20)
        .all()
    )
    seen: set[str] = set()
    for r in rows:
        if r.indicator_name not in seen:
            indicators[r.indicator_name] = r.value
            seen.add(r.indicator_name)

    groups = [g for g, flag in [
        ("G7", country.is_g7), ("G20", country.is_g20), ("EU", country.is_eu),
        ("NATO", country.is_nato), ("BRICS", country.is_brics), ("OPEC", country.is_opec),
    ] if flag]
    group_str = ", ".join(groups[:3]) if groups else "the UN"

    parts = [
        f"{country.name} ({country.code}) is a"
        f" {country.development_status or 'developing'} economy"
        f" with a GDP of {_fmt_gdp(indicators.get('gdp_usd'))}.",
    ]
    if "gdp_growth_pct" in indicators:
        line = f"GDP growth is {indicators['gdp_growth_pct']:.1f}%"
        if "inflation_pct" in indicators:
            line += f" and inflation is {indicators['inflation_pct']:.1f}%."
        else:
            line += "."
        parts.append(line)
    if "interest_rate_pct" in indicators:
        parts.append(f"The central bank rate stands at {indicators['interest_rate_pct']:.2f}%.")
    if "unemployment_pct" in indicators:
        parts.append(f"Unemployment is {indicators['unemployment_pct']:.1f}%.")
    parts.append(
        f"A member of {group_str}, it uses the"
        f" {country.currency_name or country.currency_code or 'local currency'}."
    )
    return " ".join(parts)


def _stock_summary_text(asset: Asset, db) -> str:
    hq = db.query(Country).filter(Country.id == asset.country_id).first() if asset.country_id else None

    def fmt_cap(v):
        if v is None:
            return "N/A"
        if v >= 1e12:
            return f"${v/1e12:.1f}T"
        if v >= 1e9:
            return f"${v/1e9:.0f}B"
        return f"${v/1e6:.0f}M"

    revs = (
        db.query(StockCountryRevenue, Country)
        .join(Country, StockCountryRevenue.country_id == Country.id)
        .filter(StockCountryRevenue.asset_id == asset.id)
        .order_by(StockCountryRevenue.revenue_pct.desc())
        .limit(3)
        .all()
    )

    hq_str = f" headquartered in {hq.name}" if hq else ""
    parts = [
        f"{asset.name} ({asset.symbol}) is a {fmt_cap(asset.market_cap_usd)}"
        f" market cap {asset.sector or 'company'}{hq_str}.",
    ]
    if revs:
        top_rev, top_c = revs[0]
        parts.append(
            f"It derives {top_rev.revenue_pct:.0f}% of revenue from"
            f" {top_c.flag_emoji or ''} {top_c.name} (FY{top_rev.fiscal_year})."
        )
        if len(revs) >= 2:
            r2, c2 = revs[1]
            parts.append(f"The second-largest market is {c2.name} at {r2.revenue_pct:.0f}%.")
    return " ".join(parts)


def _trade_summary_text(exporter: Country, importer: Country, trade: TradePair) -> str:
    balance_word = "surplus" if (trade.balance_usd or 0) >= 0 else "deficit"
    products = []
    if trade.top_export_products:
        products = [p.get("name", "") for p in trade.top_export_products[:3] if p.get("name")]

    parts = [
        f"{exporter.name} exported {_fmt_usd(trade.exports_usd)} to {importer.name}"
        f" in {trade.year}, running a {_fmt_usd(trade.balance_usd)} trade {balance_word}.",
    ]
    if products:
        parts.append(f"Top exports include {', '.join(products)}.")
    if trade.exporter_gdp_share_pct:
        parts.append(
            f"Bilateral trade represents {trade.exporter_gdp_share_pct:.1f}%"
            f" of {exporter.name}'s GDP."
        )
    return " ".join(parts)


def _upsert_summary(db, entity_type: str, entity_code: str, text_: str):
    now = datetime.now(timezone.utc)
    existing = (
        db.query(PageSummary)
        .filter(PageSummary.entity_type == entity_type)
        .filter(PageSummary.entity_code == entity_code)
        .first()
    )
    if existing:
        existing.summary = text_
        existing.generated_at = now
    else:
        db.add(PageSummary(
            entity_type=entity_type,
            entity_code=entity_code,
            summary=text_,
            generated_at=now,
        ))


# ── Celery tasks ───────────────────────────────────────────────────────────────

@app.task(name="tasks.summaries.generate_page_summaries", bind=True, max_retries=2)
def generate_page_summaries(self):
    """Daily 2am UTC: regenerate all page summaries into page_summaries table."""
    db = SessionLocal()
    try:
        count = 0

        # Country summaries
        countries = db.query(Country).all()
        for c in countries:
            try:
                summary = _country_summary_text(c, db)
                _upsert_summary(db, "country", c.code, summary)
                count += 1
            except Exception as e:
                log.warning("Country summary failed %s: %s", c.code, e)

        db.commit()
        log.info("Generated %d country summaries", len(countries))

        # Stock summaries
        stocks = db.query(Asset).filter(Asset.asset_type == "stock").all()
        for s in stocks:
            try:
                summary = _stock_summary_text(s, db)
                _upsert_summary(db, "stock", s.symbol, summary)
                count += 1
            except Exception as e:
                log.warning("Stock summary failed %s: %s", s.symbol, e)

        db.commit()
        log.info("Generated %d stock summaries", len(stocks))

        # Trade pair summaries — only pairs with data
        pairs = db.query(TradePair).order_by(TradePair.year.desc()).all()
        seen_pairs: set[str] = set()
        for pair in pairs:
            exp = db.query(Country).filter(Country.id == pair.exporter_id).first()
            imp = db.query(Country).filter(Country.id == pair.importer_id).first()
            if not exp or not imp:
                continue
            pair_code = f"{exp.code}-{imp.code}"
            if pair_code in seen_pairs:
                continue
            seen_pairs.add(pair_code)
            try:
                summary = _trade_summary_text(exp, imp, pair)
                _upsert_summary(db, "trade", pair_code, summary)
                count += 1
            except Exception as e:
                log.warning("Trade summary failed %s: %s", pair_code, e)

        db.commit()
        log.info("Total summaries generated/updated: %d", count)
        return {"summaries_generated": count}

    except Exception as exc:
        db.rollback()
        log.error("generate_page_summaries failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@app.task(name="tasks.summaries.refresh_spotlight", bind=True, max_retries=2)
def refresh_spotlight(self):
    """Every 3 hours: rebuild adaptive spotlight cards and cache in Redis."""
    db = SessionLocal()
    try:
        rows = db.execute(
            text("""
                SELECT
                    a.symbol, a.name, a.sector,
                    r.revenue_pct, r.fiscal_year,
                    hq.flag_emoji AS hq_flag,
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

        r = _get_redis()
        r.setex(SPOTLIGHT_KEY, SPOTLIGHT_TTL, json.dumps(cards))
        log.info("Spotlight refreshed: %d cards cached for 3hr", len(cards))
        return {"cards": len(cards)}

    except Exception as exc:
        log.error("refresh_spotlight failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()
