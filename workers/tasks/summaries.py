"""
Page summary + daily insight + spotlight refresh tasks.

generate_page_summaries  — daily 2am UTC
  Generates 75-100 word summaries for all countries, stocks, commodities, and trade pairs.
  Summaries are stable descriptions — only regenerated daily; in practice update when data changes.

generate_daily_insights  — daily 5am UTC
  Generates 60-80 word opinionated analyst insights for countries, stocks, and commodities.
  These are forward-looking takes, refreshed every day regardless of data changes.

refresh_entity_summary / refresh_entity_insight  — event-triggered
  Refresh a single entity on demand.

refresh_spotlight        — every 3 hours
  Rebuilds adaptive spotlight cards and caches in Redis (TTL = 3 hours).
"""
import json
import logging
import os
import ssl
from datetime import datetime, timezone, date

import redis as redis_lib
from sqlalchemy import text

from celery_app import app
from app.database import SessionLocal
from app.models.country import Country, CountryIndicator, TradePair
from app.models.asset import Asset, StockCountryRevenue
from app.models.feed import FeedEvent
from app.models.summary import PageSummary, PageInsight

log = logging.getLogger(__name__)

SPOTLIGHT_KEY = "intelligence:spotlight:v1"
SPOTLIGHT_TTL = 10_800  # 3 hours

# Commodity metadata — sector + category for richer prompts
COMMODITY_META: dict[str, dict] = {
    "WTI":     {"sector": "Energy",      "full_name": "Crude Oil (WTI)", "unit": "USD/barrel"},
    "BRENT":   {"sector": "Energy",      "full_name": "Crude Oil (Brent)", "unit": "USD/barrel"},
    "NG":      {"sector": "Energy",      "full_name": "Natural Gas", "unit": "USD/MMBtu"},
    "GASOLINE":{"sector": "Energy",      "full_name": "Gasoline RBOB", "unit": "USD/gallon"},
    "COAL":    {"sector": "Energy",      "full_name": "Thermal Coal", "unit": "USD/metric ton"},
    "XAUUSD":  {"sector": "Metals",      "full_name": "Gold", "unit": "USD/troy oz"},
    "XAGUSD":  {"sector": "Metals",      "full_name": "Silver", "unit": "USD/troy oz"},
    "XPTUSD":  {"sector": "Metals",      "full_name": "Platinum", "unit": "USD/troy oz"},
    "HG":      {"sector": "Metals",      "full_name": "Copper", "unit": "USD/lb (COMEX)"},
    "ALI":     {"sector": "Metals",      "full_name": "Aluminum", "unit": "USD/metric ton (LME)"},
    "ZNC":     {"sector": "Metals",      "full_name": "Zinc", "unit": "USD/metric ton (LME)"},
    "NI":      {"sector": "Metals",      "full_name": "Nickel", "unit": "USD/metric ton (LME)"},
    "ZW":      {"sector": "Agriculture", "full_name": "Wheat (CBOT)", "unit": "USD/bushel"},
    "ZC":      {"sector": "Agriculture", "full_name": "Corn (CBOT)", "unit": "USD/bushel"},
    "ZS":      {"sector": "Agriculture", "full_name": "Soybeans (CBOT)", "unit": "USD/bushel"},
    "KC":      {"sector": "Agriculture", "full_name": "Arabica Coffee", "unit": "USD/lb (ICE)"},
    "SB":      {"sector": "Agriculture", "full_name": "Raw Sugar No.11", "unit": "USD/lb (ICE)"},
    "CT":      {"sector": "Agriculture", "full_name": "Cotton No.2", "unit": "USD/lb (ICE)"},
    "CC":      {"sector": "Agriculture", "full_name": "Cocoa", "unit": "USD/metric ton (ICE)"},
    "LE":      {"sector": "Agriculture", "full_name": "Live Cattle", "unit": "USD/lb (CME)"},
    "PALM":    {"sector": "Agriculture", "full_name": "Crude Palm Oil (CPO)", "unit": "USD/metric ton (BMD)"},
}


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


# ── Gemini AI helper ──────────────────────────────────────────────────────────

def _call_gemini(prompt: str, min_words: int = 55, max_words: int = 110) -> str | None:
    """
    Call Gemini 2.5 Flash. Returns None on any failure — caller uses template fallback.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        r = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = r.text.strip()
        # Strip any stray markdown the model might add
        if text.startswith("**") or text.startswith("#"):
            import re
            text = re.sub(r"^[#*\-]+\s*", "", text, flags=re.MULTILINE).strip()
        words = len(text.split())
        if (min_words - 15) < words < (max_words + 25):
            return text
        return None
    except Exception as exc:
        log.debug("Gemini call failed: %s", exc)
        return None


# ── Country summary ────────────────────────────────────────────────────────────

def _country_summary_text(country: Country, db) -> str:
    """
    Stable 75-100 word macro overview for a country page.
    Uses Gemini AI with real indicator data. Falls back to polished template.
    """
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

    if country.development_status:
        dev_status = country.development_status.lower()
    elif country.is_g7 or country.is_oecd or country.income_level == "high":
        dev_status = "developed"
    elif country.income_level in ("low", "lower_middle"):
        dev_status = "developing"
    else:
        dev_status = "emerging"
    currency = country.currency_name or country.currency_code or "its local currency"

    if os.environ.get("GEMINI_API_KEY"):
        facts = (
            f"Country: {country.name} ({country.code})\n"
            f"Economy classification: {dev_status}\n"
            f"Region: {country.region or 'N/A'}\n"
            f"GDP: {_fmt_gdp(gdp)}\n"
            f"GDP growth: {f'{growth:.1f}%' if growth is not None else 'N/A'}\n"
            f"Inflation: {f'{inflation:.1f}%' if inflation is not None else 'N/A'}\n"
            f"Central bank policy rate: {f'{rate:.2f}%' if rate is not None else 'N/A'}\n"
            f"Unemployment: {f'{unemployment:.1f}%' if unemployment is not None else 'N/A'}\n"
            f"Government debt (% of GDP): {f'{debt:.0f}%' if debt is not None else 'N/A'}\n"
            f"S&P credit rating: {country.credit_rating_sp or 'N/A'}\n"
            f"International group memberships: {', '.join(groups) if groups else 'UN member'}\n"
            f"Currency: {currency}\n"
            f"Major exports: {country.major_exports or 'N/A'}\n"
        )
        prompt = (
            f"You are a senior macro strategist writing for MetricsHour, a financial intelligence "
            f"platform used by institutional investors, hedge funds, and equity analysts.\n\n"
            f"Write a factual 75-100 word macro overview for the {country.name} country page.\n\n"
            f"Data:\n{facts}\n\n"
            f"Requirements:\n"
            f"- Cover GDP size and growth trajectory\n"
            f"- Describe the inflation and monetary policy environment\n"
            f"- Note key group memberships that matter for trade and policy\n"
            f"- Highlight any standout macro characteristic (high debt, commodity exports, trade balance, credit quality)\n"
            f"- Write in Financial Times macro-brief style: third-person, authoritative, data-specific\n"
            f"- Include exact numbers. No bullet points. No headers. End with a period."
        )
        ai = _call_gemini(prompt, min_words=65, max_words=110)
        if ai:
            return ai

    # Polished template fallback
    group_str = ", ".join(groups[:3]) if groups else "the United Nations"
    parts = []
    gdp_str = _fmt_gdp(gdp)
    if dev_status == "developed":
        parts.append(f"{country.name} ({country.code}) is a developed economy with a GDP of {gdp_str}.")
    else:
        parts.append(f"{country.name} ({country.code}) is a {dev_status} economy with a GDP of {gdp_str}.")
    if growth is not None and inflation is not None:
        growth_word = "expanding" if growth > 0 else "contracting"
        parts.append(f"The economy is {growth_word} at {growth:.1f}% annual growth with inflation at {inflation:.1f}%.")
    elif growth is not None:
        parts.append(f"Annual GDP growth stands at {growth:.1f}%.")
    if rate is not None:
        if rate > 10:
            parts.append(f"The central bank maintains a restrictive {rate:.2f}% policy rate.")
        elif rate > 5:
            parts.append(f"The central bank holds rates at {rate:.2f}%.")
        else:
            parts.append(f"Monetary policy is accommodative at {rate:.2f}%.")
    if unemployment is not None:
        parts.append(f"Unemployment stands at {unemployment:.1f}%.")
    parts.append(
        f"A member of {group_str}, {country.name} transacts in {currency}."
        f" Trade flows, bilateral relationships, and global stock exposure are tracked on MetricsHour."
    )
    return " ".join(parts)


# ── Country daily insight ──────────────────────────────────────────────────────

def _country_insight_text(country: Country, db) -> str | None:
    """
    Opinionated 60-80 word analyst take for a country page. Generated daily.
    Focuses on what investors should watch NOW — not a description.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        return None

    ind: dict[str, float] = {}
    rows = (
        db.query(CountryIndicator)
        .filter(CountryIndicator.country_id == country.id)
        .filter(CountryIndicator.indicator.in_([
            "gdp_usd", "gdp_growth_pct", "inflation_pct",
            "interest_rate_pct", "unemployment_pct",
            "current_account_usd", "govt_debt_pct_gdp",
            "current_account_pct_gdp",
        ]))
        .order_by(CountryIndicator.period_date.desc())
        .limit(40)
        .all()
    )
    seen: set[str] = set()
    for r in rows:
        if r.indicator not in seen:
            ind[r.indicator] = r.value
            seen.add(r.indicator)

    groups = [g for g, flag in [
        ("G7", country.is_g7), ("G20", country.is_g20), ("EU", country.is_eu),
        ("NATO", country.is_nato), ("BRICS", country.is_brics), ("OPEC", country.is_opec),
        ("ASEAN", country.is_asean), ("OECD", country.is_oecd),
    ] if flag]

    def _pct1(key: str) -> str:
        v = ind.get(key)
        return f"{v:.1f}%" if v is not None else "N/A"

    def _pct2(key: str) -> str:
        v = ind.get(key)
        return f"{v:.2f}%" if v is not None else "N/A"

    def _pct0(key: str) -> str:
        v = ind.get(key)
        return f"{v:.0f}%" if v is not None else "N/A"

    facts = (
        f"Country: {country.name} ({country.code})\n"
        f"GDP: {_fmt_gdp(ind.get('gdp_usd'))}\n"
        f"GDP growth: {_pct1('gdp_growth_pct')}\n"
        f"Inflation: {_pct1('inflation_pct')}\n"
        f"Policy rate: {_pct2('interest_rate_pct')}\n"
        f"Unemployment: {_pct1('unemployment_pct')}\n"
        f"Govt debt/GDP: {_pct0('govt_debt_pct_gdp')}\n"
        f"Current account (% GDP): {_pct1('current_account_pct_gdp')}\n"
        f"S&P rating: {country.credit_rating_sp or 'N/A'}\n"
        f"Group memberships: {', '.join(groups) if groups else 'UN member'}\n"
        f"Currency: {country.currency_name or country.currency_code or 'N/A'}\n"
        f"Today's date: {date.today().strftime('%B %d, %Y')}\n"
    )

    prompt = (
        f"You are a macro strategist at a tier-1 investment bank writing a daily intelligence brief "
        f"for professional investors on MetricsHour.\n\n"
        f"Write a 60-80 word DAILY INSIGHT for {country.name}. This is NOT a description — "
        f"it is a forward-looking analytical take.\n\n"
        f"Data:\n{facts}\n\n"
        f"Requirements:\n"
        f"- Identify the ONE most important macro dynamic investors should watch in this country right now\n"
        f"- Reference a specific indicator level or trend that supports your view\n"
        f"- Name the key risk or opportunity for portfolio positioning\n"
        f"- Use active, confident language: 'Watch for...', 'The key tension is...', 'Investors should note...'\n"
        f"- Be opinionated and specific. No generic statements.\n"
        f"- No bullet points. No headers. Third-person. End with a period."
    )
    return _call_gemini(prompt, min_words=50, max_words=95)


# ── Stock summary ──────────────────────────────────────────────────────────────

def _stock_summary_text(asset: Asset, db) -> str:
    """
    Stable 75-100 word overview for a stock page.
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

    if os.environ.get("GEMINI_API_KEY"):
        rev_lines = "\n".join(
            f"  - {c.flag_emoji or ''} {c.name}: {r.revenue_pct:.0f}% (FY{r.fiscal_year})"
            for r, c in revs
        ) if revs else "  - Geographic breakdown not yet available (SEC EDGAR pending)"

        prompt = (
            f"You are a senior equity analyst at a global investment bank writing for MetricsHour, "
            f"a financial intelligence platform used by fund managers and institutional investors.\n\n"
            f"Write a factual 75-100 word geographic revenue overview for {asset.name} ({asset.symbol}).\n\n"
            f"Company data:\n"
            f"- Name: {asset.name} ({asset.symbol})\n"
            f"- Sector: {sector}\n"
            f"- Industry: {asset.industry or 'N/A'}\n"
            f"- Headquarters: {hq_name}\n"
            f"- Market cap: {cap_str}\n"
            f"- Geographic revenue (SEC EDGAR 10-K filings):\n{rev_lines}\n\n"
            f"Requirements:\n"
            f"- Lead with the company's business and scale\n"
            f"- Highlight the top 2-3 revenue markets by geography\n"
            f"- Explain what the geographic concentration means for investors "
            f"(FX risk, tariff exposure, geopolitical sensitivity, or growth tailwind)\n"
            f"- Connect revenue geography to real-world macro risk where specific\n"
            f"- Write in Goldman Sachs equity note style: precise, data-driven, forward-oriented\n"
            f"- No bullet points. No headers. Third-person. Include exact percentages. End with a period."
        )
        ai = _call_gemini(prompt, min_words=65, max_words=110)
        if ai:
            return ai

    # Polished template fallback
    parts = [f"{asset.name} ({asset.symbol}) is a {cap_str} market cap {sector} headquartered in {hq_name}."]
    if revs:
        top_rev, top_c = revs[0]
        flag = top_c.flag_emoji or ""
        parts.append(
            f"SEC EDGAR FY{top_rev.fiscal_year} filings show {flag} {top_c.name} as the largest revenue market"
            f" at {top_rev.revenue_pct:.0f}% of total revenue."
        )
        if len(revs) >= 2:
            r2, c2 = revs[1]
            parts.append(f"{c2.flag_emoji or ''} {c2.name} contributes {r2.revenue_pct:.0f}%.")
        top_pct = top_rev.revenue_pct
        if top_pct >= 40:
            parts.append(
                f"This concentration makes {asset.symbol} particularly sensitive to macro conditions and trade policy in {top_c.name}."
            )
        elif top_pct >= 20:
            parts.append(
                f"This exposure links {asset.symbol}'s earnings to {top_c.name}'s GDP trajectory and bilateral trade flows."
            )
    else:
        parts.append("Geographic revenue data is tracked on MetricsHour using SEC EDGAR 10-K and 10-Q filings.")
    return " ".join(parts)


# ── Stock daily insight ────────────────────────────────────────────────────────

def _stock_insight_text(asset: Asset, db) -> str | None:
    """
    Opinionated 60-80 word analyst take for a stock page. Generated daily.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        return None

    hq = db.query(Country).filter(Country.id == asset.country_id).first() if asset.country_id else None

    revs = (
        db.query(StockCountryRevenue, Country)
        .join(Country, StockCountryRevenue.country_id == Country.id)
        .filter(StockCountryRevenue.asset_id == asset.id)
        .order_by(StockCountryRevenue.revenue_pct.desc())
        .limit(4)
        .all()
    )

    if not revs:
        return None

    rev_lines = "\n".join(
        f"  - {c.flag_emoji or ''} {c.name}: {r.revenue_pct:.0f}% (FY{r.fiscal_year})"
        for r, c in revs
    )

    # Pull HQ country indicators for macro context
    hq_macro = ""
    if hq:
        hq_inds: dict[str, float] = {}
        hq_rows = (
            db.query(CountryIndicator)
            .filter(CountryIndicator.country_id == hq.id)
            .filter(CountryIndicator.indicator.in_(["gdp_growth_pct", "inflation_pct", "interest_rate_pct"]))
            .order_by(CountryIndicator.period_date.desc())
            .limit(10)
            .all()
        )
        seen_h: set[str] = set()
        for r in hq_rows:
            if r.indicator not in seen_h:
                hq_inds[r.indicator] = r.value
                seen_h.add(r.indicator)
        if hq_inds:
            hq_macro = (
                f"HQ country ({hq.name}) macro: "
                f"GDP growth {hq_inds.get('gdp_growth_pct', 'N/A'):.1f}%" if isinstance(hq_inds.get('gdp_growth_pct'), float) else
                f"HQ country ({hq.name})"
            )

    prompt = (
        f"You are a sell-side equity analyst writing a daily intelligence brief for MetricsHour investors.\n\n"
        f"Write a 60-80 word DAILY INSIGHT for {asset.name} ({asset.symbol}). "
        f"This is NOT a company description — it is a forward-looking analyst take.\n\n"
        f"Company data:\n"
        f"- Sector: {asset.sector or 'N/A'}, Market cap: {_fmt_cap(asset.market_cap_usd)}\n"
        f"- Headquarters: {hq.name if hq else 'N/A'}\n"
        f"- Geographic revenue breakdown:\n{rev_lines}\n"
        f"- Today's date: {date.today().strftime('%B %d, %Y')}\n\n"
        f"Requirements:\n"
        f"- Pick ONE geographic exposure that carries the highest near-term risk or opportunity\n"
        f"- Name the specific macro driver: tariff risk, FX headwind/tailwind, recession risk, trade flow, or growth catalyst\n"
        f"- Give an actionable framing of what this means for the stock's earnings outlook\n"
        f"- Write like a Wall Street equity research note: confident, specific, numbers-driven\n"
        f"- No bullet points. No headers. Active voice. End with a period."
    )
    return _call_gemini(prompt, min_words=50, max_words=95)


# ── Trade summary ──────────────────────────────────────────────────────────────

def _trade_summary_text(exporter: Country, importer: Country, trade: TradePair | None) -> str:
    """
    Stable 75-100 word overview for a bilateral trade page.
    """
    if not trade:
        return (
            f"{exporter.name} and {importer.name} are bilateral trade partners tracked by MetricsHour "
            f"using WTO, IMF, and UN Comtrade data. Historical trade flows, top export products, "
            f"and GDP dependency ratios are updated annually."
        )

    balance_word = "surplus" if (trade.balance_usd or 0) >= 0 else "deficit"
    products = [p.get("name", "") for p in (trade.top_export_products or [])[:3] if p.get("name")]
    exp_flag = exporter.flag_emoji or ""
    imp_flag = importer.flag_emoji or ""

    if os.environ.get("GEMINI_API_KEY"):
        facts = (
            f"Exporter: {exporter.name} ({exporter.code}) {exp_flag}\n"
            f"Importer: {importer.name} ({importer.code}) {imp_flag}\n"
            f"Data year: {trade.year}\n"
            f"Exports value: {_fmt_usd(trade.exports_usd)}\n"
            f"Imports value: {_fmt_usd(trade.imports_usd)}\n"
            f"Trade balance: {_fmt_usd(trade.balance_usd)} ({balance_word} for {exporter.name})\n"
            f"Trade as % of {exporter.name} GDP: {f'{trade.exporter_gdp_share_pct:.1f}%' if trade.exporter_gdp_share_pct else 'N/A'}\n"
            f"Top export products: {', '.join(products) if products else 'N/A'}\n"
        )
        prompt = (
            f"You are a macro economist and trade analyst writing for MetricsHour, used by supply chain "
            f"analysts, FX traders, and equity investors.\n\n"
            f"Write a factual 75-100 word overview of the {exporter.name}–{importer.name} trade relationship.\n\n"
            f"Data:\n{facts}\n\n"
            f"Requirements:\n"
            f"- Lead with the scale and direction of the trade relationship\n"
            f"- Describe the trade balance and what it implies about economic dependency or leverage\n"
            f"- Name the top export product categories and which industries rely on these flows\n"
            f"- Explain any strategic or geopolitical significance of this trade corridor\n"
            f"- Note what FX traders and equity investors exposed to these countries should understand\n"
            f"- Write in Reuters/FT trade desk style: factual, concise, market-aware\n"
            f"- No bullet points. No headers. Include specific dollar amounts. End with a period."
        )
        ai = _call_gemini(prompt, min_words=65, max_words=110)
        if ai:
            return ai

    # Polished template fallback
    parts = []
    parts.append(
        f"{exp_flag} {exporter.name} exported {_fmt_usd(trade.exports_usd)} to"
        f" {imp_flag} {importer.name} in {trade.year},"
        f" running a {_fmt_usd(trade.balance_usd)} trade {balance_word}."
    )
    if products:
        prod_str = ", ".join(products[:-1]) + f" and {products[-1]}" if len(products) > 1 else products[0]
        parts.append(f"Top exports include {prod_str}.")
    if trade.exporter_gdp_share_pct:
        sig = "critical" if trade.exporter_gdp_share_pct >= 5 else "significant" if trade.exporter_gdp_share_pct >= 2 else "modest"
        parts.append(f"This {sig} {trade.exporter_gdp_share_pct:.1f}% of {exporter.name}'s GDP is sourced from UN Comtrade {trade.year} data.")
    parts.append("Track stock revenue exposure, macro indicators, and currency links for both countries on MetricsHour.")
    return " ".join(parts)


# ── Trade daily insight ───────────────────────────────────────────────────────

def _trade_insight_text(exporter: Country, importer: Country, trade: TradePair | None) -> str | None:
    """
    Opinionated 60-80 word daily analyst take for a bilateral trade page.
    Forward-looking: tariff risk, FX impact, supply chain shifts, geopolitical tension.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        return None

    balance_word = "surplus" if (trade.balance_usd or 0) >= 0 else "deficit" if trade else "balanced"
    products = [p.get("name", "") for p in (trade.top_export_products or [])[:3] if p.get("name")] if trade else []
    exp_flag = exporter.flag_emoji or ""
    imp_flag = importer.flag_emoji or ""

    facts = (
        f"Exporter: {exporter.name} ({exporter.code}) {exp_flag}\n"
        f"Importer: {importer.name} ({importer.code}) {imp_flag}\n"
        f"Data year: {trade.year if trade else 'N/A'}\n"
        f"Export value: {_fmt_usd(trade.exports_usd) if trade else 'N/A'}\n"
        f"Trade balance: {_fmt_usd(trade.balance_usd) if trade else 'N/A'} ({balance_word} for {exporter.name})\n"
        f"Exporter GDP share: {f'{trade.exporter_gdp_share_pct:.1f}%' if trade and trade.exporter_gdp_share_pct else 'N/A'}\n"
        f"Top exports: {', '.join(products) if products else 'N/A'}\n"
        f"Exporter groups: {', '.join([g for g,f in [('G7',exporter.is_g7),('G20',exporter.is_g20),('EU',exporter.is_eu),('NATO',exporter.is_nato),('BRICS',exporter.is_brics),('OPEC',exporter.is_opec)] if f])}\n"
        f"Importer groups: {', '.join([g for g,f in [('G7',importer.is_g7),('G20',importer.is_g20),('EU',importer.is_eu),('NATO',importer.is_nato),('BRICS',importer.is_brics),('OPEC',importer.is_opec)] if f])}\n"
        f"Today's date: {date.today().strftime('%B %d, %Y')}\n"
    )

    prompt = (
        f"You are a macro trade analyst at a global investment bank writing a daily brief for MetricsHour.\n\n"
        f"Write a 60-80 word DAILY INSIGHT for the {exporter.name}–{importer.name} trade corridor. "
        f"This is NOT a description — it is a forward-looking market take.\n\n"
        f"Data:\n{facts}\n\n"
        f"Requirements:\n"
        f"- Identify the ONE most important near-term risk or opportunity in this trade relationship\n"
        f"- Reference tariff policy, FX moves, supply chain shifts, sanctions risk, or commodity exposure\n"
        f"- Name which equity sectors or asset classes are most exposed to a disruption or improvement\n"
        f"- Be specific and opinionated: 'Watch for...', 'The key tension is...', 'Investors should note...'\n"
        f"- No bullet points. No headers. Active voice. End with a period."
    )
    return _call_gemini(prompt, min_words=50, max_words=95)


# ── Commodity summary ──────────────────────────────────────────────────────────

def _commodity_summary_text(asset: Asset) -> str:
    """
    Stable 75-100 word overview for a commodity page.
    """
    meta = COMMODITY_META.get(asset.symbol, {})
    full_name = meta.get("full_name", asset.name)
    sector = meta.get("sector", asset.sector or "Commodity")
    unit = meta.get("unit", "USD")

    if os.environ.get("GEMINI_API_KEY"):
        prompt = (
            f"You are a commodity analyst at a major trading house writing for MetricsHour, "
            f"a financial intelligence platform used by commodity traders, macro investors, and corporate procurement teams.\n\n"
            f"Write a factual 75-100 word overview for the {full_name} ({asset.symbol}) commodity page.\n\n"
            f"Commodity details:\n"
            f"- Full name: {full_name}\n"
            f"- Symbol: {asset.symbol}\n"
            f"- Sector: {sector}\n"
            f"- Pricing unit: {unit}\n\n"
            f"Requirements:\n"
            f"- Describe what this commodity is and why it matters to the global economy\n"
            f"- Name the key producers, consumers, or trading regions that drive this market\n"
            f"- Explain the primary supply and demand factors that move the price\n"
            f"- Identify which equity sectors or asset classes are most exposed to this commodity\n"
            f"- Mention any exchange or benchmark standard (NYMEX WTI, LME copper, CBOT wheat, etc.)\n"
            f"- Write in commodity desk style: precise, market-fluent, no fluff\n"
            f"- No bullet points. No headers. Third-person. End with a period."
        )
        ai = _call_gemini(prompt, min_words=65, max_words=110)
        if ai:
            return ai

    # Fallback template
    return (
        f"{full_name} ({asset.symbol}) is a globally traded {sector.lower()} commodity priced in {unit}. "
        f"Price movements are driven by supply and demand dynamics across major producers and consumers worldwide. "
        f"MetricsHour tracks {asset.symbol} alongside bilateral trade flows, country macro indicators, "
        f"and equity stocks exposed to this commodity sector."
    )


# ── Commodity daily insight ────────────────────────────────────────────────────

def _commodity_insight_text(asset: Asset) -> str | None:
    """
    Opinionated 60-80 word daily analyst take for a commodity page.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        return None

    meta = COMMODITY_META.get(asset.symbol, {})
    full_name = meta.get("full_name", asset.name)
    sector = meta.get("sector", asset.sector or "Commodity")
    unit = meta.get("unit", "USD")

    prompt = (
        f"You are a commodity market analyst at a major trading house writing a daily brief for MetricsHour.\n\n"
        f"Write a 60-80 word DAILY INSIGHT for {full_name} ({asset.symbol}). "
        f"This is NOT a description — it is a forward-looking market take.\n\n"
        f"Commodity: {full_name} ({asset.symbol}), {sector}, priced in {unit}\n"
        f"Today's date: {date.today().strftime('%B %d, %Y')}\n\n"
        f"Requirements:\n"
        f"- Identify the dominant supply or demand factor driving this market right now\n"
        f"- Name one near-term catalyst or risk that traders should watch\n"
        f"- Reference specific geopolitics, production data, seasonal pattern, or demand trend\n"
        f"- Explain what equity sector or macro theme is most exposed to this price move\n"
        f"- Write like a Reuters commodity brief: direct, specific, market-focused\n"
        f"- No bullet points. No headers. Active voice. End with a period."
    )
    return _call_gemini(prompt, min_words=50, max_words=95)


# ── Emoji helpers ─────────────────────────────────────────────────────────────

_COMMODITY_EMOJI: dict[str, str] = {
    "WTI": "🛢️", "BRENT": "🛢️", "NG": "🔥", "GASOLINE": "⛽", "COAL": "⚫",
    "XAUUSD": "🥇", "XAGUSD": "🥈", "XPTUSD": "⬜", "HG": "🟤", "ALI": "⬛",
    "ZNC": "🔩", "NI": "🔩", "ZW": "🌾", "ZC": "🌽", "ZS": "🟤",
    "KC": "☕", "SB": "🍬", "CT": "🌿", "CC": "🍫", "LE": "🐄", "PALM": "🌴",
}

def _commodity_emoji(symbol: str) -> str:
    return _COMMODITY_EMOJI.get(symbol, "📦")


# ── Staleness checks — skip summary regeneration if data hasn't changed ────────

def _country_summary_stale(country: Country, existing: PageSummary | None, db) -> bool:
    """True if the country summary needs regenerating."""
    if not existing:
        return True
    age_days = (datetime.now(timezone.utc) - existing.generated_at).days
    if age_days > 30:
        return True
    # Regenerate if any indicator is newer than the summary
    latest_ind = (
        db.query(CountryIndicator.period_date)
        .filter(CountryIndicator.country_id == country.id)
        .order_by(CountryIndicator.period_date.desc())
        .scalar()
    )
    if latest_ind and latest_ind > existing.generated_at.date():
        return True
    return False


def _stock_summary_stale(asset: Asset, existing: PageSummary | None, db) -> bool:
    """True if the stock summary needs regenerating."""
    if not existing:
        return True
    age_days = (datetime.now(timezone.utc) - existing.generated_at).days
    if age_days > 30:
        return True
    # Regenerate if a newer fiscal year of revenue data has arrived
    latest_fy = (
        db.query(StockCountryRevenue.fiscal_year)
        .filter(StockCountryRevenue.asset_id == asset.id)
        .order_by(StockCountryRevenue.fiscal_year.desc())
        .scalar()
    )
    if latest_fy and latest_fy > existing.generated_at.year:
        return True
    return False


def _trade_summary_stale(pair_code: str, trade_year: int | None, existing: PageSummary | None) -> bool:
    """True if the trade summary needs regenerating."""
    if not existing:
        return True
    age_days = (datetime.now(timezone.utc) - existing.generated_at).days
    if age_days > 365:
        return True
    # Regenerate if a newer year of trade data has arrived
    if trade_year and trade_year > existing.generated_at.year:
        return True
    return False


def _commodity_summary_stale(existing: PageSummary | None) -> bool:
    """True if the commodity summary needs regenerating (static text — refresh weekly)."""
    if not existing:
        return True
    return (datetime.now(timezone.utc) - existing.generated_at).days > 7


# ── Upsert helpers ─────────────────────────────────────────────────────────────

def _upsert_feed_insight(
    db,
    now: datetime,
    title: str,
    body: str,
    source_url: str,
    entity_type: str,
    entity_name: str,
    entity_flag: str,
    importance_score: float,
    related_country_ids: list | None = None,
    related_asset_ids: list | None = None,
):
    """
    Upsert a daily_insight FeedEvent. Uses source_url as a unique key (one per entity per day).
    Old records from previous days are replaced.
    """
    # Delete yesterday's insight for this entity (keep only today's)
    db.query(FeedEvent).filter(
        FeedEvent.event_type == "daily_insight",
        FeedEvent.source_url == source_url,
    ).delete()

    event_data = {
        "entity_type": entity_type,
        "entity_name": entity_name,
        "entity_flag": entity_flag,
    }

    db.add(FeedEvent(
        title=title,
        body=body,
        event_type="daily_insight",
        event_subtype=entity_type,
        source_url=source_url,
        published_at=now,
        related_country_ids=related_country_ids,
        related_asset_ids=related_asset_ids,
        event_data=event_data,
        importance_score=importance_score,
    ))


def _insert_insight(db, entity_type: str, entity_code: str, text_: str):
    """Insert a new insight row — keeps full history, one row per day per entity."""
    now = datetime.now(timezone.utc)
    db.add(PageInsight(
        entity_type=entity_type,
        entity_code=entity_code,
        summary=text_,
        generated_at=now,
    ))


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
    Daily 2am UTC: regenerate stable page summaries for countries, stocks, commodities, trade pairs.
    Uses Gemini 2.5 Flash if GEMINI_API_KEY is set, else polished templates.
    Summaries are factual/descriptive — only regenerate when underlying data changes meaningfully.
    """
    db = SessionLocal()
    try:
        total = 0

        # Pre-load existing summaries into a lookup dict to avoid N+1 queries
        existing_map: dict[tuple, PageSummary] = {
            (r.entity_type, r.entity_code): r
            for r in db.query(PageSummary).all()
        }

        skipped = 0

        # Country summaries
        countries = db.query(Country).all()
        for c in countries:
            existing = existing_map.get(("country", c.code))
            if not _country_summary_stale(c, existing, db):
                skipped += 1
                continue
            try:
                summary = _country_summary_text(c, db)
                _upsert_summary(db, "country", c.code, summary)
                total += 1
            except Exception as e:
                log.warning("Country summary failed %s: %s", c.code, e)
        db.commit()
        log.info("Country summaries: %d regenerated, %d skipped (up to date)", total, skipped)

        # Stock summaries
        stocks = db.query(Asset).filter(Asset.asset_type == "stock").all()
        stock_skip = 0
        for s in stocks:
            existing = existing_map.get(("stock", s.symbol))
            if not _stock_summary_stale(s, existing, db):
                stock_skip += 1
                continue
            try:
                summary = _stock_summary_text(s, db)
                _upsert_summary(db, "stock", s.symbol, summary)
                total += 1
            except Exception as e:
                log.warning("Stock summary failed %s: %s", s.symbol, e)
        db.commit()
        log.info("Stock summaries: %d regenerated, %d skipped", total, stock_skip)

        # Commodity summaries
        commodities = db.query(Asset).filter(Asset.asset_type == "commodity").all()
        comm_skip = 0
        for c in commodities:
            existing = existing_map.get(("commodity", c.symbol))
            if not _commodity_summary_stale(existing):
                comm_skip += 1
                continue
            try:
                summary = _commodity_summary_text(c)
                _upsert_summary(db, "commodity", c.symbol, summary)
                total += 1
            except Exception as e:
                log.warning("Commodity summary failed %s: %s", c.symbol, e)
        db.commit()
        log.info("Commodity summaries: %d regenerated, %d skipped", total, comm_skip)

        # Trade pair summaries — latest year per pair only
        pairs = db.query(TradePair).order_by(TradePair.year.desc()).all()
        seen_pairs: set[str] = set()
        trade_skip = 0
        for pair in pairs:
            exp = db.query(Country).filter(Country.id == pair.exporter_id).first()
            imp = db.query(Country).filter(Country.id == pair.importer_id).first()
            if not exp or not imp:
                continue
            pair_code = f"{exp.code}-{imp.code}"
            if pair_code in seen_pairs:
                continue
            seen_pairs.add(pair_code)
            existing = existing_map.get(("trade", pair_code))
            if not _trade_summary_stale(pair_code, pair.year, existing):
                trade_skip += 1
                continue
            try:
                summary = _trade_summary_text(exp, imp, pair)
                _upsert_summary(db, "trade", pair_code, summary)
                total += 1
            except Exception as e:
                log.warning("Trade summary failed %s: %s", pair_code, e)
        db.commit()
        log.info("Trade summaries: %d regenerated, %d skipped", total, trade_skip)

        log.info("Total summaries regenerated: %d (data-driven skips applied)", total)
        return {"summaries_generated": total, "skipped": skipped + stock_skip + comm_skip + trade_skip}

    except Exception as exc:
        db.rollback()
        log.error("generate_page_summaries failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@app.task(name="tasks.summaries.generate_daily_insights", bind=True, max_retries=2)
def generate_daily_insights(self):
    """
    Daily 5am UTC: regenerate opinionated AI insights for all key pages.
    Insights are forward-looking analyst takes — always refreshed daily regardless of data changes.
    Stored as entity_type = 'country_insight', 'stock_insight', 'commodity_insight'.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        log.warning("generate_daily_insights: no GEMINI_API_KEY — skipping")
        return {"skipped": True}

    db = SessionLocal()
    try:
        total = 0

        now = datetime.now(timezone.utc)

        # Country insights
        countries = db.query(Country).all()
        for c in countries:
            try:
                insight = _country_insight_text(c, db)
                if insight:
                    _upsert_summary(db, "country_insight", c.code, insight)
                    _insert_insight(db, "country", c.code, insight)
                    _upsert_feed_insight(db, now,
                        title=f"{c.flag_emoji or '🌍'} {c.name} — Daily Macro Insight",
                        body=insight,
                        source_url=f"/countries/{c.code.lower()}",
                        entity_type="country",
                        entity_name=c.name,
                        entity_flag=c.flag_emoji or "🌍",
                        related_country_ids=[c.id],
                        importance_score=6.0,
                    )
                    total += 1
            except Exception as e:
                log.warning("Country insight failed %s: %s", c.code, e)
        db.commit()
        log.info("Country insights done: %d", total)

        # Stock insights
        stock_count = 0
        stocks = db.query(Asset).filter(Asset.asset_type == "stock").all()
        for s in stocks:
            try:
                insight = _stock_insight_text(s, db)
                if insight:
                    _upsert_summary(db, "stock_insight", s.symbol, insight)
                    _insert_insight(db, "stock", s.symbol, insight)
                    _upsert_feed_insight(db, now,
                        title=f"{s.symbol} — Daily Equity Insight",
                        body=insight,
                        source_url=f"/stocks/{s.symbol}",
                        entity_type="stock",
                        entity_name=s.name,
                        entity_flag=s.symbol[:2],
                        related_asset_ids=[s.id],
                        importance_score=6.5,
                    )
                    total += 1
                    stock_count += 1
            except Exception as e:
                log.warning("Stock insight failed %s: %s", s.symbol, e)
        db.commit()
        log.info("Stock insights done: %d", stock_count)

        # Commodity insights
        commodity_count = 0
        commodities = db.query(Asset).filter(Asset.asset_type == "commodity").all()
        for c in commodities:
            try:
                insight = _commodity_insight_text(c)
                if insight:
                    meta = COMMODITY_META.get(c.symbol, {})
                    _upsert_summary(db, "commodity_insight", c.symbol, insight)
                    _insert_insight(db, "commodity", c.symbol, insight)
                    _upsert_feed_insight(db, now,
                        title=f"{meta.get('full_name', c.name)} — Daily Commodity Insight",
                        body=insight,
                        source_url=f"/stocks/{c.symbol}",
                        entity_type="commodity",
                        entity_name=meta.get("full_name", c.name),
                        entity_flag=_commodity_emoji(c.symbol),
                        related_asset_ids=[c.id],
                        importance_score=6.0,
                    )
                    total += 1
                    commodity_count += 1
            except Exception as e:
                log.warning("Commodity insight failed %s: %s", c.symbol, e)
        db.commit()
        log.info("Commodity insights done: %d", commodity_count)

        # Trade pair insights — latest year per pair only
        trade_count = 0
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
                insight = _trade_insight_text(exp, imp, pair)
                if insight:
                    _upsert_summary(db, "trade_insight", pair_code, insight)
                    _insert_insight(db, "trade", pair_code, insight)
                    _upsert_feed_insight(db, now,
                        title=f"{exp.flag_emoji or ''} {exp.name} ↔ {imp.flag_emoji or ''} {imp.name} — Trade Insight",
                        body=insight,
                        source_url=f"/trade/{pair_code.lower()}",
                        entity_type="trade",
                        entity_name=f"{exp.name}–{imp.name}",
                        entity_flag=exp.flag_emoji or "🌐",
                        related_country_ids=[exp.id, imp.id],
                        importance_score=5.5,
                    )
                    total += 1
                    trade_count += 1
            except Exception as e:
                log.warning("Trade insight failed %s: %s", pair_code, e)
        db.commit()
        log.info("Trade insights done: %d", trade_count)

        log.info("Total daily insights generated: %d", total)
        return {"insights_generated": total}

    except Exception as exc:
        db.rollback()
        log.error("generate_daily_insights failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@app.task(name="tasks.summaries.refresh_entity_summary", bind=True, max_retries=1)
def refresh_entity_summary(self, entity_type: str, entity_code: str):
    """
    Refresh a single entity summary on demand.
    entity_type: 'country' | 'stock' | 'commodity' | 'trade'
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
        elif entity_type == "commodity":
            asset = db.query(Asset).filter(
                Asset.symbol == entity_code.upper(), Asset.asset_type == "commodity"
            ).first()
            if asset:
                summary = _commodity_summary_text(asset)
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
