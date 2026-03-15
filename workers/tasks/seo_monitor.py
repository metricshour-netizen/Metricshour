"""
SEO health monitor — runs weekly (Sunday 2am UTC) via Celery Beat.

Phase 1 — HTTP health checks:
  1. Key pages return HTTP 200
  2. Sitemap URL count >= minimum expected

Phase 2 — AI SEO audit:
  3. Fetch HTML of sample pages, extract SEO signals (title, meta description,
     H1, canonical, og:image, og:title)
  4. Gemini (gemini-2.5-flash-lite) analyses signals and returns actionable findings
  5. Structured weekly report + action buttons sent to Telegram
"""
import logging
import os
import re
from datetime import datetime, timezone
from xml.etree import ElementTree

import requests

from celery_app import app

log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_KEY_2   = os.environ.get("GEMINI_API_KEY_2", "")
_GEMINI_KEY        = GEMINI_API_KEY or GEMINI_API_KEY_2   # use whichever is set

SITE_URL = "https://metricshour.com"
API_URL  = "https://api.metricshour.com"

# Pages that must return 200
KEY_PAGES = [
    f"{SITE_URL}/",
    f"{SITE_URL}/countries",
    f"{SITE_URL}/countries/us",
    f"{SITE_URL}/countries/de",
    f"{SITE_URL}/countries/cn",
    f"{SITE_URL}/stocks",
    f"{SITE_URL}/stocks/aapl",
    f"{SITE_URL}/trade",
    f"{SITE_URL}/trade/united-states--china",
    f"{SITE_URL}/commodities",
    f"{SITE_URL}/markets",
    f"{SITE_URL}/feed",
    f"{API_URL}/health",
    f"{API_URL}/sitemap.xml",
    f"{API_URL}/robots.txt",
]

# Pages to include in the AI SEO audit (subset of KEY_PAGES — HTML-rendering pages only)
AUDIT_PAGES = [
    f"{SITE_URL}/",
    f"{SITE_URL}/countries",
    f"{SITE_URL}/countries/us",
    f"{SITE_URL}/stocks/aapl",
    f"{SITE_URL}/trade/united-states--china",
    f"{SITE_URL}/commodities",
    f"{SITE_URL}/markets",
    f"{SITE_URL}/feed",
]

SITEMAP_MIN_URLS = 600
HTTP_TIMEOUT = 15
GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


# ── Telegram helpers ──────────────────────────────────────────────────────────

def _send_telegram(text: str, reply_markup: dict | None = None) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured — cannot send SEO report")
        return
    payload: dict = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=10,
        )
    except Exception as e:
        log.error("Telegram send failed: %s", e)


def _url_button(label: str, url: str) -> dict:
    return {"text": label, "url": url}


# ── Phase 1: HTTP health checks ───────────────────────────────────────────────

def _check_pages() -> list[str]:
    """Return list of failure strings for pages that don't return 200."""
    failures = []
    for url in KEY_PAGES:
        try:
            r = requests.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True,
                             headers={"User-Agent": "MetricsHour-SEOMonitor/1.0"})
            if r.status_code != 200:
                failures.append(f"{r.status_code} — {url}")
        except Exception as e:
            failures.append(f"ERROR — {url} ({e})")
    return failures


def _check_sitemap() -> tuple[int, list[str]]:
    """Return (url_count, warnings)."""
    warnings = []
    try:
        r = requests.get(f"{API_URL}/sitemap.xml", timeout=15,
                         headers={"User-Agent": "MetricsHour-SEOMonitor/1.0"})
        r.raise_for_status()
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        root = ElementTree.fromstring(r.content)
        urls = root.findall("sm:url/sm:loc", ns)
        count = len(urls)
        if count < SITEMAP_MIN_URLS:
            warnings.append(
                f"Sitemap has only {count} URLs (expected ≥{SITEMAP_MIN_URLS}) — "
                f"pages may have been dropped"
            )
        return count, warnings
    except Exception as e:
        return 0, [f"Sitemap fetch failed: {e}"]


# ── Phase 2: AI SEO audit ─────────────────────────────────────────────────────

def _extract_seo_signals(html: str, url: str) -> dict:
    """Extract key SEO signals from raw HTML using regex (no external deps)."""
    def _first(pattern: str, flags: int = re.I | re.S) -> str:
        m = re.search(pattern, html, flags)
        return m.group(1).strip() if m else ""

    title        = _first(r"<title[^>]*>(.*?)</title>")
    meta_desc    = _first(r'<meta\s+name=["\']description["\'][^>]*content=["\'](.*?)["\']')
    if not meta_desc:
        meta_desc = _first(r'<meta\s+content=["\'](.*?)["\']\s+name=["\']description["\']')
    h1           = _first(r"<h1[^>]*>(.*?)</h1>")
    h1           = re.sub(r"<[^>]+>", "", h1).strip()  # strip inner tags
    canonical    = _first(r'<link\s+rel=["\']canonical["\'][^>]*href=["\'](.*?)["\']')
    og_title     = _first(r'<meta\s+property=["\']og:title["\'][^>]*content=["\'](.*?)["\']')
    og_desc      = _first(r'<meta\s+property=["\']og:description["\'][^>]*content=["\'](.*?)["\']')
    og_image     = _first(r'<meta\s+property=["\']og:image["\'][^>]*content=["\'](.*?)["\']')
    robots       = _first(r'<meta\s+name=["\']robots["\'][^>]*content=["\'](.*?)["\']')

    return {
        "url":        url,
        "title":      title,
        "title_len":  len(title),
        "meta_desc":  meta_desc,
        "desc_len":   len(meta_desc),
        "h1":         h1,
        "canonical":  canonical,
        "og_title":   og_title,
        "og_desc":    og_desc,
        "og_image":   bool(og_image),
        "robots":     robots or "not set",
    }


def _fetch_page_signals(pages: list[str]) -> list[dict]:
    """Fetch HTML for each audit page and return extracted SEO signals."""
    results = []
    for url in pages:
        try:
            r = requests.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True,
                             headers={"User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"})
            if r.status_code == 200:
                signals = _extract_seo_signals(r.text, url)
            else:
                signals = {"url": url, "error": f"HTTP {r.status_code}"}
        except Exception as e:
            signals = {"url": url, "error": str(e)}
        results.append(signals)
        log.debug("SEO audit fetched %s", url)
    return results


def _build_audit_prompt(signals: list[dict]) -> str:
    lines = ["You are an SEO analyst reviewing MetricsHour.com, a financial intelligence platform.\n"]
    lines.append("Review the following page SEO signals and return a concise audit report.\n")
    lines.append("For each page with issues, give 1-2 specific, actionable fixes.\n")
    lines.append("At the end, give an overall score 0-100 and 3 top priority actions.\n\n")
    lines.append("SEO SIGNALS:\n")

    for s in signals:
        url = s.get("url", "?")
        if "error" in s:
            lines.append(f"PAGE: {url}\n  ERROR: {s['error']}\n")
            continue
        title_note = ""
        if s["title_len"] == 0:
            title_note = " ⚠️ MISSING"
        elif s["title_len"] < 30:
            title_note = f" ⚠️ TOO SHORT ({s['title_len']} chars)"
        elif s["title_len"] > 70:
            title_note = f" ⚠️ TOO LONG ({s['title_len']} chars)"
        else:
            title_note = f" ✓ ({s['title_len']} chars)"

        desc_note = ""
        if s["desc_len"] == 0:
            desc_note = " ⚠️ MISSING"
        elif s["desc_len"] < 100:
            desc_note = f" ⚠️ TOO SHORT ({s['desc_len']} chars)"
        elif s["desc_len"] > 165:
            desc_note = f" ⚠️ TOO LONG ({s['desc_len']} chars)"
        else:
            desc_note = f" ✓ ({s['desc_len']} chars)"

        lines.append(f"PAGE: {url}")
        lines.append(f"  Title: \"{s['title']}\"{title_note}")
        lines.append(f"  Meta desc: \"{s['meta_desc'][:120]}\"{desc_note}")
        lines.append(f"  H1: \"{s['h1']}\"" + (" ⚠️ MISSING" if not s["h1"] else ""))
        lines.append(f"  Canonical: {s['canonical'] or '⚠️ MISSING'}")
        lines.append(f"  OG image: {'✓' if s['og_image'] else '⚠️ MISSING'}")
        lines.append(f"  OG title: \"{s['og_title'][:80]}\"" if s["og_title"] else "  OG title: ⚠️ MISSING")
        lines.append(f"  Robots: {s['robots']}")
        lines.append("")

    lines.append(
        "Return your audit as:\n"
        "SCORE: [0-100]\n"
        "SUMMARY: [2 sentences]\n"
        "ISSUES:\n"
        "- [page short name]: [specific fix]\n"
        "- ...\n"
        "TOP 3 PRIORITIES:\n"
        "1. [action]\n"
        "2. [action]\n"
        "3. [action]\n"
        "Keep total response under 350 words."
    )
    return "\n".join(lines)


def _call_gemini_audit(prompt: str) -> str | None:
    """Call Gemini for the SEO audit. Returns raw text or None on failure."""
    if not _GEMINI_KEY:
        log.warning("No Gemini API key set — skipping AI audit")
        return None
    try:
        resp = requests.post(
            GEMINI_API_URL,
            params={"key": _GEMINI_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 800,
                },
            },
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.error("Gemini SEO audit failed: %s", e)
        return None


def _parse_score(ai_text: str) -> int:
    """Extract numeric score from AI response."""
    m = re.search(r"SCORE:\s*(\d+)", ai_text)
    return int(m.group(1)) if m else 0


# ── Telegram report builders ──────────────────────────────────────────────────

def _score_emoji(score: int) -> str:
    if score >= 80:
        return "🟢"
    if score >= 60:
        return "🟡"
    return "🔴"


def _send_health_report(now: str, page_failures: list[str],
                        sitemap_count: int, sitemap_warnings: list[str]) -> None:
    """Phase 1 report: HTTP health + sitemap."""
    ok_count = len(KEY_PAGES) - len(page_failures)
    all_issues = page_failures + sitemap_warnings

    if all_issues:
        issue_lines = "\n".join(f"  • {i}" for i in all_issues)
        status = f"🚨 {len(all_issues)} issue(s) found"
        body = f"{issue_lines}\n"
    else:
        status = "✅ All pages healthy"
        body = ""

    msg = (
        f"<b>🔍 SEO Monitor — Weekly Report</b>\n"
        f"<i>{now}</i>\n\n"
        f"<b>Health Check:</b> {status}\n"
        f"{body}"
        f"Pages OK: {ok_count}/{len(KEY_PAGES)} | Sitemap: {sitemap_count} URLs"
    )

    # Action buttons for failed pages (max 5 shown as URL buttons)
    buttons = []
    for failure in page_failures[:5]:
        url_match = re.search(r"https?://\S+", failure)
        if url_match:
            page_url = url_match.group(0)
            short = page_url.replace("https://metricshour.com", "").replace("https://api.metricshour.com", "/api") or "/"
            buttons.append(_url_button(f"Check {short}", page_url))

    reply_markup = None
    if buttons:
        # Group buttons in rows of 2
        rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
        reply_markup = {"inline_keyboard": rows}

    _send_telegram(msg, reply_markup)


def _send_ai_report(now: str, ai_text: str, signals: list[dict]) -> None:
    """Phase 2 report: AI SEO audit with action buttons."""
    score = _parse_score(ai_text)
    emoji = _score_emoji(score)

    # Truncate ai_text to fit Telegram's 4096 char limit
    # Strip the SCORE line since we show it in header
    audit_body = re.sub(r"^SCORE:\s*\d+\s*\n?", "", ai_text, flags=re.M).strip()
    # Escape HTML special chars in AI output
    audit_body = audit_body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Telegram message limit is 4096; leave room for header
    max_body = 3400
    if len(audit_body) > max_body:
        audit_body = audit_body[:max_body] + "…"

    msg = (
        f"<b>{emoji} SEO AI Audit — Score: {score}/100</b>\n"
        f"<i>{now}</i>\n\n"
        f"<pre>{audit_body}</pre>"
    )

    # Quick-access buttons for key pages to verify / fix manually
    quick_pages = [
        ("🏠 Home", f"{SITE_URL}/"),
        ("🌍 Countries", f"{SITE_URL}/countries"),
        ("📈 Stocks", f"{SITE_URL}/stocks"),
        ("🔗 Trade", f"{SITE_URL}/trade"),
        ("🛢 Commodities", f"{SITE_URL}/commodities"),
        ("🗺 Sitemap", f"{API_URL}/sitemap.xml"),
    ]
    rows = [[_url_button(label, url) for label, url in quick_pages[i:i+2]]
            for i in range(0, len(quick_pages), 2)]
    reply_markup = {"inline_keyboard": rows}

    _send_telegram(msg, reply_markup)


# ── Main task ─────────────────────────────────────────────────────────────────

@app.task(name="tasks.seo_monitor.run_seo_checks", bind=True, max_retries=1)
def run_seo_checks(self):
    """
    Weekly SEO health check + AI audit. Runs Sunday 2am UTC.
    Sends two Telegram messages: (1) HTTP health report, (2) AI SEO audit.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log.info("SEO monitor starting — %s", now)

    # ── Phase 1: HTTP health checks ──
    page_failures = _check_pages()
    sitemap_count, sitemap_warnings = _check_sitemap()
    ok_count = len(KEY_PAGES) - len(page_failures)
    log.info(
        "SEO health: %d/%d pages OK, sitemap %d URLs, %d issues",
        ok_count, len(KEY_PAGES), sitemap_count, len(page_failures + sitemap_warnings),
    )
    _send_health_report(now, page_failures, sitemap_count, sitemap_warnings)

    # ── Phase 2: AI SEO audit ──
    log.info("SEO audit: fetching HTML signals for %d pages", len(AUDIT_PAGES))
    signals = _fetch_page_signals(AUDIT_PAGES)

    prompt   = _build_audit_prompt(signals)
    ai_text  = _call_gemini_audit(prompt)

    if ai_text:
        log.info("SEO audit: AI analysis complete (%d chars)", len(ai_text))
        _send_ai_report(now, ai_text, signals)
    else:
        log.warning("SEO audit: AI call failed — sending signals summary only")
        # Fallback: send raw signal counts
        issues_found = sum(
            1 for s in signals
            if "error" in s
            or s.get("title_len", 0) == 0
            or s.get("desc_len", 0) == 0
            or not s.get("h1")
        )
        fallback = (
            f"<b>📊 SEO Signals Summary</b>\n"
            f"<i>{now}</i>\n\n"
            f"Pages audited: {len(signals)}\n"
            f"Pages with signal gaps: {issues_found}\n\n"
            f"<i>AI analysis unavailable — check GEMINI_API_KEY</i>"
        )
        _send_telegram(fallback)

    return {
        "ok": ok_count,
        "failed": len(page_failures),
        "sitemap_urls": sitemap_count,
        "issues": page_failures + sitemap_warnings,
        "ai_score": _parse_score(ai_text) if ai_text else None,
        "pages_audited": len(signals),
    }
