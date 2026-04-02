"""
One-time import: seed China A-shares (SHG + SHE) from Tiingo supported_tickers CSV.
Imports active stocks (endDate >= 2026 or blank).
Run: python import_china_stocks.py
"""
import os, sys, io, zipfile, csv, requests
sys.path.insert(0, '/root/metricshour/backend')
sys.path.insert(0, '/root/metricshour/workers')

from dotenv import load_dotenv
load_dotenv('/root/metricshour/backend/.env')

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.database import SessionLocal
from app.models.asset import Asset, AssetType

TIINGO_KEY = os.environ.get('TIINGO_API_KEY', '')
CSV_URL = 'https://apimedia.tiingo.com/docs/tiingo/daily/supported_tickers.zip'

print('Downloading Tiingo supported tickers...')
resp = requests.get(CSV_URL, timeout=60)
resp.raise_for_status()

with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
    csv_name = [n for n in z.namelist() if n.endswith('.csv')][0]
    with z.open(csv_name) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
        rows = list(reader)

print(f'Total tickers in CSV: {len(rows)}')

# Filter for active SHG and SHE stocks
china = [
    r for r in rows
    if r.get('exchange') in ('SHG', 'SHE')
    and r.get('assetType') == 'Stock'
    and (not r.get('endDate') or r.get('endDate', '') >= '2026')
]
print(f'Active China A-shares: {len(china)}')

# Sort: Shanghai (SHG) first (larger caps), then Shenzhen (SHE)
# Within each, sort by startDate ascending (oldest = most established)
china.sort(key=lambda r: (0 if r['exchange'] == 'SHG' else 1, r.get('startDate', '9999')))

db = SessionLocal()

# Get existing symbols to avoid duplicates
existing = {a.symbol for a in db.execute(
    select(Asset).where(Asset.exchange.in_(['SHG', 'SHE']))
).scalars().all()}
print(f'Already in DB: {len(existing)}')

to_insert = [r for r in china if r['ticker'] not in existing]
print(f'To insert: {len(to_insert)}')

inserted = 0
for r in to_insert:
    try:
        asset = Asset(
            symbol=r['ticker'],
            name=r['ticker'],  # Tiingo CSV doesn't include company names
            asset_type=AssetType.stock,
            exchange=r['exchange'],
            currency=r.get('priceCurrency', 'CNY') or 'CNY',
            is_active=True,
        )
        db.add(asset)
        db.flush()
        inserted += 1
        if inserted % 500 == 0:
            db.commit()
            print(f'  Committed {inserted}...')
    except Exception as e:
        db.rollback()
        print(f'  Error inserting {r["ticker"]}: {e}')

db.commit()
print(f'Done. Inserted {inserted} China A-shares.')
db.close()
