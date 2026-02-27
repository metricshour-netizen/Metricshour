"""
Page summary + spotlight refresh tasks.

generate_page_summaries  — daily 2am UTC
  Generates 75-100 word templated summaries for all countries, stocks, and trade pairs.
  Upserts into page_summaries table. Falls back to Gemini AI if API key available.

refresh_summary_on_event  — triggered by macro_release / price_move events
  Refreshes a single entity's summary when new data arrives.

refresh_spotlight        — every 3 hours
  Rebuilds adaptive spotlight cards and caches in Redis (TTL = 3 hours).
"""
import json
import logging
import os
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


# ── Format helpers ─────────────────────────────────────────────────────────────

def _fmt_gdp(v) -> str:
    if v is None:
        return "N/A"
    if v >= 1e12:
        return f"${v/1e12:.1f}T"
    if v >= 1e9:
        return f"${v/1e9:.0f}B"
    return f"${v/1e6:.0f}M"


def _fmt_usd(v) -> str:
    if v is None:
        return "N/A"
    a = abs(v)
    if a >= 1e12:
        return f"${a/1e12:.1f}T"
    if a >= 1e9:
        return f"${a/1e9:.0f}B"
    return f"${a/1e6:.0f}M"


def _fmt_cap(v) -> str:
    if v is None:
        return "N/A"
    if v >= 1e12:
        return f"${v/1e12:.1f}T"
    if v >= 1e9:
        return f"${v/1e9:.0f}B"
    return f"${v/1e6:.0f}M"


# ── Gemini AI summary helper ───────────────────────────────────────────────────

def _ai_summary(prompt: str) -> str | None:
    """
    Call Gemini 2.0 Flash for a polished 75-100 word summary.
    Returns None on any failure — caller falls back to template.
    Free tier: 2M tokens/day, more than enough for all entities daily.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        resp = model.generate_content(
            f"{prompt}\n\nIMPORTANT: Reply with ONLY the summary text. "
            "75-100 words. No headers. No bullet points. No markdown. "
            "Professional financial tone, third-person. End with a period.",
            generation_config={"max_output_tokens": 180, "temperature": 0.4},
        )
        text = resp.text.strip()
        if 40 < len(text.split()) < 130:
            return text
        return None
    except Exception as exc:
        log.debug("Gemini summary failed: %s", exc)
        return None


# ── Country summary ────────────────────────────────────────────────────────────

def _country_summary_text(country: Country, db) -> str:
    """
    Write a compelling, SEO-rich 75-100 word summary for a country page.
    Uses Gemini AI with real indicator data. Falls back to polished template.
    """
    # Gather latest indicators
    ind: dict[str, float] = {}
    rows = (
        db.query(CountryIndicator)
        .filter(CountryIndicator.country_id == country.id)
        .filter(CountryIndicator.indicator.in_([
            "gdp_usd", "gdp_growth_pct", "inflation_pct",
            "interest_rate_pct", "unemployment_pct",
            "current_account_usd", "govt_debt_pct_gdp",
        ]))
        .order_by(CountryIndicator.period_date.desc())
        .limit(30)
        .all()
    )
    seen: set[str] = set()
    for r in rows:
        if r.indicator not in seen:
            ind[r.indicator] = r.value
            seen.add(r.indicator)

    gdp = ind.get("gdp_usd")
    growth = ind.get("gdp_growth_pct")
    inflation = ind.get("inflation_pct")
    rate = ind.get("interest_rate_pct")
    unemployment = ind.get("unemployment_pct")
    debt = ind.get("govt_debt_pct_gdp")

    groups = [g for g, flag in [
        ("G7", country.is_g7), ("G20", country.is_g20), ("EU", country.is_eu),
        ("NATO", country.is_nato), ("BRICS", country.is_brics), ("OPEC", country.is_opec),
        ("ASEAN", country.is_asean), ("OECD", country.is_oecd),
    ] if flag]

    # Infer development status if not explicitly set — never default to "developing" for G7/OECD
    if country.development_status:
        dev_status = country.development_status.lower()
    elif country.is_g7 or country.is_oecd or country.income_level == "high":
        dev_status = "developed"
    elif country.income_level in ("low", "lower_middle"):
        dev_status = "developing"
    else:
        dev_status = "emerging"
    currency = country.currency_name or country.currency_code or "its local currency"

    # Try Gemini AI first
    if os.environ.get("GEMINI_API_KEY"):
        facts = (
            f"Country: {country.name} ({country.code})\n"
            f"Economy type: {dev_status}\n"
            f"GDP: {_fmt_gdp(gdp)}\n"
            f"GDP growth: {f'{growth:.1f}%' if growth is not None else 'N/A'}\n"
            f"Inflation: {f'{inflation:.1f}%' if inflation is not None else 'N/A'}\n"
            f"Central bank rate: {f'{rate:.2f}%' if rate is not None else 'N/A'}\n"
            f"Unemployment: {f'{unemployment:.1f}%' if unemployment is not None else 'N/A'}\n"
            f"Government debt (% GDP): {f'{debt:.0f}%' if debt is not None else 'N/A'}\n"
            f"Memberships: {', '.join(groups) if groups else 'UN member'}\n"
            f"Currency: {currency}\n"
            f"Region: {country.region or 'N/A'}\n"
        )
        prompt = (
            f"Write a concise financial intelligence summary for the MetricsHour country page "
            f"for {country.name}. Use these latest economic indicators:\n\n{facts}\n\n"
            f"The summary should help investors and analysts quickly understand the macro environment. "
            f"Mention GDP, growth trend, inflation, and key group memberships. "
            f"Focus on what matters for financial decision-making."
        )
        ai = _ai_summary(prompt)
        if ai:
            return ai

    # Polished template fallback
    group_str = ", ".join(groups[:3]) if groups else "the United Nations"
    parts = []

    # Opening: economy classification and size
    gdp_str = _fmt_gdp(gdp)
    if dev_status == "developed":
        parts.append(
            f"{country.name} ({country.code}) is a developed economy with a GDP of {gdp_str},"
            f" one of the world's larger markets by output."
        )
    else:
        parts.append(
            f"{country.name} ({country.code}) is a {dev_status} economy with a GDP of {gdp_str},"
            f" tracked across 80+ macroeconomic indicators on MetricsHour."
        )

    # Growth and inflation together
    if growth is not None and inflation is not None:
        growth_word = "expanding" if growth > 0 else "contracting"
        parts.append(
            f"The economy is {growth_word} at {growth:.1f}% annual growth with inflation at {inflation:.1f}%."
        )
    elif growth is not None:
        parts.append(f"Annual GDP growth stands at {growth:.1f}%.")

    # Monetary policy
    if rate is not None:
        if rate > 10:
            parts.append(f"The central bank maintains a high {rate:.2f}% policy rate, signalling tight monetary conditions.")
        elif rate > 5:
            parts.append(f"The central bank holds rates at {rate:.2f}%, balancing growth and inflation pressures.")
        else:
            parts.append(f"With a {rate:.2f}% policy rate, monetary conditions remain relatively accommodative.")

    # Labour market
    if unemployment is not None:
        if unemployment < 5:
            parts.append(f"Unemployment is tight at {unemployment:.1f}%.")
        else:
            parts.append(f"Unemployment stands at {unemployment:.1f}%.")

    # Closing: memberships and currency
    parts.append(
        f"A member of {group_str}, {country.name} transacts in {currency}."
        f" Trade flows, bilateral relationships, and stock exposure are linked from this page."
    )

    return " ".join(parts)


# ── Stock summary ──────────────────────────────────────────────────────────────

def _stock_summary_text(asset: Asset, db) -> str:
    """
    Write a compelling 75-100 word summary for a stock page.
    Focuses on geographic revenue exposure — the MetricsHour differentiator.
    """
    hq = db.query(Country).filter(Country.id == asset.country_id).first() if asset.country_id else None

    revs = (
        db.query(StockCountryRevenue, Country)
        .join(Country, StockCountryRevenue.country_id == Country.id)
        .filter(StockCountryRevenue.asset_id == asset.id)
        .order_by(StockCountryRevenue.revenue_pct.desc())
        .limit(5)
        .all()
    )

    hq_name = hq.name if hq else "the United States"
    cap_str = _fmt_cap(asset.market_cap_usd)
    sector = asset.sector or "company"

    # Try Gemini AI first
    if os.environ.get("GEMINI_API_KEY") and revs:
        rev_lines = "\n".join(
            f"  - {c.name} ({c.flag_emoji or ''}): {r.revenue_pct:.0f}% (FY{r.fiscal_year})"
            for r, c in revs
        )
        prompt = (
            f"Write a concise financial intelligence summary for the MetricsHour stock page for {asset.name} ({asset.symbol}).\n\n"
            f"Key facts:\n"
            f"- Company: {asset.name} ({asset.symbol})\n"
            f"- Sector: {sector}\n"
            f"- Headquarters: {hq_name}\n"
            f"- Market cap: {cap_str}\n"
            f"- Geographic revenue breakdown (from SEC EDGAR 10-K filings):\n{rev_lines}\n\n"
            f"Focus on the geographic revenue exposure and what it means for investors — e.g., "
            f"exposure to trade tensions, currency risk, or geopolitical events. "
            f"This is the unique data MetricsHour provides."
        )
        ai = _ai_summary(prompt)
        if ai:
            return ai

    # Polished template fallback
    parts = []

    # Opening: size and sector
    parts.append(
        f"{asset.name} ({asset.symbol}) is a {cap_str} market capitalisation {sector} headquartered in {hq_name}."
    )

    # Geographic revenue — the core value proposition
    if revs:
        top_rev, top_c = revs[0]
        fiscal_year = top_rev.fiscal_year
        flag = top_c.flag_emoji or ""
        parts.append(
            f"According to SEC EDGAR {fiscal_year} filings, the largest revenue market is"
            f" {flag} {top_c.name}, contributing {top_rev.revenue_pct:.0f}% of total revenue."
        )
        if len(revs) >= 2:
            r2, c2 = revs[1]
            parts.append(
                f"{c2.flag_emoji or ''} {c2.name} is the second-largest market at {r2.revenue_pct:.0f}%."
            )
        if len(revs) >= 3:
            r3, c3 = revs[2]
            parts.append(f"{c3.name} contributes {r3.revenue_pct:.0f}%.")

        # Insight: what this exposure means
        top_pct = top_rev.revenue_pct
        if top_pct >= 40:
            parts.append(
                f"This high geographic concentration makes {asset.symbol} particularly sensitive"
                f" to macro conditions, trade policy, and currency movements in {top_c.name}."
            )
        elif top_pct >= 20:
            parts.append(
                f"This exposure links {asset.symbol}'s earnings outlook to {top_c.name}'s"
                f" GDP trajectory and bilateral trade flows tracked on MetricsHour."
            )
    else:
        parts.append(
            f"Geographic revenue data and bilateral trade exposure are tracked on MetricsHour"
            f" using SEC EDGAR 10-K and 10-Q filings."
        )

    return " ".join(parts)


# ── Trade summary ──────────────────────────────────────────────────────────────

def _trade_summary_text(exporter: Country, importer: Country, trade: TradePair | None) -> str:
    """
    Write a compelling 75-100 word summary for a bilateral trade page.
    Includes trade value, balance, top products, and GDP significance.
    """
    if not trade:
        return (
            f"{exporter.name} and {importer.name} are bilateral trade partners"
            f" tracked by MetricsHour using WTO and IMF data."
            f" Historical trade flows, top export products, and GDP dependency ratios"
            f" are updated annually from UN Comtrade releases."
        )

    balance_word = "surplus" if (trade.balance_usd or 0) >= 0 else "deficit"
    products = [p.get("name", "") for p in (trade.top_export_products or [])[:3] if p.get("name")]
    exp_flag = exporter.flag_emoji or ""
    imp_flag = importer.flag_emoji or ""

    # Try Gemini AI first
    if os.environ.get("GEMINI_API_KEY"):
        facts = (
            f"Exporter: {exporter.name} ({exporter.code}) {exp_flag}\n"
            f"Importer: {importer.name} ({importer.code}) {imp_flag}\n"
            f"Year: {trade.year}\n"
            f"Exports value: {_fmt_usd(trade.exports_usd)}\n"
            f"Imports value: {_fmt_usd(trade.imports_usd)}\n"
            f"Trade balance: {_fmt_usd(trade.balance_usd)} ({balance_word})\n"
            f"Trade as % of exporter GDP: {f'{trade.exporter_gdp_share_pct:.1f}%' if trade.exporter_gdp_share_pct else 'N/A'}\n"
            f"Top export products: {', '.join(products) if products else 'N/A'}\n"
        )
        prompt = (
            f"Write a concise financial intelligence summary for the MetricsHour bilateral trade page "
            f"for {exporter.name}–{importer.name}.\n\n{facts}\n\n"
            f"Explain the significance of this trade relationship — its scale, balance, "
            f"key products, and what it means for both economies. "
            f"Mention what investors tracking global supply chains should know."
        )
        ai = _ai_summary(prompt)
        if ai:
            return ai

    # Polished template fallback
    parts = []
    exp_str = _fmt_usd(trade.exports_usd)
    bal_str = _fmt_usd(trade.balance_usd)

    parts.append(
        f"{exp_flag} {exporter.name} exported {exp_str} to"
        f" {imp_flag} {importer.name} in {trade.year},"
        f" running a {bal_str} trade {balance_word}."
    )

    if products:
        prod_str = ", ".join(products[:-1]) + f" and {products[-1]}" if len(products) > 1 else products[0]
        parts.append(f"Top exports include {prod_str}.")

    if trade.exporter_gdp_share_pct:
        significance = (
            "a critical" if trade.exporter_gdp_share_pct >= 5 else
            "a significant" if trade.exporter_gdp_share_pct >= 2 else
            "a modest"
        )
        parts.append(
            f"Bilateral trade represents {significance} {trade.exporter_gdp_share_pct:.1f}%"
            f" of {exporter.name}'s GDP, sourced from UN Comtrade {trade.year} data."
        )

    parts.append(
        f"Track stock revenue exposure, macro indicators, and currency links"
        f" for both countries on MetricsHour."
    )

    return " ".join(parts)


# ── Upsert helper ──────────────────────────────────────────────────────────────

def _upsert_summary(db, entity_type: str, entity_code: str, text_: str):
    now = datetime.now(timezone.utc)
    existing = (
        db.query(PageSummary)
        .filter(PageSummary.entity_type == entity_type, PageSummary.entity_code == entity_code)
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
    """
    Daily 2am UTC: regenerate all page summaries.
    Uses Gemini AI (free tier) if GEMINI_API_KEY is set, else polished templates.
    """
    db = SessionLocal()
    try:
        total = 0

        # Country summaries
        countries = db.query(Country).all()
        for c in countries:
            try:
                summary = _country_summary_text(c, db)
                _upsert_summary(db, "country", c.code, summary)
                total += 1
            except Exception as e:
                log.warning("Country summary failed %s: %s", c.code, e)
        db.commit()
        log.info("Country summaries done: %d", len(countries))

        # Stock summaries
        stocks = db.query(Asset).filter(Asset.asset_type == "stock").all()
        for s in stocks:
            try:
                summary = _stock_summary_text(s, db)
                _upsert_summary(db, "stock", s.symbol, summary)
                total += 1
            except Exception as e:
                log.warning("Stock summary failed %s: %s", s.symbol, e)
        db.commit()
        log.info("Stock summaries done: %d", len(stocks))

        # Trade pair summaries — latest year per pair only
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
                total += 1
            except Exception as e:
                log.warning("Trade summary failed %s: %s", pair_code, e)
        db.commit()
        log.info("Trade summaries done: %d", len(seen_pairs))

        log.info("Total summaries generated/updated: %d", total)
        return {"summaries_generated": total}

    except Exception as exc:
        db.rollback()
        log.error("generate_page_summaries failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@app.task(name="tasks.summaries.refresh_entity_summary", bind=True, max_retries=1)
def refresh_entity_summary(self, entity_type: str, entity_code: str):
    """
    Refresh a single entity summary. Triggered by macro_release or price_move events.
    entity_type: 'country' | 'stock' | 'trade'
    entity_code: 'US' | 'AAPL' | 'US-CN'
    """
    db = SessionLocal()
    try:
        summary: str | None = None
        if entity_type == "country":
            country = db.query(Country).filter(Country.code == entity_code.upper()).first()
            if country:
                summary = _country_summary_text(country, db)
        elif entity_type == "stock":
            asset = db.query(Asset).filter(Asset.symbol == entity_code.upper()).first()
            if asset:
                summary = _stock_summary_text(asset, db)
        elif entity_type == "trade":
            codes = entity_code.upper().split("-")
            if len(codes) == 2:
                exp = db.query(Country).filter(Country.code == codes[0]).first()
                imp = db.query(Country).filter(Country.code == codes[1]).first()
                if exp and imp:
                    trade = (
                        db.query(TradePair)
                        .filter(TradePair.exporter_id == exp.id, TradePair.importer_id == imp.id)
                        .order_by(TradePair.year.desc())
                        .first()
                    )
                    summary = _trade_summary_text(exp, imp, trade)

        if summary:
            _upsert_summary(db, entity_type, entity_code.upper(), summary)
            db.commit()
            log.info("Summary refreshed: %s/%s", entity_type, entity_code)
            return {"refreshed": True, "entity_type": entity_type, "entity_code": entity_code}

        return {"refreshed": False, "reason": "entity not found"}

    except Exception as exc:
        db.rollback()
        log.error("refresh_entity_summary failed %s/%s: %s", entity_type, entity_code, exc)
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
