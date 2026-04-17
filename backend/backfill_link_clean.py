"""
Fix internal links in all published blog posts:
- Normalize https://metricshour.com/ → https://www.metricshour.com/ in markdown URLs
- Strip fake hero/cover image links (including ! prefix)
- Strip lone ! lines left by image stripping
- Strip links to tickers not in STOCKS dict
- Strip path-style link texts
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.models.feed import BlogPost, BlogStatus
from app.utils.deep_links import STOCKS

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

def clean_body(body: str) -> str:
    # Normalize non-www internal links
    body = re.sub(r'\(https://metricshour\.com/', '(https://www.metricshour.com/', body)
    # Strip placeholder hero image links (with optional leading !)
    body = re.sub(r'!?\[[^\]]*\]\(hero-image-url\)', '', body, flags=re.IGNORECASE)
    body = re.sub(r'!?\[[^\]]*\]\(https?://(?:www\.)?metricshour\.com/images/[^\)]+\)', '', body, flags=re.IGNORECASE)
    # Strip blog cover CDN links in body (with optional leading !)
    body = re.sub(r'!?\[[^\]]*\]\(https://cdn\.metricshour\.com/blog-covers/[^\)]+\)', '', body, flags=re.IGNORECASE)
    # Strip any full image embeds on their own line
    body = re.sub(r'^\s*!\[[^\]]*\]\([^\)]+\)\s*$', '', body, flags=re.MULTILINE)
    # Strip lone ! left behind
    body = re.sub(r'^!\s*$', '', body, flags=re.MULTILINE)
    # Strip links to stock tickers not in our STOCKS dict
    def _check_stock_link(m):
        ticker = m.group(2).rstrip('/')
        if ticker.upper() not in STOCKS:
            return m.group(1)
        return m.group(0)
    body = re.sub(
        r'\[([^\]]+)\]\(https?://(?:www\.)?metricshour\.com/stocks/([A-Z0-9.]+)/?(?:[^\)]*)\)',
        _check_stock_link, body
    )
    # Strip path-style link texts: [/some/path](url) → keep path as text
    body = re.sub(r'\[(/[^\]]+)\]\(https?://(?:www\.)?metricshour\.com([^\)]+)\)', lambda m: m.group(2), body)
    # Collapse extra blank lines
    body = re.sub(r'\n{3,}', '\n\n', body)
    return body.strip()

fixed = 0
skipped = 0
with Session(engine) as db:
    posts = db.execute(
        select(BlogPost).where(BlogPost.status == BlogStatus.published)
    ).scalars().all()
    for post in posts:
        original = post.body or ""
        cleaned = clean_body(original)
        if cleaned != original:
            post.body = cleaned
            fixed += 1
            print(f"  Fixed post {post.id}: {post.title[:60]}")
        else:
            skipped += 1
    db.commit()

print(f"\nDone: {fixed} posts fixed, {skipped} unchanged")
