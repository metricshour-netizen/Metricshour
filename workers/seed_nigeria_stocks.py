"""
Seed Nigerian stocks — runs once to insert assets into the DB.

LSE-listed (live prices via yfinance):
  SEPL.L  — Seplat Energy Plc
  AAF.L   — Airtel Africa Plc

NGX-listed (Nigerian Exchange Group, prices unavailable via free APIs):
  DANGCEM, MTNN, ZENITHBANK, GTCO, ACCESSCORP, FBNH, NB,
  NESTLE, STANBIC, BUAFOODS, BUACEMENT, WAPCO, DANGSUGAR
"""

import sys
sys.path.insert(0, '/root/metricshour/backend')
sys.path.insert(0, '/root/metricshour/workers')

from dotenv import load_dotenv
load_dotenv('/root/metricshour/backend/.env')

from app.database import SessionLocal
from app.models.asset import Asset, AssetType
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

db = SessionLocal()

# Nigeria country_id = 179
NG = 179

STOCKS = [
    # LSE-listed — yfinance symbol = symbol (SEPL.L, AAF.L)
    dict(
        symbol='SEPL.L', name='Seplat Energy Plc', asset_type='stock',
        exchange='LSE', currency='GBp', sector='Energy',
        industry='Oil & Gas Exploration & Production',
        country_id=NG, is_active=True,
    ),
    dict(
        symbol='AAF.L', name='Airtel Africa Plc', asset_type='stock',
        exchange='LSE', currency='GBp', sector='Communication Services',
        industry='Wireless Telecommunications Services',
        country_id=NG, is_active=True,
    ),
    # NGX-listed
    dict(
        symbol='DANGCEM', name='Dangote Cement Plc', asset_type='stock',
        exchange='NGX', currency='NGN', sector='Materials',
        industry='Construction Materials',
        country_id=NG, is_active=True,
    ),
    dict(
        symbol='MTNN', name='MTN Nigeria Communications Plc', asset_type='stock',
        exchange='NGX', currency='NGN', sector='Communication Services',
        industry='Wireless Telecommunications Services',
        country_id=NG, is_active=True,
    ),
    dict(
        symbol='ZENITHBANK', name='Zenith Bank Plc', asset_type='stock',
        exchange='NGX', currency='NGN', sector='Financials',
        industry='Commercial Banking',
        country_id=NG, is_active=True,
    ),
    dict(
        symbol='GTCO', name='Guaranty Trust Holding Company Plc', asset_type='stock',
        exchange='NGX', currency='NGN', sector='Financials',
        industry='Commercial Banking',
        country_id=NG, is_active=True,
    ),
    dict(
        symbol='ACCESSCORP', name='Access Holdings Plc', asset_type='stock',
        exchange='NGX', currency='NGN', sector='Financials',
        industry='Commercial Banking',
        country_id=NG, is_active=True,
    ),
    dict(
        symbol='FBNH', name='FBN Holdings Plc', asset_type='stock',
        exchange='NGX', currency='NGN', sector='Financials',
        industry='Commercial Banking',
        country_id=NG, is_active=True,
    ),
    dict(
        symbol='NB', name='Nigerian Breweries Plc', asset_type='stock',
        exchange='NGX', currency='NGN', sector='Consumer Staples',
        industry='Brewers',
        country_id=NG, is_active=True,
    ),
    dict(
        symbol='NESTLE', name='Nestle Nigeria Plc', asset_type='stock',
        exchange='NGX', currency='NGN', sector='Consumer Staples',
        industry='Packaged Foods & Meats',
        country_id=NG, is_active=True,
    ),
    dict(
        symbol='STANBIC', name='Stanbic IBTC Holdings Plc', asset_type='stock',
        exchange='NGX', currency='NGN', sector='Financials',
        industry='Commercial Banking',
        country_id=NG, is_active=True,
    ),
    dict(
        symbol='BUAFOODS', name='BUA Foods Plc', asset_type='stock',
        exchange='NGX', currency='NGN', sector='Consumer Staples',
        industry='Packaged Foods & Meats',
        country_id=NG, is_active=True,
    ),
    dict(
        symbol='BUACEMENT', name='BUA Cement Plc', asset_type='stock',
        exchange='NGX', currency='NGN', sector='Materials',
        industry='Construction Materials',
        country_id=NG, is_active=True,
    ),
    dict(
        symbol='WAPCO', name='Lafarge Africa Plc', asset_type='stock',
        exchange='NGX', currency='NGN', sector='Materials',
        industry='Construction Materials',
        country_id=NG, is_active=True,
    ),
    dict(
        symbol='DANGSUGAR', name='Dangote Sugar Refinery Plc', asset_type='stock',
        exchange='NGX', currency='NGN', sector='Consumer Staples',
        industry='Agricultural Products',
        country_id=NG, is_active=True,
    ),
]

inserted = 0
skipped = 0

for s in STOCKS:
    existing = db.execute(
        select(Asset).where(Asset.symbol == s['symbol'], Asset.exchange == s['exchange'])
    ).scalar_one_or_none()

    if existing:
        print(f'  SKIP  {s["symbol"]} ({s["exchange"]}) — already exists')
        skipped += 1
        continue

    asset = Asset(
        symbol=s['symbol'],
        name=s['name'],
        asset_type=AssetType.stock,
        exchange=s['exchange'],
        currency=s['currency'],
        sector=s['sector'],
        industry=s['industry'],
        country_id=s['country_id'],
        is_active=s['is_active'],
    )
    db.add(asset)
    print(f'  ADD   {s["symbol"]} — {s["name"]} ({s["exchange"]})')
    inserted += 1

db.commit()
db.close()
print(f'\nDone: {inserted} inserted, {skipped} skipped.')
