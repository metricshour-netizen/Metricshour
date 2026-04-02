"""
One-shot backfill: fetch Unsplash cover images for all published posts missing cover_image_url.
Run from /root/metricshour/backend/ with venv active.
"""
import sys, time
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.feed import BlogPost, BlogStatus
from app.utils.fetch_cover import attach_cover

db = SessionLocal()

posts = (
    db.query(BlogPost)
    .filter(
        BlogPost.status == BlogStatus.published,
        BlogPost.cover_image_url.is_(None),
    )
    .order_by(BlogPost.id)
    .all()
)

print(f"Found {len(posts)} published posts without covers.")

ok = 0
fail = 0

for p in posts:
    url = attach_cover(p.id, p.title, db)
    if url:
        print(f"  [{p.id}] ✓  {p.title[:60]}")
        ok += 1
    else:
        print(f"  [{p.id}] ✗  {p.title[:60]}")
        fail += 1
    # Unsplash free tier: 50 req/hour → ~1.2s/req safe
    time.sleep(1.5)

db.close()
print(f"\nDone. {ok} covers set, {fail} failed.")
