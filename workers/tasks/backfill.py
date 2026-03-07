"""
Historical price backfill — 5 years of daily OHLCV for stocks, crypto, and FX.

Safe to re-run — upserts on conflict. Run once after deploy, then monthly.

Trigger manually:
    celery -A celery_app call tasks.backfill.backfill_price_history

Or schedule via beat (see celery_app.py).
"""

import logging
import time
from datetime import datetime, timezone

import yfinance as yf
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

# yfinance crypto tickers (free, multi-year history)
YFINANCE_CRYPTO_MAP: dict[str, str] = {
    'BTC':  'BTC-USD',
    'ETH':  'ETH-USD',
    'BNB':  'BNB-USD',
    'SOL':  'SOL-USD',
    'XRP':  'XRP-USD',
    'DOGE': 'DOGE-USD',
    'ADA':  'ADA-USD',
    'AVAX': 'AVAX-USD',
    'DOT':  'DOT-USD',
    'LINK': 'LINK-USD',
}

# FX symbol map — must match fx.py
YFINANCE_FX_MAP: dict[str, str] = {
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

CHUNK_SIZE = 10  # smaller chunks for 5yr downloads


def _upsert_rows(db, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = pg_insert(Price).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint='uq_price_asset_time_interval',
        set_={
            'open':   stmt.excluded.open,
            'high':   stmt.excluded.high,
            'low':    stmt.excluded.low,
            'close':  stmt.excluded.close,
            'volume': stmt.excluded.volume,
        },
    )
    db.execute(stmt)
    return len(rows)


def _backfill_stocks(db, assets: list) -> int:
    symbol_to_asset = {a.symbol: a for a in assets}
    symbols = list(symbol_to_asset.keys())
    total = 0

    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i:i + CHUNK_SIZE]
        try:
            if len(chunk) == 1:
                raw = yf.download(chunk[0], period='5y', interval='1d',
                                  progress=False, auto_adjust=True)
                frames = {chunk[0]: raw}
            else:
                raw = yf.download(chunk, period='5y', interval='1d',
                                  group_by='ticker', progress=False,
                                  threads=True, auto_adjust=True)
                frames = {sym: raw[sym] for sym in chunk}

            rows = []
            for sym, df in frames.items():
                asset = symbol_to_asset.get(sym)
                if asset is None or df.empty:
                    continue
                df = df.dropna(subset=['Close'])
                for ts, r in df.iterrows():
                    rows.append({
                        'asset_id':  asset.id,
                        'timestamp': ts.to_pydatetime().replace(tzinfo=timezone.utc),
                        'interval':  '1d',
                        'open':      float(r['Open'])   if r.get('Open')   is not None else None,
                        'high':      float(r['High'])   if r.get('High')   is not None else None,
                        'low':       float(r['Low'])    if r.get('Low')    is not None else None,
                        'close':     float(r['Close']),
                        'volume':    float(r['Volume']) if r.get('Volume') is not None else None,
                    })

            n = _upsert_rows(db, rows)
            db.commit()
            total += n
            log.info(f'Stocks backfill chunk {i}–{i+len(chunk)}: {n} rows')
        except Exception:
            db.rollback()
            log.exception(f'Stocks backfill chunk {i}–{i+len(chunk)} failed')

        time.sleep(1)

    return total


def _backfill_crypto(db, assets: list) -> int:
    symbol_to_asset = {a.symbol: a for a in assets}
    yf_to_asset = {
        yf_sym: symbol_to_asset[our_sym]
        for our_sym, yf_sym in YFINANCE_CRYPTO_MAP.items()
        if our_sym in symbol_to_asset
    }
    if not yf_to_asset:
        return 0

    yf_syms = list(yf_to_asset.keys())
    total = 0

    for i in range(0, len(yf_syms), CHUNK_SIZE):
        chunk = yf_syms[i:i + CHUNK_SIZE]
        try:
            if len(chunk) == 1:
                raw = yf.download(chunk[0], period='5y', interval='1d',
                                  progress=False, auto_adjust=True)
                frames = {chunk[0]: raw}
            else:
                raw = yf.download(chunk, period='5y', interval='1d',
                                  group_by='ticker', progress=False,
                                  threads=True, auto_adjust=True)
                frames = {sym: raw[sym] for sym in chunk}

            rows = []
            for yf_sym, df in frames.items():
                asset = yf_to_asset.get(yf_sym)
                if asset is None or df.empty:
                    continue
                df = df.dropna(subset=['Close'])
                for ts, r in df.iterrows():
                    rows.append({
                        'asset_id':  asset.id,
                        'timestamp': ts.to_pydatetime().replace(tzinfo=timezone.utc),
                        'interval':  '1d',
                        'open':      float(r['Open'])   if r.get('Open')   is not None else None,
                        'high':      float(r['High'])   if r.get('High')   is not None else None,
                        'low':       float(r['Low'])    if r.get('Low')    is not None else None,
                        'close':     float(r['Close']),
                        'volume':    float(r['Volume']) if r.get('Volume') is not None else None,
                    })

            n = _upsert_rows(db, rows)
            db.commit()
            total += n
            log.info(f'Crypto backfill chunk {i}–{i+len(chunk)}: {n} rows')
        except Exception:
            db.rollback()
            log.exception(f'Crypto backfill chunk {i}–{i+len(chunk)} failed')

        time.sleep(1)

    return total


def _backfill_fx(db, assets: list) -> int:
    symbol_to_asset = {a.symbol: a for a in assets}
    yf_to_asset = {
        yf_sym: symbol_to_asset[our_sym]
        for our_sym, yf_sym in YFINANCE_FX_MAP.items()
        if our_sym in symbol_to_asset
    }
    if not yf_to_asset:
        return 0

    yf_syms = list(yf_to_asset.keys())
    total = 0

    try:
        if len(yf_syms) == 1:
            raw = yf.download(yf_syms[0], period='5y', interval='1d',
                              progress=False, auto_adjust=True)
            frames = {yf_syms[0]: raw}
        else:
            raw = yf.download(yf_syms, period='5y', interval='1d',
                              group_by='ticker', progress=False,
                              threads=True, auto_adjust=True)
            frames = {sym: raw[sym] for sym in yf_syms}

        rows = []
        for yf_sym, df in frames.items():
            asset = yf_to_asset.get(yf_sym)
            if asset is None or df.empty:
                continue
            df = df.dropna(subset=['Close'])
            for ts, r in df.iterrows():
                rows.append({
                    'asset_id':  asset.id,
                    'timestamp': ts.to_pydatetime().replace(tzinfo=timezone.utc),
                    'interval':  '1d',
                    'open':      float(r['Open'])  if r.get('Open')  is not None else None,
                    'high':      float(r['High'])  if r.get('High')  is not None else None,
                    'low':       float(r['Low'])   if r.get('Low')   is not None else None,
                    'close':     float(r['Close']),
                    'volume':    None,
                })

        total = _upsert_rows(db, rows)
        db.commit()
        log.info(f'FX backfill: {total} rows')
    except Exception:
        db.rollback()
        log.exception('FX backfill failed')

    return total


@app.task(name='tasks.backfill.backfill_price_history', bind=True)
def backfill_price_history(self):
    """
    Backfill 5 years of daily price history for all active assets.
    Upserts on conflict — safe to re-run. Scheduled monthly on the 2nd at 1am.
    """
    db = SessionLocal()
    try:
        all_assets = db.query(Asset).filter(Asset.is_active == True).all()
        stocks = [a for a in all_assets if a.asset_type == AssetType.stock]
        crypto = [a for a in all_assets if a.asset_type == AssetType.crypto]
        fx     = [a for a in all_assets if a.asset_type == AssetType.fx]

        log.info(f'Backfill starting: {len(stocks)} stocks, {len(crypto)} crypto, {len(fx)} FX')

        s = _backfill_stocks(db, stocks)
        c = _backfill_crypto(db, crypto)
        f = _backfill_fx(db, fx)

        log.info(f'Backfill complete — stocks: {s}, crypto: {c}, FX: {f}')
        return {'stocks': s, 'crypto': c, 'fx': f}

    except Exception as exc:
        db.rollback()
        log.exception('Price history backfill failed')
        raise
    finally:
        db.close()
