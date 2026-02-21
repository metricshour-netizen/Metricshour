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
        'feed-generator-every-15min': {
            'task': 'tasks.feed_generator.generate_feed_events',
            'schedule': 900.0,
        },
    },
)
