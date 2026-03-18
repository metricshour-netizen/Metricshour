"""
Social Content Pipeline — generates post copy and delivers to Telegram for manual publishing.

Flow:
  Celery Beat (scheduled daily)
    → pull interesting data hooks from DB
    → Gemini 2.5 Flash generates Twitter + LinkedIn + Facebook + Instagram copy
    → send each to Telegram as 5 separate copy-ready messages (image + 4 platforms)
    → user reads in Telegram, long-press copies, and posts manually

Content hooks:
  1. Country spotlight — G20 country with notable indicator value
  2. Stock geo exposure — US stock with highest non-US revenue %
  3. Trade insight — largest bilateral pair with key stat
  4. Market movers — top 5 biggest price movers (8am)
  5. Day wrap — biggest gainer + loser end-of-day (5pm)
  6. Viral stat — shocking "did you know" financial stat (6pm)

Reel scheduling (via tg-bridge → Moltis):
  7. Morning reel — market recap at 8:30 UTC
  8. Evening reel — crypto/wrap at 17:30 UTC
"""
import json
import logging
import os
import random
import time
from datetime import date, timedelta, datetime, timezone

import requests
from celery_app import app
from sqlalchemy import select, func, text

from app.database import SessionLocal
from app.models.country import Country, CountryIndicator
from app.models.asset import Asset, StockCountryRevenue
from sqlalchemy.orm import aliased

log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_KEY_2 = os.environ.get("GEMINI_API_KEY_2", "")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

SITE_URL = "https://metricshour.com"
CDN_URL = "https://cdn.metricshour.com"
TG_BRIDGE_URL = "http://10.0.0.3:8767/webhook"

# Indicators worth posting about (interesting to investors)
SPOTLIGHT_INDICATORS = [
    ("government_debt_gdp_pct", "Govt Debt / GDP", "%"),
    ("inflation_pct", "Inflation Rate", "%"),
    ("gdp_growth_pct", "GDP Growth", "%"),
    ("unemployment_pct", "Unemployment Rate", "%"),
    ("current_account_gdp_pct", "Current Account / GDP", "%"),
    ("budget_balance_gdp_pct", "Budget Balance / GDP", "%"),
    ("foreign_reserves_usd", "Foreign Reserves", "USD"),
    ("fdi_inflows_gdp_pct", "FDI Inflows / GDP", "%"),
]

# G20 country codes
G20_CODES = [
    "AR", "AU", "BR", "CA", "CN", "FR", "DE", "IN", "ID", "IT",
    "JP", "MX", "RU", "SA", "ZA", "KR", "TR", "GB", "US",
]


def _fmt_value(value: float, unit: str) -> str:
    if unit == "%":
        return f"{value:.1f}%"
    if unit == "USD":
        if abs(value) >= 1e12:
            return f"${value / 1e12:.1f}T"
        if abs(value) >= 1e9:
            return f"${value / 1e9:.1f}B"
        return f"${value:,.0f}"
    return f"{value:.2f}"


DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


def _parse_json_response(text: str) -> dict | None:
    """Parse JSON from LLM response, with recovery for truncated output."""
    import re as _re
    text = text.strip()
    # Strip markdown code fences if present
    text = _re.sub(r'^```(?:json)?\s*', '', text, flags=_re.MULTILINE)
    text = _re.sub(r'\s*```$', '', text, flags=_re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try closing truncated JSON
    try:
        fixed = text.rstrip(",").rstrip()
        if fixed and not fixed.endswith("}"):
            fixed = fixed + ('"' if fixed.count('"') % 2 == 1 else "") + "}"
        return json.loads(fixed)
    except Exception:
        pass
    # Regex extraction of completed string values
    try:
        partial = {}
        for key in ("twitter", "linkedin", "facebook", "instagram", "reddit_subreddit", "reddit_title", "reddit_body"):
            m = _re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', text, _re.DOTALL)
            if m:
                partial[key] = m.group(1).replace('\\"', '"').replace("\\n", "\n")
        return partial if partial else None
    except Exception:
        return None


def _call_gemini_with_key(api_key: str, prompt: str) -> dict | None:
    """Call Gemini 2.5 Flash via direct REST (SDK hangs on this server)."""
    if not api_key:
        return None
    try:
        resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2048,
                    "responseMimeType": "application/json",
                },
            },
            timeout=30,
        )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return _parse_json_response(text)
    except Exception as e:
        log.warning("Gemini call failed (key=...%s): %s", api_key[-6:], e)
        return None


def _call_gemini(prompt: str) -> dict | None:
    """Try primary Gemini key, fall back to secondary key if primary fails."""
    result = _call_gemini_with_key(GEMINI_API_KEY, prompt)
    if result:
        return result
    if GEMINI_API_KEY_2:
        log.info("Primary Gemini key failed — trying secondary Gemini key")
        return _call_gemini_with_key(GEMINI_API_KEY_2, prompt)
    return None


def _call_deepseek(prompt: str) -> dict | None:
    """Call DeepSeek V3 via OpenAI-compatible API. Fallback when Gemini is unavailable."""
    if not DEEPSEEK_API_KEY:
        return None
    try:
        resp = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a financial social media copywriter. Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 2048,
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return _parse_json_response(text)
    except Exception as e:
        log.warning("DeepSeek social content failed: %s", e)
        return None


def _call_ai(prompt: str) -> dict | None:
    """Call Gemini first, fall back to DeepSeek V3 if Gemini is unavailable."""
    result = _call_gemini(prompt)
    if result:
        return result
    log.info("Gemini unavailable — falling back to DeepSeek V3")
    return _call_deepseek(prompt)


# Audience persona injected into every content prompt
AUDIENCE_PERSONA = (
    "Audience: retail investor aged 30-45 who follows stocks and macro on Twitter/Reddit. "
    "They want to feel smarter than CNBC viewers. Tone: sharp, confident, data-grounded, slightly provocative. "
    "Goal: make them want to share this with one friend."
)


def _fetch_news_context(query: str, max_results: int = 2) -> str:
    """Fetch recent news headlines for a topic via Google News RSS. Returns '' on failure."""
    import xml.etree.ElementTree as ET
    import urllib.parse
    try:
        url = (
            "https://news.google.com/rss/search"
            f"?q={urllib.parse.quote(query + ' economy finance')}"
            "&hl=en&gl=US&ceid=US:en"
        )
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return ""
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")[:max_results]
        headlines = []
        for item in items:
            title = item.findtext("title", "").strip()
            # Strip source suffix e.g. "- Reuters"
            if " - " in title:
                title = title.rsplit(" - ", 1)[0].strip()
            if title:
                headlines.append(f"• {title}")
        return "\n".join(headlines) if headlines else ""
    except Exception:
        return ""


def _compute_angle(history_rows, current_val: float, unit: str) -> str:
    """Return a plain-English note on what's notable about this value vs history."""
    if len(history_rows) < 2:
        return ""
    vals = [float(r.value) for r in history_rows]
    notes = []
    if len(vals) >= 2:
        yoy = vals[0] - vals[1]
        direction = "up" if yoy > 0 else "down"
        if unit == "%":
            notes.append(f"YoY: {direction} {abs(yoy):.1f}pp from {vals[1]:.1f}%")
        else:
            notes.append(f"YoY: {direction} {_fmt_value(abs(yoy), unit)}")
    if len(vals) >= 4:
        if vals[0] >= max(vals):
            notes.append(f"Highest in {len(vals)} years of data")
        elif vals[0] <= min(vals):
            notes.append(f"Lowest in {len(vals)} years of data")
        # Trend: all moving same direction?
        trend = [vals[i] - vals[i+1] for i in range(len(vals)-1)]
        if all(t > 0 for t in trend):
            notes.append(f"Rising for {len(vals)-1} consecutive years")
        elif all(t < 0 for t in trend):
            notes.append(f"Falling for {len(vals)-1} consecutive years")
    return ". ".join(notes)


def _pick_best_country_indicator(db) -> tuple | None:
    """
    Scan G20 countries × spotlight indicators and return the (country_code, indicator_key, label, unit)
    with the largest absolute YoY change. Falls back to random if query fails.
    """
    try:
        rows = db.execute(text("""
            WITH ranked AS (
                SELECT
                    c.code, c.name, ci.indicator,
                    ci.value,
                    ci.period_date,
                    LAG(ci.value) OVER (
                        PARTITION BY c.id, ci.indicator ORDER BY ci.period_date
                    ) AS prev_value
                FROM country_indicators ci
                JOIN countries c ON c.id = ci.country_id
                WHERE c.code = ANY(:codes)
                  AND ci.indicator = ANY(:inds)
                  AND ci.period_date >= NOW() - INTERVAL '5 years'
            )
            SELECT code, name, indicator, value, prev_value,
                   ABS(value - prev_value) AS abs_change
            FROM ranked
            WHERE prev_value IS NOT NULL
            ORDER BY abs_change DESC
            LIMIT 20
        """), {
            "codes": G20_CODES,
            "inds": [i[0] for i in SPOTLIGHT_INDICATORS],
        }).fetchall()
        if not rows:
            return None
        # Pick from top 5 — randomise a bit to avoid always same country
        pick = random.choice(rows[:5])
        ind_meta = {k: (l, u) for k, l, u in SPOTLIGHT_INDICATORS}
        label, unit = ind_meta.get(pick.indicator, (pick.indicator, ""))
        return pick.code, pick.indicator, label, unit
    except Exception as e:
        log.warning("_pick_best_country_indicator failed: %s", e)
        return None


def _hook_country_spotlight(db) -> dict | None:
    """Pick G20 country + indicator with biggest recent change, generate post copy."""
    # Smarter selection: country with biggest YoY indicator change
    best = _pick_best_country_indicator(db)
    if best:
        country_code, indicator_key, label, unit = best
    else:
        indicator_key, label, unit = random.choice(SPOTLIGHT_INDICATORS)
        country_code = random.choice(G20_CODES)

    country = db.execute(
        select(Country).where(Country.code == country_code)
    ).scalar_one_or_none()
    if not country:
        return None

    # Get latest value + 4-year history
    rows = db.execute(
        select(CountryIndicator.period_date, CountryIndicator.value)
        .where(
            CountryIndicator.country_id == country.id,
            CountryIndicator.indicator == indicator_key,
        )
        .order_by(CountryIndicator.period_date.desc())
        .limit(5)
    ).all()
    if not rows:
        return None

    current_val = float(rows[0].value)
    current_year = rows[0].period_date.year
    history_str = ", ".join(
        f"{r.period_date.year}: {_fmt_value(float(r.value), unit)}"
        for r in rows
    )
    angle = _compute_angle(rows, current_val, unit)
    news = _fetch_news_context(f"{country.name} {label}")

    page_url = f"{SITE_URL}/countries/{country_code.lower()}"
    og_image_url = f"{CDN_URL}/og/countries/{country_code.lower()}.png"

    angle_block = f"\nWhat's notable: {angle}" if angle else ""
    news_block = f"\nCurrent news context:\n{news}" if news else ""

    prompt = f"""
You are writing finance social media content for MetricsHour (macro intelligence platform).
{AUDIENCE_PERSONA}

Data: {country.name} — {label}: {_fmt_value(current_val, unit)} ({current_year})
History: {history_str}{angle_block}{news_block}
Page: {page_url}

Use the angle and news context to frame WHY this data matters RIGHT NOW — not just what the number is.
Write FIVE posts about this macro data point:

1. TWITTER (max 260 chars, include the number, end with a punchy hook or question, 1-2 relevant emojis, include the URL)

2. LINKEDIN — Exact format to follow:

[Country] [indicator]: [value] — [1-line insight explaining why it matters]

[2-3 observations, each on its own line, max 20 words each. Cover: historical context, market signal, investor implication. Name specific currencies, sectors, rates.]

[URL]

No emojis. No hashtags. No "Follow for more." No sign-off. Under 100 words total.

GOOD (write like this):
Germany debt-to-GDP: 66.4% — above the EU's 60% ceiling for the first time since 2015.
Berlin's constitutional debt brake limits new borrowing, capping fiscal stimulus.
Growth forecasts are being cut; the ECB rate cut timeline matters more now.
Watch EUR and Bund spreads — fiscal drag could outlast the rate cycle.
metricshour.com/countries/de

BAD (never write like this):
"In today's global economy, understanding fiscal dynamics is crucial. Germany's debt-to-GDP ratio has reached 66.4%, highlighting significant challenges for investors navigating European markets."

3. FACEBOOK — Single paragraph, no line breaks. [Stat + country + one punchy implication, max 30 words]. [One specific risk or opportunity, max 20 words]. [1 emoji] [URL]

GOOD: Germany's debt hit 66.4% of GDP — above the EU's limit. Budget cuts ahead mean slower growth for Europe's largest economy. 📊 metricshour.com/countries/de
BAD: "Interesting economic update! Germany's debt-to-GDP ratio has climbed to 66.4%. What do you think about this trend? 📊"

4. INSTAGRAM — punchy first line as hook (before fold), 3-5 relevant emojis woven in naturally, data-led financial angle, include URL naturally in caption body, 5-8 relevant hashtags at end. Max 200 words total.

5. REDDIT — write a genuinely useful discussion post, NOT promotional:
   - "subreddit": best single subreddit from [investing, economics, worldnews, geopolitics, economy, stocks, MacroEconomics, dataisbeautiful] — pick based on content angle
   - "title": compelling Reddit title (max 200 chars) — data-led, sparks discussion, no clickbait
   - "body": 3-4 paragraphs. Open with the raw data and historical context. Second paragraph: what this means for markets/investors with specific implications. Third paragraph: 1-2 contrarian angles or risks people miss. End with a genuine open question to drive comments. Do NOT mention MetricsHour by name in body — only include the URL naturally as "source" or "more data". No marketing language. Write like a knowledgeable community member.

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "instagram": "...", "reddit_subreddit": "...", "reddit_title": "...", "reddit_body": "..."}}
"""
    result = _call_ai(prompt)
    if not result:
        return None
    return {
        "type": "country_spotlight",
        "entity": country.name,
        "entity_code": country_code.lower(),
        "label": label,
        "value": _fmt_value(current_val, unit),
        "url": page_url,
        "og_image_url": og_image_url,
        "twitter": result.get("twitter", ""),
        "linkedin": result.get("linkedin", ""),
        "facebook": result.get("facebook", ""),
        "instagram": result.get("instagram", ""),
        "reddit_subreddit": result.get("reddit_subreddit", ""),
        "reddit_title": result.get("reddit_title", ""),
        "reddit_body": result.get("reddit_body", ""),
    }


def _hook_stock_exposure(db) -> dict | None:
    """
    Pick a stock that moved significantly this week AND has high international revenue.
    Falls back to highest intl revenue if no price data available.
    """
    # Try to find recently-moved stocks with international exposure
    try:
        moved_rows = db.execute(text("""
            WITH recent_moves AS (
                SELECT DISTINCT ON (a.id)
                       a.id, a.symbol, a.name,
                       ABS((p.close - p.open) / NULLIF(p.open, 0) * 100) AS abs_pct
                FROM prices p
                JOIN assets a ON a.id = p.asset_id
                WHERE p.interval = '1d'
                  AND p.open IS NOT NULL
                  AND p.timestamp >= NOW() - INTERVAL '7 days'
                  AND a.asset_type = 'stock'
                ORDER BY a.id, p.timestamp DESC
            )
            SELECT rm.id, rm.symbol, rm.name, rm.abs_pct,
                   SUM(scr.revenue_pct) AS intl_pct
            FROM recent_moves rm
            JOIN stock_country_revenues scr ON scr.asset_id = rm.id
            JOIN countries c ON c.id = scr.country_id AND c.code != 'US'
            GROUP BY rm.id, rm.symbol, rm.name, rm.abs_pct
            HAVING SUM(scr.revenue_pct) > 20
            ORDER BY rm.abs_pct DESC
            LIMIT 10
        """)).fetchall()
    except Exception:
        moved_rows = []

    RevCountry = aliased(Country)
    if moved_rows:
        pick_row = random.choice(moved_rows[:5])
        ticker = pick_row.symbol
        name = pick_row.name
        intl_pct = float(pick_row.intl_pct)
    else:
        # Fallback: highest intl revenue
        rows = db.execute(
            select(
                Asset.symbol, Asset.name,
                func.sum(StockCountryRevenue.revenue_pct).label("intl_pct"),
            )
            .join(StockCountryRevenue, StockCountryRevenue.asset_id == Asset.id)
            .join(RevCountry, RevCountry.id == StockCountryRevenue.country_id)
            .where(RevCountry.code != "US", StockCountryRevenue.revenue_pct > 5)
            .group_by(Asset.id, Asset.symbol, Asset.name)
            .order_by(func.sum(StockCountryRevenue.revenue_pct).desc())
            .limit(20)
        ).all()
        if not rows:
            return None
        pick = random.choice(rows[:10])
        ticker = pick.symbol
        name = pick.name
        intl_pct = float(pick.intl_pct)

    # Get top 3 revenue countries
    RevCountry2 = aliased(Country)
    top_countries = db.execute(
        select(
            RevCountry2.code,
            StockCountryRevenue.revenue_pct,
        )
        .join(Asset, Asset.id == StockCountryRevenue.asset_id)
        .join(RevCountry2, RevCountry2.id == StockCountryRevenue.country_id)
        .where(
            Asset.symbol == ticker,
            RevCountry2.code != "US",
        )
        .order_by(StockCountryRevenue.revenue_pct.desc())
        .limit(3)
    ).all()

    geo_breakdown = ", ".join(
        f"{r.code} {float(r.revenue_pct):.0f}%" for r in top_countries
    )
    page_url = f"{SITE_URL}/stocks/{ticker.lower()}"
    og_image_url = f"{CDN_URL}/og/stocks/{ticker.lower()}.png"

    news = _fetch_news_context(f"{name} {ticker} stock")
    news_block = f"\nCurrent news context:\n{news}" if news else ""

    prompt = f"""
You are writing finance social media content for MetricsHour (macro intelligence platform).
{AUDIENCE_PERSONA}

Data: {name} ({ticker}) earns {intl_pct:.0f}% of revenue outside the US.
Top international markets: {geo_breakdown}
Page: {page_url}{news_block}

Use the news context to frame WHY this geographic exposure matters RIGHT NOW — tie the data to current macro events (tariffs, FX moves, geopolitics) where possible.
Write FIVE posts about this stock's geographic revenue exposure and what it means:

1. TWITTER (max 260 chars, include the %, specific countries, hook about macro risk/opportunity, 1-2 emojis, include URL)

2. LINKEDIN — Exact format to follow:

[Ticker] earns [X]% of revenue outside the US — [1-line insight on what that exposure means right now]

[2-3 observations, each on its own line, max 20 words each. Cover: which regions drive growth, specific macro risks (tariffs/FX/policy), what the market may be mispricing.]

[URL]

No emojis. No hashtags. No "Follow for more." No sign-off. Under 100 words total.

GOOD (write like this):
AAPL earns 58% of revenue outside the US — China alone is 19%, making it one of the most geopolitically exposed megacaps.
A 10% CNY depreciation cuts EPS by ~$0.40 — rarely priced in during calm periods.
EU Digital Markets Act compliance costs are rising; watch operating margins in Europe next quarter.
metricshour.com/stocks/aapl

BAD (never write like this):
"In today's interconnected markets, geographic revenue diversification is more important than ever. Apple's international exposure represents both opportunity and risk for investors seeking global growth."

3. FACEBOOK — Single paragraph, no line breaks. [Ticker + the % + top markets in one punchy line, max 30 words]. [One specific risk or opportunity this creates, max 20 words]. [1 emoji] [URL]

GOOD: Apple earns 58% of revenue outside the US — China is 19%. A trade war escalation hits EPS directly. 🌍 metricshour.com/stocks/aapl
BAD: "Did you know Apple earns most of its revenue internationally? This is really interesting for investors to consider! 🌍"

4. INSTAGRAM — punchy first line as hook (before fold), 3-5 relevant emojis woven in naturally, data-led financial angle, include URL naturally in caption body, 5-8 relevant hashtags at end. Max 200 words total.

5. REDDIT — write a genuinely useful discussion post, NOT promotional:
   - "subreddit": best single subreddit from [investing, stocks, SecurityAnalysis, ValueInvesting, StockMarket, geopolitics, economics] — pick based on content angle
   - "title": compelling Reddit title (max 200 chars) — specific numbers, sparks discussion, no clickbait
   - "body": 3-4 paragraphs. Open with the geographic breakdown and specific revenue %s. Second paragraph: which macro risks (tariffs, FX, geopolitics) are most relevant for each region and why. Third paragraph: what the market may be mispricing or overlooking. End with a genuine question about how others are thinking about this exposure. Do NOT mention MetricsHour by name in body — only include URL naturally as "source". Write like a thoughtful investor, not a marketer.

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "instagram": "...", "reddit_subreddit": "...", "reddit_title": "...", "reddit_body": "..."}}
"""
    result = _call_ai(prompt)
    if not result:
        return None
    return {
        "type": "stock_exposure",
        "entity": f"{ticker} ({name})",
        "entity_code": ticker.lower(),
        "label": "Geographic Revenue",
        "value": f"{intl_pct:.0f}% international",
        "url": page_url,
        "og_image_url": og_image_url,
        "twitter": result.get("twitter", ""),
        "linkedin": result.get("linkedin", ""),
        "facebook": result.get("facebook", ""),
        "instagram": result.get("instagram", ""),
        "reddit_subreddit": result.get("reddit_subreddit", ""),
        "reddit_title": result.get("reddit_title", ""),
        "reddit_body": result.get("reddit_body", ""),
    }


def _hook_trade_insight(db) -> dict | None:
    """Pick a notable G20 bilateral trade pair and generate insight post."""
    from app.models.country import TradePair
    rows = db.execute(
        select(TradePair)
        .where(TradePair.trade_value_usd != None)
        .order_by(TradePair.trade_value_usd.desc())
        .limit(30)
    ).scalars().all()
    if not rows:
        return None

    pair = random.choice(rows[:15])
    exp = db.execute(select(Country).where(Country.id == pair.exporter_id)).scalar_one_or_none()
    imp = db.execute(select(Country).where(Country.id == pair.importer_id)).scalar_one_or_none()
    if not exp or not imp:
        return None

    val = pair.trade_value_usd
    val_str = f"${val / 1e9:.0f}B" if val >= 1e9 else f"${val / 1e6:.0f}M"
    products = ", ".join(p["name"] for p in (pair.top_export_products or [])[:3]) or ""
    page_url = f"{SITE_URL}/trade/{exp.code.lower()}-{imp.code.lower()}"
    og_image_url = f"{CDN_URL}/og/trade/{exp.code.lower()}-{imp.code.lower()}.png"

    news = _fetch_news_context(f"{exp.name} {imp.name} trade")
    news_block = f"\nCurrent news context:\n{news}" if news else ""

    prompt = f"""
You are writing finance social media content for MetricsHour (macro intelligence platform).
{AUDIENCE_PERSONA}

Data: {exp.name}–{imp.name} bilateral trade: {val_str}/year ({pair.year})
Top traded goods: {products}
Page: {page_url}{news_block}

Use the news context to explain WHY this trade corridor is relevant right now — tariffs, diplomatic tensions, sanctions, supply chain shifts. Don't just describe the data; frame it as a live story.
Write FIVE posts about this trade relationship and why it matters to investors:

1. TWITTER (max 260 chars, include the dollar figure, key goods, geopolitical/market angle, 1-2 emojis, URL)

2. LINKEDIN — Exact format to follow:

[Exporter]→[Importer]: $[value]/year — [1-line insight on why this corridor matters or what's at risk]

[2-3 observations, each on its own line, max 20 words each. Cover: what's being traded, the geopolitical or policy risk, which sectors/companies are most exposed.]

[URL]

No emojis. No hashtags. No "Follow for more." No sign-off. Under 100 words total.

GOOD (write like this):
China→US: $427B/year — the world's most politically contested trade corridor.
Electronics and machinery dominate; 60%+ of US consumer tech imports originate here.
A 25% tariff shock would add ~$180/device to manufacturing costs — largely passed to consumers.
Watch semiconductor and retail stocks for the first signs of margin compression.
metricshour.com/trade/cn-us

BAD (never write like this):
"Trade relationships between nations are a critical component of the global economy. The China-US trade corridor represents a significant economic partnership with important implications for investors worldwide."

3. FACEBOOK — Single paragraph, no line breaks. [Dollar figure + corridor + the key goods in one punchy line, max 30 words]. [One specific risk or who gets hurt if it breaks, max 20 words]. [1 emoji] [URL]

GOOD: China ships $427B to the US annually — mostly electronics and machinery. Tariffs on this corridor hit consumer prices immediately. 🌐 metricshour.com/trade/cn-us
BAD: "The trade relationship between China and the US is fascinating and has many implications for global markets! 🌐"

4. INSTAGRAM — punchy first line as hook (before fold), 3-5 relevant emojis woven in naturally, data-led financial angle, include URL naturally in caption body, 5-8 relevant hashtags at end. Max 200 words total.

5. REDDIT — write a genuinely useful discussion post, NOT promotional:
   - "subreddit": best single subreddit from [geopolitics, investing, economics, worldnews, StockMarket, MacroEconomics, GlobalPowers] — pick based on content angle
   - "title": compelling Reddit title (max 200 chars) — specific dollar figure, geopolitical angle, sparks debate, no clickbait
   - "body": 3-4 paragraphs. Open with the bilateral trade value and what's being traded. Second paragraph: geopolitical or policy risks that could disrupt this corridor (tariffs, sanctions, diplomatic tensions). Third paragraph: which sectors and companies are most exposed — give specific examples if possible. End with a genuine open question about where this corridor is heading. URL as "source" link only. Write like an informed macro analyst sharing knowledge, not promoting a product.

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "instagram": "...", "reddit_subreddit": "...", "reddit_title": "...", "reddit_body": "..."}}
"""
    result = _call_ai(prompt)
    if not result:
        return None
    return {
        "type": "trade_insight",
        "entity": f"{exp.name}–{imp.name}",
        "entity_code": f"{exp.code.lower()}-{imp.code.lower()}",
        "label": "Bilateral Trade",
        "value": val_str,
        "url": page_url,
        "og_image_url": og_image_url,
        "twitter": result.get("twitter", ""),
        "linkedin": result.get("linkedin", ""),
        "facebook": result.get("facebook", ""),
        "instagram": result.get("instagram", ""),
        "reddit_subreddit": result.get("reddit_subreddit", ""),
        "reddit_title": result.get("reddit_title", ""),
        "reddit_body": result.get("reddit_body", ""),
    }


def _hook_market_movers(db) -> dict | None:
    """Top 5 biggest price movers from the last 24h — market open hook."""
    try:
        rows = db.execute(text("""
            SELECT symbol, name, close, change_pct FROM (
                SELECT DISTINCT ON (a.id)
                       a.symbol, a.name,
                       ROUND(CAST(p.close AS numeric), 2) AS close,
                       ROUND(CAST((p.close - p.open) / NULLIF(p.open, 0) * 100 AS numeric), 2) AS change_pct
                FROM prices p
                JOIN assets a ON a.id = p.asset_id
                WHERE p.interval = '1d'
                  AND p.open IS NOT NULL
                  AND p.timestamp >= NOW() - INTERVAL '36 hours'
                ORDER BY a.id, p.timestamp DESC
            ) latest
            ORDER BY ABS(change_pct) DESC
            LIMIT 5
        """)).fetchall()
    except Exception as e:
        log.warning("market movers query failed: %s", e)
        return None

    if not rows:
        return None

    movers_str = "\n".join(
        f"{r.symbol} | {r.name} | {r.close} | {float(r.change_pct):+.2f}%"
        for r in rows
    )
    og_image_url = f"{CDN_URL}/og/section/markets.png"

    prompt = f"""
You are writing finance social media content for MetricsHour (macro intelligence platform).
{AUDIENCE_PERSONA}

Today's biggest market movers (price change %):
{movers_str}

Write FOUR posts as a market-open hook. Lead with the most surprising or counterintuitive move — don't just list numbers, tell people what it means:

1. TWITTER (max 260 chars, top 3 movers with % change, punchy hook or question, 1-2 emojis, include URL: {SITE_URL}/markets)

2. LINKEDIN — clean 3-observation format, data-led. No emojis. No hashtags. No sign-off. Under 100 words.
Format:
[Headline: biggest move + context]
[Observation 1: what drove it]
[Observation 2: sector/macro implication]
[Observation 3: what to watch next]
{SITE_URL}/markets

3. FACEBOOK — one punchy paragraph. Dollar/% figures + 1 emoji. Include URL. Max 50 words.

4. INSTAGRAM — punchy first line as hook (before fold), 3-5 relevant emojis woven in naturally, top movers with % changes, include URL {SITE_URL}/markets naturally in caption, 5-8 relevant hashtags at end. Max 200 words.

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "instagram": "..."}}
"""
    result = _call_ai(prompt)
    if not result:
        return None
    return {
        "type": "market_movers",
        "entity": "Market Movers",
        "entity_code": "markets",
        "label": "Biggest Movers Today",
        "value": f"{len(rows)} movers",
        "url": f"{SITE_URL}/markets",
        "og_image_url": og_image_url,
        "twitter": result.get("twitter", ""),
        "linkedin": result.get("linkedin", ""),
        "facebook": result.get("facebook", ""),
        "instagram": result.get("instagram", ""),
    }


def _hook_day_wrap(db) -> dict | None:
    """End-of-day wrap — biggest gainer and loser."""
    try:
        rows = db.execute(text("""
            SELECT symbol, name, close, change_pct FROM (
                SELECT DISTINCT ON (a.id)
                       a.symbol, a.name,
                       ROUND(CAST(p.close AS numeric), 2) AS close,
                       ROUND(CAST((p.close - p.open) / NULLIF(p.open, 0) * 100 AS numeric), 2) AS change_pct
                FROM prices p
                JOIN assets a ON a.id = p.asset_id
                WHERE p.interval = '1d'
                  AND p.open IS NOT NULL
                  AND p.timestamp >= NOW() - INTERVAL '36 hours'
                ORDER BY a.id, p.timestamp DESC
            ) latest
            ORDER BY ABS(change_pct) DESC
            LIMIT 5
        """)).fetchall()
    except Exception as e:
        log.warning("day wrap query failed: %s", e)
        return None

    if not rows:
        return None

    # Find biggest gainer and loser
    by_change = sorted(rows, key=lambda r: float(r.change_pct), reverse=True)
    gainer = by_change[0]
    loser = by_change[-1]
    movers_str = "\n".join(
        f"{r.symbol} | {r.name} | {r.close} | {float(r.change_pct):+.2f}%"
        for r in rows
    )
    og_image_url = f"{CDN_URL}/og/section/markets.png"

    prompt = f"""
You are writing finance social media content for MetricsHour (macro intelligence platform).
{AUDIENCE_PERSONA}

Today's market wrap — biggest movers:
{movers_str}

Biggest gainer: {gainer.symbol} ({gainer.name}) {float(gainer.change_pct):+.2f}%
Biggest loser: {loser.symbol} ({loser.name}) {float(loser.change_pct):+.2f}%

Write FOUR end-of-day wrap posts. Don't just state the moves — explain what they signal about tomorrow and what surprised most people today:

1. TWITTER (max 260 chars, biggest gainer AND loser with %, punchy market wrap tone, 1-2 emojis, include URL: {SITE_URL}/markets)

2. LINKEDIN — clean 3-observation end-of-day wrap. Data-led. No emojis. No hashtags. No sign-off. Under 100 words.
Format:
[Headline: day's biggest swing + context]
[Observation 1: what drove the biggest mover]
[Observation 2: what the loser signals]
[Observation 3: what to watch tomorrow]
{SITE_URL}/markets

3. FACEBOOK — one punchy end-of-day paragraph. Gainer and loser with % figures + 1 emoji. Include URL. Max 50 words.

4. INSTAGRAM — punchy first line as hook (before fold), 3-5 relevant emojis, today's gainer + loser with % changes, include URL {SITE_URL}/markets naturally in caption, 5-8 relevant hashtags at end. Max 200 words.

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "instagram": "..."}}
"""
    result = _call_ai(prompt)
    if not result:
        return None
    return {
        "type": "day_wrap",
        "entity": "Day Wrap",
        "entity_code": "markets_wrap",
        "label": "Market Day Wrap",
        "value": f"{gainer.symbol} {float(gainer.change_pct):+.1f}% / {loser.symbol} {float(loser.change_pct):+.1f}%",
        "url": f"{SITE_URL}/markets",
        "og_image_url": og_image_url,
        "twitter": result.get("twitter", ""),
        "linkedin": result.get("linkedin", ""),
        "facebook": result.get("facebook", ""),
        "instagram": result.get("instagram", ""),
    }


def _hook_viral_stat(db) -> dict | None:
    """Pick a shocking / 'did you know' financial stat at random."""
    options = [
        "high_inflation", "high_debt", "trade_yoy", "stock_intl",
        "china_exposure", "big_price_mover", "commodity_extreme", "debt_yoy_surge",
    ]
    random.shuffle(options)

    for option in options:
        try:
            result = _try_viral_option(db, option)
            if result:
                return result
        except Exception as e:
            log.warning("viral stat option %s failed: %s", option, e)
            continue
    return None


def _try_viral_option(db, option: str) -> dict | None:
    """Attempt a single viral stat option. Returns draft dict or None."""
    if option == "high_inflation":
        row = db.execute(text("""
            SELECT c.code, c.name, ci.value
            FROM country_indicators ci
            JOIN countries c ON c.id = ci.country_id
            WHERE ci.indicator = 'inflation_pct'
              AND ci.value > 10
            ORDER BY ci.value DESC, ci.period_date DESC
            LIMIT 1
        """)).fetchone()
        if not row:
            return None
        code = row.code.lower()
        entity = row.name
        val_str = f"{float(row.value):.1f}%"
        label = "Inflation Rate"
        page_url = f"{SITE_URL}/countries/{code}"
        og_image_url = f"{CDN_URL}/og/countries/{code}.png"
        data_context = f"{entity} has an inflation rate of {val_str}"
        hook_angle = "Did you know? Hyperinflation / extreme inflation is destroying purchasing power in this country"

    elif option == "high_debt":
        row = db.execute(text("""
            SELECT c.code, c.name, ci.value
            FROM country_indicators ci
            JOIN countries c ON c.id = ci.country_id
            WHERE ci.indicator = 'government_debt_gdp_pct'
              AND ci.value > 100
            ORDER BY ci.value DESC, ci.period_date DESC
            LIMIT 1
        """)).fetchone()
        if not row:
            return None
        code = row.code.lower()
        entity = row.name
        val_str = f"{float(row.value):.1f}%"
        label = "Govt Debt / GDP"
        page_url = f"{SITE_URL}/countries/{code}"
        og_image_url = f"{CDN_URL}/og/countries/{code}.png"
        data_context = f"{entity} has government debt of {val_str} of GDP"
        hook_angle = "Did you know? This country owes more than its entire annual economic output"

    elif option == "trade_yoy":
        rows = db.execute(text("""
            SELECT tp.id, c1.name AS exp_name, c2.name AS imp_name,
                   c1.code AS exp_code, c2.code AS imp_code,
                   tp.trade_value_usd, tp.year
            FROM trade_pairs tp
            JOIN countries c1 ON c1.id = tp.exporter_id
            JOIN countries c2 ON c2.id = tp.importer_id
            WHERE tp.trade_value_usd IS NOT NULL
            ORDER BY tp.trade_value_usd DESC
            LIMIT 30
        """)).fetchall()
        if not rows:
            return None
        pick = random.choice(rows[:10]) if len(rows) >= 10 else rows[0]
        val = float(pick.trade_value_usd)
        val_str = f"${val / 1e9:.0f}B" if val >= 1e9 else f"${val / 1e6:.0f}M"
        exp_code = pick.exp_code.lower()
        imp_code = pick.imp_code.lower()
        entity = f"{pick.exp_name}–{pick.imp_name}"
        code = f"{exp_code}-{imp_code}"
        label = "Bilateral Trade"
        page_url = f"{SITE_URL}/trade/{exp_code}-{imp_code}"
        og_image_url = f"{CDN_URL}/og/trade/{exp_code}-{imp_code}.png"
        data_context = f"{pick.exp_name} exports {val_str}/year to {pick.imp_name}"
        hook_angle = "Did you know? The scale of this trade relationship will surprise you"

    elif option == "stock_intl":
        RevCountry = aliased(Country)
        rows = db.execute(
            select(
                Asset.symbol, Asset.name,
                func.sum(StockCountryRevenue.revenue_pct).label("intl_pct"),
            )
            .join(StockCountryRevenue, StockCountryRevenue.asset_id == Asset.id)
            .join(RevCountry, RevCountry.id == StockCountryRevenue.country_id)
            .where(
                RevCountry.code != "US",
                StockCountryRevenue.revenue_pct > 5,
            )
            .group_by(Asset.id, Asset.symbol, Asset.name)
            .having(func.sum(StockCountryRevenue.revenue_pct) > 80)
            .order_by(func.sum(StockCountryRevenue.revenue_pct).desc())
            .limit(10)
        ).all()
        if not rows:
            return None
        pick = random.choice(rows)
        ticker = pick.symbol
        name = pick.name
        intl_pct = float(pick.intl_pct)
        code = ticker.lower()
        entity = f"{ticker} ({name})"
        val_str = f"{intl_pct:.0f}% international revenue"
        label = "Geographic Revenue"
        page_url = f"{SITE_URL}/stocks/{code}"
        og_image_url = f"{CDN_URL}/og/stocks/{code}.png"
        data_context = f"{name} ({ticker}) earns {intl_pct:.0f}% of revenue outside the US"
        hook_angle = "Did you know? This US-listed stock earns most of its money abroad"

    elif option == "china_exposure":
        # US stocks with highest China revenue — hot topic given tariffs
        ChinaRev = aliased(StockCountryRevenue)
        ChinaCountry = aliased(Country)
        row = db.execute(
            select(Asset.symbol, Asset.name, ChinaRev.revenue_pct, ChinaRev.revenue_usd)
            .join(ChinaRev, ChinaRev.asset_id == Asset.id)
            .join(ChinaCountry, ChinaCountry.id == ChinaRev.country_id)
            .where(ChinaCountry.code == "CN", ChinaRev.revenue_pct > 5)
            .order_by(ChinaRev.revenue_usd.desc().nullslast(), ChinaRev.revenue_pct.desc())
            .limit(10)
        ).first()
        if not row:
            return None
        ticker = row.symbol
        name = row.name
        china_pct = float(row.revenue_pct)
        china_usd = row.revenue_usd
        code = ticker.lower()
        entity = f"{ticker} ({name})"
        val_str = f"{china_pct:.1f}% China revenue"
        if china_usd and china_usd >= 1e9:
            val_str += f" (${china_usd/1e9:.1f}B)"
        label = "China Revenue Exposure"
        page_url = f"{SITE_URL}/stocks/{code}"
        og_image_url = f"{CDN_URL}/og/stocks/{code}.png"
        data_context = f"{name} ({ticker}) earns {val_str} from China"
        hook_angle = (
            "With US-China tariffs at historic highs, this stock's China revenue is a direct line item risk. "
            "Most investors don't realize how exposed it is."
        )

    elif option == "big_price_mover":
        # Most dramatic price move in last 7 days + its geographic story
        row = db.execute(text("""
            SELECT DISTINCT ON (a.id)
                   a.symbol, a.name,
                   ROUND(CAST((p.close - p.open) / NULLIF(p.open, 0) * 100 AS numeric), 1) AS change_pct,
                   p.close
            FROM prices p
            JOIN assets a ON a.id = p.asset_id
            WHERE p.interval = '1d'
              AND p.open IS NOT NULL
              AND p.timestamp >= NOW() - INTERVAL '7 days'
              AND a.asset_type IN ('stock', 'crypto', 'commodity')
            ORDER BY a.id, p.timestamp DESC
        """)).fetchall()
        if not row:
            return None
        rows_sorted = sorted(row, key=lambda r: abs(float(r.change_pct)), reverse=True)
        pick = rows_sorted[0]
        ticker = pick.symbol
        name = pick.name
        chg = float(pick.change_pct)
        direction = "surged" if chg > 0 else "crashed"
        code = ticker.lower()
        entity = f"{ticker} ({name})"
        val_str = f"{chg:+.1f}% this week"
        label = "Weekly Move"
        page_url = f"{SITE_URL}/stocks/{code}"
        og_image_url = f"{CDN_URL}/og/stocks/{code}.png"
        data_context = f"{name} ({ticker}) {direction} {abs(chg):.1f}% this week"
        hook_angle = (
            f"The biggest market move this week was {ticker} at {chg:+.1f}%. "
            "Most people missed why — the real driver is in the macro data."
        )

    elif option == "commodity_extreme":
        # Commodity near 52-week high or low
        row = db.execute(text("""
            WITH weekly AS (
                SELECT DISTINCT ON (a.id)
                       a.id, a.symbol, a.name,
                       p.close AS current_price,
                       p.timestamp
                FROM prices p
                JOIN assets a ON a.id = p.asset_id
                WHERE a.asset_type = 'commodity'
                  AND p.interval = '1d'
                  AND p.open IS NOT NULL
                ORDER BY a.id, p.timestamp DESC
            ),
            yearly AS (
                SELECT asset_id,
                       MAX(close) AS high_52w,
                       MIN(close) AS low_52w
                FROM prices
                WHERE interval = '1d'
                  AND timestamp >= NOW() - INTERVAL '52 weeks'
                GROUP BY asset_id
            )
            SELECT w.symbol, w.name, w.current_price, y.high_52w, y.low_52w,
                   ROUND(CAST((w.current_price - y.low_52w) / NULLIF(y.high_52w - y.low_52w, 0) * 100 AS numeric), 1) AS pct_of_range
            FROM weekly w
            JOIN yearly y ON y.asset_id = w.id
            WHERE y.high_52w > y.low_52w
            ORDER BY ABS(50 - ROUND(CAST((w.current_price - y.low_52w) / NULLIF(y.high_52w - y.low_52w, 0) * 100 AS numeric), 1)) DESC
            LIMIT 1
        """)).fetchone()
        if not row:
            return None
        ticker = row.symbol
        name = row.name
        price = float(row.current_price)
        high_52w = float(row.high_52w)
        low_52w = float(row.low_52w)
        pct_range = float(row.pct_of_range)
        extreme = "52-week HIGH" if pct_range >= 80 else "52-week LOW"
        code = ticker.lower()
        entity = f"{ticker} ({name})"
        val_str = f"${price:.2f} — near {extreme}"
        label = "52-Week Extreme"
        page_url = f"{SITE_URL}/commodities/{code}"
        og_image_url = f"{CDN_URL}/og/commodities/{code}.png"
        data_context = f"{name} ({ticker}) is at ${price:.2f}, near its {extreme} (range: ${low_52w:.2f}–${high_52w:.2f})"
        hook_angle = f"{name} is near a {extreme}. Commodity extremes rarely last — here's what drives the next move."

    elif option == "debt_yoy_surge":
        # Country whose debt-to-GDP jumped most YoY
        row = db.execute(text("""
            WITH ranked AS (
                SELECT c.code, c.name, ci.value, ci.period_date,
                       LAG(ci.value) OVER (PARTITION BY c.id ORDER BY ci.period_date) AS prev_value
                FROM country_indicators ci
                JOIN countries c ON c.id = ci.country_id
                WHERE ci.indicator = 'government_debt_gdp_pct'
                  AND ci.period_date >= NOW() - INTERVAL '3 years'
            )
            SELECT code, name, value, prev_value, (value - prev_value) AS yoy_change
            FROM ranked
            WHERE prev_value IS NOT NULL AND (value - prev_value) > 5
            ORDER BY yoy_change DESC
            LIMIT 5
        """)).fetchone()
        if not row:
            return None
        code = row.code.lower()
        entity = row.name
        debt_now = float(row.value)
        debt_prev = float(row.prev_value)
        jump = float(row.yoy_change)
        val_str = f"debt jumped +{jump:.1f}pp to {debt_now:.1f}% of GDP in one year"
        label = "Debt Surge"
        page_url = f"{SITE_URL}/countries/{code}"
        og_image_url = f"{CDN_URL}/og/countries/{code}.png"
        data_context = f"{entity}'s government debt {val_str} (was {debt_prev:.1f}%)"
        hook_angle = f"A {jump:.0f}pp single-year debt jump is a major fiscal red flag — bond markets price this in slowly, then suddenly."

    else:
        return None

    news = _fetch_news_context(entity)
    news_block = f"\nCurrent news context:\n{news}" if news else ""

    prompt = f"""
You are writing finance social media content for MetricsHour (macro intelligence platform).
{AUDIENCE_PERSONA}

Data: {data_context}
Angle: {hook_angle}{news_block}
Page: {page_url}

Write FIVE "did you know" / shocking stat posts:

1. TWITTER (max 260 chars, lead with the shocking number, "Did you know?" or similar hook, 1-2 emojis, include URL)

2. LINKEDIN — data-led, no emojis, no hashtags, no sign-off. Under 100 words.
Start with the shocking stat as headline. 2-3 brief observations on why it matters. Include URL.

3. FACEBOOK — one punchy paragraph, lead with the surprising number, 1 emoji, include URL. Max 50 words.

4. INSTAGRAM — punchy "Did you know?" hook as first line (before fold), 3-5 relevant emojis woven in, data-led, include URL {page_url} naturally in caption, 5-8 relevant hashtags at end. Max 200 words.

5. REDDIT — write a genuinely useful discussion post, NOT promotional:
   - "subreddit": best single subreddit from [investing, economics, worldnews, geopolitics, MacroEconomics, dataisbeautiful, StockMarket] — pick based on content angle
   - "title": compelling "Did you know" style title (max 200 chars) — shocking stat, sparks discussion
   - "body": 3-4 paragraphs. Lead with the surprising data point. Explain why it matters. Historical context or comparison. End with genuine open question. URL as source link only. No marketing language.

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "instagram": "...", "reddit_subreddit": "...", "reddit_title": "...", "reddit_body": "..."}}
"""
    result = _call_ai(prompt)
    if not result:
        return None
    return {
        "type": "viral_stat",
        "entity": entity,
        "entity_code": code,
        "label": label,
        "value": val_str,
        "url": page_url,
        "og_image_url": og_image_url,
        "twitter": result.get("twitter", ""),
        "linkedin": result.get("linkedin", ""),
        "facebook": result.get("facebook", ""),
        "instagram": result.get("instagram", ""),
        "reddit_subreddit": result.get("reddit_subreddit", ""),
        "reddit_title": result.get("reddit_title", ""),
        "reddit_body": result.get("reddit_body", ""),
    }


def _send_draft_to_telegram(draft: dict) -> str | None:
    """Send draft to Telegram as 5 separate copy-ready messages. Returns 'ok' or None."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return None

    tg_api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    og_image_url = draft.get("og_image_url", "")
    entity = draft.get("entity", "")
    label = draft.get("label", "")
    value = draft.get("value", "")
    slot_name = draft.get("type", "post").replace("_", " ").title()

    sent_count = 0

    # 1. Photo message with caption (if OG image available)
    if og_image_url:
        try:
            r = requests.post(
                f"{tg_api}/sendPhoto",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "photo": og_image_url,
                    "caption": f"📊 {slot_name} — {entity} {value}",
                },
                timeout=10,
            )
            r.raise_for_status()
            sent_count += 1
        except Exception as e:
            log.warning("Telegram photo send failed: %s", e)

    # 2. Twitter message
    twitter_text = draft.get("twitter", "")
    if twitter_text:
        try:
            r = requests.post(
                f"{tg_api}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": (
                        "🐦 TWITTER (copy & post)\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        f"{twitter_text}"
                    ),
                },
                timeout=10,
            )
            r.raise_for_status()
            sent_count += 1
        except Exception as e:
            log.warning("Telegram Twitter message failed: %s", e)

    # 3. LinkedIn message
    linkedin_text = draft.get("linkedin", "")
    if linkedin_text:
        try:
            r = requests.post(
                f"{tg_api}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": (
                        "💼 LINKEDIN (copy & post)\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        f"{linkedin_text}"
                    ),
                },
                timeout=10,
            )
            r.raise_for_status()
            sent_count += 1
        except Exception as e:
            log.warning("Telegram LinkedIn message failed: %s", e)

    # 4. Facebook message
    facebook_text = draft.get("facebook", "")
    if facebook_text:
        try:
            r = requests.post(
                f"{tg_api}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": (
                        "📘 FACEBOOK (copy & post)\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        f"{facebook_text}"
                    ),
                },
                timeout=10,
            )
            r.raise_for_status()
            sent_count += 1
        except Exception as e:
            log.warning("Telegram Facebook message failed: %s", e)

    # 5. Instagram message
    instagram_text = draft.get("instagram", "")
    if instagram_text:
        try:
            r = requests.post(
                f"{tg_api}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": (
                        "📸 INSTAGRAM (copy & post)\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        f"{instagram_text}"
                    ),
                },
                timeout=10,
            )
            r.raise_for_status()
            sent_count += 1
        except Exception as e:
            log.warning("Telegram Instagram message failed: %s", e)

    if sent_count > 0:
        log.info("Draft sent to Telegram: %s (%d messages)", entity, sent_count)
        return "ok"
    return None


def _send_failure_alert(slot_name: str, error_msg: str) -> None:
    """Send a Telegram alert when a scheduled slot fails permanently after all retries."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": f"\u274c *SLOT FAILED: {slot_name}*\n{error_msg}",
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
    except Exception:
        pass


def _trigger_reel_via_moltis(style: str, subject: str, hook: str) -> bool:
    """Trigger a reel generation via tg-bridge injection to Moltis. Returns True on success."""
    if not TELEGRAM_WEBHOOK_SECRET or not TELEGRAM_CHAT_ID:
        log.warning("Reel trigger skipped — TELEGRAM_WEBHOOK_SECRET or TELEGRAM_CHAT_ID not set")
        return False
    payload = {
        "update_id": 999999,
        "message": {
            "message_id": 999999,
            "from": {"id": int(TELEGRAM_CHAT_ID), "is_bot": False, "first_name": "Scheduler"},
            "chat": {"id": int(TELEGRAM_CHAT_ID), "type": "private"},
            "date": int(time.time()),
            "text": (
                    "[AUTOMATED "
                    + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                    + "] TOOL CALL REQUIRED - do NOT respond with text first."
                    f" Call mcp__metricshour__smart_reel immediately."
                    f" Arguments: style={style} subject={subject} hook={hook}"
                ),
        },
    }
    try:
        r = requests.post(
            TG_BRIDGE_URL,
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": TELEGRAM_WEBHOOK_SECRET},
            timeout=10,
        )
        log.info("Reel trigger (%s/%s) → tg-bridge: HTTP %s", style, subject, r.status_code)
        return r.status_code < 400
    except Exception as e:
        log.warning("Reel trigger failed (%s/%s): %s", style, subject, e)
        return False


@app.task(name='tasks.social_content.generate_social_drafts', bind=True, max_retries=2)
def generate_social_drafts(self):
    """Generate 1 rotating social post draft and send to Telegram. Runs daily at 9am UTC.
    Rotates daily: country spotlight → stock exposure → trade insight → repeat.
    Keeps morning total at 2 posts (market_open at 8am + this at 9am) + 1 reel (8:30am).
    """
    db = SessionLocal()
    try:
        # Rotate hook type by day-of-year so it cycles: country → stock → trade
        from datetime import date
        day_index = date.today().timetuple().tm_yday % 3
        hook_fns = [_hook_country_spotlight, _hook_stock_exposure, _hook_trade_insight]
        # Try primary hook first, fall back to next ones if data unavailable
        draft = None
        for i in range(3):
            fn = hook_fns[(day_index + i) % 3]
            draft = fn(db)
            if draft and draft.get("linkedin"):
                break
        if draft and draft.get("linkedin"):
            if _send_draft_to_telegram(draft):
                log.info("Social draft (09:00) sent to Telegram: %s", draft.get("entity", "?"))
                return "ok: 1 draft sent"
        log.warning("Social draft (09:00): no data or AI unavailable")
        raise self.retry(
            exc=RuntimeError("Social draft: no data or AI call failed"),
            countdown=300,
        )
    except self.MaxRetriesExceededError:
        log.error("Social drafts: max retries exceeded — AI unavailable at 9am UTC")
        _send_failure_alert("POST 2 (09:00 social draft)", "AI unavailable after 3 attempts — Gemini/DeepSeek both down?")
        return "error: max retries exceeded"
    except Exception as exc:
        log.exception("Social content generation failed")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


@app.task(name='tasks.social_content.generate_market_open_drafts', bind=True, max_retries=2)
def generate_market_open_drafts(self):
    """Generate market-open draft from top movers. Runs daily at 8am UTC."""
    db = SessionLocal()
    try:
        draft = _hook_market_movers(db)
        if draft and draft.get("twitter"):
            if _send_draft_to_telegram(draft):
                log.info("Market open draft sent to Telegram")
                return "ok: 1 draft sent"
        log.warning("Market open draft: no data or AI unavailable")
        raise self.retry(
            exc=RuntimeError("Market movers: no data or AI call failed"),
            countdown=300,
        )
    except self.MaxRetriesExceededError:
        log.error("Market open drafts: max retries exceeded")
        _send_failure_alert("POST 1 (08:00 market open)", "AI unavailable after 3 attempts — check celery.log")
        return "error: max retries exceeded"
    except Exception as exc:
        log.exception("Market open draft generation failed")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


@app.task(name='tasks.social_content.generate_evening_wrap_drafts', bind=True, max_retries=2)
def generate_evening_wrap_drafts(self):
    """Generate end-of-day wrap draft. Runs daily at 5pm UTC."""
    db = SessionLocal()
    try:
        draft = _hook_day_wrap(db)
        if draft and draft.get("twitter"):
            if _send_draft_to_telegram(draft):
                log.info("Evening wrap draft sent to Telegram")
                return "ok: 1 draft sent"
        log.warning("Evening wrap draft: no data or AI unavailable")
        raise self.retry(
            exc=RuntimeError("Day wrap: no data or AI call failed"),
            countdown=300,
        )
    except self.MaxRetriesExceededError:
        log.error("Evening wrap drafts: max retries exceeded")
        _send_failure_alert("POST 3 (17:00 evening wrap)", "AI unavailable after 3 attempts — check celery.log")
        return "error: max retries exceeded"
    except Exception as exc:
        log.exception("Evening wrap draft generation failed")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


@app.task(name='tasks.social_content.generate_viral_hook_drafts', bind=True, max_retries=2)
def generate_viral_hook_drafts(self):
    """Generate viral / shocking stat draft. Runs daily at 6pm UTC."""
    db = SessionLocal()
    try:
        draft = _hook_viral_stat(db)
        if draft and draft.get("twitter"):
            if _send_draft_to_telegram(draft):
                log.info("Viral hook draft sent to Telegram")
                return "ok: 1 draft sent"
        log.warning("Viral hook draft: no data or AI unavailable")
        raise self.retry(
            exc=RuntimeError("Viral stat: no data or AI call failed"),
            countdown=300,
        )
    except self.MaxRetriesExceededError:
        log.error("Viral hook drafts: max retries exceeded")
        _send_failure_alert("POST 4 (18:00 viral stat)", "AI unavailable after 3 attempts — check celery.log")
        return "error: max retries exceeded"
    except Exception as exc:
        log.exception("Viral hook draft generation failed")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


@app.task(name='tasks.social_content.generate_morning_reel', bind=True, max_retries=2)
def generate_morning_reel(self):
    """Generate morning market reel via Moltis at 8:30 UTC."""
    try:
        ok = _trigger_reel_via_moltis("market_recap", "markets", "Markets open: here are today's biggest movers")
        if not ok:
            raise RuntimeError("tg-bridge rejected or unreachable")
        return "reel triggered"
    except self.MaxRetriesExceededError:
        _send_failure_alert("REEL 1 (08:30 market_recap)", "tg-bridge unreachable after 3 attempts — is it running on Contabo?")
        return "error: max retries exceeded"
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


@app.task(name='tasks.social_content.generate_morning_reel_2', bind=True, max_retries=2)
def generate_morning_reel_2(self):
    """Generate second morning reel via Moltis at 9:30 UTC.
    Rotates daily: country_deep_dive → stock_analysis → trade_spotlight.
    """
    from datetime import date
    styles = [
        ("country_deep_dive", "US", "The macro story behind the world's largest economy"),
        ("stock_analysis", "AAPL", "How global trade shapes this stock's revenue"),
        ("trade_spotlight", "US-CN", "The world's most important trade relationship"),
    ]
    pick = styles[date.today().timetuple().tm_yday % 3]
    try:
        ok = _trigger_reel_via_moltis(pick[0], pick[1], pick[2])
        if not ok:
            raise RuntimeError("tg-bridge rejected or unreachable")
        return "reel triggered"
    except self.MaxRetriesExceededError:
        _send_failure_alert(f"REEL 2 (09:30 {pick[0]})", "tg-bridge unreachable after 3 attempts — is it running on Contabo?")
        return "error: max retries exceeded"
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


@app.task(name='tasks.social_content.generate_evening_reel', bind=True, max_retries=2)
def generate_evening_reel(self):
    """Generate evening crypto/wrap reel via Moltis at 17:30 UTC."""
    try:
        ok = _trigger_reel_via_moltis("crypto_update", "bitcoin", "Today's crypto wrap: biggest moves of the day")
        if not ok:
            raise RuntimeError("tg-bridge rejected or unreachable")
        return "reel triggered"
    except self.MaxRetriesExceededError:
        _send_failure_alert("REEL 3 (17:30 crypto_update)", "tg-bridge unreachable after 3 attempts — is it running on Contabo?")
        return "error: max retries exceeded"
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


@app.task(name='tasks.social_content.generate_evening_reel_2', bind=True, max_retries=2)
def generate_evening_reel_2(self):
    """Generate second evening reel via Moltis at 18:30 UTC.
    Rotates daily: commodities → trade_spotlight → country_deep_dive.
    """
    from datetime import date
    styles = [
        ("commodities", "gold", "Gold, oil, metals — today's commodity moves"),
        ("trade_spotlight", "DE-CN", "Europe's biggest trade corridor in focus"),
        ("country_deep_dive", "CN", "China's economy: the numbers that move markets"),
    ]
    pick = styles[date.today().timetuple().tm_yday % 3]
    try:
        ok = _trigger_reel_via_moltis(pick[0], pick[1], pick[2])
        if not ok:
            raise RuntimeError("tg-bridge rejected or unreachable")
        return "reel triggered"
    except self.MaxRetriesExceededError:
        _send_failure_alert(f"REEL 4 (18:30 {pick[0]})", "tg-bridge unreachable after 3 attempts — is it running on Contabo?")
        return "error: max retries exceeded"
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)
