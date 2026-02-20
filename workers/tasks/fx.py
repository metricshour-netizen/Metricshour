"""
FX rate ingestion — yfinance (free, no key required).
Runs every 15 minutes on weekdays.
"""

import logging
from datetime import datetime, timezone

import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

# Maps our DB symbol → yfinance FX ticker
YFINANCE_MAP: dict[str, str] = {
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    'USDCNY': 'USDCNY=X',
    'USDCHF': 'USDCHF=X',
    'AUDUSD': 'AUDUSD=X',
    'USDCAD': 'USDCAD=X',
    'USDMXN': 'USDMXN=X',
    'USDBRL': 'USDBRL=X',
    'USDINR': 'USDINR=X',
}


def _is_weekday() -> bool:
    return datetime.now(timezone.utc).weekday() < 5


@app.task(name='tasks.fx.fetch_fx_rates', bind=True, max_retries=3)
def fetch_fx_rates(self):
    if not _is_weekday():
        return 'skipped: weekend'

    db = SessionLocal()
    try:
        assets = (
            db.query(Asset)
            .filter(Asset.asset_type == AssetType.fx, Asset.is_active == True)
            .all()
        )
        symbol_to_asset = {a.symbol: a for a in assets}

        yf_to_asset = {
            yf_sym: symbol_to_asset[our_sym]
            for our_sym, yf_sym in YFINANCE_MAP.items()
            if our_sym in symbol_to_asset
        }

        if not yf_to_asset:
            return

        yf_symbols = list(yf_to_asset.keys())
        prices: dict[str, float] = {}

        try:
            df = yf.download(
                yf_symbols, period='1d', interval='15m',
                group_by='ticker', progress=False, threads=True,
            )
            for yf_sym in yf_symbols:
                try:
                    close = df[yf_sym]['Close'].dropna()
                    if not close.empty:
                        prices[yf_sym] = float(close.iloc[-1])
                except (KeyError, IndexError):
                    pass
        except Exception:
            log.exception('FX yfinance fetch failed')

        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        rows = [
            {
                'asset_id': yf_to_asset[yf_sym].id,
                'timestamp': now,
                'interval': '15m',
                'open': None,
                'high': None,
                'low': None,
                'close': price,
                'volume': None,
            }
            for yf_sym, price in prices.items()
            if yf_sym in yf_to_asset
        ]

        if rows:
            stmt = pg_insert(Price).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_price_asset_time_interval',
                set_={'close': stmt.excluded.close},
            )
            db.execute(stmt)
            db.commit()
            log.info(f'FX: upserted {len(rows)} rates')

    except Exception as exc:
        db.rollback()
        log.exception('FX rate fetch failed')
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
