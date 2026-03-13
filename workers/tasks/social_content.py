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


def _call_gemini(prompt: str) -> dict | None:
    """Call Gemini Flash Lite, return parsed JSON {twitter, linkedin} or None."""
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        from google.genai import types as genai_types
        client = genai.Client(api_key=GEMINI_API_KEY)
        r = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                max_output_tokens=2000,
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )
        text = (r.text or "").strip()
        return json.loads(text)
    except Exception as e:
        log.warning("Gemini social content failed: %s", e)
        return None


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
2. LINKEDIN (3 short paragraphs: data context, what it means for investors/markets, call to action with URL. Professional but engaging. ~150 words.)
3. FACEBOOK (conversational, 2-3 sentences + the number + URL. More casual than LinkedIn, more context than Twitter. 1 emoji.)
4. REDDIT — write a genuinely useful discussion post, NOT promotional:
   - "subreddit": best single subreddit from [investing, economics, worldnews, geopolitics, economy, stocks, MacroEconomics, dataisbeautiful] — pick based on content angle
   - "title": compelling Reddit title (max 200 chars) — data-led, sparks discussion, no clickbait
   - "body": 3-4 paragraphs. Open with the raw data and historical context. Second paragraph: what this means for markets/investors with specific implications. Third paragraph: 1-2 contrarian angles or risks people miss. End with a genuine open question to drive comments. Do NOT mention MetricsHour by name in body — only include the URL naturally as "source" or "more data". No marketing language. Write like a knowledgeable community member.

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "reddit_subreddit": "...", "reddit_title": "...", "reddit_body": "..."}}
"""
    result = _call_gemini(prompt)
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
2. LINKEDIN (3 short paragraphs: the geographic breakdown, macro risk/opportunity for each region, investor takeaway with URL. ~150 words. Professional tone.)
3. FACEBOOK (conversational, 2-3 sentences about the % and top countries + URL. Casual but informative. 1 emoji.)
4. REDDIT — write a genuinely useful discussion post, NOT promotional:
   - "subreddit": best single subreddit from [investing, stocks, SecurityAnalysis, ValueInvesting, StockMarket, geopolitics, economics] — pick based on content angle
   - "title": compelling Reddit title (max 200 chars) — specific numbers, sparks discussion, no clickbait
   - "body": 3-4 paragraphs. Open with the geographic breakdown and specific revenue %s. Second paragraph: which macro risks (tariffs, FX, geopolitics) are most relevant for each region and why. Third paragraph: what the market may be mispricing or overlooking. End with a genuine question about how others are thinking about this exposure. Do NOT mention MetricsHour by name in body — only include URL naturally as "source". Write like a thoughtful investor, not a marketer.

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "reddit_subreddit": "...", "reddit_title": "...", "reddit_body": "..."}}
"""
    result = _call_gemini(prompt)
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
2. LINKEDIN (3 short paragraphs: the trade relationship, what macro/political risks apply, investor implication with URL. ~150 words.)
3. FACEBOOK (conversational, 2-3 sentences: the trade value, what's traded, why it matters + URL. Casual tone. 1 emoji.)
4. REDDIT — write a genuinely useful discussion post, NOT promotional:
   - "subreddit": best single subreddit from [geopolitics, investing, economics, worldnews, StockMarket, MacroEconomics, GlobalPowers] — pick based on content angle
   - "title": compelling Reddit title (max 200 chars) — specific dollar figure, geopolitical angle, sparks debate, no clickbait
   - "body": 3-4 paragraphs. Open with the bilateral trade value and what's being traded. Second paragraph: geopolitical or policy risks that could disrupt this corridor (tariffs, sanctions, diplomatic tensions). Third paragraph: which sectors and companies are most exposed — give specific examples if possible. End with a genuine open question about where this corridor is heading. URL as "source" link only. Write like an informed macro analyst sharing knowledge, not promoting a product.

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "reddit_subreddit": "...", "reddit_title": "...", "reddit_body": "..."}}
"""
    result = _call_gemini(prompt)
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


@app.task(name='tasks.social_content.generate_social_drafts', bind=True, max_retries=1)
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
        return f"ok: {sent} drafts sent"
    except Exception as exc:
        log.exception("Social content generation failed")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
