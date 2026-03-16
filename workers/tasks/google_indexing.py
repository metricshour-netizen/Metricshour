"""
Google Indexing API — submit URLs directly to Google for fast crawling.

Default quota: 200 URL notifications per day.
With ~2,800 URLs total, a full cycle takes ~14 days at default quota.

Setup (one-time):
  1. Google Cloud Console → IAM → Service Accounts → create account
  2. Grant it no project roles (it doesn't need any)
  3. Keys → Add Key → JSON → download
  4. Google Search Console → Settings → Users and permissions
     → Add user → paste service account email → Owner
  5. Save JSON file to server:
       scp key.json root@10.0.0.1:/root/metricshour/backend/google_service_account.json
  6. Add to .env:
       GOOGLE_INDEXING_KEY_FILE=/root/metricshour/backend/google_service_account.json
  7. systemctl restart metricshour-api metricshour-worker

Docs: https://developers.google.com/search/apis/indexing-api/v3/quickstart
"""
import os
import json
import logging
import redis
from celery_app import app
from xml.etree import ElementTree
import requests

logger = logging.getLogger(__name__)

SITEMAP_URL   = "https://api.metricshour.com/sitemap.xml"
SITE_BASE     = "https://metricshour.com"
INDEXING_API  = "https://indexing.googleapis.com/v3/urlNotifications:publish"
REDIS_KEY     = "google_indexing:cursor"   # tracks rotation position
DAILY_QUOTA   = 200                        # Google default; raise after approval

# URL priority order — highest value pages first
URL_PRIORITY = [
    "/",
    "/countries",
    "/stocks",
    "/commodities",
    "/trade",
    "/markets",
    "/indices",
    "/pricing",
    "/feed",
]


def _get_credentials():
    """Load Google service account credentials. Returns None if not configured."""
    key_file = os.environ.get("GOOGLE_INDEXING_KEY_FILE", "")
    if not key_file or not os.path.exists(key_file):
        logger.warning("GOOGLE_INDEXING_KEY_FILE not set or file not found — skipping")
        return None
    try:
        from google.oauth2 import service_account
        scopes = ["https://www.googleapis.com/auth/indexing"]
        creds = service_account.Credentials.from_service_account_file(key_file, scopes=scopes)
        return creds
    except Exception as e:
        logger.error("Failed to load Google service account: %s", e)
        return None


def _get_access_token(creds) -> str | None:
    """Refresh and return the OAuth bearer token."""
    try:
        import google.auth.transport.requests as google_requests
        creds.refresh(google_requests.Request())
        return creds.token
    except Exception as e:
        logger.error("Failed to refresh Google token: %s", e)
        return None


def _notify_single(url: str, token: str, notification_type: str = "URL_UPDATED") -> int:
    """Submit one URL. Returns HTTP status code."""
    try:
        r = requests.post(
            INDEXING_API,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"url": url, "type": notification_type},
            timeout=10,
        )
        return r.status_code
    except Exception as e:
        logger.error("Google Indexing request failed for %s: %s", url, e)
        return 0


def _fetch_sitemap_urls() -> list[str]:
    """Parse sitemap and return all <loc> URLs, priority pages first."""
    try:
        resp = requests.get(SITEMAP_URL, timeout=15)
        resp.raise_for_status()
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        root = ElementTree.fromstring(resp.content)
        all_urls = [el.text.strip() for el in root.findall("sm:url/sm:loc", ns) if el.text]

        # Sort: priority paths first, then alphabetically for stable rotation
        def priority_key(u):
            path = u.replace(SITE_BASE, "")
            for i, p in enumerate(URL_PRIORITY):
                if path == p or path.startswith(p + "/"):
                    return (i, path)
            return (len(URL_PRIORITY), path)

        return sorted(all_urls, key=priority_key)
    except Exception as e:
        logger.error("Failed to fetch sitemap: %s", e)
        return []


def _get_redis():
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    kwargs = {"decode_responses": True}
    if redis_url.startswith("rediss://"):
        import ssl
        kwargs["ssl_cert_reqs"] = ssl.CERT_NONE
    return redis.from_url(redis_url, **kwargs)


@app.task(name="tasks.google_indexing.submit_daily_batch", bind=True, max_retries=1)
def submit_daily_batch(self):
    """
    Daily task: submit up to DAILY_QUOTA URLs to Google Indexing API.
    Uses a Redis cursor to rotate through all sitemap URLs across days.
    Runs at 4:05 AM UTC (just after IndexNow at 4:00 AM).
    """
    creds = _get_credentials()
    if not creds:
        return {"status": "skipped", "reason": "no credentials"}

    token = _get_access_token(creds)
    if not token:
        return {"status": "error", "reason": "could not get token"}

    urls = _fetch_sitemap_urls()
    if not urls:
        return {"status": "error", "reason": "empty sitemap"}

    total = len(urls)
    r = _get_redis()

    # Load cursor — where we left off in the rotation
    cursor = int(r.get(REDIS_KEY) or 0)
    if cursor >= total:
        cursor = 0  # full cycle complete, restart

    # Take up to DAILY_QUOTA URLs starting from cursor (wrap around)
    indices = [(cursor + i) % total for i in range(DAILY_QUOTA)]
    batch = [urls[i] for i in indices]
    new_cursor = (cursor + DAILY_QUOTA) % total

    results = {"ok": 0, "error": 0, "codes": {}}
    for url in batch:
        code = _notify_single(url, token)
        if code in (200, 202):
            results["ok"] += 1
        else:
            results["error"] += 1
        results["codes"][code] = results["codes"].get(code, 0) + 1

    # Save cursor for next run
    r.set(REDIS_KEY, new_cursor)

    cycle_pct = round((new_cursor / total) * 100, 1)
    logger.info(
        "Google Indexing daily batch: %d submitted, %d ok, %d errors. Cursor %d/%d (%.1f%% of cycle)",
        len(batch), results["ok"], results["error"], new_cursor, total, cycle_pct,
    )
    return {
        "status":     "done",
        "submitted":  len(batch),
        "ok":         results["ok"],
        "errors":     results["error"],
        "codes":      results["codes"],
        "cursor":     new_cursor,
        "total_urls": total,
        "cycle_pct":  cycle_pct,
    }


@app.task(name="tasks.google_indexing.notify_url", bind=True, max_retries=2)
def notify_url(self, url: str, notification_type: str = "URL_UPDATED"):
    """
    Notify Google about a single URL immediately.
    Use after new content is published or a page is significantly updated.
    notification_type: URL_UPDATED or URL_DELETED
    """
    creds = _get_credentials()
    if not creds:
        return {"status": "skipped", "reason": "no credentials"}

    token = _get_access_token(creds)
    if not token:
        return {"status": "error", "reason": "could not get token"}

    code = _notify_single(url, token, notification_type)
    ok = code in (200, 202)
    logger.info("Google Indexing notify_url %s → HTTP %s", url, code)

    if not ok and code not in (429, 403):
        raise self.retry(countdown=60)

    return {"status": "ok" if ok else "error", "url": url, "http": code}


@app.task(name="tasks.google_indexing.notify_urls", bind=True, max_retries=1)
def notify_urls(urls: list[str], notification_type: str = "URL_UPDATED"):
    """
    Notify Google about a list of URLs immediately (e.g. after a data refresh).
    Capped at DAILY_QUOTA to avoid burning the quota in a single call.
    """
    creds = _get_credentials()
    if not creds:
        return {"status": "skipped", "reason": "no credentials"}

    token = _get_access_token(creds)
    if not token:
        return {"status": "error", "reason": "could not get token"}

    batch = urls[:DAILY_QUOTA]
    results = {"ok": 0, "error": 0}
    for url in batch:
        code = _notify_single(url, token, notification_type)
        if code in (200, 202):
            results["ok"] += 1
        else:
            results["error"] += 1

    logger.info("Google Indexing notify_urls: %d/%d ok", results["ok"], len(batch))
    return {"status": "done", "submitted": len(batch), **results}
