"""
Sitemap deployment pipeline — runs daily at 4 AM UTC via Celery Beat.

Steps:
1. Trigger a Cloudflare Pages deploy (rebuilds sitemap.xml from live API data).
2. Wait ~90 s for the build to propagate.
3. Submit all URLs to IndexNow (covers Bing, Yandex, Seznam, Naver, etc.).
4. Ping Bing sitemap endpoint directly as a belt-and-suspenders fallback.

Note: Google deprecated their sitemap ping endpoint in January 2024 — it
silently ignores all requests. To tell Google about the sitemap, submit it
once manually in Search Console:
  https://search.google.com/search-console → Sitemaps → add
  https://api.metricshour.com/sitemap.xml

Setup env vars:
- CF_PAGES_DEPLOY_HOOK: Cloudflare Pages → Settings → Deploy Hooks → create one
- INDEXNOW_KEY:         6f2e9bac2bb44ccc9b1f202cbf6e670f  (set in .env)
"""
import os
import time
import logging
import requests
from xml.etree import ElementTree
from celery_app import app

logger = logging.getLogger(__name__)

SITEMAP_URL   = 'https://api.metricshour.com/sitemap.xml'
INDEXNOW_HOST = 'metricshour.com'
INDEXNOW_KEY  = os.getenv('INDEXNOW_KEY', '6f2e9bac2bb44ccc9b1f202cbf6e670f')
INDEXNOW_KEY_LOCATION = f'https://{INDEXNOW_HOST}/{INDEXNOW_KEY}.txt'
INDEXNOW_ENDPOINT     = 'https://api.indexnow.org/indexnow'

# IndexNow accepts up to 10,000 URLs per request
_INDEXNOW_BATCH = 10_000


def _fetch_sitemap_urls() -> list[str]:
    """Parse the live sitemap and return all <loc> URLs."""
    try:
        resp = requests.get(SITEMAP_URL, timeout=15)
        resp.raise_for_status()
        ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        root = ElementTree.fromstring(resp.content)
        urls = [el.text.strip() for el in root.findall('sm:url/sm:loc', ns) if el.text]
        logger.info('Fetched %d URLs from sitemap', len(urls))
        return urls
    except Exception as exc:
        logger.error('Failed to fetch/parse sitemap: %s', exc)
        return []


def _submit_indexnow(urls: list[str]) -> dict:
    """Submit URLs to IndexNow in batches. Returns {batch_n: status_code}."""
    if not urls:
        return {}

    results = {}
    for i in range(0, len(urls), _INDEXNOW_BATCH):
        batch = urls[i:i + _INDEXNOW_BATCH]
        batch_n = i // _INDEXNOW_BATCH + 1
        payload = {
            'host':        INDEXNOW_HOST,
            'key':         INDEXNOW_KEY,
            'keyLocation': INDEXNOW_KEY_LOCATION,
            'urlList':     batch,
        }
        try:
            r = requests.post(
                INDEXNOW_ENDPOINT,
                json=payload,
                headers={'Content-Type': 'application/json; charset=utf-8'},
                timeout=30,
            )
            results[f'batch_{batch_n}'] = r.status_code
            if r.status_code in (200, 202):
                logger.info('IndexNow batch %d → HTTP %s (%d URLs)', batch_n, r.status_code, len(batch))
            else:
                logger.warning('IndexNow batch %d → HTTP %s: %s', batch_n, r.status_code, r.text[:200])
        except requests.RequestException as exc:
            results[f'batch_{batch_n}'] = f'error: {exc}'
            logger.error('IndexNow batch %d failed: %s', batch_n, exc)

    return results


def _ping_bing() -> int | str:
    """Ping Bing sitemap endpoint (still active as of 2025)."""
    try:
        r = requests.get(
            f'https://www.bing.com/ping?sitemap={SITEMAP_URL}',
            timeout=10,
        )
        logger.info('Bing sitemap ping → HTTP %s', r.status_code)
        return r.status_code
    except requests.RequestException as exc:
        logger.warning('Bing sitemap ping failed: %s', exc)
        return f'error: {exc}'


@app.task(name='tasks.sitemap_deploy.trigger_pages_deploy', bind=True, max_retries=2)
def trigger_pages_deploy(self):
    """Trigger CF Pages deploy, wait for propagation, then submit to IndexNow + Bing."""
    hook_url = os.getenv('CF_PAGES_DEPLOY_HOOK')
    if not hook_url:
        logger.warning('CF_PAGES_DEPLOY_HOOK not set — skipping sitemap redeploy')
        return {'status': 'skipped', 'reason': 'no hook url'}

    # Step 1: trigger deploy
    try:
        resp = requests.post(hook_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        deploy_id = data.get('result', {}).get('id', 'unknown')
        logger.info('Cloudflare Pages deploy triggered: %s', deploy_id)
    except requests.RequestException as exc:
        logger.error('Failed to trigger CF Pages deploy: %s', exc)
        raise self.retry(exc=exc, countdown=300)

    # Step 2: wait for Pages build to propagate (~90 s for typical build)
    time.sleep(90)

    # Step 3: fetch all URLs and submit to IndexNow
    urls    = _fetch_sitemap_urls()
    indexnow = _submit_indexnow(urls)

    # Step 4: belt-and-suspenders Bing ping
    bing = _ping_bing()

    return {
        'status':    'done',
        'deploy_id': deploy_id,
        'url_count': len(urls),
        'indexnow':  indexnow,
        'bing':      bing,
    }


@app.task(name='tasks.sitemap_deploy.ping_only', bind=True, max_retries=1)
def ping_only(self):
    """Submit current sitemap URLs to IndexNow + Bing without triggering a deploy.

    Useful to call after a large data update (e.g. new blog posts, trade data).
    """
    urls     = _fetch_sitemap_urls()
    indexnow = _submit_indexnow(urls)
    bing     = _ping_bing()

    return {
        'status':    'done',
        'url_count': len(urls),
        'indexnow':  indexnow,
        'bing':      bing,
    }
