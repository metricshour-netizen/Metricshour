"""
FX rate ingestion — yfinance (free, no key required).
Runs every 15 minutes on weekdays.
"""

import logging
from datetime import datetime, timezone

import yfinance as yf

# yfinance logs internal per-ticker errors at ERROR level before our except blocks run.
# We handle missing tickers ourselves, so suppress yfinance's own noisy output.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
from sqlalchemy import select
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
        assets = db.execute(
            select(Asset).where(Asset.asset_type == AssetType.fx, Asset.is_active == True)
        ).scalars().all()
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
                except (KeyError, IndexError, TypeError):
                    pass
        except Exception:
            log.exception('FX yfinance fetch failed')

        # Fallback: retry any symbol that got no 15m data using daily interval.
        # Some EM pairs (CNY, INR, BRL) have sparse intraday coverage on yfinance.
        missing = [s for s in yf_symbols if s not in prices]
        if missing:
            try:
                tickers = missing if len(missing) > 1 else missing * 2
                df_daily = yf.download(
                    tickers, period='5d', interval='1d',
                    group_by='ticker', progress=False, threads=True,
                )
                for yf_sym in missing:
                    try:
                        close = df_daily[yf_sym]['Close'].dropna()
                        if not close.empty:
                            prices[yf_sym] = float(close.iloc[-1])
                            log.info('FX daily fallback OK: %s', yf_sym)
                    except (KeyError, IndexError, TypeError):
                        log.warning('FX no data (15m+1d): %s', yf_sym)
            except Exception:
                log.exception('FX daily fallback fetch failed')

        now_minute = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        now_day = now_minute.replace(hour=0, minute=0)

        # Also fetch daily open for change % calculation
        daily_open: dict[str, float | None] = {}
        try:
            tickers_d = yf_symbols if len(yf_symbols) > 1 else yf_symbols * 2
            df_d = yf.download(
                tickers_d, period='2d', interval='1d',
                group_by='ticker', progress=False, threads=True,
            )
            for yf_sym in yf_symbols:
                try:
                    open_ = df_d[yf_sym]['Open'].dropna()
                    daily_open[yf_sym] = float(open_.iloc[-1]) if not open_.empty else None
                except (KeyError, IndexError, TypeError):
                    daily_open[yf_sym] = None
        except Exception:
            pass

        rows_15m = []
        rows_1d = []
        for yf_sym, price in prices.items():
            if yf_sym not in yf_to_asset:
                continue
            asset_id = yf_to_asset[yf_sym].id
            fetched = datetime.now(timezone.utc)
            rows_15m.append({
                'asset_id': asset_id,
                'timestamp': now_minute,
                'interval': '15m',
                'open': None, 'high': None, 'low': None,
                'close': price, 'volume': None,
                'fetched_at': fetched,
            })
            rows_1d.append({
                'asset_id': asset_id,
                'timestamp': now_day,
                'interval': '1d',
                'open': daily_open.get(yf_sym), 'high': None, 'low': None,
                'close': price, 'volume': None,
                'fetched_at': fetched,
            })

        if rows_15m:
            stmt = pg_insert(Price).values(rows_15m)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_price_asset_time_interval',
                set_={'close': stmt.excluded.close, 'fetched_at': stmt.excluded.fetched_at},
            )
            db.execute(stmt)

        if rows_1d:
            stmt = pg_insert(Price).values(rows_1d)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_price_asset_time_interval',
                set_={'close': stmt.excluded.close, 'open': stmt.excluded.open, 'fetched_at': stmt.excluded.fetched_at},
            )
            db.execute(stmt)

        db.commit()
        log.info(f'FX: upserted {len(rows_15m)} 15m + {len(rows_1d)} 1d rates')

    except Exception as exc:
        db.rollback()
        log.exception('FX rate fetch failed')
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
