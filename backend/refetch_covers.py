"""
Re-fetch Unsplash covers for specific post IDs (replaces existing cover_image_url).
Run from /root/metricshour/backend/ with venv active.
"""
import sys, time
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.feed import BlogPost
from app.utils.fetch_cover import attach_cover, _keywords_from_title

# Post 148 (published Microsoft) + all current drafts
TARGET_IDS = [148, 150, 152, 154, 156, 158, 160, 163, 164, 165, 166, 167, 168, 169, 170]

db = SessionLocal()

posts = db.query(BlogPost).filter(BlogPost.id.in_(TARGET_IDS)).order_by(BlogPost.id).all()
print(f"Re-fetching covers for {len(posts)} posts...\n")

ok = fail = 0
for p in posts:
    query = _keywords_from_title(p.title)
    print(f"  [{p.id}] query={query!r}")
    print(f"        title={p.title[:70]}")
    url = attach_cover(p.id, p.title, db)
    if url:
        print(f"        ✓ {url}")
        ok += 1
    else:
        print(f"        ✗ failed")
        fail += 1
    time.sleep(1.5)

db.close()
print(f"\nDone. {ok} updated, {fail} failed.")
