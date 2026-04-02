"""
One-time backfill: scan all published blog post bodies and populate
related_asset_ids + related_country_ids using the same detect_entities() logic.
Also updates the linked FeedEvent on each post.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select
from app.database import SessionLocal
from app.models.feed import BlogPost, BlogStatus, FeedEvent
from app.models.asset import Asset
from app.models.country import Country
from app.utils.deep_links import detect_entities

db = SessionLocal()

# Build lookup maps once
asset_rows = db.execute(select(Asset.id, Asset.symbol).where(Asset.is_active == True)).all()
ticker_to_id = {r.symbol: r.id for r in asset_rows}

country_rows = db.execute(select(Country.id, Country.code)).all()
code_to_id = {r.code: r.id for r in country_rows}

posts = db.execute(
    select(BlogPost).where(BlogPost.status == BlogStatus.published)
).scalars().all()

updated = 0
for post in posts:
    tickers, codes = detect_entities(post.body or "")

    asset_ids = list(dict.fromkeys(
        list(post.related_asset_ids or []) +
        [ticker_to_id[t] for t in tickers if t in ticker_to_id]
    ))
    country_ids = list(dict.fromkeys(
        list(post.related_country_ids or []) +
        [code_to_id[c.upper()] for c in codes if c.upper() in code_to_id]
    ))

    changed = (asset_ids != list(post.related_asset_ids or []) or
               country_ids != list(post.related_country_ids or []))

    if changed:
        post.related_asset_ids = asset_ids
        post.related_country_ids = country_ids

        # Sync FeedEvent
        if post.feed_event_id:
            event = db.get(FeedEvent, post.feed_event_id)
            if event:
                event.related_asset_ids = asset_ids
                event.related_country_ids = country_ids

        updated += 1
        print(f"  [{post.id}] {post.title[:60]}")
        print(f"       assets: {asset_ids[:8]}{'...' if len(asset_ids)>8 else ''}")
        print(f"       countries: {country_ids[:8]}{'...' if len(country_ids)>8 else ''}")

db.commit()
db.close()
print(f"\nDone — updated {updated}/{len(posts)} posts")
