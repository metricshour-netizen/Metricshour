"""
Celery app — MetricsHour background workers.

Run worker:   celery -A celery_app worker --loglevel=info
Run beat:     celery -A celery_app beat --loglevel=info
Run combined: celery -A celery_app worker --beat --loglevel=info
"""

import ssl
import sys
import os

# Make backend importable
sys.path.insert(0, '/root/metricshour/backend')

from dotenv import load_dotenv
load_dotenv('/root/metricshour/backend/.env')

import sentry_sdk
from celery import Celery, signals
from celery.schedules import crontab
from sentry_sdk.integrations.celery import CeleryIntegration

_sentry_dsn = os.environ.get("SENTRY_DSN", "")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[CeleryIntegration()],
        traces_sample_rate=0.0,
        send_default_pii=False,
        environment="production",
    )

@signals.task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, args=None,
                        kwargs=None, traceback=None, einfo=None, **kw):
    """Fire on every final task failure (after all retries exhausted)."""
    from tasks.alerts import on_task_failure
    task_name = sender.name if sender else "unknown"
    retries = getattr(sender, "request", None)
    retry_count = retries.retries if retries else 0
    on_task_failure(task_name, exception, retry_count)


app = Celery('metricshour', include=[
    'tasks.crypto',
    'tasks.stocks',
    'tasks.commodities',
    'tasks.fx',
    'tasks.backup',
    'tasks.feed_generator',
    'tasks.summaries',
    'tasks.og_images',
    # Data collection workers
    'tasks.world_bank_update',
    'tasks.ecb_fx_rates',
    'tasks.central_bank_rss',
    'tasks.imf_update',
    'tasks.oecd_update',
    'tasks.trade_update',
    'tasks.sitemap_deploy',
])

# Upstash Redis uses TLS (rediss://); Celery requires ssl_cert_reqs to be explicit.
_ssl_opts = {'ssl_cert_reqs': ssl.CERT_NONE}

app.conf.update(
    broker_url=os.environ['REDIS_URL'],
    result_backend=os.environ['REDIS_URL'],
    broker_use_ssl=_ssl_opts,
    redis_backend_use_ssl=_ssl_opts,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        'crypto-every-1min': {
            'task': 'tasks.crypto.fetch_crypto_prices',
            'schedule': 60.0,
        },
        'stocks-every-15min': {
            'task': 'tasks.stocks.fetch_stock_prices',
            'schedule': 900.0,
        },
        'commodities-every-15min': {
            'task': 'tasks.commodities.fetch_commodity_prices',
            'schedule': 900.0,
        },
        'fx-every-15min': {
            'task': 'tasks.fx.fetch_fx_rates',
            'schedule': 900.0,
        },
        'db-backup-daily-3am': {
            'task': 'tasks.backup.run_backup',
            'schedule': crontab(hour=3, minute=0),
        },
        'feed-generator-every-3min': {
            'task': 'tasks.feed_generator.generate_feed_events',
            'schedule': 180.0,
        },
        'sitemap-redeploy-daily-4am': {
            'task': 'tasks.sitemap_deploy.trigger_pages_deploy',
            'schedule': crontab(hour=4, minute=0),
        },
        'page-summaries-daily-2am': {
            'task': 'tasks.summaries.generate_page_summaries',
            'schedule': crontab(hour=2, minute=0),
        },
        'spotlight-refresh-every-3hr': {
            'task': 'tasks.summaries.refresh_spotlight',
            'schedule': crontab(minute=0, hour='*/3'),
        },
        'og-images-daily-330am': {
            'task': 'tasks.og_images.generate_og_images',
            'schedule': crontab(hour=3, minute=30),
        },
        'feed-og-images-daily-4am': {
            'task': 'tasks.og_images.generate_feed_og_images',
            'schedule': crontab(hour=4, minute=15),
        },

        # --- Data collection: public domain sources ---

        # World Bank: 50+ indicators, all 196 countries — daily at 6am
        'world-bank-update-daily-6am': {
            'task': 'tasks.world_bank_update.update_world_bank',
            'schedule': crontab(hour=6, minute=0),
        },

        # ECB: EUR FX reference rates — daily at 6:30am (published ~16:00 CET prior day)
        'ecb-fx-daily-630am': {
            'task': 'tasks.ecb_fx_rates.update_ecb_fx',
            'schedule': crontab(hour=6, minute=30),
        },

        # Central bank RSS: Fed, ECB, BoE, BoJ rate decisions → FeedEvents — daily 8am
        'central-bank-rss-daily-8am': {
            'task': 'tasks.central_bank_rss.fetch_central_bank_news',
            'schedule': crontab(hour=8, minute=0),
        },

        # IMF DataMapper: GDP forecasts, inflation, debt — monthly on 1st at 5am
        'imf-update-monthly': {
            'task': 'tasks.imf_update.update_imf_data',
            'schedule': crontab(hour=5, minute=0, day_of_month=1),
        },

        # OECD MEI: interest rates, CPI, industrial production, CLI — weekly Sunday 1am
        'oecd-update-weekly-sunday': {
            'task': 'tasks.oecd_update.update_oecd_data',
            'schedule': crontab(hour=1, minute=0, day_of_week=0),
        },

        # WITS trade matrix: full annual refresh — Jan 15 at 2am
        'trade-update-annual-jan15': {
            'task': 'tasks.trade_update.update_trade_data_annual',
            'schedule': crontab(hour=2, minute=0, day_of_month=15, month_of_year=1),
        },

        # Comtrade quarterly update: Apr/Jul/Oct 1st at 3am
        'trade-update-quarterly': {
            'task': 'tasks.trade_update.update_trade_data_quarterly',
            'schedule': crontab(hour=3, minute=0, day_of_month=1, month_of_year='4,7,10'),
        },
    },
)
