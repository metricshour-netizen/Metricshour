"""
Celery app — MetricsHour background workers.

Run worker:   celery -A celery_app worker --loglevel=info
Run beat:     celery -A celery_app beat --loglevel=info
Run combined: celery -A celery_app worker --beat --loglevel=info
"""

import sys
import os

# Make backend importable
sys.path.insert(0, '/root/metricshour/backend')

from dotenv import load_dotenv
load_dotenv('/root/metricshour/backend/.env')

from celery import Celery

app = Celery('metricshour', include=[
    'tasks.crypto',
    'tasks.stocks',
    'tasks.commodities',
    'tasks.fx',
])

app.conf.update(
    broker_url=os.environ['REDIS_URL'],
    result_backend=os.environ['REDIS_URL'],
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
    },
)
