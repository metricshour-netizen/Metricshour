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
from tasks.market_hours import is_commodity_market_open

# Max single-run price change before a tick is rejected as bad source data.
# yfinance futures occasionally return stale weekend prices or bad ticks.
MAX_COMMODITY_SPIKE_PCT = 12.0

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
    'ZNC':      'ZNC=F',   # Zinc futures (CME)
    'ZW':       'ZW=F',
    'ZC':       'ZC=F',
    'ZS':       'ZS=F',
    'KC':       'KC=F',
    'SB':       'SB=F',
    'CT':       'CT=F',
    'CC':       'CC=F',
    'LE':       'LE=F',
    'PALM':     'FCPO=F',  # Bursa Malaysia Crude Palm Oil futures (MYR/MT) — actual palm oil
    # COAL: no CME/NYMEX futures on yfinance (ICE/SGX-only) — asset disabled in seeder
    # NI (Nickel): LME-only, no yfinance ticker — asset disabled in seeder
}


def _fetch_commodity_prices(yf_symbols: list[str]) -> dict[str, float]:
    """Returns {yfinance_symbol: latest_close}."""
    result: dict[str, float] = {}
    try:
        # Always use multi-ticker path so df[sym] gives a clean sub-DataFrame
        tickers = yf_symbols if len(yf_symbols) > 1 else yf_symbols * 2
        df = yf.download(
            tickers, period='5d', interval='1d',
            group_by='ticker', progress=False, threads=True,
        )
        if df.empty:
            return result
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
        now_utc = datetime.now(timezone.utc)
        if not is_commodity_market_open(now_utc):
            log.debug('Commodity fetch skipped — futures market closed')
            return

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

        # Build last-known prices for spike guard
        last_prices: dict[int, float] = {}
        for asset in yf_to_asset.values():
            last = (
                db.query(Price.close)
                .filter(Price.asset_id == asset.id)
                .order_by(Price.timestamp.desc())
                .first()
            )
            if last:
                last_prices[asset.id] = last[0]

        rows = []
        for yf_sym, price in prices.items():
            if yf_sym not in yf_to_asset:
                continue
            asset = yf_to_asset[yf_sym]
            if asset.id in last_prices and last_prices[asset.id] > 0:
                chg = abs((price - last_prices[asset.id]) / last_prices[asset.id]) * 100
                if chg > MAX_COMMODITY_SPIKE_PCT:
                    log.warning(
                        'Commodity spike rejected: %s new=%.4f prev=%.4f chg=%.1f%%',
                        asset.symbol, price, last_prices[asset.id], chg,
                    )
                    continue
            rows.append({
                'asset_id': asset.id,
                'timestamp': now,
                'interval': '1d',
                'open': None, 'high': None, 'low': None,
                'close': price,
                'volume': None,
            })

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
