"""
Nigeria stocks price ingestion — yfinance for LSE-listed Nigerian companies.
Runs daily at 17:00 UTC (after LSE close at ~16:30 UTC).
Only fetches LSE exchange assets with Nigerian country_id.
"""

import logging
import warnings
from datetime import datetime, timezone, date, timedelta

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

warnings.filterwarnings('ignore')
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
log = logging.getLogger(__name__)

LSE_EXCHANGE = 'LSE'
NIGERIA_COUNTRY_ID = 179


@app.task(name='tasks.nigeria_stocks.fetch_nigeria_prices', bind=True, max_retries=3)
def fetch_nigeria_prices(self):
    db = SessionLocal()
    try:
        assets = db.execute(
            select(Asset).where(
                Asset.asset_type == AssetType.stock,
                Asset.is_active == True,
                Asset.exchange == LSE_EXCHANGE,
                Asset.country_id == NIGERIA_COUNTRY_ID,
            )
        ).scalars().all()

        if not assets:
            log.info('No LSE-listed Nigerian assets found in DB')
            return

        symbol_to_asset = {a.symbol: a for a in assets}
        symbols = list(symbol_to_asset.keys())
        fetched = datetime.now(timezone.utc)
        today_ts = fetched.replace(hour=0, minute=0, second=0, microsecond=0)
        rows = []
        errors = 0

        for sym in symbols:
            try:
                df = yf.download(sym, period='5d', interval='1d', progress=False)
                if df.empty:
                    log.debug('Nigeria stock %s: no data from yfinance', sym)
                    continue

                # MultiIndex columns when single ticker
                close_col = ('Close', sym) if ('Close', sym) in df.columns else 'Close'
                open_col  = ('Open',  sym) if ('Open',  sym) in df.columns else 'Open'
                high_col  = ('High',  sym) if ('High',  sym) in df.columns else 'High'
                low_col   = ('Low',   sym) if ('Low',   sym) in df.columns else 'Low'
                vol_col   = ('Volume',sym) if ('Volume',sym) in df.columns else 'Volume'

                close_s = df[close_col].dropna()
                if close_s.empty:
                    continue

                asset = symbol_to_asset[sym]
                rows.append({
                    'asset_id':  asset.id,
                    'timestamp': today_ts,
                    'interval':  '1d',
                    'open':      float(df[open_col].dropna().iloc[-1]) if not df[open_col].dropna().empty else None,
                    'high':      float(df[high_col].dropna().iloc[-1]) if not df[high_col].dropna().empty else None,
                    'low':       float(df[low_col].dropna().iloc[-1])  if not df[low_col].dropna().empty  else None,
                    'close':     float(close_s.iloc[-1]),
                    'volume':    float(df[vol_col].dropna().iloc[-1])  if not df[vol_col].dropna().empty  else None,
                    'fetched_at': fetched,
                })
                log.debug('Nigeria %s: close=%.2f', sym, float(close_s.iloc[-1]))

            except Exception as e:
                errors += 1
                log.warning('Nigeria stock %s error: %s', sym, e)

        if rows:
            stmt = pg_insert(Price).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_price_asset_time_interval',
                set_={
                    'close':      stmt.excluded.close,
                    'open':       stmt.excluded.open,
                    'high':       stmt.excluded.high,
                    'low':        stmt.excluded.low,
                    'volume':     stmt.excluded.volume,
                    'fetched_at': stmt.excluded.fetched_at,
                },
            )
            db.execute(stmt)
            db.commit()
            log.info(
                'Nigeria LSE stocks: upserted %d prices (%d errors) for %d stocks',
                len(rows), errors, len(assets),
            )

    except Exception as exc:
        db.rollback()
        log.warning('Nigeria stock fetch failed: %s', exc)
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
