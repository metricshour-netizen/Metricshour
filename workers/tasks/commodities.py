"""
Commodity price ingestion — yfinance futures symbols (free, no key required).
Runs every 15 minutes during trading hours.
"""

import logging
from datetime import datetime, timezone

import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

# Maps our DB symbol → yfinance futures ticker
YFINANCE_MAP: dict[str, str] = {
    'WTI':      'CL=F',
    'BRENT':    'BZ=F',
    'NG':       'NG=F',
    'GASOLINE': 'RB=F',
    'XAUUSD':   'GC=F',
    'XAGUSD':   'SI=F',
    'XPTUSD':   'PL=F',
    'HG':       'HG=F',
    'ALI':      'ALI=F',
    'ZW':       'ZW=F',
    'ZC':       'ZC=F',
    'ZS':       'ZS=F',
    'KC':       'KC=F',
    'SB':       'SB=F',
    'CT':       'CT=F',
    'CC':       'CC=F',
    'LE':       'LE=F',
    # COAL, ZNC (Zinc), NI (Nickel) not reliably available on Yahoo Finance
}


def _fetch_commodity_prices(yf_symbols: list[str]) -> dict[str, float]:
    """Returns {yfinance_symbol: latest_close}."""
    result: dict[str, float] = {}
    try:
        if len(yf_symbols) == 1:
            df = yf.download(yf_symbols[0], period='5d', interval='1d', progress=False)
            if not df.empty:
                close = df['Close'].dropna()
                if not close.empty:
                    result[yf_symbols[0]] = float(close.iloc[-1])
        else:
            df = yf.download(
                yf_symbols, period='5d', interval='1d',
                group_by='ticker', progress=False, threads=True,
            )
            for sym in yf_symbols:
                try:
                    close = df[sym]['Close'].dropna()
                    if not close.empty:
                        result[sym] = float(close.iloc[-1])
                except (KeyError, IndexError):
                    pass
    except Exception:
        log.exception('Commodity yfinance fetch failed')
    return result


@app.task(name='tasks.commodities.fetch_commodity_prices', bind=True, max_retries=3)
def fetch_commodity_prices(self):
    db = SessionLocal()
    try:
        assets = (
            db.query(Asset)
            .filter(Asset.asset_type == AssetType.commodity, Asset.is_active == True)
            .all()
        )
        symbol_to_asset = {a.symbol: a for a in assets}

        # Build reverse map: yfinance_sym → our DB asset
        yf_to_asset = {
            yf_sym: symbol_to_asset[our_sym]
            for our_sym, yf_sym in YFINANCE_MAP.items()
            if our_sym in symbol_to_asset
        }

        if not yf_to_asset:
            return

        prices = _fetch_commodity_prices(list(yf_to_asset.keys()))
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        rows = [
            {
                'asset_id': yf_to_asset[yf_sym].id,
                'timestamp': now,
                'interval': '1d',
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
            log.info(f'Commodities: upserted {len(rows)} prices')

    except Exception as exc:
        db.rollback()
        log.exception('Commodity price fetch failed')
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
