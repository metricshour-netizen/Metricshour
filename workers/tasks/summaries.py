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
import hashlib
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, date, timedelta

from sqlalchemy import text, select, func, delete

from celery_app import app
from app.database import SessionLocal
from app.storage import get_redis
from app.models.country import Country, CountryIndicator, TradePair
from app.models.asset import Asset, StockCountryRevenue, Price
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


# ── AI helpers ────────────────────────────────────────────────────────────────
# Cost-optimised routing:
#   gemini-2.5-flash      → long-form content (G20, quality matters)
#   gemini-2.5-flash-lite → short insights (fast, cheap)
#   deepseek-chat            → primary bulk (cheapest; Gemini is fallback only)
#
#   prefer_gemini=True  → Gemini first, DeepSeek fallback  (used for G20 only)
#   prefer_gemini=False → DeepSeek first, Gemini fallback  (all other entities)
#
# Long-form (>150w): gemini-2.5-flash. Short insights: flash-lite via caller override.
# Keys never logged.
# Falls back gracefully if either key is absent.

MAX_SUMMARY_WORKERS = 4  # concurrent threads for bulk AI calls; stays within DB pool

_MD_RE = None  # compiled lazily


def _strip_markdown(text: str) -> str:
    global _MD_RE
    import re
    if _MD_RE is None:
        _MD_RE = re.compile(r"^[#*\-]+\s*", re.MULTILINE)
    if text[:2] in ("**", "# ", "- "):
        text = _MD_RE.sub("", text).strip()
    return text


def _call_gemini(prompt: str, min_words: int = 55, max_words: int = 110,
                 model: str = "gemini-2.5-flash") -> str | None:
    """Call Gemini AI model. Returns None on any failure."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types as genai_types
        client = genai.Client(api_key=api_key)
        r = client.models.generate_content(
            model=model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=_SHARED_SYSTEM,
                temperature=0.1,
                max_output_tokens=int(max_words * 2.5),  # ~1.5 tok/word + buffer
            ),
        )
        text = _strip_markdown(r.text.strip())
        words = len(text.split())
        if (min_words - 8) <= words <= (max_words + 8):
            return text
        return None
    except Exception as exc:
        log.debug("Gemini call failed (%s): %s", model, exc)
        return None


_SHARED_SYSTEM = (
    "You are a financial data writer for an institutional terminal. "
    "OUTPUT ONLY the paragraph requested — no greeting, no sign-off, no 'Certainly', "
    "no meta-commentary, no markdown, no ellipsis, no em-dashes as separators. "
    "Use only numbers and facts from the provided data — never invent statistics. "
    "Active voice only. Assert — never hedge. Do not use: could, may, might, would likely, "
    "appears to, seems to, is expected to, is likely to, is poised to. "
    "Zero filler. Begin writing immediately with the first data point. "
    "BANNED WORDS (never use): navigates, robust, resilient, notable, significant, landscape, "
    "remains, amid, complex, dynamic, headwinds, tailwinds, uncertainty, poised, well-positioned, "
    "strategic, synergies, leverage, ecosystem, stakeholders, underscores, highlights, reflects, "
    "showcases, demonstrates, continues to, going forward, in conclusion, furthermore, moreover, "
    "it is worth noting, it should be noted, plays a key role, plays a crucial role, "
    "boasts, boasting, bolsters, bolstering, underpins, underpinning, spurs, spurring."
)
_DS_SYSTEM = _SHARED_SYSTEM


def _call_deepseek(prompt: str, min_words: int = 55, max_words: int = 110) -> str | None:
    """Call DeepSeek V3 (OpenAI-compatible REST). Returns None on any failure."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return None
    try:
        import requests as _req
        resp = _req.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": _DS_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 900,
                "temperature": 0.1,
                "frequency_penalty": 0.3,
            },
            timeout=30,
        )
        resp.raise_for_status()
        text = _strip_markdown(resp.json()["choices"][0]["message"]["content"].strip())
        words = len(text.split())
        if (min_words - 8) <= words <= (max_words + 5):
            return text
        return None
    except Exception as exc:
        log.debug("DeepSeek call failed: %s", exc)
        return None


def _call_ai(prompt: str, min_words: int = 55, max_words: int = 110,
             prefer_gemini: bool = False) -> str | None:
    """
    Cost-optimised AI routing — both paths use gemini-2.5-flash-lite:
      prefer_gemini=True  → Gemini first, DeepSeek fallback  (G20 / top corridors)
      prefer_gemini=False → DeepSeek first, Gemini fallback  (everything else)
    """
    if prefer_gemini:
        return (
            _call_gemini(prompt, min_words, max_words)
            or _call_deepseek(prompt, min_words, max_words)
        )
    return (
        _call_deepseek(prompt, min_words, max_words)
        or _call_gemini(prompt, min_words, max_words)
    )


def _has_ai_key() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("GEMINI_API_KEY"))


# ── Country summary ────────────────────────────────────────────────────────────

def _country_summary_text(country: Country, db) -> str:
    """
    Stable 75-100 word macro overview for a country page.
    Uses Gemini AI with real indicator data. Falls back to polished template.
    """
    ind: dict[str, float] = {}
    rows = db.execute(
        select(CountryIndicator)
        .where(
            CountryIndicator.country_id == country.id,
            CountryIndicator.indicator.in_([
                "gdp_usd", "gdp_growth_pct", "inflation_pct",
                "interest_rate_pct", "unemployment_pct",
                "current_account_usd", "government_debt_gdp_pct",
            ])
        )
        .order_by(CountryIndicator.period_date.desc())
        .limit(30)
    ).scalars().all()
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
    debt = ind.get("government_debt_gdp_pct")

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

    if _has_ai_key():
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
            f"Country overview — {country.name} — 220-280 words. Third-person. No title. No headings.\n\n"
            f"Data:\n{facts}\n\n"
            f"Write 5 tight paragraphs (2-3 sentences each):\n"
            f"1. GDP size and growth: classify the economy ({dev_status}), state GDP and growth rate. Compare to a well-known benchmark only if the comparison is meaningful.\n"
            f"2. Monetary policy: state the inflation rate and central bank policy rate. Describe the stance (restrictive/neutral/accommodative) and the real rate (policy minus inflation).\n"
            f"3. Labour and fiscal: state unemployment and government debt as % of GDP. Assess fiscal sustainability. State what the S&P rating (or its absence) implies about sovereign credit risk.\n"
            f"4. External position: major exports and the country's primary trade dependency. Use only data provided — do not invent trade share percentages.\n"
            f"5. Geopolitical and structural: bloc memberships that shape trade and capital flows, currency, and the single biggest structural risk or opportunity for investors.\n"
            f"Rules: use provided numbers only — never invent statistics. No filler phrases. No repeated points. Every paragraph must add new information. End with a period."
        )
        # G20 countries → Gemini (quality tier); rest → DeepSeek (bulk tier)
        ai = _call_ai(prompt, min_words=200, max_words=320, prefer_gemini=bool(country.is_g20))
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
    Opinionated analyst take for a country page.
    Focuses on the single most investable signal in the data — not a description.
    """
    if not _has_ai_key():
        return None

    ind: dict[str, float] = {}
    rows = db.execute(
        select(CountryIndicator)
        .where(
            CountryIndicator.country_id == country.id,
            CountryIndicator.indicator.in_([
                "gdp_usd", "gdp_growth_pct", "inflation_pct",
                "interest_rate_pct", "unemployment_pct",
                "current_account_usd", "government_debt_gdp_pct",
                "current_account_gdp_pct",
            ])
        )
        .order_by(CountryIndicator.period_date.desc())
        .limit(40)
    ).scalars().all()
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

    def _f1(key: str) -> str:
        v = ind.get(key)
        return f"{v:.1f}%" if v is not None else "N/A"

    def _f2(key: str) -> str:
        v = ind.get(key)
        return f"{v:.2f}%" if v is not None else "N/A"

    # Real interest rate = policy rate - inflation (key FX/bond signal)
    rate = ind.get("interest_rate_pct")
    infl = ind.get("inflation_pct")
    real_rate = f"{(rate - infl):.1f}%" if rate is not None and infl is not None else "N/A"

    # Build facts block with only available data — omit any field that would show N/A
    fact_lines = [f"Country: {country.name} ({country.code})"]
    if country.currency_code:
        fact_lines[0] += f" | Currency: {country.currency_code}"
    gdp_str = _fmt_gdp(ind.get('gdp_usd'))
    gdp_growth = ind.get('gdp_growth_pct')
    if gdp_str != "N/A" or gdp_growth is not None:
        parts = []
        if gdp_str != "N/A": parts.append(f"GDP: {gdp_str}")
        if gdp_growth is not None: parts.append(f"GDP growth: {gdp_growth:.1f}%")
        fact_lines.append(" | ".join(parts))
    if infl is not None or rate is not None:
        parts = []
        if infl is not None: parts.append(f"Inflation: {infl:.1f}%")
        if rate is not None: parts.append(f"Policy rate: {rate:.2f}%")
        if real_rate != "N/A": parts.append(f"Real rate: {real_rate}")
        fact_lines.append(" | ".join(parts))
    if ind.get("unemployment_pct") is not None:
        fact_lines.append(f"Unemployment: {ind['unemployment_pct']:.1f}%")
    if ind.get("current_account_gdp_pct") is not None:
        fact_lines.append(f"Current account: {ind['current_account_gdp_pct']:.1f}% of GDP")
    if ind.get("government_debt_gdp_pct") is not None:
        fact_lines.append(f"Govt debt/GDP: {ind['government_debt_gdp_pct']:.1f}%")
    if country.credit_rating_sp:
        fact_lines.append(f"S&P rating: {country.credit_rating_sp}")
    fact_lines.append(f"Blocs: {', '.join(groups) if groups else 'UN member'}")
    fact_lines.append(f"Date: {date.today().strftime('%B %d, %Y')}")
    facts = "\n".join(fact_lines) + "\n"

    # Only offer angles where the key data exists — avoids N/A appearing in AI output
    _COUNTRY_ANGLES = []
    if real_rate != "N/A" and rate is not None and infl is not None:
        _COUNTRY_ANGLES.append((45, 60,
         f"The real rate for {country.name} is {real_rate} (policy {_f2('interest_rate_pct')} minus inflation {_f1('inflation_pct')}). "
         f"Open with what that spread means for the currency and bond market right now, citing the exact numbers. "
         f"Then say what it implies for the next policy move. Close with the specific data release or CB meeting that will reset this trade."))
    if ind.get("current_account_gdp_pct") is not None:
        _COUNTRY_ANGLES.append((50, 65,
         f"Open with {country.name}'s current account ({_f1('current_account_gdp_pct')} of GDP) and what it means for FX and capital flows — "
         f"name the pressure specifically (surplus = currency support, deficit = funding risk). "
         f"Then identify the most acute near-term FX risk. Close with the trade or policy event nearest to today that could reprice it."))
    if ind.get("gdp_growth_pct") is not None and ind.get("unemployment_pct") is not None:
        _COUNTRY_ANGLES.append((55, 70,
         f"Open with the tension between GDP growth ({_f1('gdp_growth_pct')}) and unemployment ({_f1('unemployment_pct')}) "
         f"and what it means for consumer spending and equities — name the sector most exposed. "
         f"Then say whether this is acceleration or deceleration and why it matters now. "
         f"Close with the next GDP or labour print to watch."))
    if ind.get("government_debt_gdp_pct") is not None and country.credit_rating_sp:
        _COUNTRY_ANGLES.append((45, 60,
         f"Open with {country.name}'s debt/GDP ({_f1('government_debt_gdp_pct')}) and S&P rating ({country.credit_rating_sp}) — "
         f"is the fiscal position sustainable at a real rate of {real_rate if real_rate != 'N/A' else 'current rates'}? "
         f"State the bond market implication directly. Close with the next budget event, auction, or ratings review."))

    # Skip AI entirely if no angle has sufficient data
    if not _COUNTRY_ANGLES:
        log.debug("Skipping AI insight for %s — insufficient data", country.code)
        return None

    angle = _daily_angle(country.code, len(_COUNTRY_ANGLES))
    min_w, max_w, focus = _COUNTRY_ANGLES[angle]

    prompt = (
        f"Daily macro brief — {country.name} — {min_w}–{max_w} words. "
        f"Audience: FX and EM equity traders. No narrative — numbers only.\n\n"
        f"Data (World Bank / IMF):\n{facts}\n\n"
        f"{focus}\n\n"
        f"Rules: opening sentence must name a specific rate, percentage, or dollar figure. "
        f"Every sentence asserts — no 'could', 'may', 'might'. "
        f"No bullets. No headers. End with a period."
    )
    result = _call_ai(prompt, min_words=min_w - 5, max_words=max_w + 10,
                      prefer_gemini=bool(country.is_g20))
    if result:
        return result

    # Rule-based fallback — uses already-loaded indicator data
    rate = ind.get("interest_rate_pct")
    infl = ind.get("inflation_pct")
    growth = ind.get("gdp_growth_pct")
    debt = ind.get("government_debt_gdp_pct")
    gdp = ind.get("gdp_usd")
    if rate is not None and infl is not None:
        real = rate - infl
        stance = "restrictive" if real > 2 else "accommodative" if real < 0 else "neutral"
        lines = [
            f"{country.name}'s real interest rate is {real:+.1f}% (policy rate {rate:.2f}% minus inflation {infl:.1f}%), a {stance} monetary stance."
        ]
        if growth is not None:
            direction = "expanding" if growth > 0 else "contracting"
            lines.append(f"The economy is {direction} at {growth:.1f}% annually.")
        if debt is not None and country.credit_rating_sp:
            lines.append(f"Government debt stands at {debt:.0f}% of GDP; S&P rates {country.code} {country.credit_rating_sp}.")
        return " ".join(lines)
    if growth is not None:
        gdp_str = _fmt_gdp(gdp)
        lines = [f"{country.name} GDP growth is {growth:.1f}% (GDP: {gdp_str})."]
        if ind.get("unemployment_pct") is not None:
            lines.append(f"Unemployment stands at {ind['unemployment_pct']:.1f}%.")
        if debt is not None:
            lines.append(f"Government debt is {debt:.0f}% of GDP.")
        return " ".join(lines)
    return None


# ── Stock summary ──────────────────────────────────────────────────────────────

def _stock_summary_text(asset: Asset, db) -> str:
    """
    Stable 220-280 word overview for a stock page.
    Focuses on geographic revenue exposure — the MetricsHour differentiator.
    """
    hq = db.execute(select(Country).where(Country.id == asset.country_id)).scalar_one_or_none() if asset.country_id else None

    revs = db.execute(
        select(StockCountryRevenue, Country)
        .join(Country, StockCountryRevenue.country_id == Country.id)
        .where(StockCountryRevenue.asset_id == asset.id)
        .order_by(StockCountryRevenue.revenue_pct.desc())
        .limit(5)
    ).all()

    hq_name = hq.name if hq else "the United States"
    cap_str = _fmt_cap(asset.market_cap_usd)
    sector = asset.sector or "company"

    if _has_ai_key():
        rev_lines = "\n".join(
            f"  - {c.flag_emoji or ''} {c.name}: {r.revenue_pct:.0f}% (FY{r.fiscal_year})"
            for r, c in revs
        ) if revs else "  - Geographic breakdown not yet available (SEC EDGAR pending)"

        prompt = (
            f"Stock overview — {asset.name} ({asset.symbol}) — 220-280 words. Third-person. No title. No headings.\n\n"
            f"Data:\n"
            f"- Sector: {sector} | Industry: {asset.industry or 'N/A'} | HQ: {hq_name} | Cap: {cap_str}\n"
            f"- Geographic revenue (SEC EDGAR 10-K):\n{rev_lines}\n\n"
            f"Write 5 paragraphs, each 2-3 sentences:\n"
            f"(1) Company identity: name, sector, industry, market cap, and HQ country. Context on size within sector.\n"
            f"(2) Top revenue geography: name the country with the highest %, fiscal year, and what that concentration means — FX exposure, tariff risk, or demand cycle. Be specific.\n"
            f"(3) Second and third geographies with percentages — explain whether this is diversification or further concentration risk.\n"
            f"(4) Earnings sensitivity: what does a 100bp move in the dominant market's GDP growth or currency imply for EPS? State the direction and magnitude.\n"
            f"(5) Macro linkage: which country-level indicators (rate decisions, inflation, consumer spending) most directly drive this stock's near-term earnings. Name the data release to watch.\n"
            f"GS equity note style. Every sentence has a number. No padding. End with a period."
        )
        ai = _call_ai(prompt, min_words=130, max_words=320, prefer_gemini=False)
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
        parts.append("Geographic revenue data is tracked using SEC EDGAR 10-K and 10-Q filings.")
    return " ".join(parts)


# ── FX pair summary ────────────────────────────────────────────────────────────

def _fx_summary_text(asset: Asset) -> str:
    """Stable 75-100 word overview for an FX pair page."""
    name = asset.name or asset.symbol
    if _has_ai_key():
        prompt = (
            f"FX pair overview — {name} ({asset.symbol}) — 75-100 words. Third-person. No title.\n\n"
            f"4 sentences:\n"
            f"(1) Name the base and quote currencies, the exchange where this pair trades, and average daily volume in USD trillions.\n"
            f"(2) The primary macro driver of this pair — name the specific central bank, interest rate differential, or economic indicator.\n"
            f"(3) The 2 biggest fundamental factors that historically move this pair — name real events or data releases.\n"
            f"(4) Which equity sectors or commodity markets are most exposed to moves in this currency pair and why.\n"
            f"Every sentence has a number or institution name. No padding. End with a period."
        )
        ai = _call_ai(prompt, min_words=65, max_words=110, prefer_gemini=False)
        if ai:
            return ai
    return (
        f"{name} ({asset.symbol}) is a major foreign exchange pair traded on the global FX market. "
        f"Price movements are driven by interest rate differentials, central bank policy, and macroeconomic data from both economies. "
        f"Trade flows, bilateral economic links, and equity sector exposure for both currencies are tracked on MetricsHour."
    )


# ── Crypto summary ─────────────────────────────────────────────────────────────

def _crypto_summary_text(asset: Asset) -> str:
    """Stable 75-100 word overview for a cryptocurrency page."""
    cap_str = _fmt_cap(asset.market_cap_usd)
    if _has_ai_key():
        prompt = (
            f"Cryptocurrency overview — {asset.name} ({asset.symbol}) — 75-100 words. "
            f"Third-person. No title.\n\n"
            f"Market cap: {cap_str}\n\n"
            f"4 sentences:\n"
            f"(1) What it is — blockchain type, consensus mechanism, and current market cap.\n"
            f"(2) Primary use case — DeFi, smart contracts, payments, store of value — name the specific application.\n"
            f"(3) The 2 dominant price drivers — one on-chain metric, one macro/institutional factor — cite real figures.\n"
            f"(4) Which listed equity sectors carry the most direct exposure to this asset's price moves.\n"
            f"Every sentence has a number or proper noun. No padding. End with a period."
        )
        ai = _call_ai(prompt, min_words=65, max_words=110, prefer_gemini=False)
        if ai:
            return ai
    cap_desc = f"a {cap_str} market cap" if cap_str != "N/A" else "a top"
    return (
        f"{asset.name} ({asset.symbol}) is {cap_desc} cryptocurrency traded on global digital asset exchanges. "
        f"Price movements are driven by on-chain activity, institutional flows, and broader risk appetite. "
        f"Macro exposure and correlated equity sectors are tracked alongside price history on MetricsHour."
    )


# ── ETF summary ────────────────────────────────────────────────────────────────

def _etf_summary_text(asset: Asset) -> str:
    """Stable 75-100 word overview for an ETF page."""
    cap_str = _fmt_cap(asset.market_cap_usd)
    sector = asset.sector or "broad market"
    if _has_ai_key():
        prompt = (
            f"ETF overview — {asset.name} ({asset.symbol}) — 75-100 words. Third-person. No title.\n\n"
            f"AUM: {cap_str} | Category: {sector}\n\n"
            f"4 sentences:\n"
            f"(1) What index or benchmark it tracks, AUM, and the issuer (e.g. iShares, Vanguard, SPDR).\n"
            f"(2) Top 3 sector or geographic exposures with approximate weight percentages.\n"
            f"(3) The primary macro factor — rate environment, credit spreads, or equity cycle — that drives this ETF's returns.\n"
            f"(4) Which investors use it and why — e.g. portfolio hedging, core allocation, tactical exposure.\n"
            f"Every sentence has a number or institution name. No padding. End with a period."
        )
        ai = _call_ai(prompt, min_words=65, max_words=110, prefer_gemini=False)
        if ai:
            return ai
    aum_str = f"{cap_str} AUM" if cap_str != "N/A" else "significant AUM"
    return (
        f"{asset.name} ({asset.symbol}) is an exchange-traded fund with {aum_str} covering the {sector} market. "
        f"It provides investors with diversified exposure to its underlying index or benchmark. "
        f"Price performance, sector weightings, and macro sensitivity are tracked on MetricsHour."
    )


# ── Index summary ──────────────────────────────────────────────────────────────

def _index_summary_text(asset: Asset) -> str:
    """Stable 75-100 word overview for a market index page."""
    sector = asset.sector or "broad market"
    if _has_ai_key():
        prompt = (
            f"Market index overview — {asset.name} ({asset.symbol}) — 75-100 words. Third-person. No title.\n\n"
            f"Category: {sector}\n\n"
            f"4 sentences:\n"
            f"(1) What it tracks — country/region, number of constituents, weighting methodology (market cap, price, equal).\n"
            f"(2) Top 3 sector weights with approximate percentages.\n"
            f"(3) The single most important macro driver for this index — name the rate, currency, or earnings cycle.\n"
            f"(4) Which ETFs or futures contracts are the most liquid vehicles for gaining exposure to this index.\n"
            f"Every sentence has a number or proper noun. No padding. End with a period."
        )
        ai = _call_ai(prompt, min_words=65, max_words=110, prefer_gemini=False)
        if ai:
            return ai
    return (
        f"{asset.name} ({asset.symbol}) is a {sector} market index tracking the performance of its constituent securities. "
        f"Index movements are driven by earnings growth, interest rate expectations, and macro risk sentiment. "
        f"Constituent performance, sector weightings, and country exposure are tracked on MetricsHour."
    )


# ── Bond summary ───────────────────────────────────────────────────────────────

def _bond_summary_text(asset: Asset) -> str:
    """Stable 75-100 word overview for a bond/bond ETF page."""
    cap_str = _fmt_cap(asset.market_cap_usd)
    sector = asset.sector or "fixed income"
    if _has_ai_key():
        prompt = (
            f"Bond / fixed income overview — {asset.name} ({asset.symbol}) — 75-100 words. "
            f"Third-person. No title.\n\n"
            f"AUM/Value: {cap_str} | Category: {sector}\n\n"
            f"4 sentences:\n"
            f"(1) What it is — issuer type (government/corporate/EM), duration, and AUM or notional size.\n"
            f"(2) The current yield or yield range and what it implies about credit risk or duration risk.\n"
            f"(3) The primary macro driver — Fed policy, credit spreads, or EM sovereign risk — name a specific rate or spread.\n"
            f"(4) Which equity sectors or FX markets are most sensitive to moves in this instrument.\n"
            f"Every sentence has a number or institution name. No padding. End with a period."
        )
        ai = _call_ai(prompt, min_words=65, max_words=110, prefer_gemini=False)
        if ai:
            return ai
    aum_str = f"{cap_str}" if cap_str != "N/A" else "large"
    return (
        f"{asset.name} ({asset.symbol}) is a {sector} instrument with {aum_str} in assets. "
        f"Returns are driven by interest rate movements, credit spreads, and central bank policy. "
        f"Duration risk, credit quality, and macro sensitivity are tracked on MetricsHour."
    )


# ── Stock daily insight ────────────────────────────────────────────────────────

def _stock_price_insight_text(asset: Asset, hq, db) -> str | None:
    """
    Price-based insight for stocks without SEC EDGAR geographic revenue data.
    Uses sector, macro context from HQ country, and price momentum.
    """
    if not _has_ai_key():
        return None

    # Latest price
    price_row = db.execute(
        select(Price)
        .where(Price.asset_id == asset.id)
        .order_by(Price.timestamp.desc())
        .limit(1)
    ).scalar_one_or_none()

    price_info = ""
    if price_row:
        chg_pct = ((price_row.close - price_row.open) / price_row.open * 100) if price_row.open else None
        price_info = (
            f"Latest price: {price_row.close:.2f} {asset.currency or 'USD'}"
            + (f" ({chg_pct:+.2f}% vs open)" if chg_pct is not None else "")
        )

    # HQ macro
    hq_macro = ""
    if hq:
        hq_rows = db.execute(
            select(CountryIndicator)
            .where(
                CountryIndicator.country_id == hq.id,
                CountryIndicator.indicator.in_(["gdp_growth_pct", "inflation_pct", "interest_rate_pct"])
            )
            .order_by(CountryIndicator.period_date.desc())
            .limit(9)
        ).scalars().all()
        seen_h: set[str] = set()
        inds: dict[str, float] = {}
        for r in hq_rows:
            if r.indicator not in seen_h:
                inds[r.indicator] = r.value
                seen_h.add(r.indicator)
        parts = []
        if "gdp_growth_pct" in inds:
            parts.append(f"GDP growth {inds['gdp_growth_pct']:.1f}%")
        if "inflation_pct" in inds:
            parts.append(f"inflation {inds['inflation_pct']:.1f}%")
        if "interest_rate_pct" in inds:
            parts.append(f"policy rate {inds['interest_rate_pct']:.2f}%")
        if parts:
            hq_macro = f"HQ macro ({hq.name}): {', '.join(parts)}"

    _PRICE_ANGLES = [
        (45, 60,
         f"Focus on the sector macro cycle. Name how the current rate/inflation environment is "
         f"hitting the {asset.sector or 'sector'} right now — with a specific number. "
         f"Close with the nearest macro catalyst that could reprice the sector."),
        (45, 60,
         f"Focus on valuation and earnings. Open by stating the market cap and what it implies "
         f"for the expected growth rate. Name the biggest near-term earnings catalyst or risk. "
         f"Close with the next data point that reprices this stock."),
        (45, 60,
         f"Focus on capital allocation. Comment on how the current rate environment affects "
         f"this company's cost of capital and shareholder returns. "
         f"Close with the next Fed/central bank decision date and what it means for this sector."),
        (45, 60,
         f"Focus on competitive positioning. Name the macro headwind or tailwind most "
         f"relevant to this sector right now, with a number. "
         f"Close with the sector catalyst that will confirm or deny this trend."),
    ]
    angle = _daily_angle(asset.symbol, len(_PRICE_ANGLES))
    min_w, max_w, focus = _PRICE_ANGLES[angle]

    prompt = (
        f"Daily stock brief — {asset.name} ({asset.symbol}) — {min_w}–{max_w} words. "
        f"Audience: portfolio managers who want EPS signals.\n\n"
        f"Stock: {asset.symbol} | Sector: {asset.sector or 'N/A'} | "
        f"Cap: {_fmt_cap(asset.market_cap_usd)} | HQ: {hq.name if hq else 'N/A'}\n"
        f"{price_info}\n"
        f"{hq_macro}\n"
        f"Date: {date.today().strftime('%B %d, %Y')}\n\n"
        f"{focus}\n\n"
        f"Rules: opening sentence names a specific percentage or dollar figure. "
        f"Every assertion is declarative — no 'could', 'may', 'might'. "
        f"No bullets. No headers. End with a period."
    )
    result = _call_ai(prompt, min_words=min_w - 5, max_words=max_w + 10, prefer_gemini=False)
    if result:
        return result

    # Rule-based fallback using price and sector data
    cap_str = _fmt_cap(asset.market_cap_usd)
    lines = [f"{asset.name} ({asset.symbol}) is a {cap_str} {asset.sector or 'equity'} stock."]
    if price_row:
        chg_pct = ((price_row.close - price_row.open) / price_row.open * 100) if price_row.open else None
        chg_str = f" ({chg_pct:+.1f}% vs open)" if chg_pct is not None else ""
        lines.append(f"Latest price: {price_row.close:.2f} {asset.currency or 'USD'}{chg_str}.")
    if hq_macro:
        lines.append(hq_macro + ".")
    return " ".join(lines)


def _stock_insight_text(asset: Asset, db) -> str | None:
    """
    Opinionated 60-80 word analyst take for a stock page. Generated daily.
    """
    if not _has_ai_key():
        return None

    hq = db.execute(select(Country).where(Country.id == asset.country_id)).scalar_one_or_none() if asset.country_id else None

    revs = db.execute(
        select(StockCountryRevenue, Country)
        .join(Country, StockCountryRevenue.country_id == Country.id)
        .where(StockCountryRevenue.asset_id == asset.id)
        .order_by(StockCountryRevenue.revenue_pct.desc())
        .limit(4)
    ).all()

    if not revs:
        # Fallback: price-based insight for stocks without geographic revenue data
        return _stock_price_insight_text(asset, hq, db)

    rev_lines = "\n".join(
        f"  - {c.flag_emoji or ''} {c.name}: {r.revenue_pct:.0f}% (FY{r.fiscal_year})"
        for r, c in revs
    )

    # Pull HQ country indicators for macro context
    hq_macro = ""
    if hq:
        hq_inds: dict[str, float] = {}
        hq_rows = db.execute(
            select(CountryIndicator)
            .where(
                CountryIndicator.country_id == hq.id,
                CountryIndicator.indicator.in_(["gdp_growth_pct", "inflation_pct", "interest_rate_pct"])
            )
            .order_by(CountryIndicator.period_date.desc())
            .limit(10)
        ).scalars().all()
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

    _STOCK_ANGLES = [
        # 0: geographic revenue risk
        (45, 60,
         f"The top revenue geography is the analytical anchor. Open by naming which market is the single "
         f"biggest EPS risk or upside driver right now — cite the revenue % and the specific macro driver "
         f"(tariff rate, recession, policy rate). Quantify the exposure. Close with the one catalyst or date that could reprice it."),
        # 1: FX translation risk
        (50, 65,
         f"Focus on FX translation. Open by identifying which revenue geography's currency has moved most "
         f"against the reporting currency — cite the move. Translate it into revenue: if that geography is X% "
         f"of sales, a Y% FX move = Z% EPS delta. Close with the central bank decision or macro print that changes this."),
        # 2: earnings catalyst
        (55, 70,
         f"Focus on what happens next to earnings. Open with the most concrete upcoming catalyst — "
         f"product cycle, contract, regulatory decision, or earnings date. Name the geography most exposed. "
         f"Quantify what a miss vs beat means: which revenue line moves, by how much, and what that does to consensus."),
        # 3: sector macro cycle
        (45, 60,
         f"Focus on the macro cycle. Open by saying specifically how the current rate/inflation/credit environment "
         f"is hitting {asset.sector or 'this sector'} right now — not generically, but with a number. "
         f"Then say which revenue geography amplifies or damps that exposure. "
         f"Close with the macro data or policy decision nearest to today that reprices the sector."),
    ]
    angle = _daily_angle(asset.symbol, len(_STOCK_ANGLES))
    min_w, max_w, focus = _STOCK_ANGLES[angle]

    prompt = (
        f"Daily stock brief — {asset.name} ({asset.symbol}) — {min_w}–{max_w} words. "
        f"Audience: portfolio managers who want EPS signals, not company description.\n\n"
        f"Stock: {asset.symbol} | {asset.sector or 'N/A'} | Cap: {_fmt_cap(asset.market_cap_usd)} | HQ: {hq.name if hq else 'N/A'}\n"
        f"{f'{hq_macro}' if hq_macro else ''}\n"
        f"Geographic revenue (SEC EDGAR):\n{rev_lines}\n"
        f"Date: {date.today().strftime('%B %d, %Y')}\n\n"
        f"{focus}\n\n"
        f"Rules: opening sentence names a specific percentage or dollar figure. "
        f"Every assertion is declarative — no 'could', 'may', 'might'. "
        f"No bullets. No headers. End with a period."
    )
    result = _call_ai(prompt, min_words=min_w - 5, max_words=max_w + 10, prefer_gemini=False)
    if result:
        return result

    # Rule-based fallback using geographic revenue data
    top_rev, top_c = revs[0]
    flag = top_c.flag_emoji or ""
    lines = [
        f"{asset.symbol}'s largest revenue market is {flag} {top_c.name} at {top_rev.revenue_pct:.0f}% of sales (FY{top_rev.fiscal_year})."
    ]
    if len(revs) >= 2:
        r2, c2 = revs[1]
        lines.append(f"{c2.flag_emoji or ''} {c2.name} contributes {r2.revenue_pct:.0f}%.")
    if top_rev.revenue_pct >= 40:
        lines.append(
            f"This concentration ties {asset.symbol} earnings directly to macro conditions in {top_c.name}."
        )
    elif len(revs) >= 3:
        r3, c3 = revs[2]
        lines.append(f"Further exposure via {c3.flag_emoji or ''} {c3.name} at {r3.revenue_pct:.0f}%.")
    return " ".join(lines)


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

    if _has_ai_key():
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
            f"Trade corridor overview — {exporter.name}–{importer.name} — 220-280 words. "
            f"Third-person. No title. No headings.\n\n"
            f"Data:\n{facts}\n\n"
            f"Write 5 paragraphs, each 2-3 sentences:\n"
            f"(1) Headline: total bilateral trade value, year, and which country runs a surplus or deficit. State the dollar amount of the imbalance and name which country holds structural leverage.\n"
            f"(2) Export composition: top 2-3 products that {exporter.name} ships to {importer.name} — state each product's approximate share or value and what that reveals (commodity dependence, manufactured goods, intermediate inputs, or strategic technology).\n"
            f"(3) GDP dependency: trade value as % of {exporter.name}'s GDP. State whether this makes the corridor critical or peripheral to the exporting economy. Compare to {importer.name}'s dependency in the reverse direction if data available.\n"
            f"(4) Geopolitical and structural context: name the bilateral treaties, tariff regimes, or sanctions that govern this corridor. State whether the relationship is deepening or at risk of fragmentation.\n"
            f"(5) Investor implications: which listed equity sectors, ETFs, or FX pairs are most exposed to a 10% swing in this trade corridor. Name the specific exposure and why.\n"
            f"Every sentence has a number. No padding. End with a period."
        )
        # G20×G20 corridors → Gemini; all others → DeepSeek
        top_corridor = bool(exporter.is_g20 and importer.is_g20)
        ai = _call_ai(prompt, min_words=190, max_words=310, prefer_gemini=top_corridor)
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
    if not _has_ai_key():
        return None

    if not trade:
        return None

    balance_word = "surplus" if (trade.balance_usd or 0) >= 0 else "deficit"
    products = [p.get("name", "") for p in (trade.top_export_products or [])[:3] if p.get("name")]
    imp_products = [p.get("name", "") for p in (trade.top_import_products or [])[:2] if p.get("name")]
    exp_flag = exporter.flag_emoji or ""
    imp_flag = importer.flag_emoji or ""

    def _grp(c: Country) -> str:
        return ", ".join(g for g, f in [
            ("G7", c.is_g7), ("G20", c.is_g20), ("EU", c.is_eu),
            ("NATO", c.is_nato), ("BRICS", c.is_brics), ("OPEC", c.is_opec),
        ] if f) or "none"

    facts = (
        f"{exp_flag} {exporter.name} ({exporter.code}, {_grp(exporter)}) → "
        f"{imp_flag} {importer.name} ({importer.code}, {_grp(importer)})\n"
        f"Data year: {trade.year}\n"
        f"Exports {exporter.name}→{importer.name}: {_fmt_usd(trade.exports_usd)} "
        f"({f'{trade.exporter_gdp_share_pct:.1f}% of {exporter.name} GDP' if trade.exporter_gdp_share_pct else 'GDP share N/A'})\n"
        f"Imports {importer.name}→{exporter.name}: {_fmt_usd(trade.imports_usd)} "
        f"({f'{trade.importer_gdp_share_pct:.1f}% of {importer.name} GDP' if trade.importer_gdp_share_pct else 'GDP share N/A'})\n"
        f"Trade balance: {_fmt_usd(trade.balance_usd)} ({balance_word} for {exporter.name})\n"
        f"Top exports ({exporter.name}→{importer.name}): {', '.join(products) if products else 'N/A'}\n"
        f"Top imports ({importer.name}→{exporter.name}): {', '.join(imp_products) if imp_products else 'N/A'}\n"
        f"Date: {date.today().strftime('%B %d, %Y')}\n"
    )

    _TRADE_ANGLES = [
        # 0: tariff / policy risk
        (45, 60,
         f"The policy angle. Open with the single highest-impact tariff, sanction, or trade restriction "
         f"on this corridor right now — state the rate or dollar value and who imposed it. "
         f"Name the equity sector or listed stock most exposed. "
         f"Close with the specific negotiation date, election, or vote that could change it."),
        # 1: FX repricing
        (50, 65,
         f"The FX angle. Open with how currency moves between {exporter.currency_code or exporter.code} "
         f"and {importer.currency_code or importer.code} are repricing this corridor — cite the pair and its recent direction. "
         f"Translate it: a weaker exporter currency boosts export competitiveness but squeezes importer margins. "
         f"Close with the next central bank decision for either country."),
        # 2: supply chain concentration
        (55, 70,
         f"The supply chain angle. Open with the single most concentrated product flow in this corridor "
         f"(from the top exports list) and what event could disrupt it. "
         f"Name the alternative supplier country that gains if this corridor breaks. "
         f"Close with the logistics, port, customs, or regulatory trigger nearest to today."),
        # 3: commodity / strategic exposure
        (45, 60,
         f"The commodity angle. Identify the commodity or strategic material embedded in this trade "
         f"relationship's top products. State how exposed this corridor is to a price move in that commodity. "
         f"Quantify the dollar impact of a 10% commodity price swing on this {_fmt_usd(trade.exports_usd)} corridor. "
         f"Close with the next supply or demand catalyst for that commodity."),
    ]
    angle = _daily_angle(f"{exporter.code}-{importer.code}", len(_TRADE_ANGLES))
    min_w, max_w, focus = _TRADE_ANGLES[angle]

    prompt = (
        f"Daily corridor brief — {exporter.name}–{importer.name} — {min_w}–{max_w} words. "
        f"Audience: FX traders and equity investors, not diplomats.\n\n"
        f"Data (UN Comtrade {trade.year}):\n{facts}\n\n"
        f"{focus}\n\n"
        f"Rules: opening sentence names a specific dollar value or percentage from the data. "
        f"Every assertion is declarative — no 'could', 'may', 'might'. "
        f"Banned phrases: 'bilateral relations', 'strategic partnership'. "
        f"No bullets. No headers. End with a period."
    )
    top_corridor = bool(exporter.is_g20 and importer.is_g20)
    result = _call_ai(prompt, min_words=min_w - 5, max_words=max_w + 10,
                      prefer_gemini=top_corridor)
    if result:
        return result

    # Rule-based fallback using trade data already loaded above
    lines = [
        f"{exp_flag} {exporter.name} exported {_fmt_usd(trade.exports_usd)} to"
        f" {imp_flag} {importer.name} in {trade.year},"
        f" running a {_fmt_usd(trade.balance_usd)} trade {balance_word}."
    ]
    if products:
        prod_str = ", ".join(products[:-1]) + f" and {products[-1]}" if len(products) > 1 else products[0]
        lines.append(f"Top {exporter.code} exports: {prod_str}.")
    if trade.exporter_gdp_share_pct:
        critical = "critical" if trade.exporter_gdp_share_pct >= 5 else "notable"
        lines.append(
            f"This corridor represents a {critical} {trade.exporter_gdp_share_pct:.1f}% of {exporter.name}'s GDP."
        )
    return " ".join(lines)


# ── Commodity summary ──────────────────────────────────────────────────────────

def _commodity_summary_text(asset: Asset) -> str:
    """
    Stable 75-100 word overview for a commodity page.
    """
    meta = COMMODITY_META.get(asset.symbol, {})
    full_name = meta.get("full_name", asset.name)
    sector = meta.get("sector", asset.sector or "Commodity")
    unit = meta.get("unit", "USD")

    if _has_ai_key():
        prompt = (
            f"Commodity overview — {full_name} ({asset.symbol}), priced in {unit} — 75-100 words. "
            f"Third-person. No title.\n\n"
            f"4 sentences:\n"
            f"(1) What it is, where it trades (exchange name), and its global annual production or "
            f"consumption volume (use a real figure in million tonnes, barrels, or bushels).\n"
            f"(2) Top 2-3 producer or exporter nations with approximate market share percentages.\n"
            f"(3) The 2 primary price drivers — one supply-side, one demand-side — name the specific "
            f"industry sector or country that drives each.\n"
            f"(4) Which listed equity sectors carry the most direct price exposure "
            f"(e.g. energy majors, mining stocks, food processors) and why.\n"
            f"Every sentence has a number or exchange/country name. No padding. End with a period."
        )
        ai = _call_ai(prompt, min_words=65, max_words=110, prefer_gemini=False)
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

def _commodity_insight_text(asset: Asset, db=None) -> str | None:
    """
    Opinionated analyst take for a commodity page. Includes latest price from DB.
    """
    if not _has_ai_key():
        return None

    meta = COMMODITY_META.get(asset.symbol, {})
    full_name = meta.get("full_name", asset.name)
    sector = meta.get("sector", asset.sector or "Commodity")
    unit = meta.get("unit", "USD")

    # Pull latest daily close + prior close for % change
    price_line = ""
    if db:
        prices = db.execute(
            select(Price.close, Price.timestamp)
            .where(Price.asset_id == asset.id, Price.interval == "1d")
            .order_by(Price.timestamp.desc())
            .limit(2)
        ).all()
        if prices:
            latest_close = prices[0].close
            prior_close = prices[1].close if len(prices) > 1 else None
            pct = f" ({((latest_close - prior_close) / prior_close * 100):+.1f}% prev session)" if prior_close else ""
            price_line = f"Latest price: {latest_close:,.2f} {unit}{pct}\n"

    _COMMODITY_ANGLES = [
        # 0: supply side
        (45, 60,
         f"Open with the single dominant supply-side driver or disruption risk for {full_name} right now — "
         f"name the producer nation, cartel decision, mine, or weather event. "
         f"Identify the nearest catalyst (OPEC meeting, inventory report, sanctions). "
         f"Close by naming which equity sector or trade corridor takes the hardest hit if the disruption deepens."),
        # 1: demand outlook
        (50, 65,
         f"Open with the demand driver — China, US, or the specific industrial sector whose activity is "
         f"moving {full_name} price most right now. Be concrete: which PMI, import figure, or capacity "
         f"utilisation rate tells the story. Close with the next demand-side release that could reprice the market."),
        # 2: dollar / macro
        (45, 60,
         f"Open with how the USD and current macro regime (Fed expectations, recession probability) "
         f"is driving {full_name}. Name the producer-country currency that amplifies the dollar effect — "
         f"a strong dollar squeezes USD-denominated commodity margins in local terms. "
         f"Close with the next Fed decision or CPI print that could reprice both the dollar and this commodity."),
    ]
    angle = _daily_angle(asset.symbol, len(_COMMODITY_ANGLES))
    min_w, max_w, focus = _COMMODITY_ANGLES[angle]

    prompt = (
        f"Daily commodity brief — {full_name} ({asset.symbol}) — {min_w}–{max_w} words. "
        f"Audience: commodity traders who need price signals, not background.\n\n"
        f"{asset.symbol} | {sector} | {unit}\n"
        f"{price_line}"
        f"Date: {date.today().strftime('%B %d, %Y')}\n\n"
        f"{focus}\n\n"
        f"Rules: opening sentence names the current price or a specific supply/demand figure. "
        f"Every assertion is declarative — no 'could', 'may', 'might'. "
        f"Say 'price swings' not 'volatility'. "
        f"No bullets. No headers. End with a period."
    )
    result = _call_ai(prompt, min_words=min_w - 5, max_words=max_w + 10, prefer_gemini=False)
    if result:
        return result

    # Rule-based fallback using price data already loaded above
    lines = [
        f"{full_name} ({asset.symbol}) is a globally traded {sector.lower()} commodity priced in {unit}."
    ]
    if price_line:
        # price_line format: "Latest price: X.XX UNIT (+Y.Y% prev session)\n"
        lines.append(price_line.strip())
    lines.append(
        f"Price is driven by supply and demand dynamics across major producers and consumers. "
        f"Trade flow exposure and equity sector links are tracked on MetricsHour."
    )
    return " ".join(lines)


# ── Emoji helpers ─────────────────────────────────────────────────────────────

_COMMODITY_EMOJI: dict[str, str] = {
    "WTI": "🛢️", "BRENT": "🛢️", "NG": "🔥", "GASOLINE": "⛽", "COAL": "⚫",
    "XAUUSD": "🥇", "XAGUSD": "🥈", "XPTUSD": "⬜", "HG": "🟤", "ALI": "⬛",
    "ZNC": "🔩", "NI": "🔩", "ZW": "🌾", "ZC": "🌽", "ZS": "🟤",
    "KC": "☕", "SB": "🍬", "CT": "🌿", "CC": "🍫", "LE": "🐄", "PALM": "🌴",
}

def _commodity_emoji(symbol: str) -> str:
    return _COMMODITY_EMOJI.get(symbol, "📦")


# ── SEO: angle rotation + dedup ────────────────────────────────────────────────

def _daily_angle(entity_code: str, n_angles: int) -> int:
    """
    Deterministic but day-varying angle index for an entity.
    Same entity returns a different angle each calendar day, preventing structurally
    identical content being written repeatedly to the same URL.
    """
    key = f"{entity_code}{date.today().isoformat()}"
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % n_angles


def _insight_is_duplicate(new_text: str, old_text: str | None, threshold: float = 0.75) -> bool:
    """
    Jaccard similarity check — returns True if the new insight is too similar to the
    previous one. Prevents writing a 'new' page that Google would score as unchanged.
    Uses word-set overlap, ignoring stopwords is intentionally skipped (keep it cheap).
    """
    if not old_text:
        return False
    new_words = set(new_text.lower().split())
    old_words = set(old_text.lower().split())
    union = len(new_words | old_words)
    return (len(new_words & old_words) / union) >= threshold if union else False


# ── Staleness checks — skip summary regeneration if data hasn't changed ────────

def _asset_price_moved(asset_id: int, since: datetime, db, threshold_pct: float = 2.0) -> bool:
    """True if the asset's latest daily close has moved >= threshold_pct since `since`."""
    price_then = db.execute(
        select(Price.close)
        .where(Price.asset_id == asset_id, Price.interval == "1d", Price.timestamp <= since)
        .order_by(Price.timestamp.desc())
        .limit(1)
    ).scalar()
    price_now = db.execute(
        select(Price.close)
        .where(Price.asset_id == asset_id, Price.interval == "1d")
        .order_by(Price.timestamp.desc())
        .limit(1)
    ).scalar()
    if not price_then or not price_now or price_then == 0:
        return False
    return abs((price_now - price_then) / price_then) * 100 >= threshold_pct


def _has_fresh_data(insight_type: str, entity_code: str, since: datetime, db) -> bool:
    """
    True if the underlying data for this entity changed since `since`.
    Used to prioritise and gate insight regeneration — avoids generic daily bulk rewrites.
    - country:   any indicator period_date newer than since
    - stock:     daily price moved >2% since since
    - commodity: daily price moved >2% since since
    - trade:     annual data only — always False (staleness alone drives trade insights)
    """
    if insight_type == "country":
        c = db.execute(select(Country).where(Country.code == entity_code)).scalar_one_or_none()
        if not c:
            return False
        latest = db.execute(
            select(CountryIndicator.period_date)
            .where(CountryIndicator.country_id == c.id)
            .order_by(CountryIndicator.period_date.desc())
            .limit(1)
        ).scalar()
        return bool(latest and latest > since.date())
    if insight_type in ("stock", "commodity"):
        asset = db.execute(select(Asset).where(Asset.symbol == entity_code)).scalars().first()
        if not asset:
            return False
        return _asset_price_moved(asset.id, since, db, threshold_pct=2.0)
    if insight_type == "index":
        asset = db.execute(select(Asset).where(Asset.symbol == entity_code, Asset.asset_type == "index")).scalars().first()
        if not asset:
            return False
        return _asset_price_moved(asset.id, since, db, threshold_pct=1.0)
    return False  # trade: annual data, no intra-day signal


def _country_summary_stale(country: Country, existing: PageSummary | None, db) -> bool:
    """True if the country summary needs regenerating."""
    if not existing:
        return True
    age_days = (datetime.now(timezone.utc) - existing.generated_at).days
    if age_days > 30:
        return True
    # Regenerate if summary is too short (generated before 220-280 word target was set)
    if len(existing.summary.split()) < 200:
        return True
    # Regenerate if any indicator is newer than the summary
    latest_ind = db.execute(
        select(CountryIndicator.period_date)
        .where(CountryIndicator.country_id == country.id)
        .order_by(CountryIndicator.period_date.desc())
        .limit(1)
    ).scalar()
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
    # Regenerate if summary is too short (generated before 220-280 word target was set)
    if len(existing.summary.split()) < 130:
        return True
    # Regenerate if a newer fiscal year of revenue data has arrived
    latest_fy = db.execute(
        select(StockCountryRevenue.fiscal_year)
        .where(StockCountryRevenue.asset_id == asset.id)
        .order_by(StockCountryRevenue.fiscal_year.desc())
        .limit(1)
    ).scalar()
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


def _commodity_summary_stale(asset: Asset, existing: PageSummary | None, db) -> bool:
    """True if the commodity summary needs regenerating.
    Refreshes weekly by default, or sooner if price moved >5% since last generation."""
    if not existing:
        return True
    if (datetime.now(timezone.utc) - existing.generated_at).days > 30:
        return True
    return _asset_price_moved(asset.id, existing.generated_at, db, threshold_pct=5.0)


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
    db.execute(
        delete(FeedEvent).where(
            FeedEvent.event_type == "daily_insight",
            FeedEvent.source_url == source_url,
        )
    )

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
    """Insert daily insight — keeps full history, one row per calendar day per entity."""
    from datetime import date, timedelta
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    tomorrow_start = today_start + timedelta(days=1)
    # Upsert within today — prevents duplicate rows if task runs more than once
    existing_today = db.execute(
        select(PageInsight)
        .where(
            PageInsight.entity_type == entity_type,
            PageInsight.entity_code == entity_code,
            PageInsight.generated_at >= today_start,
            PageInsight.generated_at < tomorrow_start,
        )
    ).scalar_one_or_none()
    if existing_today:
        existing_today.summary = text_
        existing_today.generated_at = now
    else:
        db.add(PageInsight(
            entity_type=entity_type,
            entity_code=entity_code,
            summary=text_,
            generated_at=now,
        ))


def _upsert_summary(db, entity_type: str, entity_code: str, text_: str):
    now = datetime.now(timezone.utc)
    existing = db.execute(
        select(PageSummary)
        .where(PageSummary.entity_type == entity_type, PageSummary.entity_code == entity_code)
    ).scalar_one_or_none()
    if existing:
        if existing.summary == text_:
            return  # No change — skip write
        existing.summary = text_
        existing.generated_at = now
    else:
        db.add(PageSummary(
            entity_type=entity_type,
            entity_code=entity_code,
            summary=text_,
            generated_at=now,
        ))


# ── Thread-safe summary worker ─────────────────────────────────────────────────

def _summary_worker(args: dict) -> dict:
    """
    Thread-safe: opens its own DB session, generates one summary, closes session.
    DB writes happen on the calling thread after this returns.
    """
    entity_type = args["entity_type"]
    entity_code = args["entity_code"]
    db = SessionLocal()
    try:
        if entity_type == "country":
            e = db.execute(select(Country).where(Country.id == args["id"])).scalar_one_or_none()
            text = _country_summary_text(e, db) if e else None
        elif entity_type == "stock":
            e = db.execute(select(Asset).where(Asset.id == args["id"])).scalar_one_or_none()
            text = _stock_summary_text(e, db) if e else None
        elif entity_type == "commodity":
            e = db.execute(select(Asset).where(Asset.id == args["id"])).scalar_one_or_none()
            text = _commodity_summary_text(e) if e else None
        elif entity_type == "trade":
            exp = db.execute(select(Country).where(Country.id == args["exp_id"])).scalar_one_or_none()
            imp = db.execute(select(Country).where(Country.id == args["imp_id"])).scalar_one_or_none()
            pair = db.execute(select(TradePair).where(TradePair.id == args["pair_id"])).scalar_one_or_none()
            text = _trade_summary_text(exp, imp, pair) if exp and imp else None
        elif entity_type == "fx":
            e = db.execute(select(Asset).where(Asset.id == args["id"])).scalar_one_or_none()
            text = _fx_summary_text(e) if e else None
        elif entity_type == "crypto":
            e = db.execute(select(Asset).where(Asset.id == args["id"])).scalar_one_or_none()
            text = _crypto_summary_text(e) if e else None
        elif entity_type == "etf":
            e = db.execute(select(Asset).where(Asset.id == args["id"])).scalar_one_or_none()
            text = _etf_summary_text(e) if e else None
        elif entity_type == "index":
            e = db.execute(select(Asset).where(Asset.id == args["id"])).scalar_one_or_none()
            text = _index_summary_text(e) if e else None
        elif entity_type == "bond":
            e = db.execute(select(Asset).where(Asset.id == args["id"])).scalar_one_or_none()
            text = _bond_summary_text(e) if e else None
        else:
            text = None
        return {"entity_type": entity_type, "entity_code": entity_code, "text": text}
    except Exception as e:
        log.warning("Summary worker failed %s/%s: %s", entity_type, entity_code, e)
        return {"entity_type": entity_type, "entity_code": entity_code, "text": None}
    finally:
        db.close()


# ── Celery tasks ───────────────────────────────────────────────────────────────

@app.task(name="tasks.summaries.generate_page_summaries", bind=True, max_retries=2)
def generate_page_summaries(self):
    """
    Daily 2am UTC: regenerate stable page summaries for all entity types.
    G20 countries + G20×G20 trade corridors → Gemini.
    All other bulk (230 countries, stocks, commodities, non-top trade pairs) → DeepSeek.
    Concurrent: MAX_SUMMARY_WORKERS threads fire AI calls in parallel.
    Schedule unchanged; execution time reduced ~4×.
    """
    db = SessionLocal()
    try:
        existing_map: dict[tuple, PageSummary] = {
            (r.entity_type, r.entity_code): r
            for r in db.execute(select(PageSummary)).scalars().all()
        }

        # ── Build work queue (stale entities only) ──────────────────────────
        work_items: list[dict] = []
        skipped = 0

        for c in db.execute(select(Country)).scalars().all():
            if _country_summary_stale(c, existing_map.get(("country", c.code)), db):
                work_items.append({"entity_type": "country", "entity_code": c.code, "id": c.id})
            else:
                skipped += 1

        for s in db.execute(select(Asset).where(Asset.asset_type == "stock")).scalars().all():
            if _stock_summary_stale(s, existing_map.get(("stock", s.symbol)), db):
                work_items.append({"entity_type": "stock", "entity_code": s.symbol, "id": s.id})
            else:
                skipped += 1

        for c in db.execute(select(Asset).where(Asset.asset_type == "commodity")).scalars().all():
            if _commodity_summary_stale(c, existing_map.get(("commodity", c.symbol)), db):
                work_items.append({"entity_type": "commodity", "entity_code": c.symbol, "id": c.id})
            else:
                skipped += 1

        # Non-commodity asset types — refresh weekly
        for asset_type in ("fx", "crypto", "etf", "index", "bond"):
            for a in db.execute(select(Asset).where(Asset.asset_type == asset_type)).scalars().all():
                existing = existing_map.get((asset_type, a.symbol))
                if not existing or (datetime.now(timezone.utc) - existing.generated_at).days > 7:
                    work_items.append({"entity_type": asset_type, "entity_code": a.symbol, "id": a.id})
                else:
                    skipped += 1

        seen_pairs: set[str] = set()
        for pair in db.execute(select(TradePair).order_by(TradePair.year.desc())).scalars().all():
            exp = db.execute(select(Country).where(Country.id == pair.exporter_id)).scalar_one_or_none()
            imp = db.execute(select(Country).where(Country.id == pair.importer_id)).scalar_one_or_none()
            if not exp or not imp:
                continue
            pair_code = f"{exp.code}-{imp.code}"
            if pair_code in seen_pairs:
                continue
            seen_pairs.add(pair_code)
            if _trade_summary_stale(pair_code, pair.year, existing_map.get(("trade", pair_code))):
                work_items.append({
                    "entity_type": "trade", "entity_code": pair_code,
                    "exp_id": exp.id, "imp_id": imp.id, "pair_id": pair.id,
                })
            else:
                skipped += 1

        log.info("generate_page_summaries: %d stale, %d up-to-date", len(work_items), skipped)

        # ── Process concurrently (workers create own DB sessions) ───────────
        total = 0
        with ThreadPoolExecutor(max_workers=MAX_SUMMARY_WORKERS) as executor:
            futures = {executor.submit(_summary_worker, item): item for item in work_items}
            for future in as_completed(futures):
                result = future.result()
                if result["text"]:
                    _upsert_summary(db, result["entity_type"], result["entity_code"], result["text"])
                    total += 1
                    if total % 20 == 0:
                        db.commit()
                        log.info("  ... %d summaries written", total)

        db.commit()
        log.info("generate_page_summaries complete: %d regenerated, %d skipped", total, skipped)
        return {"summaries_generated": total, "skipped": skipped}

    except Exception as exc:
        db.rollback()
        log.error("generate_page_summaries failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


# ── Index daily insight ────────────────────────────────────────────────────────

INDEX_META: dict[str, dict] = {
    "DJI":    {"full_name": "Dow Jones Industrial Average", "region": "US",     "emoji": "🇺🇸"},
    "SPX":    {"full_name": "S&P 500",                      "region": "US",     "emoji": "🇺🇸"},
    "NDX":    {"full_name": "Nasdaq 100",                   "region": "US",     "emoji": "🇺🇸"},
    "RUT":    {"full_name": "Russell 2000",                 "region": "US",     "emoji": "🇺🇸"},
    "VIX":    {"full_name": "CBOE Volatility Index",        "region": "Global", "emoji": "📊"},
    "UKX":    {"full_name": "FTSE 100",                     "region": "UK",     "emoji": "🇬🇧"},
    "DAX":    {"full_name": "DAX 40",                       "region": "Germany","emoji": "🇩🇪"},
    "CAC":    {"full_name": "CAC 40",                       "region": "France", "emoji": "🇫🇷"},
    "IBEX":   {"full_name": "IBEX 35",                      "region": "Spain",  "emoji": "🇪🇸"},
    "SMI":    {"full_name": "Swiss Market Index",           "region": "Switzerland","emoji": "🇨🇭"},
    "NKY":    {"full_name": "Nikkei 225",                   "region": "Japan",  "emoji": "🇯🇵"},
    "HSI":    {"full_name": "Hang Seng Index",              "region": "HK",     "emoji": "🇭🇰"},
    "SHCOMP": {"full_name": "Shanghai Composite",           "region": "China",  "emoji": "🇨🇳"},
    "SENSEX": {"full_name": "BSE Sensex",                   "region": "India",  "emoji": "🇮🇳"},
    "KOSPI":  {"full_name": "KOSPI",                        "region": "Korea",  "emoji": "🇰🇷"},
    "ASX200": {"full_name": "ASX 200",                      "region": "Australia","emoji": "🇦🇺"},
    "MSCIW":  {"full_name": "MSCI World",                   "region": "Global", "emoji": "🌐"},
    "MSCIEM": {"full_name": "MSCI Emerging Markets",        "region": "Global", "emoji": "🌍"},
}

_INDEX_ANGLES = [
    # 0 — macro driver
    (50, 70,
     "Open with the single macro force moving this index today — Fed policy, earnings season, "
     "or a geopolitical shock. Name the specific catalyst (rate decision date, CPI print, "
     "corporate earnings release). Close by identifying which sector inside the index is "
     "absorbing the most pressure or momentum."),
    # 1 — sector rotation
    (50, 70,
     "Open with which sector inside this index is leading or lagging and why. "
     "Name the specific company or sector weight driving the move. "
     "Close with the next scheduled event that could extend or reverse the rotation."),
    # 2 — cross-asset signal
    (50, 70,
     "Open with the cross-asset signal most correlated to this index right now — "
     "bond yields, dollar, oil, or credit spreads. Name the specific level or threshold "
     "that would shift the index direction. Close with the risk scenario most consensus "
     "is not pricing in."),
]


def _index_insight_text(asset: Asset, db=None) -> str | None:
    if not _has_ai_key():
        return None

    meta = INDEX_META.get(asset.symbol, {})
    full_name = meta.get("full_name", asset.name)
    region = meta.get("region", asset.sector or "Global")

    price_line = ""
    if db:
        prices = db.execute(
            select(Price.close, Price.timestamp)
            .where(Price.asset_id == asset.id, Price.interval == "1d")
            .order_by(Price.timestamp.desc())
            .limit(2)
        ).all()
        if prices:
            latest = prices[0].close
            prior = prices[1].close if len(prices) > 1 else None
            pct = f" ({((latest - prior) / prior * 100):+.1f}% prev session)" if prior else ""
            price_line = f"Latest close: {latest:,.2f}{pct}\n"

    angle = _daily_angle(asset.symbol, len(_INDEX_ANGLES))
    min_w, max_w, focus = _INDEX_ANGLES[angle]

    prompt = (
        f"Daily index brief — {full_name} ({asset.symbol}) — {min_w}–{max_w} words. "
        f"Audience: equity investors who need a sharp market signal, not background.\n\n"
        f"{asset.symbol} | {region} equity index\n"
        f"{price_line}"
        f"Date: {date.today().strftime('%B %d, %Y')}\n\n"
        f"{focus}\n\n"
        f"Rules: opening sentence names the index level or a specific percentage move. "
        f"Every assertion is declarative — no 'could', 'may', 'might'. "
        f"No clichés ('navigating', 'landscape', 'headwinds'). "
        f"Do not mention MetricsHour. Plain text only, no markdown."
    )

    return _call_ai(prompt, min_words=min_w, max_words=max_w)


@app.task(name="tasks.summaries.generate_daily_insights", bind=True, max_retries=2)
def generate_daily_insights(self):
    """
    Daily 5am UTC: regenerate opinionated AI insights for all key pages.
    Insights are forward-looking analyst takes — always refreshed daily regardless of data changes.
    Stored as entity_type = 'country_insight', 'stock_insight', 'commodity_insight'.
    """
    if not _has_ai_key():
        log.warning("generate_daily_insights: no AI key configured — skipping")
        return {"skipped": True}

    db = SessionLocal()
    try:
        total = 0

        now = datetime.now(timezone.utc)

        # Country insights
        countries = db.execute(select(Country)).scalars().all()
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
        stocks = db.execute(select(Asset).where(Asset.asset_type == "stock")).scalars().all()
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
        commodities = db.execute(select(Asset).where(Asset.asset_type == "commodity")).scalars().all()
        for c in commodities:
            try:
                insight = _commodity_insight_text(c, db)
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
        pairs = db.execute(select(TradePair).order_by(TradePair.year.desc())).scalars().all()
        seen_pairs: set[str] = set()
        for pair in pairs:
            exp = db.execute(select(Country).where(Country.id == pair.exporter_id)).scalar_one_or_none()
            imp = db.execute(select(Country).where(Country.id == pair.importer_id)).scalar_one_or_none()
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

        # Index insights
        index_count = 0
        indices = db.execute(select(Asset).where(Asset.asset_type == "index")).scalars().all()
        for idx in indices:
            try:
                insight = _index_insight_text(idx, db)
                if insight:
                    meta = INDEX_META.get(idx.symbol, {})
                    _upsert_summary(db, "index_insight", idx.symbol, insight)
                    _insert_insight(db, "index", idx.symbol, insight)
                    _upsert_feed_insight(db, now,
                        title=f"{meta.get('emoji', '📈')} {meta.get('full_name', idx.name)} — Daily Index Insight",
                        body=insight,
                        source_url=f"/indices/{idx.symbol.lower()}",
                        entity_type="index",
                        entity_name=meta.get("full_name", idx.name),
                        entity_flag=meta.get("emoji", "📈"),
                        related_asset_ids=[idx.id],
                        importance_score=6.5,
                    )
                    total += 1
                    index_count += 1
            except Exception as e:
                log.warning("Index insight failed %s: %s", idx.symbol, e)
        db.commit()
        log.info("Index insights done: %d", index_count)

        log.info("Total daily insights generated: %d", total)
        return {"insights_generated": total}

    except Exception as exc:
        db.rollback()
        log.error("generate_daily_insights failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


# Batch sizes per run — tuned so all entities cycle once per day across multiple runs
_INSIGHT_BATCH = {"country": 25, "stock": 6, "commodity": 5, "trade": 25, "index": 6}


@app.task(name="tasks.summaries.run_insight_batch", bind=True, max_retries=2)
def run_insight_batch(self, insight_type: str):
    """
    Staggered insight generation — called multiple times per day per type.
    Each run processes only the stalest BATCH_SIZE entities (oldest generated_at first,
    never-generated entities first). This spreads page update timestamps throughout the
    day rather than bulk-stamping everything at once, which avoids bulk-AI-content signals.

    insight_type: 'country' | 'stock' | 'commodity' | 'trade'
    """
    if not _has_ai_key():
        log.warning("run_insight_batch(%s): no AI key configured — skipping", insight_type)
        return {"skipped": True}

    batch_size = _INSIGHT_BATCH.get(insight_type, 20)
    summary_type = f"{insight_type}_insight"
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    count = 0

    try:
        # Build full ordered list of entity codes for this type
        if insight_type == "country":
            # Only countries with indicator data — skip uninhabited territories (no angles → always None)
            codes_with_data = {
                row[0] for row in db.execute(
                    select(Country.code)
                    .join(CountryIndicator, CountryIndicator.country_id == Country.id)
                    .distinct()
                ).all()
            }
            all_codes = [row[0] for row in db.execute(select(Country.code)).all() if row[0] in codes_with_data]
        elif insight_type == "stock":
            # All active stocks — price-based fallback handles those without revenue data
            all_codes = [row[0] for row in db.execute(
                select(Asset.symbol)
                .where(Asset.asset_type == "stock", Asset.is_active == True)
            ).all()]
        elif insight_type == "commodity":
            all_codes = [row[0] for row in db.execute(select(Asset.symbol).where(Asset.asset_type == "commodity")).all()]
        elif insight_type == "trade":
            pairs = db.execute(select(TradePair).order_by(TradePair.year.desc())).scalars().all()
            seen: set[str] = set()
            all_codes = []
            for p in pairs:
                exp_code = db.execute(select(Country.code).where(Country.id == p.exporter_id)).scalar()
                imp_code = db.execute(select(Country.code).where(Country.id == p.importer_id)).scalar()
                if exp_code and imp_code:
                    code = f"{exp_code}-{imp_code}"
                    if code not in seen:
                        seen.add(code)
                        all_codes.append(code)
        elif insight_type == "index":
            all_codes = [row[0] for row in db.execute(select(Asset.symbol).where(Asset.asset_type == "index")).all()]
        else:
            log.error("run_insight_batch: unknown type %s", insight_type)
            return {"error": "unknown_type"}

        # Preload existing insights: code → (generated_at, summary_text)
        _existing_rows = db.execute(
            select(PageSummary.entity_code, PageSummary.generated_at, PageSummary.summary)
            .where(PageSummary.entity_type == summary_type)
        ).all()
        existing_ts: dict[str, datetime] = {r.entity_code: r.generated_at for r in _existing_rows}
        existing_texts: dict[str, str] = {r.entity_code: r.summary for r in _existing_rows}
        _epoch = datetime.min.replace(tzinfo=timezone.utc)
        min_age_cutoff = now - timedelta(hours=22)

        # Build candidate list with priority:
        #   priority 0 = has fresh data (goes first regardless of age)
        #   priority 1 = old enough but no fresh data (normal staleness rotation)
        #   excluded   = generated recently AND no data change (skip entirely)
        candidates: list[tuple[int, datetime, str]] = []
        for code in all_codes:
            last_gen = existing_ts.get(code)
            if last_gen and last_gen > min_age_cutoff:
                # Generated within last 22h — only include if underlying data changed
                if _has_fresh_data(insight_type, code, last_gen, db):
                    candidates.append((0, last_gen, code))
                # else: skip — no new information to write about
            else:
                # Never generated or old enough — include; bump priority if data changed
                fresh = _has_fresh_data(insight_type, code, last_gen or _epoch, db) if last_gen else True
                candidates.append((0 if fresh else 1, last_gen or _epoch, code))

        # Sort: data-fresh entities first, then oldest-generated within each priority group
        candidates.sort(key=lambda x: (x[0], x[1]))
        batch = [c[2] for c in candidates[:batch_size]]

        for entity_code in batch:
            try:
                if insight_type == "country":
                    c = db.execute(select(Country).where(Country.code == entity_code)).scalar_one_or_none()
                    if not c:
                        continue
                    insight = _country_insight_text(c, db)
                    if insight and _insight_is_duplicate(insight, existing_texts.get(entity_code)):
                        log.debug("Skipping %s — new insight too similar to previous (no new data)", entity_code)
                        continue
                    if insight:
                        _upsert_summary(db, summary_type, entity_code, insight)
                        _insert_insight(db, "country", entity_code, insight)
                        _upsert_feed_insight(db, now,
                            title=f"{c.flag_emoji or '🌍'} {c.name} — Daily Macro Insight",
                            body=insight,
                            source_url=f"/countries/{entity_code.lower()}",
                            entity_type="country",
                            entity_name=c.name,
                            entity_flag=c.flag_emoji or "🌍",
                            related_country_ids=[c.id],
                            importance_score=6.0,
                        )
                        count += 1

                elif insight_type == "stock":
                    s = db.execute(select(Asset).where(Asset.symbol == entity_code, Asset.asset_type == "stock")).scalars().first()
                    if not s:
                        continue
                    insight = _stock_insight_text(s, db)
                    if insight and _insight_is_duplicate(insight, existing_texts.get(entity_code)):
                        log.debug("Skipping %s — insight too similar to previous", entity_code)
                        continue
                    if insight:
                        _upsert_summary(db, summary_type, entity_code, insight)
                        _insert_insight(db, "stock", entity_code, insight)
                        _upsert_feed_insight(db, now,
                            title=f"{entity_code} — Daily Equity Insight",
                            body=insight,
                            source_url=f"/stocks/{entity_code}",
                            entity_type="stock",
                            entity_name=s.name,
                            entity_flag=entity_code[:2],
                            related_asset_ids=[s.id],
                            importance_score=6.5,
                        )
                        count += 1

                elif insight_type == "commodity":
                    c = db.execute(select(Asset).where(Asset.symbol == entity_code, Asset.asset_type == "commodity")).scalars().first()
                    if not c:
                        continue
                    insight = _commodity_insight_text(c, db)
                    if insight and _insight_is_duplicate(insight, existing_texts.get(entity_code)):
                        log.debug("Skipping %s — insight too similar to previous", entity_code)
                        continue
                    if insight:
                        meta = COMMODITY_META.get(entity_code, {})
                        _upsert_summary(db, summary_type, entity_code, insight)
                        _insert_insight(db, "commodity", entity_code, insight)
                        _upsert_feed_insight(db, now,
                            title=f"{meta.get('full_name', c.name)} — Daily Commodity Insight",
                            body=insight,
                            source_url=f"/stocks/{entity_code}",
                            entity_type="commodity",
                            entity_name=meta.get("full_name", c.name),
                            entity_flag=_commodity_emoji(entity_code),
                            related_asset_ids=[c.id],
                            importance_score=6.0,
                        )
                        count += 1

                elif insight_type == "trade":
                    exp_code, imp_code = entity_code.split("-", 1)
                    exp = db.execute(select(Country).where(Country.code == exp_code)).scalar_one_or_none()
                    imp = db.execute(select(Country).where(Country.code == imp_code)).scalar_one_or_none()
                    if not exp or not imp:
                        continue
                    pair = db.execute(
                        select(TradePair)
                        .where(TradePair.exporter_id == exp.id, TradePair.importer_id == imp.id)
                        .order_by(TradePair.year.desc())
                        .limit(1)
                    ).scalars().first()
                    insight = _trade_insight_text(exp, imp, pair)
                    if insight and _insight_is_duplicate(insight, existing_texts.get(entity_code)):
                        log.debug("Skipping %s — insight too similar to previous", entity_code)
                        continue
                    if insight:
                        _upsert_summary(db, summary_type, entity_code, insight)
                        _insert_insight(db, "trade", entity_code, insight)
                        _upsert_feed_insight(db, now,
                            title=f"{exp.flag_emoji or ''} {exp.name} ↔ {imp.flag_emoji or ''} {imp.name} — Trade Insight",
                            body=insight,
                            source_url=f"/trade/{entity_code.lower()}",
                            entity_type="trade",
                            entity_name=f"{exp.name}–{imp.name}",
                            entity_flag=exp.flag_emoji or "🌐",
                            related_country_ids=[exp.id, imp.id],
                            importance_score=5.5,
                        )
                        count += 1

                elif insight_type == "index":
                    idx = db.execute(select(Asset).where(Asset.symbol == entity_code, Asset.asset_type == "index")).scalars().first()
                    if not idx:
                        continue
                    insight = _index_insight_text(idx, db)
                    if insight and _insight_is_duplicate(insight, existing_texts.get(entity_code)):
                        log.debug("Skipping %s — insight too similar to previous", entity_code)
                        continue
                    if insight:
                        meta = INDEX_META.get(entity_code, {})
                        _upsert_summary(db, summary_type, entity_code, insight)
                        _insert_insight(db, "index", entity_code, insight)
                        _upsert_feed_insight(db, now,
                            title=f"{meta.get('emoji', '📈')} {meta.get('full_name', idx.name)} — Daily Index Insight",
                            body=insight,
                            source_url=f"/indices/{entity_code.lower()}",
                            entity_type="index",
                            entity_name=meta.get("full_name", idx.name),
                            entity_flag=meta.get("emoji", "📈"),
                            related_asset_ids=[idx.id],
                            importance_score=6.5,
                        )
                        count += 1

            except Exception as e:
                log.warning("Insight failed %s/%s: %s", insight_type, entity_code, e)
            db.commit()

        log.info("run_insight_batch(%s): %d generated", insight_type, count)
        return {"insight_type": insight_type, "generated": count}

    except Exception as exc:
        db.rollback()
        log.error("run_insight_batch(%s) failed: %s", insight_type, exc)
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
            country = db.execute(select(Country).where(Country.code == entity_code.upper())).scalar_one_or_none()
            if country:
                summary = _country_summary_text(country, db)
        elif entity_type == "stock":
            asset = db.execute(select(Asset).where(Asset.symbol == entity_code.upper())).scalar_one_or_none()
            if asset:
                summary = _stock_summary_text(asset, db)
        elif entity_type == "commodity":
            asset = db.execute(
                select(Asset).where(Asset.symbol == entity_code.upper(), Asset.asset_type == "commodity")
            ).scalar_one_or_none()
            if asset:
                summary = _commodity_summary_text(asset)
        elif entity_type == "fx":
            asset = db.execute(select(Asset).where(Asset.symbol == entity_code.upper())).scalar_one_or_none()
            if asset:
                summary = _fx_summary_text(asset)
        elif entity_type == "crypto":
            asset = db.execute(select(Asset).where(Asset.symbol == entity_code.upper())).scalar_one_or_none()
            if asset:
                summary = _crypto_summary_text(asset)
        elif entity_type in ("etf", "index", "bond"):
            asset = db.execute(select(Asset).where(Asset.symbol == entity_code.upper())).scalar_one_or_none()
            if asset:
                fn = {"etf": _etf_summary_text, "index": _index_summary_text, "bond": _bond_summary_text}[entity_type]
                summary = fn(asset)
        elif entity_type == "trade":
            codes = entity_code.upper().split("-")
            if len(codes) == 2:
                exp = db.execute(select(Country).where(Country.code == codes[0])).scalar_one_or_none()
                imp = db.execute(select(Country).where(Country.code == codes[1])).scalar_one_or_none()
                if exp and imp:
                    trade = db.execute(
                        select(TradePair)
                        .where(TradePair.exporter_id == exp.id, TradePair.importer_id == imp.id)
                        .order_by(TradePair.year.desc())
                    ).scalar_one_or_none()
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

        r = get_redis()
        r.setex(SPOTLIGHT_KEY, SPOTLIGHT_TTL, json.dumps(cards))
        log.info("Spotlight refreshed: %d cards cached for 3hr", len(cards))
        return {"cards": len(cards)}

    except Exception as exc:
        log.error("refresh_spotlight failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()
