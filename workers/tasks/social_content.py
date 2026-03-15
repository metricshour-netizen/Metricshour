"""
Social Content Pipeline — generates post drafts and sends to Telegram for approval.

Flow:
  Celery Beat (9am UTC daily)
    → pull 3 interesting data hooks from DB
    → Gemini 2.5 Flash Lite generates Twitter + LinkedIn copy
    → send each to Telegram with inline buttons [Twitter] [LinkedIn] [Both] [Skip]
    → user taps approval → FastAPI webhook → posts to platform

Content hooks (rotates daily):
  1. Country spotlight — G20 country with notable indicator value
  2. Stock geo exposure — US stock with highest non-US revenue %
  3. Trade insight — largest bilateral pair with key stat
"""
import json
import logging
import os
import random
from datetime import date, timedelta

import requests
from celery_app import app
from sqlalchemy import select, func

from app.database import SessionLocal
from app.models.country import Country, CountryIndicator
from app.models.asset import Asset, StockCountryRevenue
from sqlalchemy.orm import aliased

from app.storage import get_redis

log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_KEY_2 = os.environ.get("GEMINI_API_KEY_2", "")

DRAFT_TTL = 60 * 60 * 48  # 48h — drafts expire if not acted on

SITE_URL = "https://metricshour.com"

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
        for key in ("twitter", "linkedin", "facebook", "reddit_subreddit", "reddit_title", "reddit_body"):
            m = _re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', text, _re.DOTALL)
            if m:
                partial[key] = m.group(1).replace('\\"', '"').replace("\\n", "\n")
        return partial if partial else None
    except Exception:
        return None


def _call_gemini_with_key(api_key: str, prompt: str) -> dict | None:
    """Call Gemini 2.5 Flash Lite via direct REST (SDK hangs on this server)."""
    if not api_key:
        return None
    try:
        resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
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


def _hook_country_spotlight(db) -> dict | None:
    """Pick a random G20 country + interesting indicator, generate post copy."""
    indicator_key, label, unit = random.choice(SPOTLIGHT_INDICATORS)
    country_code = random.choice(G20_CODES)

    country = db.execute(
        select(Country).where(Country.code == country_code)
    ).scalar_one_or_none()
    if not country:
        return None

    # Get latest value + 3-year history
    rows = db.execute(
        select(CountryIndicator.period_date, CountryIndicator.value)
        .where(
            CountryIndicator.country_id == country.id,
            CountryIndicator.indicator == indicator_key,
        )
        .order_by(CountryIndicator.period_date.desc())
        .limit(4)
    ).all()
    if not rows:
        return None

    current_val = float(rows[0].value)
    current_year = rows[0].period_date.year
    history_str = ", ".join(
        f"{r.period_date.year}: {_fmt_value(float(r.value), unit)}"
        for r in rows
    )
    page_url = f"{SITE_URL}/countries/{country_code.lower()}"

    prompt = f"""
You are writing finance social media content for MetricsHour (macro intelligence platform).

Data: {country.name} — {label}: {_fmt_value(current_val, unit)} ({current_year})
History: {history_str}
Page: {page_url}

Write FOUR posts about this macro data point:

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
4. REDDIT — write a genuinely useful discussion post, NOT promotional:
   - "subreddit": best single subreddit from [investing, economics, worldnews, geopolitics, economy, stocks, MacroEconomics, dataisbeautiful] — pick based on content angle
   - "title": compelling Reddit title (max 200 chars) — data-led, sparks discussion, no clickbait
   - "body": 3-4 paragraphs. Open with the raw data and historical context. Second paragraph: what this means for markets/investors with specific implications. Third paragraph: 1-2 contrarian angles or risks people miss. End with a genuine open question to drive comments. Do NOT mention MetricsHour by name in body — only include the URL naturally as "source" or "more data". No marketing language. Write like a knowledgeable community member.

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "reddit_subreddit": "...", "reddit_title": "...", "reddit_body": "..."}}
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
        "twitter": result.get("twitter", ""),
        "linkedin": result.get("linkedin", ""),
        "facebook": result.get("facebook", ""),
        "reddit_subreddit": result.get("reddit_subreddit", ""),
        "reddit_title": result.get("reddit_title", ""),
        "reddit_body": result.get("reddit_body", ""),
    }


def _hook_stock_exposure(db) -> dict | None:
    """Pick a well-known stock with highest international revenue exposure."""
    # Get stocks with meaningful geo revenue data
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

    prompt = f"""
You are writing finance social media content for MetricsHour (macro intelligence platform).

Data: {name} ({ticker}) earns {intl_pct:.0f}% of revenue outside the US.
Top international markets: {geo_breakdown}
Page: {page_url}

Write FOUR posts about this stock's geographic revenue exposure and what it means:

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
4. REDDIT — write a genuinely useful discussion post, NOT promotional:
   - "subreddit": best single subreddit from [investing, stocks, SecurityAnalysis, ValueInvesting, StockMarket, geopolitics, economics] — pick based on content angle
   - "title": compelling Reddit title (max 200 chars) — specific numbers, sparks discussion, no clickbait
   - "body": 3-4 paragraphs. Open with the geographic breakdown and specific revenue %s. Second paragraph: which macro risks (tariffs, FX, geopolitics) are most relevant for each region and why. Third paragraph: what the market may be mispricing or overlooking. End with a genuine question about how others are thinking about this exposure. Do NOT mention MetricsHour by name in body — only include URL naturally as "source". Write like a thoughtful investor, not a marketer.

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "reddit_subreddit": "...", "reddit_title": "...", "reddit_body": "..."}}
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
        "twitter": result.get("twitter", ""),
        "linkedin": result.get("linkedin", ""),
        "facebook": result.get("facebook", ""),
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

    prompt = f"""
You are writing finance social media content for MetricsHour (macro intelligence platform).

Data: {exp.name}–{imp.name} bilateral trade: {val_str}/year ({pair.year})
Top traded goods: {products}
Page: {page_url}

Write FOUR posts about this trade relationship and why it matters to investors:

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
4. REDDIT — write a genuinely useful discussion post, NOT promotional:
   - "subreddit": best single subreddit from [geopolitics, investing, economics, worldnews, StockMarket, MacroEconomics, GlobalPowers] — pick based on content angle
   - "title": compelling Reddit title (max 200 chars) — specific dollar figure, geopolitical angle, sparks debate, no clickbait
   - "body": 3-4 paragraphs. Open with the bilateral trade value and what's being traded. Second paragraph: geopolitical or policy risks that could disrupt this corridor (tariffs, sanctions, diplomatic tensions). Third paragraph: which sectors and companies are most exposed — give specific examples if possible. End with a genuine open question about where this corridor is heading. URL as "source" link only. Write like an informed macro analyst sharing knowledge, not promoting a product.

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "reddit_subreddit": "...", "reddit_title": "...", "reddit_body": "..."}}
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
        "twitter": result.get("twitter", ""),
        "linkedin": result.get("linkedin", ""),
        "facebook": result.get("facebook", ""),
        "reddit_subreddit": result.get("reddit_subreddit", ""),
        "reddit_title": result.get("reddit_title", ""),
        "reddit_body": result.get("reddit_body", ""),
    }


def _send_draft_to_telegram(draft: dict) -> str | None:
    """Send draft to Telegram with inline approval buttons. Returns message_id or None."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return None

    draft_key = f"social:draft:{draft['type']}:{draft['entity_code']}:{date.today().isoformat()}"

    # Store draft in Redis for webhook to retrieve
    try:
        r = get_redis()
        r.setex(draft_key, DRAFT_TTL, json.dumps(draft))
    except Exception as e:
        log.warning("Redis store draft failed: %s", e)
        return None

    fb_text = draft.get("facebook", "")
    reddit_sub = draft.get("reddit_subreddit", "")
    reddit_title = draft.get("reddit_title", "")
    reddit_body = draft.get("reddit_body", "")

    text = (
        f"📱 <b>Social Draft — {draft['entity']}</b>\n"
        f"<i>{draft['label']}: {draft['value']}</i>\n\n"
        f"💼 <b>LinkedIn:</b>\n{draft['linkedin'][:500]}\n\n"
        + (f"📘 <b>Facebook:</b>\n{fb_text[:300]}\n\n" if fb_text else "")
        + f"🐦 <b>Twitter:</b>\n<code>{draft['twitter'][:280]}</code>"
        + (f"\n\n🟠 <b>Reddit r/{reddit_sub}:</b>\n<b>{reddit_title}</b>\n{reddit_body[:400]}" if reddit_title else "")
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "💼 LinkedIn", "callback_data": f"social:linkedin:{draft_key}"},
                {"text": "📘 Facebook", "callback_data": f"social:facebook:{draft_key}"},
            ],
            [
                {"text": "🟠 Reddit", "callback_data": f"social:reddit:{draft_key}"},
                {"text": "✅ LI + FB + Reddit", "callback_data": f"social:all:{draft_key}"},
            ],
            [
                {"text": "✅ LI + FB", "callback_data": f"social:both:{draft_key}"},
                {"text": "❌ Skip", "callback_data": f"social:skip:{draft_key}"},
            ],
        ]
    }

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text[:4000],
                "parse_mode": "HTML",
                "reply_markup": keyboard,
            },
            timeout=10,
        )
        r.raise_for_status()
        msg_id = r.json().get("result", {}).get("message_id")
        log.info("Draft sent to Telegram: %s (msg_id=%s)", draft["entity"], msg_id)
        return str(msg_id)
    except Exception as e:
        log.warning("Telegram draft send failed: %s", e)
        return None


@app.task(name='tasks.social_content.generate_social_drafts', bind=True, max_retries=2)
def generate_social_drafts(self):
    """Generate 3 social post drafts and send to Telegram for approval. Runs daily at 9am UTC."""
    db = SessionLocal()
    try:
        hooks = [
            _hook_country_spotlight(db),
            _hook_stock_exposure(db),
            _hook_trade_insight(db),
        ]
        sent = 0
        for draft in hooks:
            if draft and draft.get("linkedin"):
                if _send_draft_to_telegram(draft):
                    sent += 1
        log.info("Social drafts generated and sent: %d/3", sent)
        if sent == 0:
            # All AI calls failed — retry after 5 minutes
            raise self.retry(
                exc=RuntimeError("All 3 AI calls failed — both Gemini and DeepSeek unavailable"),
                countdown=300,
            )
        return f"ok: {sent} drafts sent"
    except self.MaxRetriesExceededError:
        log.error("Social drafts: max retries exceeded — AI unavailable at 9am UTC")
        return "error: max retries exceeded"
    except Exception as exc:
        log.exception("Social content generation failed")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
