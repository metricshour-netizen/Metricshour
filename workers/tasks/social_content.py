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

import redis as _redis_lib
import requests
from celery_app import app
from sqlalchemy import select, func, text

from app.database import SessionLocal
from app.models.country import Country, CountryIndicator
from app.models.asset import Asset, StockCountryRevenue
from sqlalchemy.orm import aliased

log = logging.getLogger(__name__)

# ── Redis idempotency lock ────────────────────────────────────────────────────
# Prevents duplicate post delivery when Celery restores unacknowledged messages
# (e.g. after worker restart mid-retry). Each slot locks for 2 hours per day.
def _get_redis():
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    return _redis_lib.from_url(url, decode_responses=True, socket_connect_timeout=2, socket_timeout=3)


# Slot → content_log slot_name prefix mapping for DB fallback dedup
_SLOT_TO_LOG_PREFIX = {
    "morning_reel": "reel_market_recap",
    "morning_reel_2": "reel_",
    "evening_reel": "reel_crypto_update",
    "evening_reel_2": "reel_trade_spotlight",
    "market_open": "market_movers",
    "social_drafts": None,
    "evening_wrap": "day_wrap",
    "viral_hook": "viral_stat",
}


def _acquire_slot_lock(slot: str) -> bool:
    """Try to acquire a per-slot-per-day lock. Returns True if acquired (ok to run),
    False if another instance already holds it (skip this run).
    Falls back to content_log DB check when Redis is unavailable."""
    key = f"social:lock:{slot}:{date.today().isoformat()}"
    try:
        r = _get_redis()
        acquired = r.set(key, "1", nx=True, ex=7200)  # 2-hour TTL
        if not acquired:
            log.warning("Slot %s already locked today — skipping duplicate run", slot)
        return bool(acquired)
    except Exception as e:
        log.warning("Redis lock unavailable (%s) — falling back to DB dedup check", e)
        # DB fallback: check if this slot ran in the last 2 hours
        try:
            prefix = _SLOT_TO_LOG_PREFIX.get(slot)
            if prefix:
                db = SessionLocal()
                try:
                    row = db.execute(text(
                        "SELECT 1 FROM content_log WHERE slot_name LIKE :prefix"
                        " AND created_at >= NOW() - INTERVAL '2 hours' LIMIT 1"
                    ), {"prefix": f"{prefix}%"}).fetchone()
                    if row:
                        log.warning("Slot %s already in content_log (last 2h) — skipping", slot)
                        return False
                finally:
                    db.close()
        except Exception as db_e:
            log.warning("DB dedup check also failed (%s) — allowing run", db_e)
        return True


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
        for key in ("twitter", "linkedin", "facebook", "instagram"):
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
                    "maxOutputTokens": 4096,
                    "responseMimeType": "application/json",
                },
            },
            timeout=30,
        )
        resp.raise_for_status()
        _cands = resp.json().get("candidates", [])
        _parts = _cands[0].get("content", {}).get("parts", []) if _cands else []
        text = next((p.get("text", "") for p in _parts if p.get("text")), "")
        if not text:
            log.warning("Gemini call failed (key=...%s): empty parts in response", api_key[-6:])
            return None
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
                "max_tokens": 4096,
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


# AI slop — generic phrases that indicate low-quality output, trigger a retry
_BANNED_PHRASES = [
    # preamble / filler
    "it's important to note", "it is important to note",
    "in today's fast-paced", "in today's world", "in the current landscape",
    "it goes without saying", "needless to say",
    "at the end of the day", "when all is said and done",
    "in conclusion", "to summarize", "as we can see",
    "interestingly enough", "it's worth noting", "it is worth noting",
    "in the world of", "the reality is", "let that sink in",
    "food for thought", "worth watching", "stay tuned",
    "follow for more", "like and share", "drop a comment",
    # vague analyst-speak
    "nuanced", "multifaceted", "navigating", "leveraging",
    "game-changer", "game changer", "paradigm shift",
    "here's what you need to know", "what you need to know",
    "why it matters", "here's why", "unpacking", "deep dive",
    "key takeaway", "bottom line", "make no mistake",
    "more than ever", "unprecedented", "historic levels",
    "investors should consider", "investors should note",
    "the markets are", "global markets", "market participants",
    # hedging / weasel words that dilute the claim
    "price action", "signals a new", "signals that",
    "amid uncertainty", "amid growing", "amid rising",
    "could potentially", "may potentially", "might potentially",
    "headwinds", "tailwinds", "going forward",
    "macro environment", "broader market", "broader economy",
    "signals optimism", "signals concern", "signals confidence",
    "strategic advantage", "competitive advantage", "competitive landscape",
    "moving forward", "in the near term", "in the short term",
    "adds to concerns", "raises concerns", "easing concerns",
]

import re as _re


def _quality_check(result: dict) -> bool:
    """Reject output with banned phrases or missing specific numbers in Twitter copy."""
    combined = " ".join(str(v) for v in result.values()).lower()
    for phrase in _BANNED_PHRASES:
        if phrase in combined:
            log.warning("Quality gate rejected — banned phrase: '%s'", phrase)
            return False
    # Twitter must contain at least one specific number (%, $, digit) — no vague generalities
    twitter = result.get("twitter", "")
    if twitter and not _re.search(r'[\d]+[%$]|[\$£€]\d|[\d]+\.\d', twitter):
        log.warning("Quality gate rejected — Twitter copy has no specific numbers: %s", twitter[:80])
        return False
    return True


def _call_ai(prompt: str) -> dict | None:
    """Call Gemini (fallback DeepSeek). Retries once on quality gate failure."""
    for attempt in range(2):
        result = _call_gemini(prompt)
        if not result:
            log.info("Gemini unavailable — falling back to DeepSeek V3")
            result = _call_deepseek(prompt)
        if result:
            if _quality_check(result):
                return result
            if attempt == 0:
                log.info("Quality gate failed — retrying AI call")
                continue
    return result  # return even if quality gate fails on second attempt (better than None)


# Audience persona — injected into every prompt
AUDIENCE_PERSONA = (
    "AUDIENCE: Retail investor, 30-45, follows macro and stocks on Twitter/Reddit/LinkedIn. "
    "Information-saturated — skips anything obvious, generic, or preachy. "
    "Shares ONLY posts that make them say 'I didn't know that' or 'that changes my view'.\n"
    "LANGUAGE RULES (non-negotiable — violations will be rejected):\n"
    "  - Every number MUST be a specific figure (e.g. 58.5%, $427B, -0.5pp) — NEVER 'high', 'low', 'significant'\n"
    "  - Name specific tickers, currencies, central banks, rates — NEVER 'the markets', 'investors', 'the economy'\n"
    "  - COMMIT to a specific claim — NEVER hedge with 'could', 'may', 'potentially', 'suggests', 'signals that'\n"
    "  - Write like a trader explaining their thesis, not an analyst writing a report\n"
    "  - Twitter: statements only — NO questions, NO 'Did you know', NO opening emojis\n"
    "  - No preamble ('In today's...', 'As we navigate...', 'It's important to note...')\n"
    "  - Every sentence must contain either a specific number OR a specific named entity (ticker, country, rate, policy)\n"
    "ANGLE SELECTION (mandatory before writing): identify 3 possible angles for this data. "
    "REJECT the obvious one. PICK the angle that contradicts expectations, reveals a hidden mechanism, or connects to a live macro trade. "
    "WEAK: 'X economy is struggling', 'investors are watching Y', 'this could impact Z'. "
    "STRONG: 'Turkey raised rates to 45% — real yield still -13.5%, TRY holders lose money every month', "
    "'AAPL earns 19% from China but US is the only growing segment — the geographic bet is priced backwards', "
    "'Germany GDP -0.5%: debt brake prevents stimulus, ECB pace is the only lever — short EUR/long Bunds is the trade'.\n"
    "GOAL: one post that one person screenshots and sends to a friend.\n"
    "FRESHNESS RULE: If 'Recent headlines' are listed in the prompt, your Twitter and Instagram "
    "OPENING LINE must tie the data to one of those headlines — make the stat feel relevant to THIS WEEK, "
    "not just a historical figure. Do not repeat the headline verbatim — connect the data to its implication.\n"
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
        if yoy != 0:  # skip when consecutive values are identical — avoids "0.0pp" output
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
    Pick the G20 country+indicator most worth posting about.
    Scoring: % YoY change, filtered by minimum absolute thresholds per indicator
    to avoid mathematical noise from near-zero baseline values.
    Bonus points for extreme absolute values (e.g. inflation > 20%, debt > 100%).
    """
    # Minimum absolute change required per indicator to be considered meaningful
    MIN_ABS = {
        "inflation_pct": 1.5,
        "gdp_growth_pct": 0.7,
        "government_debt_gdp_pct": 3.0,
        "unemployment_pct": 0.7,
        "budget_balance_gdp_pct": 1.2,
        "current_account_gdp_pct": 1.2,
        "foreign_reserves_usd": 0.0,  # handled separately via rel_change
        "fdi_inflows_gdp_pct": 0.4,
    }
    try:
        rows = db.execute(text("""
            WITH ranked AS (
                SELECT c.code, c.name, ci.indicator, ci.value, ci.period_date,
                       LAG(ci.value) OVER (
                           PARTITION BY c.id, ci.indicator ORDER BY ci.period_date
                       ) AS prev_value
                FROM country_indicators ci
                JOIN countries c ON c.id = ci.country_id
                WHERE c.code = ANY(:codes)
                  AND ci.indicator = ANY(:inds)
                  AND ci.period_date >= NOW() - INTERVAL '5 years'
            )
            SELECT code, name, indicator, value, prev_value, period_date,
                   ABS(value - prev_value) AS abs_change,
                   CASE WHEN prev_value != 0
                        THEN ABS((value - prev_value) / prev_value)
                        ELSE 0 END AS rel_change
            FROM ranked
            WHERE prev_value IS NOT NULL
            ORDER BY period_date DESC, rel_change DESC
            LIMIT 60
        """), {
            "codes": G20_CODES,
            "inds": [i[0] for i in SPOTLIGHT_INDICATORS],
        }).fetchall()
        if not rows:
            return None

        # Filter by minimum absolute thresholds then score
        scored = []
        for r in rows:
            min_abs = MIN_ABS.get(r.indicator, 1.0)
            if r.indicator == "foreign_reserves_usd":
                # For reserves, require 10%+ relative change
                if r.rel_change < 0.10:
                    continue
            elif float(r.abs_change) < min_abs:
                continue

            score = float(r.rel_change)

            # Bonus for extreme absolute values that are inherently newsworthy
            v = float(r.value)
            if r.indicator == "inflation_pct" and v > 15:
                score *= 2.0
            elif r.indicator == "inflation_pct" and v < 0:
                score *= 1.8  # deflation is rare and important
            elif r.indicator == "government_debt_gdp_pct" and v > 100:
                score *= 1.5
            elif r.indicator == "gdp_growth_pct" and v < -1:
                score *= 1.8  # recession
            elif r.indicator == "gdp_growth_pct" and v > 6:
                score *= 1.4  # boom
            elif r.indicator == "budget_balance_gdp_pct" and v < -6:
                score *= 1.5  # fiscal crisis territory
            elif r.indicator == "unemployment_pct" and v > 12:
                score *= 1.4

            scored.append((score, r))

        if not scored:
            return None

        scored.sort(key=lambda x: x[0], reverse=True)

        # Exclude recently used countries
        try:
            recent = db.execute(text(
                "SELECT entity FROM content_log WHERE content_type='post' "
                "AND slot_name='country_spotlight' AND created_at >= NOW() - INTERVAL '14 days'"
            )).scalars().all()
            recent_set = set(r.upper() for r in recent)
        except Exception:
            recent_set = set()

        candidates = [r for _, r in scored[:12] if r.name.upper() not in recent_set]
        if not candidates:
            candidates = [r for _, r in scored[:5]]

        pick = candidates[0]  # take the top scorer, not random — best = most interesting
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
    prev_val = float(rows[1].value) if len(rows) > 1 else None
    yoy_str = f" (was {_fmt_value(prev_val, unit)} in {rows[1].period_date.year})" if prev_val else ""
    news = _fetch_news_context(f"{country.name} {label} economy {current_year}")

    page_url = f"{SITE_URL}/countries/{country_code.lower()}"
    og_image_url = f"{CDN_URL}/og/countries/{country_code.lower()}.png"

    angle_block = f"\nTrend: {angle}" if angle else ""
    news_block = f"\nRecent headlines:\n{news}" if news else ""

    prompt = f"""You are a financial data journalist writing social copy for MetricsHour.
{AUDIENCE_PERSONA}

VERIFIED DATA (use exact numbers — do not invent or round differently):
Country: {country.name}
Indicator: {label}
Current value: {_fmt_value(current_val, unit)} ({current_year}){yoy_str}
5-year history: {history_str}{angle_block}{news_block}
Page URL: {page_url}

YOUR TASK: Write 4 platform posts using the SAME data with platform-specific formats.
Frame WHY this number matters to investors right now — policy implications, FX signals, sector exposure.

━━━ TWITTER ━━━
Max 250 chars for body text. Then add 1-2 SPECIFIC hashtags + URL + max 2 emojis (total tweet ~280 chars).
RULES:
- First word = country name or the number — never an emoji, never a question
- State the number with its change and the DATA YEAR: "[Country]: [indicator] [value] ([year])"
- Follow with ONE specific market consequence: name a rate/currency/sector/stock that is directly affected
- End with URL + 1-2 specific hashtags + max 2 emojis (after all text)
BANNED: questions, "Did you know", opening emojis, "investors should", "markets are", generic hashtags
EXAMPLE: "Turkey: inflation at 58.5% (2023). Central bank rate at 45% — real yield still deeply negative. TRY depreciation pressure on EM bond spreads. {SITE_URL}/countries/tr #TurkeyEconomy #EmergingMarkets 📉"

━━━ LINKEDIN ━━━
Format (copy exactly, no deviations):
Line 1: [Country] [indicator]: [exact value] ([data year]) — [1-sentence insight on what this signals for capital markets]
[blank line]
[2-3 observations, ONE per line, max 20 words each]:
- Cover: what drove the change, what policy/market mechanism it triggers, which asset class reacts first
- Name specific: central banks, currencies, bond yields, indices, sectors
[blank line]
[URL]
[blank line]
3-5 professional hashtags: SPECIFIC to country + indicator + region. BANNED: #investing #finance #economy #stocks #markets
EXAMPLE for Germany GDP: #GermanyEconomy #EuroZone #Bundesbank #ECBPolicy #DAXIndex
No emojis. No sign-off. Body under 90 words (hashtags not counted).
EXAMPLE:
Germany GDP growth: -0.5% (2023) — consecutive negative quarters signal Europe's largest economy is in contraction.

Berlin's debt brake prevents stimulus; growth must come from external demand or ECB rate cuts.
EUR/USD faces downward pressure; Bund yields diverge from Treasuries as Fed/ECB paths split.
Watch auto and industrial sectors — both are export-dependent and amplify German GDP swings.
{page_url}

#GermanyEconomy #EuroZone #Bundesbank #ECBPolicy #DAXIndex

━━━ FACEBOOK ━━━
2-3 short paragraphs. Pattern:
Para 1: [Lead with the shocking number + country + data year]. [One specific real-world consequence — name the mechanism, name specific rates/currencies/sectors].
Para 2: [Historical context or peer comparison that makes it concrete — compare to another country, a prior year level, or a real household/investor impact].
Para 3: [Forward-looking implication — name the policy lever, rate, or sector most affected]. [End with ONE engagement question inviting comment]. [1 emoji] [URL] [2-3 SPECIFIC hashtags]
Target: 100-150 words total. No "Did you know." Statements + one question at the very end only.
EXAMPLE:
"Germany's economy shrank -0.5% in 2023 — two consecutive contractions in Europe's largest economy. The debt brake means Berlin can't borrow to stimulate. The ECB's rate-cut pace is now Germany's only lever.

Compare that to France at +0.9%: same currency, same ECB rate, completely different fiscal position. Germany's manufacturing sector is the drag — auto exports fell 12% as China demand softened.

Do you think ECB rate cuts are enough to reverse this, or is this a structural problem? 📉 {page_url} #GermanyEconomy #EuroZone #ECBPolicy"

━━━ INSTAGRAM ━━━
Line 1 (CRITICAL — this is what shows before "more"): Must be a STATEMENT with the specific number AND data year. No questions. No emojis on line 1.
Example first line: "Germany's economy contracted -0.5% in 2023."
Body (4-6 lines): Each line = one data-driven observation. Include the 5-year history context. Name specific assets or policies.
Second-to-last body line: "Save this for your next portfolio review 📌" — this phrase boosts Instagram reach.
URL: include naturally mid-caption as "Full breakdown: [url]"
Hashtags (LAST — 9-12 total, MIX SIZES for reach):
- 2-3 NICHE under 100K posts: e.g. #GermanGDP #BundesbankPolicy #EurozonePMI
- 5-6 MEDIUM 100K–500K posts: e.g. #GermanyEconomy #Bundesbank #ECBPolicy #EuropeanMarkets #MacroEconomics
- 1-2 BRAND — always include: #MetricsHour #FinancialData
BANNED: #investing #finance #economy #stocks #markets #money (too broad, kills reach)
1-3 emojis max, woven into body, not clustered.

Return ONLY valid JSON with no extra text: {{"twitter": "...", "linkedin": "...", "facebook": "...", "instagram": "..."}}"""
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
            HAVING SUM(scr.revenue_pct) BETWEEN 20 AND 100
            ORDER BY rm.abs_pct DESC
            LIMIT 10
        """)).fetchall()
    except Exception:
        moved_rows = []

    RevCountry = aliased(Country)

    # Exclude last 2 stocks used to avoid daily repeats
    try:
        recent_stocks = db.execute(text(
            "SELECT entity FROM content_log WHERE content_type='post' "
            "AND slot_name='stock_exposure' AND created_at >= NOW() - INTERVAL '14 days'"
        )).scalars().all()
        # entity stored as "AAPL (Apple Inc.)" — extract ticker (first token)
        recent_tickers = set(r.split()[0].upper() for r in recent_stocks)
    except Exception:
        recent_tickers = set()

    if moved_rows:
        pool = [r for r in moved_rows[:10] if r.symbol.upper() not in recent_tickers]
        if not pool:
            pool = moved_rows[:5]
        pick_row = random.choice(pool[:5])
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
            .having(func.sum(StockCountryRevenue.revenue_pct).between(20, 100))
            .order_by(func.sum(StockCountryRevenue.revenue_pct).desc())
            .limit(20)
        ).all()
        if not rows:
            return None
        pool = [r for r in rows[:15] if r.symbol.upper() not in recent_tickers]
        if not pool:
            pool = rows[:10]
        pick = random.choice(pool[:10])
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

    # Build detailed geo breakdown with country names
    RevCountry3 = aliased(Country)
    top_countries_named = db.execute(
        select(RevCountry3.code, RevCountry3.name, StockCountryRevenue.revenue_pct, StockCountryRevenue.revenue_usd)
        .join(Asset, Asset.id == StockCountryRevenue.asset_id)
        .join(RevCountry3, RevCountry3.id == StockCountryRevenue.country_id)
        .where(Asset.symbol == ticker, RevCountry3.code != "US")
        .order_by(StockCountryRevenue.revenue_pct.desc())
        .limit(4)
    ).all()

    geo_lines = "\n".join(
        f"  {r.name} ({r.code}): {float(r.revenue_pct):.1f}%"
        + (f" (${float(r.revenue_usd)/1e9:.1f}B/yr)" if r.revenue_usd and float(r.revenue_usd) >= 1e9 else "")
        for r in top_countries_named
    )
    geo_breakdown = ", ".join(f"{r.code} {float(r.revenue_pct):.0f}%" for r in top_countries_named[:3])

    page_url = f"{SITE_URL}/stocks/{ticker.lower()}"
    og_image_url = f"{CDN_URL}/og/stocks/{ticker.lower()}.png"

    # Include price move context if stock was selected because it moved
    move_context = ""
    if moved_rows:
        for mr in moved_rows[:10]:
            if mr.symbol == ticker:
                move_context = f"\nRecent price move: {ticker} moved {float(mr.abs_pct):+.1f}% this week"
                break

    news = _fetch_news_context(f"{name} {ticker} earnings revenue tariffs China")
    news_block = f"\nRecent headlines:\n{news}" if news else ""

    prompt = f"""You are a financial data journalist writing social copy for MetricsHour.
{AUDIENCE_PERSONA}

VERIFIED DATA (use exact numbers):
Stock: {name} ({ticker})
Total non-US revenue: {intl_pct:.0f}% of annual revenue
Geographic breakdown:
{geo_lines}{move_context}{news_block}
Page URL: {page_url}

YOUR TASK: Write 4 platform posts connecting this stock's geographic exposure to current macro risk.
The angle is NOT "this stock has international revenue" — the angle is WHAT THAT MEANS for EPS, margins, or stock price given today's macro backdrop (tariffs, FX, geopolitics).

━━━ TWITTER ━━━
Max 250 chars for body text. Then add 1-2 SPECIFIC hashtags + URL + max 2 emojis (total tweet ~280 chars).
RULES:
- Start with: "{ticker} earns X% from [top country/region]" — ticker first, number second word
- Connect to a specific current risk: name the tariff rate, FX rate, or policy that directly affects EPS
- Give a specific quantified estimate of impact if possible ("~$X/share EPS risk")
- End with URL + 1-2 specific hashtags (e.g. #{ticker} #sector) + max 2 emojis
BANNED: questions, "investors should", "it's important", opening emojis, generic hashtags
EXAMPLE: "AAPL earns 19% from China. Current tariff escalation = ~$0.40/share quarterly EPS risk. China revenue growing while US consumer softens — that geographic bet is now priced wrong. {page_url} #{ticker} #ChinaTrade 🌏"

━━━ LINKEDIN ━━━
Line 1: {ticker} earns [X]% of revenue from [top region/country] — [1-sentence implication for current quarter/year]
[blank line]
[2-3 lines, one observation each, max 20 words]:
- Specific macro risk: tariff %, FX rate, or regulatory risk with a dollar/EPS estimate
- Geographic concentration risk vs diversification — which region is growing, which is slowing
- What the market is likely mispricing or over/underweighting
[blank line]
{page_url}
[blank line]
3-5 professional hashtags: SPECIFIC — ticker, sector, region, macro theme. BANNED: #investing #finance #stocks #markets
EXAMPLE for NVDA: #{ticker} #Semiconductors #ChinaRisk #TechStocks #ExportControls
No emojis. No sign-off. Body under 90 words (hashtags not counted).

━━━ FACEBOOK ━━━
2-3 short paragraphs. Pattern:
Para 1: [Ticker + the exact % + top countries]. [The specific risk or upside — name the mechanism, tariff rate, or FX pressure].
Para 2: [Context: how does this compare to a peer company, or what does this % mean in dollar terms for EPS]. [Name the specific quarter/event when this risk crystallises].
Para 3: [Forward look — which sector or analyst call is this data challenging]. [ONE engagement question at the very end]. [1 emoji] [URL] [2-3 SPECIFIC hashtags]
Target: 100-150 words. Statements + one question at the end only.
EXAMPLE: "NVDA earns 52% of revenue from Asia-Pacific — Taiwan 19%, China 17%. US semiconductor export controls put a direct line through those numbers.

AMD, by comparison, earns 25% from Asia-Pacific. The geographic concentration difference between these two makes them very different bets on the same AI trade.

Do you think NVDA's China exposure is already priced in, or is the market underestimating the risk? 🔬 {page_url} #{ticker} #Semiconductors #ChipWar"

━━━ INSTAGRAM ━━━
Line 1 (before fold): "[Ticker] earns [X]% from [country/region]." — statement, number, no emojis on line 1
Body: 4-5 lines. Revenue % by country, the macro risk, EPS/margin implication, what to watch.
Second-to-last body line: "Save this before earnings season 📌"
URL: "Full breakdown: {page_url}"
Hashtags (LAST — 9-12 total, MIX SIZES for reach):
- 2-3 NICHE under 100K posts: e.g. #{ticker}Stock #ChinaRevenueRisk #TaiwanSemiconductors
- 5-6 MEDIUM 100K–500K posts: e.g. #{ticker} #Semiconductors #AIStocks #TechStocks #ChinaTrade
- 1-2 BRAND — always include: #MetricsHour #FinancialData
BANNED: #investing #finance #stocks #markets #money

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "instagram": "..."}}"""
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
    }


def _hook_trade_insight(db) -> dict | None:
    """Pick a notable G20 bilateral trade pair and generate insight post."""
    from app.models.country import TradePair
    rows = db.execute(
        select(TradePair)
        .where(TradePair.trade_value_usd.isnot(None))
        .order_by(TradePair.trade_value_usd.desc())
        .limit(60)
    ).scalars().all()
    if not rows:
        return None

    # Skip the top 3 mega-corridors (always US-CN, US-EU, CN-JP) — pick from index 3-35 for variety
    pool = rows[3:35] if len(rows) > 8 else rows

    # Exclude last 2 trade pairs used to avoid daily repeats
    try:
        recent_trades = db.execute(text(
            "SELECT entity FROM content_log WHERE content_type='post' "
            "AND slot_name='trade_insight' AND created_at >= NOW() - INTERVAL '14 days'"
        )).scalars().all()
        recent_pairs = set(r.upper() for r in recent_trades)
    except Exception:
        recent_pairs = set()

    pair = random.choice(pool)
    if recent_pairs:
        # Try to find a non-recently-used pair (need exp/imp names to check)
        exp_tmp = db.execute(select(Country).where(Country.id == pair.exporter_id)).scalar_one_or_none()
        imp_tmp = db.execute(select(Country).where(Country.id == pair.importer_id)).scalar_one_or_none()
        if exp_tmp and imp_tmp and f"{exp_tmp.name}–{imp_tmp.name}".upper() in recent_pairs:
            remaining = [r for r in pool if r.id != pair.id]
            if remaining:
                pair = random.choice(remaining[:10])
    exp = db.execute(select(Country).where(Country.id == pair.exporter_id)).scalar_one_or_none()
    imp = db.execute(select(Country).where(Country.id == pair.importer_id)).scalar_one_or_none()
    if not exp or not imp:
        return None

    val = pair.trade_value_usd
    val_str = f"${val / 1e9:.0f}B" if val >= 1e9 else f"${val / 1e6:.0f}M"
    products = ", ".join(p["name"] for p in (pair.top_export_products or [])[:3]) or ""
    page_url = f"{SITE_URL}/trade/{exp.code.lower()}-{imp.code.lower()}"
    og_image_url = f"{CDN_URL}/og/trade/{exp.code.lower()}-{imp.code.lower()}.png"

    news = _fetch_news_context(f"{exp.name} {imp.name} trade tariffs sanctions")
    news_block = f"\nRecent headlines:\n{news}" if news else ""
    products_line = f"\nTop traded goods: {products}" if products else ""

    prompt = f"""You are a financial data journalist writing social copy for MetricsHour.
{AUDIENCE_PERSONA}

VERIFIED DATA (use exact numbers):
Trade corridor: {exp.name} → {imp.name}
Annual trade value: {val_str} ({pair.year} data){products_line}
Page URL: {page_url}{news_block}

YOUR TASK: 4 platform posts that treat this trade corridor as a live geopolitical/market story — not a description.
Frame it as: what's at stake, what could disrupt it, which stocks/sectors get hit first.

━━━ TWITTER ━━━
Max 250 chars for body text. Then add 1-2 SPECIFIC hashtags + URL + max 2 emojis (total tweet ~280 chars).
RULES:
- Start with: "{exp.name}→{imp.name}: {val_str}/yr ({pair.year} data)" — numbers first
- Name the specific goods being traded
- Name the specific risk: tariff %, sanctions regime, FX pressure, or supply chain dependency
- Name one specific stock or sector that is most exposed
- End with URL + 1-2 specific hashtags + max 2 emojis
BANNED: questions, generic hashtags, opening emojis
EXAMPLE: "South Korea→China: $180B/yr (2023) — mostly semiconductors and petrochemicals. Export controls on advanced chips put 30% of Korean tech exports at risk. Watch Samsung and SK Hynix margins. {page_url} #SouthKorea #ChipWar 🔬"

━━━ LINKEDIN ━━━
Line 1: {exp.name}→{imp.name}: {val_str}/year ({pair.year} data) — [1-sentence on what makes this corridor strategically important or vulnerable NOW]
[blank line]
[2-3 lines, one observation each, max 20 words]:
- What goods dominate the flow and why they're hard to substitute
- The specific geopolitical/policy risk (name the policy, the tariff rate, or the diplomatic event)
- Which listed companies or sectors get hit first and why
[blank line]
{page_url}
[blank line]
3-5 professional hashtags: SPECIFIC — country names, sector, trade policy. BANNED: #trade #investing #finance #economy
EXAMPLE: #SouthKorea #China #Semiconductors #ExportControls #TradePolicy
No emojis. No sign-off. Body under 90 words (hashtags not counted).

━━━ FACEBOOK ━━━
2-3 short paragraphs. Pattern:
Para 1: [Dollar value + exporter + importer + data year + top goods — punchy, specific]. [The one specific risk investors are underpricing — name the mechanism, tariff rate, or policy].
Para 2: [Context: what happened to this corridor under a previous trade tension episode, OR who the exposed listed companies are and why]. [Specific dollar or % figure to make it concrete].
Para 3: [Forward look — what event or policy decision will determine if this corridor shrinks or grows]. [ONE engagement question at the end]. [1 emoji] [URL] [2-3 SPECIFIC hashtags]
Target: 100-150 words. Statements + one question at the end only.
EXAMPLE: "South Korea ships $180B to China every year (2023 data) — mostly chips and chemicals. Export control escalation puts a third of that corridor at risk — Samsung and SK Hynix earn combined $40B from Chinese customers.

During the 2019 trade war, Korean chip exports to China dropped 18% in 6 months. That playbook is in motion again with the latest controls on HBM chips.

Do you think semiconductor export controls will hurt Korean stocks more than US ones? 🔬 {page_url} #SouthKorea #Semiconductors #ExportControls"

━━━ INSTAGRAM ━━━
Line 1 (before fold): "{exp.name}→{imp.name}: {val_str}/year." — fact statement, no emojis on line 1
Body: 4-5 lines covering: what's traded, why this corridor exists, the key risk, which companies are exposed.
Second-to-last body line: "Save this for your macro watchlist 📌"
URL: "Full data: {page_url}"
Hashtags (LAST — 9-12 total, MIX SIZES for reach):
- 2-3 NICHE under 100K posts: e.g. #KoreaChina #SemiconductorTrade #BilateralTrade
- 5-6 MEDIUM 100K–500K posts: e.g. #SouthKorea #China #Semiconductors #ExportControls #ChipWar
- 1-2 BRAND — always include: #MetricsHour #FinancialData
BANNED: #trade #investing #finance #economy #money

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "instagram": "..."}}"""
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
                  AND p.open > 0
                  AND p.timestamp >= NOW() - INTERVAL '36 hours'
                ORDER BY a.id, p.timestamp DESC
            ) latest
            WHERE change_pct IS NOT NULL
            ORDER BY ABS(change_pct) DESC
            LIMIT 5
        """)).fetchall()
    except Exception as e:
        log.warning("market movers query failed: %s", e)
        return None

    if not rows:
        return None

    # Sort by absolute change to identify the outlier
    def _safe_chg(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    rows = [r for r in rows if _safe_chg(r.change_pct) is not None]
    if not rows:
        return None
    by_abs = sorted(rows, key=lambda r: abs(_safe_chg(r.change_pct)), reverse=True)
    top_mover = by_abs[0]

    movers_str = "\n".join(
        f"{r.symbol} ({r.name}): {float(r.change_pct):+.2f}% | price: {r.close}"
        for r in by_abs
    )
    og_image_url = f"{CDN_URL}/og/section/markets.png"

    # Fetch news for the top 2 movers specifically — gives AI context for WHY they moved
    news_items = []
    for r in by_abs[:2]:
        n = _fetch_news_context(f"{r.name} {r.symbol} stock earnings")
        if n:
            news_items.append(f"{r.symbol} news:\n{n}")
    news_block = "\n\n".join(news_items) if news_items else ""
    news_section = f"\nRecent news context:\n{news_block}" if news_block else ""

    _MARKET_ANGLES = [
        # 0 — outlier deep-dive
        "Focus on the OUTLIER — the single move that breaks the pattern. Name exactly WHY it happened (earnings beat/miss, upgrade/downgrade, macro catalyst, supply chain event). Everything else is context for the outlier.",
        # 1 — sector rotation
        "Frame this as a SECTOR ROTATION story. Which sectors gained, which lost? Is capital moving from growth→value, tech→commodities, US→EM? Name the rotation and what macro signal is driving it.",
        # 2 — macro correlation
        "Connect these moves to the MACRO BACKDROP. Which Fed/inflation/geopolitical event is the real driver today? Find the move that contradicts the macro narrative — that contradiction is your lead.",
        # 3 — the disconnect
        "Find the DISCONNECT: the stock that moved when it shouldn't have, or the one that didn't move when it should have. That gap between price action and fundamentals is the most actionable signal. Lead with it.",
    ]
    angle_instruction = _MARKET_ANGLES[date.today().timetuple().tm_yday % 4]

    prompt = f"""You are a financial data journalist writing social copy for MetricsHour.
{AUDIENCE_PERSONA}

VERIFIED DATA — today's biggest price movers:
{movers_str}{news_section}

YOUR TASK: 4 posts as a market-open hook. {angle_instruction}

━━━ TWITTER ━━━
Max 250 chars for body. Then add 1-2 SPECIFIC hashtags + URL + max 2 emojis (total tweet ~280 chars).
RULES:
- Open with a scoreboard: "📊 [TOP3]: TICKER +X% | TICKER -X% | TICKER ±X%"
- Follow with ONE sentence on the outlier — name the driver (earnings miss, macro catalyst, sector rotation)
- End with URL + 1-2 specific ticker/sector hashtags + max 2 emojis
BANNED: generic hashtags, opening text emojis (scoreboard emoji is ok)
EXAMPLE: "📊 NVDA +4.2% | NKE -3.8% | META +2.1%\nNike is the outlier — China consumer weakness, not macro. Q4 guidance is the real question. {SITE_URL}/markets #NKE #ConsumerStocks"

━━━ LINKEDIN ━━━
Line 1: [Biggest mover] [%] — [1-sentence on what drove it and what it signals]
[blank line]
[2-3 lines]:
- The driver behind the top move (earnings, macro, sector-specific)
- The losing side — what's being rotated out of and why
- What to watch in the next session (name a data release, earnings report, or Fed event)
[blank line]
{SITE_URL}/markets
[blank line]
3-5 professional hashtags: SPECIFIC — ticker names, sector, market type. BANNED: #investing #stocks #markets #finance
EXAMPLE: #NVDA #Semiconductors #NKE #ConsumerStocks #MarketMovers
No emojis. No sign-off. Body under 90 words (hashtags not counted).

━━━ FACEBOOK ━━━
2-3 short paragraphs. Pattern:
Para 1: [Lead with the scoreboard — top mover + % + what drove it — one punchy sentence each for gainer and loser].
Para 2: [Zoom out: is this move idiosyncratic (company-specific) or systemic (sector/macro signal)? Name the evidence — earnings, macro data, options flow, analyst action].
Para 3: [What to watch next — name a specific ticker, earnings date, or data release]. [ONE engagement question]. [1 emoji] [URL] [2-3 SPECIFIC hashtags]
Target: 100-150 words. Statements + one question at the end.
EXAMPLE: "Today's scoreboard: NVDA +4.2%, META +2.1%, NKE -3.8%. NVDA's move is AI memory supply chain — not just hype. Nike's drop is a China consumer story.

These aren't correlated moves — they're two separate theses. NVDA reflects HBM demand from Blackwell. NKE reflects Alibaba GMV data from last week.

Which name do you think is more mispriced heading into next quarter? 📊 {SITE_URL}/markets #NVDA #NKE #Semiconductors"

━━━ INSTAGRAM ━━━
Line 1 (before fold): "Today's top moves: [TOP3 with %]." — no emojis on line 1
Body: full scorecard of all movers with %, then 2-3 lines on drivers and what to watch.
Second-to-last body line: "Save this for your watchlist 📌"
URL: {SITE_URL}/markets
Hashtags (LAST — 9-12 total, MIX SIZES for reach):
- 2-3 NICHE under 100K posts: e.g. specific ticker tags like #NVDAStock #NikeEarnings
- 5-6 MEDIUM 100K–500K posts: e.g. #NVDA #Semiconductors #NKE #AIStocks #StockMarket
- 1-2 BRAND — always include: #MetricsHour #FinancialData
BANNED: #investing #stocks #markets #finance #money

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "instagram": "..."}}"""
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
                  AND p.open > 0
                  AND p.timestamp >= NOW() - INTERVAL '36 hours'
                ORDER BY a.id, p.timestamp DESC
            ) latest
            WHERE change_pct IS NOT NULL
            ORDER BY ABS(change_pct) DESC
            LIMIT 5
        """)).fetchall()
    except Exception as e:
        log.warning("day wrap query failed: %s", e)
        return None

    if not rows:
        return None

    # Find biggest gainer and loser
    rows = [r for r in rows if r.change_pct is not None]
    if not rows:
        return None
    by_change = sorted(rows, key=lambda r: float(r.change_pct), reverse=True)
    gainer = by_change[0]
    loser = by_change[-1]
    movers_str = "\n".join(
        f"{r.symbol} | {r.name} | {r.close} | {float(r.change_pct):+.2f}%"
        for r in rows
    )
    og_image_url = f"{CDN_URL}/og/section/markets.png"

    # Per-mover news for context
    news_items = []
    for r in [gainer, loser]:
        n = _fetch_news_context(f"{r.name} {r.symbol} stock")
        if n:
            news_items.append(f"{r.symbol} news:\n{n}")
    news_section = f"\nRecent news:\n" + "\n\n".join(news_items) if news_items else ""

    _WRAP_ANGLES = [
        # 0 — tomorrow's setup
        "Frame this entirely as a SETUP FOR TOMORROW. What does today's action mean for tomorrow's open? Name a specific earnings release, data print, Fed speaker, or options expiry that makes today's close directionally important.",
        # 1 — idiosyncratic vs systemic
        "Your one job: tell readers whether today's moves are IDIOSYNCRATIC (company-specific, ignore the sector) or SYSTEMIC (sector/macro, everything in the group is affected). Commit to the call. Name which it is and why it changes how to trade tomorrow.",
        # 2 — surprising divergence
        "Find the most SURPRISING DIVERGENCE in today's data — two assets that should have moved together but didn't, or one that moved opposite to its usual correlation. That divergence is your lead.",
        # 3 — contrarian read
        "Give the CONTRARIAN READ on today's session. What is the consensus interpretation, and what does the data actually say? Name a specific ticker or sector the market is mispricing based on today's action.",
    ]
    # Offset by 2 from market_movers so they never use the same angle on the same day
    wrap_angle = _WRAP_ANGLES[(date.today().timetuple().tm_yday + 2) % 4]

    prompt = f"""You are a financial data journalist writing end-of-day social copy for MetricsHour.
{AUDIENCE_PERSONA}

VERIFIED DATA — today's closing moves:
{movers_str}

Biggest gainer: {gainer.symbol} ({gainer.name}) {float(gainer.change_pct):+.2f}%
Biggest loser: {loser.symbol} ({loser.name}) {float(loser.change_pct):+.2f}%{news_section}

YOUR TASK: 4 end-of-day wrap posts. {wrap_angle}

━━━ TWITTER ━━━
Max 250 chars for body. Then add 1-2 SPECIFIC hashtags + URL + max 2 emojis (total tweet ~280 chars).
RULES:
- Start with: "Close: [GAINER] [%] ↑ | [LOSER] [%] ↓"
- One sentence on the more SURPRISING of the two moves — name the driver
- One sentence on what this sets up for tomorrow (earnings, data release, or sector watch)
- End with URL + 1-2 specific hashtags + max 2 emojis
BANNED: generic hashtags, opening non-scoreboard emojis
EXAMPLE: "Close: NVDA +4.2% ↑ | NKE -3.8% ↓\nNike's drop is a China consumer story, not tariffs — sector-specific signal. Watch adidas tomorrow for confirmation. {SITE_URL}/markets #NKE #ConsumerStocks 📉"

━━━ LINKEDIN ━━━
Line 1: [Gainer] +X% vs [Loser] -X% — [1-sentence on what the divergence signals about sector rotation or macro]
[blank line]
[2-3 lines]:
- What drove the gainer: earnings, upgrade, macro tailwind — be specific
- What drove the loser: and whether it's idiosyncratic or a sector signal
- What to watch tomorrow: name a specific ticker, data release, or Fed event
[blank line]
{SITE_URL}/markets
[blank line]
3-5 professional hashtags: SPECIFIC — ticker names, sector, market type. BANNED: #stocks #investing #markets #finance
No emojis. No sign-off. Body under 90 words (hashtags not counted).

━━━ FACEBOOK ━━━
2-3 short paragraphs. Pattern:
Para 1: [Gainer ticker + % + what drove it in one punchy sentence]. [Loser ticker + % + whether it's idiosyncratic or a sector signal].
Para 2: [Zoom out — what does this divergence tell us? Is it a rotation story, a macro story, or company-specific? Name a comparable or historical parallel to make it concrete].
Para 3: [What to watch tomorrow — specific ticker, earnings, or data print]. [ONE engagement question]. [1 emoji] [URL] [2-3 SPECIFIC hashtags]
Target: 100-150 words. Statements + one question at the end.

━━━ INSTAGRAM ━━━
Line 1 (before fold): "Today's close: [GAINER] +X% vs [LOSER] -X%." — no emojis on line 1
Body: 4-5 lines — what drove each move, what it signals for tomorrow, what to watch.
Second-to-last body line: "Save this for tomorrow's open 📌"
URL: {SITE_URL}/markets
Hashtags (LAST — 9-12 total, MIX SIZES for reach):
- 2-3 NICHE under 100K posts: e.g. specific ticker tags like #NVDAStock #NikeEarnings
- 5-6 MEDIUM 100K–500K posts: e.g. #NVDA #NKE #Semiconductors #ConsumerStocks #StockMarket
- 1-2 BRAND — always include: #MetricsHour #FinancialData
BANNED: #stocks #investing #markets #finance #money

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "instagram": "..."}}"""
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
        hook_angle = (
            f"At {float(row.value):.1f}% inflation the counterintuitive angle is: "
            "what is the REAL yield on local bonds, what does the central bank actually have room to do, "
            "and how does this affect the currency vs USD — not just 'inflation is bad'"
        )

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
        hook_angle = (
            f"Debt at {float(row.value):.0f}% of GDP — the counterintuitive angle: "
            "sovereign default risk isn't about the level, it's about who holds the debt and whether the yield spread vs Treasuries "
            "is widening or compressing. Compare to Japan at 255% — still no default risk."
        )

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
        hook_angle = (
            f"At {val_str}/year this corridor represents a real bilateral dependency — "
            "the angle: what happens to this flow under tariff escalation, which goods are hardest to substitute, "
            "and which listed companies (name specific tickers) lose revenue first"
        )

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
        hook_angle = (
            f"At {intl_pct:.0f}% international revenue, {name} ({ticker})'s US listing masks a predominantly non-US earnings stream. "
            "The angle: retail investors price it as a US stock but its EPS is driven by FX rates, foreign consumer demand, "
            "and tariff policy — exposure most holders have never modelled"
        )

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

    news = _fetch_news_context(f"{entity} economy finance")
    news_block = f"\nRecent headlines:\n{news}" if news else ""

    _VIRAL_ANGLES = [
        # 0 — stat + broken assumption
        "State the number, then BREAK the obvious assumption most people make about it. The assumption is wrong — explain exactly why with a second specific number or comparison.",
        # 1 — historical context
        "State the number, then place it in HISTORICAL CONTEXT. When was this last seen? What happened to prices/rates/currencies the last time this level was reached? That history IS the investment signal.",
        # 2 — who gets hurt / who wins
        "State the number, then immediately answer: WHO GETS HURT and WHO WINS? Name specific asset classes, sectors, or tickers on each side. No generalities — name the mechanism.",
        # 3 — what the market is missing
        "State the number, then make the case that THE MARKET IS MISPRICING IT. What does consensus think? What does this data actually imply? Name the specific asset that is wrong.",
    ]
    viral_angle = _VIRAL_ANGLES[date.today().timetuple().tm_yday % 4]

    prompt = f"""You are a financial data journalist writing viral "shocking stat" social copy for MetricsHour.
{AUDIENCE_PERSONA}

VERIFIED DATA:
{data_context}
Counterintuitive angle: {hook_angle}{news_block}
Page URL: {page_url}

YOUR TASK: 4 posts that drop a number so specific and surprising that the reader pauses mid-scroll. {viral_angle}

━━━ TWITTER ━━━
Max 260 chars. RULES:
- Open with the raw shocking stat — no "Did you know", no question, no emoji first
- Second sentence: the implication that most people get wrong or don't know
- End with URL + max 2 emojis after text
EXAMPLES:
"US government debt: 118% of GDP. Japan: 255%. Neither is defaulting. Sovereign debt math is different from household debt — the key variable is who holds it. {page_url} 📊"
"Turkey's inflation hit 58.5% last year. The central bank responded by raising rates to 45% — still a -13.5% real yield. TRY holders are losing money in real terms every month. {page_url} 📉"

━━━ LINKEDIN ━━━
Line 1: [The shocking stat as a clean statement — number + context, no fluff]
[blank line]
[2-3 observations, one per line, max 20 words each]:
- Historical context: when was this last seen, or how does it compare to a benchmark/peer
- The mechanism: what policy or market force is this connected to
- The investment signal: which asset, rate, or currency is directly affected
[blank line]
{page_url}
No emojis. No hashtags. No sign-off. Under 90 words.

━━━ FACEBOOK ━━━
One paragraph. Lead with the raw number. One sentence on why it's surprising. One sentence on the implication. 1 emoji. URL. Max 55 words. Statements only — no questions.

━━━ INSTAGRAM ━━━
Line 1 (before fold): State the shocking number as a clean fact — no question, no "Did you know", no emojis on line 1
EXAMPLE first line: "Turkey's inflation hit 58.5% last year."
Body: 4-5 lines — historical comparison, mechanism, what it means for an investor holding EM assets, what to watch next.
Second-to-last body line: "Save this for tomorrow's open 📌"
URL: {page_url}
Hashtags (LAST — 9-12 total, MIX SIZES for reach):
- 2-3 NICHE under 100K posts: e.g. specific country/indicator tags like #TurkeyInflation #EMDebt
- 5-6 MEDIUM 100K–500K posts: e.g. #EmergingMarkets #Inflation #MacroEconomics #GlobalDebt
- 1-2 BRAND — always include: #MetricsHour #FinancialData
BANNED: #stocks #investing #markets #finance #money #economy

Return ONLY valid JSON: {{"twitter": "...", "linkedin": "...", "facebook": "...", "instagram": "..."}}"""
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
    }


def _log_content(content_type: str, slot_name: str, entity: str, style: str,
                  caption: str, twitter_copy: str, platform_copies: dict, source: str = "celery") -> None:
    """Write a row to content_log so Moltis can query real history."""
    try:
        from app.database import SessionLocal as _SL
        import json as _json
        db = _SL()
        db.execute(
            text(
                "INSERT INTO content_log (content_type, slot_name, entity, style, caption, twitter_copy, platform_copies, source) "
                "VALUES (:ct, :sn, :en, :st, :ca, :tw, :pc, :src)"
            ),
            {
                "ct": content_type, "sn": slot_name, "en": entity, "st": style,
                "ca": caption, "tw": twitter_copy,
                "pc": _json.dumps(platform_copies), "src": source,
            },
        )
        db.commit()
        db.close()
    except Exception as e:
        log.warning("content_log write failed: %s", e)


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
        _log_content(
            content_type="post",
            slot_name=draft.get("type", "post"),
            entity=entity,
            style=draft.get("hook_type", ""),
            caption=f"{label} {value}".strip(),
            twitter_copy=draft.get("twitter", ""),
            platform_copies={
                "twitter": draft.get("twitter", ""),
                "linkedin": draft.get("linkedin", ""),
                "facebook": draft.get("facebook", ""),
                "instagram": draft.get("instagram", ""),
            },
        )
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


def _pick_crypto_reel_subject() -> tuple[str, str]:
    """Pick the biggest crypto mover in last 24h. Returns (symbol_lower, hook_text)."""
    CRYPTO_SYMBOLS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOGE", "DOT", "MATIC"]
    try:
        db = SessionLocal()
        try:
            rows = db.execute(text("""
                SELECT DISTINCT ON (a.symbol) a.symbol, a.name,
                       ROUND(CAST((p.close - p.open) / NULLIF(p.open, 0) * 100 AS numeric), 2) AS chg_pct,
                       p.close
                FROM prices p JOIN assets a ON a.id = p.asset_id
                WHERE a.asset_type = 'crypto'
                  AND p.interval = '1d' AND p.open IS NOT NULL
                  AND p.timestamp >= NOW() - INTERVAL '36 hours'
                  AND a.symbol = ANY(:symbols)
                ORDER BY a.symbol, p.timestamp DESC
            """), {"symbols": CRYPTO_SYMBOLS}).fetchall()
        finally:
            db.close()
        if rows:
            top = sorted(rows, key=lambda r: abs(float(r.chg_pct)), reverse=True)[0]
            sym = top.symbol.lower()
            direction = "up" if float(top.chg_pct) >= 0 else "down"
            hook = (
                f"{top.symbol} {direction} {abs(float(top.chg_pct)):.1f}% to "
                f"${float(top.close):,.0f} — what macro catalyst drove this, whether momentum holds or reverses, "
                f"and what it signals for the broader crypto market tonight"
            )
            return sym, hook
    except Exception as e:
        log.warning("_pick_crypto_reel_subject failed: %s", e)
    return "bitcoin", "Today's crypto wrap: biggest moves of the day"


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
                    "[SYSTEM AUTOMATION "
                    + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                    + "] NO TEXT RESPONSE. CALL TOOL NOW: mcp__metricshour__smart_reel"
                    f" style={style} subject={subject} hook={hook}"
                    " — zero text before tool call, rules forbid it."
                ),
        },
    }
    trigger_time = datetime.now(timezone.utc)
    try:
        r = requests.post(
            TG_BRIDGE_URL,
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": TELEGRAM_WEBHOOK_SECRET},
            timeout=10,
        )
        log.info("Reel trigger (%s/%s) → tg-bridge: HTTP %s", style, subject, r.status_code)
        success = r.status_code < 400
        if success:
            _log_content(
                content_type="reel",
                slot_name=f"reel_{style}",
                entity=subject,
                style=style,
                caption=hook,
                twitter_copy="",
                platform_copies={},
            )
            # Queue a deferred check — Moltis writes source='moltis' to content_log on completion
            verify_reel_completion.apply_async(
                args=[style, subject, trigger_time.isoformat()],
                countdown=360,  # check 6 min after trigger
            )
        return success
    except Exception as e:
        log.warning("Reel trigger failed (%s/%s): %s", style, subject, e)
        return False


@app.task(name='tasks.social_content.verify_reel_completion')
def verify_reel_completion(style: str, subject: str, trigger_time_iso: str) -> str:
    """Confirm Moltis actually generated the reel. Sends alert if missing.
    Runs 6 min after each reel trigger. Checks content_log for source='moltis' entry.
    """
    try:
        trigger_dt = datetime.fromisoformat(trigger_time_iso)
        db = SessionLocal()
        try:
            row = db.execute(text("""
                SELECT id FROM content_log
                WHERE slot_name = :slot
                  AND source = 'moltis'
                  AND created_at >= :since
                LIMIT 1
            """), {
                "slot": f"reel_{style}",
                "since": trigger_dt,
            }).fetchone()
        finally:
            db.close()

        if row:
            log.info("Reel confirmed: %s/%s (content_log id=%s)", style, subject, row.id)
            return f"confirmed: reel_{style}/{subject}"

        # Not found — Moltis failed or tg-bridge didn't forward
        log.error("Reel NOT confirmed: %s/%s — no moltis entry in content_log since %s", style, subject, trigger_time_iso)
        _send_failure_alert(
            f"REEL MISSING: {style}/{subject}",
            f"Triggered at {trigger_time_iso[:16]} UTC but Moltis never wrote to content_log.\n"
            f"Check: tg-bridge running? Moltis responding? ssh root@10.0.0.3 journalctl -u moltis -n 30",
        )
        return f"alert_sent: reel_{style}/{subject} not confirmed"
    except Exception as e:
        log.warning("verify_reel_completion failed: %s", e)
        return f"verify_error: {e}"


@app.task(name='tasks.social_content.generate_social_drafts', bind=True, max_retries=2)
def generate_social_drafts(self):
    """Generate 1 rotating social post draft and send to Telegram. Runs daily at 9am UTC.
    Rotates daily: country spotlight → stock exposure → trade insight → repeat.
    Keeps morning total at 2 posts (market_open at 8am + this at 9am) + 1 reel (8:30am).
    """
    if not _acquire_slot_lock("social_drafts"):
        return "skipped: already completed today"
    db = SessionLocal()
    try:
        # Rotate hook type by day-of-year: country → stock → trade → viral_stat → repeat
        from datetime import date
        day_index = date.today().timetuple().tm_yday % 4
        hook_fns = [_hook_country_spotlight, _hook_stock_exposure, _hook_trade_insight, _hook_viral_stat]
        # Try primary hook first, fall back to next ones if data unavailable
        draft = None
        for i in range(4):
            fn = hook_fns[(day_index + i) % 4]
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
    if not _acquire_slot_lock("market_open"):
        return "skipped: already completed today"
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
    if not _acquire_slot_lock("evening_wrap"):
        return "skipped: already completed today"
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
    """Generate evening post. Rotates daily: viral_stat → country_spotlight → viral_stat → trade_insight."""
    if not _acquire_slot_lock("viral_hook"):
        return "skipped: already completed today"
    db = SessionLocal()
    try:
        # Rotate so the 18:00 slot isn't always a viral stat
        _evening_fns = [_hook_viral_stat, _hook_country_spotlight, _hook_viral_stat, _hook_trade_insight]
        evening_fn = _evening_fns[date.today().timetuple().tm_yday % 4]
        draft = evening_fn(db)
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
    """Generate morning market reel via Moltis at 8:30 UTC. Hook is data-driven."""
    if not _acquire_slot_lock("morning_reel"):
        return "skipped: already completed today"
    hook = "Markets open: here are today's biggest movers"
    try:
        db = SessionLocal()
        try:
            row = db.execute(text("""
                SELECT DISTINCT ON (a.id) a.symbol, a.name,
                       ROUND(CAST((p.close - p.open) / NULLIF(p.open, 0) * 100 AS numeric), 1) AS chg
                FROM prices p JOIN assets a ON a.id = p.asset_id
                WHERE p.interval = '1d' AND p.open IS NOT NULL
                  AND p.timestamp >= NOW() - INTERVAL '36 hours'
                ORDER BY a.id, p.timestamp DESC
            """)).fetchall()
            if row:
                top = sorted([r for r in row if r.chg is not None], key=lambda r: abs(float(r.chg)), reverse=True)[:3]
                if top:
                    outlier = top[0]
                    move = "surges" if float(outlier.chg) > 0 else "drops"
                    def _mv_label(sym: str, name: str) -> str:
                        # For 2-char commodity codes (CT, KC) or long obscure tickers (SSNLF), use name
                        if len(sym) <= 2 or len(sym) >= 5:
                            return (name or sym).split()[0]
                        return sym
                    outlier_label = _mv_label(outlier.symbol, outlier.name or "")
                    others = " | ".join(
                        f"{_mv_label(r.symbol, r.name or '')} {float(r.chg):+.1f}%" for r in top[1:3]
                    )
                    hook = (
                        f"{outlier_label} {move} {abs(float(outlier.chg)):.1f}% — "
                        f"what drove it and what it signals for the session: {others}"
                    ) if others else f"{outlier_label} {move} {abs(float(outlier.chg)):.1f}% — the macro story behind today's biggest market move"
        except Exception:
            pass
        finally:
            db.close()
    except Exception:
        pass
    try:
        ok = _trigger_reel_via_moltis("market_recap", "markets", hook)
        if not ok:
            raise RuntimeError("tg-bridge rejected or unreachable")
        return f"reel triggered: {hook}"
    except self.MaxRetriesExceededError:
        _send_failure_alert("REEL 1 (08:30 market_recap)", "tg-bridge unreachable after 3 attempts — is it running on Contabo?")
        return "error: max retries exceeded"
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


def _make_country_reel_hook(name: str, ind_key: str, val_float: float, label: str, val_str: str, prev_val: float | None = None) -> str:
    """Generate a specific, contextual hook for a country deep-dive reel.
    Never repeats the country name. Always includes a concrete angle tied to the actual value level."""
    direction = ""
    if prev_val is not None:
        if val_float > prev_val:
            direction = " (rising)"
        elif val_float < prev_val:
            direction = " (falling)"

    if ind_key == "gdp_growth_pct":
        if val_float < -2.0:
            return f"{name} GDP: {val_str}{direction} — deep recession territory. Which sectors are contracting, what the central bank can actually do, and whether the bond market has priced this in yet"
        elif val_float < 0:
            return f"{name} GDP contracted to {val_str} — technically in recession. Currency is first to reprice; the equity market hasn't caught up yet"
        elif val_float < 1.0:
            return f"{name} growing at just {val_str}{direction} — near-stagnation with rates still restrictive. Fiscal space is limited and something has to give"
        elif val_float < 3.0:
            return f"{name} GDP at {val_str}{direction} — which sectors are carrying this and which are quietly rolling over. Not all growth signals the same thing"
        else:
            return f"{name} growing at {val_str}{direction} — outpacing its peers. What's driving it, whether it sustains, and what the currency is pricing in"

    elif ind_key == "inflation_pct":
        if val_float > 1000:
            return f"{name}: {val_str} inflation — hyperinflation. Dollarisation logic, who holds local bonds, and why the central bank rate is functionally meaningless"
        elif val_float > 50:
            return f"{name}: {val_str} inflation — well past the threshold of CB credibility. Real yield is deeply negative and the currency tells the real story"
        elif val_float > 20:
            return f"{name} inflation at {val_str}{direction} — above the level that forces aggressive rate policy. What the real yield spread says about the exchange rate"
        elif val_float > 10:
            return f"{name}: {val_str} inflation{direction} — still above the level where central banks feel safe cutting. Rates, real yield, and the currency trade"
        elif val_float < 0:
            return f"{name} in deflation at {val_str} — rare and harder to exit than inflation. What falling prices mean for debt dynamics and central bank credibility"
        else:
            return f"{name} inflation at {val_str}{direction} — rate path from here determines the currency trade and equity risk premium"

    elif ind_key == "government_debt_gdp_pct":
        if val_float > 200:
            return f"{name}: {val_str} debt-to-GDP{direction} — deeper than Japan. Who holds it, the yield spread vs Treasuries, and why markets still aren't pricing in default risk"
        elif val_float > 100:
            return f"{name}: {val_str} debt-to-GDP{direction}. At current rates, the carry cost versus growth determines when this becomes a crisis — here's the math"
        else:
            return f"{name} debt at {val_str} of GDP{direction} — rising fast. Who funds it and where the bond market draws the line on fiscal credibility"

    elif ind_key == "unemployment_pct":
        if val_float > 15:
            return f"{name} unemployment at {val_str}{direction} — structural, not cyclical. Skills mismatch, youth unemployment, and why rate cuts alone won't fix this"
        elif val_float > 10:
            return f"{name}: {val_str} unemployment{direction} — above the level that forces fiscal response. What the government and central bank are actually doing"
        else:
            return f"{name} unemployment at {val_str}{direction} — tight labor market. Wage pressure, core inflation risk, and what it means for the next rate decision"

    elif ind_key == "current_account_gdp_pct":
        if val_float < -5:
            return f"{name} running a {val_str} current account deficit{direction} — dependent on foreign capital. Who funds it, the currency vulnerability, and how long this can last"
        elif val_float > 5:
            return f"{name}'s {val_str} current account surplus{direction} — who absorbs it. Currency appreciation pressure and what the central bank is doing to resist"
        else:
            return f"{name} current account at {val_str}{direction} — direct FX implications that are underpriced in the options market"

    elif ind_key == "budget_balance_gdp_pct":
        if val_float < -8:
            return f"{name} running a {val_str} budget deficit{direction} — fiscal crisis territory. Bond market stress, rating risk, and what's driving the overshoot"
        elif val_float < -4:
            return f"{name}: {val_str} budget deficit{direction} — unsustainable without higher growth or austerity. What the bond term premium is pricing in"
        else:
            return f"{name} budget balance at {val_str}{direction} — the fiscal trajectory from here determines the rate and currency outlook for the next 12 months"

    elif ind_key == "fdi_inflows_gdp_pct":
        if val_float > 5:
            return f"{name} attracting {val_str} of GDP in FDI{direction} — capital is voting with its feet. Which sectors, which source countries, and what it signals for growth"
        elif val_float < 0:
            return f"{name} FDI turned negative at {val_str} — capital flight. What's driving the exodus and which assets are most exposed"
        else:
            return f"{name} FDI at {val_str} of GDP{direction} — where global capital is betting on future growth"

    elif ind_key == "foreign_reserves_usd":
        return f"{name} foreign reserves: {val_str}{direction} — the buffer between here and a currency crisis. Import cover ratio, short-term debt, and where the risk threshold is"

    # Generic fallback
    return f"{name}: {val_str} {label}{direction} — the rate path, currency risk, and which investors are most exposed to this shift"


def _pick_reel_subject_morning(db) -> tuple:
    """Pick a data-driven subject for the 9:30 morning reel.
    Rotates style daily; subject is pulled from live DB data — not hardcoded.
    """
    day_index = date.today().timetuple().tm_yday % 3
    if day_index == 0:
        # country_deep_dive — pick G20 country with biggest recent indicator change
        best = _pick_best_country_indicator(db)
        if best:
            code, ind_key, label, unit = best[:4]
            country = db.execute(select(Country).where(Country.code == code)).scalar_one_or_none()
            name = country.name if country else code
            # Get current + previous value for context-aware hook
            val_rows = db.execute(text(
                "SELECT ci.value, ci.period_date FROM country_indicators ci "
                "JOIN countries c ON c.id = ci.country_id "
                "WHERE c.code = :code AND ci.indicator = :ind ORDER BY ci.period_date DESC LIMIT 2"
            ), {"code": code, "ind": ind_key}).fetchall()
            if val_rows:
                val_float = float(val_rows[0].value)
                val_str = _fmt_value(val_float, unit)
                prev_val = float(val_rows[1].value) if len(val_rows) > 1 else None
                return ("country_deep_dive", code,
                    _make_country_reel_hook(name, ind_key, val_float, label, val_str, prev_val))
            return ("country_deep_dive", code,
                f"{name}: {label} — the data-driven macro read and which assets are most exposed")
        return ("country_deep_dive", "DE",
            "Germany: two consecutive quarters of GDP contraction, ECB rate-cut pace is the only lever — what this means for EUR and European equities")
    elif day_index == 1:
        # stock_analysis — pick top moved stock with international exposure
        try:
            row = db.execute(text("""
                SELECT DISTINCT ON (a.id) a.symbol, a.name,
                       ABS((p.close - p.open) / NULLIF(p.open, 0) * 100) AS abs_pct
                FROM prices p
                JOIN assets a ON a.id = p.asset_id
                JOIN stock_country_revenues scr ON scr.asset_id = a.id
                JOIN countries c ON c.id = scr.country_id AND c.code != 'US'
                WHERE p.interval = '1d' AND p.open IS NOT NULL
                  AND p.timestamp >= NOW() - INTERVAL '7 days'
                  AND a.asset_type = 'stock'
                GROUP BY a.id, a.symbol, a.name, p.close, p.open, p.timestamp
                HAVING SUM(scr.revenue_pct) BETWEEN 20 AND 100
                ORDER BY a.id, p.timestamp DESC
            """)).fetchall()
            if row:
                pick = sorted(row, key=lambda r: float(r.abs_pct), reverse=True)[0]
                return ("stock_analysis", pick.symbol,
                    f"{pick.symbol} moved {float(pick.abs_pct):.1f}% — international revenue breakdown: where EPS actually comes from, which geographies are at risk from tariffs or FX, and what Wall Street is likely mispricing")
        except Exception:
            pass
        return ("stock_analysis", "NVDA",
            "NVDA earns 52% outside the US — China 17%, Taiwan 15%. US export controls are a direct line-item EPS risk. Here's what next quarter's guidance is really about")
    else:
        # trade_spotlight — pick top trade pair (skip top 3 mega-corridors)
        try:
            from app.models.country import TradePair as _TP
            pairs = db.execute(
                select(_TP).where(_TP.trade_value_usd.isnot(None))
                .order_by(_TP.trade_value_usd.desc()).limit(20)
            ).scalars().all()
            if len(pairs) > 4:
                pair = random.choice(pairs[3:10])
                exp = db.execute(select(Country).where(Country.id == pair.exporter_id)).scalar_one_or_none()
                imp = db.execute(select(Country).where(Country.id == pair.importer_id)).scalar_one_or_none()
                if exp and imp:
                    val = pair.trade_value_usd
                    val_str = f"${val/1e9:.0f}B" if val >= 1e9 else f"${val/1e6:.0f}M"
                    return ("trade_spotlight", f"{exp.code}-{imp.code}",
                            f"{exp.name}→{imp.name}: {val_str}/year — what goods flow, what geopolitical event could disrupt this corridor, and which listed companies are most exposed")
        except Exception:
            pass
        return ("trade_spotlight", "JP-CN", "Japan–China trade: Asia's most important bilateral corridor")


def _pick_reel_subject_evening(db) -> tuple:
    """Pick a data-driven subject for the 18:30 evening reel."""
    day_index = date.today().timetuple().tm_yday % 3
    if day_index == 0:
        # commodities — pick commodity nearest 52w high or low
        try:
            row = db.execute(text("""
                WITH weekly AS (
                    SELECT DISTINCT ON (a.id) a.id, a.symbol, a.name, p.close
                    FROM prices p JOIN assets a ON a.id = p.asset_id
                    WHERE a.asset_type = 'commodity' AND p.interval = '1d' AND p.open IS NOT NULL
                    ORDER BY a.id, p.timestamp DESC
                ),
                yearly AS (
                    SELECT asset_id, MAX(close) AS high_52w, MIN(close) AS low_52w
                    FROM prices WHERE interval = '1d' AND timestamp >= NOW() - INTERVAL '52 weeks'
                    GROUP BY asset_id
                )
                SELECT w.symbol, w.name,
                       ROUND(CAST((w.close - y.low_52w) / NULLIF(y.high_52w - y.low_52w, 0) * 100 AS numeric), 1) AS pct_of_range
                FROM weekly w JOIN yearly y ON y.asset_id = w.id
                WHERE y.high_52w > y.low_52w
                ORDER BY ABS(50 - ROUND(CAST((w.close - y.low_52w) / NULLIF(y.high_52w - y.low_52w, 0) * 100 AS numeric), 1)) DESC
                LIMIT 1
            """)).fetchone()
            if row:
                extreme = "52-week high" if float(row.pct_of_range) >= 80 else "52-week low"
                pct_of_range = float(row.pct_of_range)
                return ("commodities", row.symbol.lower(),
                        f"{row.name} at {pct_of_range:.0f}% of its 52-week range — near {extreme}. "
                        f"What macro force is driving this, whether the extreme holds or reverses, and which producers/consumers get hit")
        except Exception:
            pass
        return ("commodities", "gold", "Gold, oil and metals: today's commodity extremes")
    elif day_index == 1:
        # trade_spotlight — different pair from morning rotation
        try:
            from app.models.country import TradePair as _TP
            pairs = db.execute(
                select(_TP).where(_TP.trade_value_usd.isnot(None))
                .order_by(_TP.trade_value_usd.desc()).limit(30)
            ).scalars().all()
            if len(pairs) > 8:
                pair = random.choice(pairs[6:15])
                exp = db.execute(select(Country).where(Country.id == pair.exporter_id)).scalar_one_or_none()
                imp = db.execute(select(Country).where(Country.id == pair.importer_id)).scalar_one_or_none()
                if exp and imp:
                    val = pair.trade_value_usd or 0
                    val_str_e = f"${val/1e9:.0f}B" if val >= 1e9 else f"${val/1e6:.0f}M"
                    return ("trade_spotlight", f"{exp.code}-{imp.code}",
                            f"{exp.name}→{imp.name}: {val_str_e}/year — trade tensions, key goods, and the specific stocks and sectors that carry the most exposure to disruption")
        except Exception:
            pass
        return ("trade_spotlight", "DE-CN", "Germany–China trade: Europe's biggest China dependency")
    else:
        # country_deep_dive — pick a different country than morning (offset by 1)
        try:
            rows = db.execute(text("""
                WITH ranked AS (
                    SELECT c.code, c.name, ci.indicator, ci.value,
                           LAG(ci.value) OVER (PARTITION BY c.id, ci.indicator ORDER BY ci.period_date) AS prev_value
                    FROM country_indicators ci JOIN countries c ON c.id = ci.country_id
                    WHERE c.code = ANY(:codes) AND ci.indicator = ANY(:inds)
                      AND ci.period_date >= NOW() - INTERVAL '5 years'
                )
                SELECT code, name, indicator, value, prev_value, ABS(value - prev_value) AS abs_change
                FROM ranked WHERE prev_value IS NOT NULL
                ORDER BY abs_change DESC LIMIT 5
            """), {"codes": G20_CODES, "inds": [i[0] for i in SPOTLIGHT_INDICATORS]}).fetchall()
            if len(rows) >= 2:
                pick = rows[1]  # second biggest — morning got the top
                ev_ind_meta = {k: (l, u) for k, l, u in SPOTLIGHT_INDICATORS}
                ev_label, ev_unit = ev_ind_meta.get(pick.indicator, (pick.indicator, ""))
                ev_val = float(pick.value)
                ev_prev = float(pick.prev_value) if pick.prev_value is not None else None
                ev_val_str = _fmt_value(ev_val, ev_unit)
                return ("country_deep_dive", pick.code,
                        _make_country_reel_hook(pick.name, pick.indicator, ev_val, ev_label, ev_val_str, ev_prev))
        except Exception:
            pass
        return ("country_deep_dive", "IN", "India's economy: the data behind the world's fastest-growing major market")


@app.task(name='tasks.social_content.generate_morning_reel_2', bind=True, max_retries=2)
def generate_morning_reel_2(self):
    """Generate second morning reel via Moltis at 9:30 UTC.
    Rotates style daily; subject pulled from live DB data.
    """
    if not _acquire_slot_lock("morning_reel_2"):
        return "skipped: already completed today"
    db = SessionLocal()
    try:
        style, subject, hook = _pick_reel_subject_morning(db)
    except Exception:
        style, subject, hook = ("stock_analysis", "AAPL", "How global trade shapes this stock's revenue")
    finally:
        db.close()
    try:
        ok = _trigger_reel_via_moltis(style, subject, hook)
        if not ok:
            raise RuntimeError("tg-bridge rejected or unreachable")
        return f"reel triggered: {style}/{subject}"
    except self.MaxRetriesExceededError:
        _send_failure_alert(f"REEL 2 (09:30 {style})", "tg-bridge unreachable after 3 attempts — is it running on Contabo?")
        return "error: max retries exceeded"
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


@app.task(name='tasks.social_content.generate_evening_reel', bind=True, max_retries=2)
def generate_evening_reel(self):
    """Generate evening crypto reel via Moltis at 17:30 UTC. Subject is live biggest mover."""
    if not _acquire_slot_lock("evening_reel"):
        return "skipped: already completed today"
    try:
        subject, hook = _pick_crypto_reel_subject()
        ok = _trigger_reel_via_moltis("crypto_update", subject, hook)
        if not ok:
            raise RuntimeError("tg-bridge rejected or unreachable")
        return f"reel triggered: crypto_update/{subject}"
    except self.MaxRetriesExceededError:
        _send_failure_alert("REEL 3 (17:30 crypto_update)", "tg-bridge unreachable after 3 attempts — is it running on Contabo?")
        return "error: max retries exceeded"
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


@app.task(name='tasks.social_content.generate_evening_reel_2', bind=True, max_retries=2)
def generate_evening_reel_2(self):
    """Generate second evening reel via Moltis at 18:30 UTC.
    Rotates style daily; subject pulled from live DB data.
    """
    if not _acquire_slot_lock("evening_reel_2"):
        return "skipped: already completed today"
    db = SessionLocal()
    try:
        style, subject, hook = _pick_reel_subject_evening(db)
    except Exception:
        style, subject, hook = ("commodities", "gold", "Gold, oil and metals: today's commodity moves")
    finally:
        db.close()
    try:
        ok = _trigger_reel_via_moltis(style, subject, hook)
        if not ok:
            raise RuntimeError("tg-bridge rejected or unreachable")
        return f"reel triggered: {style}/{subject}"
    except self.MaxRetriesExceededError:
        _send_failure_alert(f"REEL 4 (18:30 {style})", "tg-bridge unreachable after 3 attempts — is it running on Contabo?")
        return "error: max retries exceeded"
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)
