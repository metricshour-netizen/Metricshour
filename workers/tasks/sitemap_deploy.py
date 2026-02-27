"""
Sitemap deployment pipeline — runs daily at 4 AM UTC via Celery Beat.

Steps:
1. Trigger a Cloudflare Pages deploy (rebuilds sitemap.xml from live API data).
2. Wait ~90 s for the build to propagate, then ping Google & Bing so they
   crawl the fresh sitemap immediately.

Setup:
- CF_PAGES_DEPLOY_HOOK: Cloudflare Pages → Settings → Deploy Hooks → create one
"""
import os
import time
import logging
import requests
from celery_app import app

logger = logging.getLogger(__name__)

# Served from API backend — no Bot Fight Mode blocking Googlebot
SITEMAP_URL = 'https://api.metricshour.com/sitemap.xml'


def _ping_search_engines() -> dict:
    """Ping Google and Bing sitemap endpoints."""
    results = {}
    for name, ping_url in [
        ('google', f'https://www.google.com/ping?sitemap={SITEMAP_URL}'),
        ('bing',   f'https://www.bing.com/ping?sitemap={SITEMAP_URL}'),
    ]:
        try:
            r = requests.get(ping_url, timeout=10)
            results[name] = r.status_code
            logger.info('Sitemap ping %s → HTTP %s', name, r.status_code)
        except requests.RequestException as exc:
            results[name] = f'error: {exc}'
            logger.warning('Sitemap ping %s failed: %s', name, exc)
    return results


@app.task(name='tasks.sitemap_deploy.trigger_pages_deploy', bind=True, max_retries=2)
def trigger_pages_deploy(self):
    """Trigger CF Pages deploy, wait for propagation, then ping search engines."""
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

    # Step 3: ping Google + Bing
    pings = _ping_search_engines()

    return {'status': 'done', 'deploy_id': deploy_id, 'pings': pings}


@app.task(name='tasks.sitemap_deploy.ping_only', bind=True, max_retries=1)
def ping_only(self):
    """Ping search engines without triggering a deploy (e.g. after data update)."""
    pings = _ping_search_engines()
    return {'status': 'done', 'pings': pings}
