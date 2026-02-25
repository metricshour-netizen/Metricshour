"""
Triggers a Cloudflare Pages deploy to regenerate the sitemap and static site.
Runs daily at 4 AM UTC via Celery Beat.

Setup:
1. In Cloudflare Pages → your project → Settings → Builds & Deployments → Deploy Hooks
2. Create a hook called "sitemap-refresh" → copy the URL
3. Add CF_PAGES_DEPLOY_HOOK=<url> to your .env
"""
import os
import logging
import requests
from celery_app import app

logger = logging.getLogger(__name__)


@app.task(name='tasks.sitemap_deploy.trigger_pages_deploy', bind=True, max_retries=2)
def trigger_pages_deploy(self):
    hook_url = os.getenv('CF_PAGES_DEPLOY_HOOK')
    if not hook_url:
        logger.warning('CF_PAGES_DEPLOY_HOOK not set — skipping sitemap redeploy')
        return {'status': 'skipped', 'reason': 'no hook url'}

    try:
        resp = requests.post(hook_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        logger.info('Cloudflare Pages deploy triggered: %s', data.get('result', {}).get('id', 'unknown'))
        return {'status': 'triggered', 'deploy_id': data.get('result', {}).get('id')}
    except requests.RequestException as exc:
        logger.error('Failed to trigger CF Pages deploy: %s', exc)
        raise self.retry(exc=exc, countdown=300)
