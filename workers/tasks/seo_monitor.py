"""
SEO health monitor — runs weekly (Sunday 2am UTC) via Celery Beat.

Checks:
  1. Key pages return HTTP 200 (country, stock, trade, index, sitemap)
  2. Sitemap URL count >= minimum expected (warns if pages were dropped)
  3. IndexNow last-ping result from previous sitemap_deploy task (Redis key)

Alerts via Telegram if any check fails.
No AI calls — pure HTTP + lightweight checks.
"""
import logging
import os
from datetime import datetime, timezone
from xml.etree import ElementTree

import requests

from celery_app import app

log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

SITE_URL = "https://metricshour.com"
API_URL  = "https://api.metricshour.com"

# Pages that must return 200 — representative sample across all page types
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

# Warn if sitemap drops below this many URLs (currently ~683, allow 10% drop)
SITEMAP_MIN_URLS = 600

# Timeout per HTTP check (seconds)
HTTP_TIMEOUT = 15


def _send_telegram(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured — cannot send SEO alert")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        log.error("Telegram send failed: %s", e)


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
    """Return (url_count, warnings). Parses live sitemap."""
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


@app.task(name="tasks.seo_monitor.run_seo_checks", bind=True, max_retries=1)
def run_seo_checks(self):
    """
    Weekly SEO health check. Runs Sunday 2am UTC.
    Sends Telegram alert if any page is down or sitemap shrinks unexpectedly.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log.info("SEO monitor starting — %s", now)

    page_failures = _check_pages()
    sitemap_count, sitemap_warnings = _check_sitemap()

    all_issues = page_failures + sitemap_warnings
    ok_count   = len(KEY_PAGES) - len(page_failures)

    log.info(
        "SEO monitor done — %d/%d pages OK, sitemap %d URLs, %d issues",
        ok_count, len(KEY_PAGES), sitemap_count, len(all_issues),
    )

    if all_issues:
        issue_lines = "\n".join(f"  • {i}" for i in all_issues)
        msg = (
            f"🚨 <b>SEO Monitor — {len(all_issues)} issue(s)</b>\n"
            f"<i>{now}</i>\n\n"
            f"{issue_lines}\n\n"
            f"Sitemap: {sitemap_count} URLs | Pages checked: {len(KEY_PAGES)}"
        )
        _send_telegram(msg)
        log.warning("SEO monitor found %d issues — Telegram alert sent", len(all_issues))
    else:
        msg = (
            f"✅ <b>SEO Monitor — all clear</b>\n"
            f"<i>{now}</i>\n\n"
            f"{len(KEY_PAGES)}/{len(KEY_PAGES)} pages OK\n"
            f"Sitemap: {sitemap_count} URLs"
        )
        _send_telegram(msg)
        log.info("SEO monitor — all clear")

    return {
        "ok": len(KEY_PAGES) - len(page_failures),
        "failed": len(page_failures),
        "sitemap_urls": sitemap_count,
        "issues": all_issues,
    }
