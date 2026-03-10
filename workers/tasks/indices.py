"""
Index, ETF, and bond yield price ingestion — yfinance.
Runs every 30 minutes during market hours.

Covers assets that the stock task doesn't:
  - Global equity indices (DJI, SPX, DAX, etc.)
  - ETFs (SPY, QQQ, GLD, etc.)
  - US Treasury bond yields (US02Y, US05Y, US10Y, US30Y)
  - Bond ETFs (HYG, LQD, EMB)
"""

import logging
from datetime import datetime, timezone

import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

# yfinance symbol map: our DB symbol → Yahoo Finance ticker
# Indices need the ^ prefix; some have different ticker codes
INDEX_YF_MAP: dict[str, str] = {
    'ASX200':  '^AXJO',
    'CAC':     '^FCHI',
    'DAX':     '^GDAXI',
    'DJI':     '^DJI',
    'HSI':     '^HSI',
    'IBEX':    '^IBEX',
    'KOSPI':   '^KS11',
    'MSCIEM':  'VWO',     # MSCI EM — Vanguard EM ETF proxy (not in our ETF list)
    'MSCIW':   'VT',      # MSCI World — Vanguard Total World ETF proxy (not in our ETF list)
    'NDX':     '^NDX',
    'NKY':     '^N225',
    'RUT':     '^RUT',
    'SENSEX':  '^BSESN',
    'SHCOMP':  '000001.SS',
    'SMI':     '^SSMI',
    'SPX':     '^GSPC',
    'UKX':     '^FTSE',
    'VIX':     '^VIX',
}

# US Treasury yield symbols on Yahoo Finance
# ^TNX = 10Y, ^FVX = 5Y, ^TYX = 30Y, ^IRX = 13-week T-bill
BOND_YF_MAP: dict[str, str] = {
    'US02Y':  '^IRX',   # closest proxy (3m T-bill, not exact but directionally correct)
    'US05Y':  '^FVX',
    'US10Y':  '^TNX',
    'US30Y':  '^TYX',
}

MAX_SPIKE_PCT = 20.0  # indices/ETFs can move more than stocks; 20% is a safe guard


def _fetch_yf_prices(yf_symbols: list[str]) -> dict[str, float]:
    """Fetch latest close prices for a list of Yahoo Finance tickers."""
    result: dict[str, float] = {}
    CHUNK = 40
    for i in range(0, len(yf_symbols), CHUNK):
        chunk = yf_symbols[i:i + CHUNK]
        try:
            if len(chunk) == 1:
                df = yf.download(chunk[0], period='5d', interval='1d', progress=False)
                if not df.empty:
                    close = df['Close'].dropna()
                    if not close.empty:
                        result[chunk[0]] = float(close.iloc[-1])
            else:
                df = yf.download(chunk, period='5d', interval='1d',
                                 group_by='ticker', progress=False, threads=True)
                for sym in chunk:
                    try:
                        close = df[sym]['Close'].dropna()
                        if not close.empty:
                            result[sym] = float(close.iloc[-1])
                    except (KeyError, IndexError):
                        pass
        except Exception:
            log.exception(f'yfinance batch failed for chunk starting at {i}')
    return result


def _upsert_prices(db, symbol_to_asset: dict, prices: dict[str, float], now: datetime) -> int:
    """Upsert price rows with spike guard."""
    asset_ids = [symbol_to_asset[s].id for s in prices if s in symbol_to_asset]
    last_prices: dict[int, float] = {}
    for aid in asset_ids:
        last = db.query(Price.close).filter(
            Price.asset_id == aid
        ).order_by(Price.timestamp.desc()).first()
        if last:
            last_prices[aid] = last[0]

    rows = []
    for sym, price in prices.items():
        if sym not in symbol_to_asset:
            continue
        asset = symbol_to_asset[sym]
        if asset.id in last_prices and last_prices[asset.id] > 0:
            chg = abs((price - last_prices[asset.id]) / last_prices[asset.id]) * 100
            if chg > MAX_SPIKE_PCT:
                log.warning('Spike rejected: %s new=%.4f prev=%.4f chg=%.1f%%',
                            sym, price, last_prices[asset.id], chg)
                continue
        rows.append({
            'asset_id': asset.id,
            'timestamp': now,
            'interval': '1d',
            'open': None, 'high': None, 'low': None,
            'close': price,
            'volume': None,
        })
    if not rows:
        return 0
    stmt = pg_insert(Price).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint='uq_price_asset_time_interval',
        set_={'close': stmt.excluded.close},
    )
    db.execute(stmt)
    return len(rows)


@app.task(name='tasks.indices.fetch_index_etf_prices', bind=True, max_retries=3)
def fetch_index_etf_prices(self):
    """Fetch prices for indices, ETFs, and bond yields."""
    db = SessionLocal()
    try:
        assets = (
            db.query(Asset)
            .filter(
                Asset.asset_type.in_([AssetType.index, AssetType.etf, AssetType.bond]),
                Asset.is_active == True,
            )
            .all()
        )
        symbol_to_asset = {a.symbol: a for a in assets}
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        # Build yfinance symbol → DB symbol reverse map
        # For ETFs and bond ETFs (HYG, LQD, EMB etc.) the symbol is the same
        yf_to_db: dict[str, str] = {}
        yf_symbols: list[str] = []

        for db_sym in symbol_to_asset:
            asset = symbol_to_asset[db_sym]
            if asset.asset_type == AssetType.index and db_sym in INDEX_YF_MAP:
                yf_sym = INDEX_YF_MAP[db_sym]
                yf_to_db[yf_sym] = db_sym
                yf_symbols.append(yf_sym)
            elif asset.asset_type == AssetType.bond and db_sym in BOND_YF_MAP:
                yf_sym = BOND_YF_MAP[db_sym]
                yf_to_db[yf_sym] = db_sym
                yf_symbols.append(yf_sym)
            elif asset.asset_type in (AssetType.etf, AssetType.bond):
                # ETFs and bond ETFs use their ticker directly
                yf_to_db[db_sym] = db_sym
                yf_symbols.append(db_sym)

        if not yf_symbols:
            log.info('No index/ETF/bond assets to fetch')
            return

        raw_prices = _fetch_yf_prices(yf_symbols)

        # Remap yf symbols back to DB symbols
        db_prices: dict[str, float] = {}
        for yf_sym, price in raw_prices.items():
            db_sym = yf_to_db.get(yf_sym)
            if db_sym:
                db_prices[db_sym] = price

        count = _upsert_prices(db, symbol_to_asset, db_prices, now)
        db.commit()
        log.info('Indices/ETFs/Bonds: upserted %d/%d prices', count, len(yf_symbols))

    except Exception as exc:
        db.rollback()
        log.exception('Index/ETF/bond price fetch failed')
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
