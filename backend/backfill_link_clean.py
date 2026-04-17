"""
Fix internal links in all published blog posts:
- Normalize https://metricshour.com/ → https://www.metricshour.com/ in markdown URLs
- Strip fake hero/cover image links embedded in body by AI
- Strip blog-cover CDN links in body text
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

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

def clean_body(body: str) -> str:
    # Normalize non-www internal links
    body = re.sub(r'\(https://metricshour\.com/', '(https://www.metricshour.com/', body)
    # Strip placeholder hero image links
    body = re.sub(r'\[[^\]]*\]\(hero-image-url\)', '', body, flags=re.IGNORECASE)
    body = re.sub(r'\[[^\]]*\]\(https?://(?:www\.)?metricshour\.com/images/[^\)]+\)', '', body, flags=re.IGNORECASE)
    # Strip blog cover CDN links in body
    body = re.sub(r'\[[^\]]*\]\(https://cdn\.metricshour\.com/blog-covers/[^\)]+\)', '', body, flags=re.IGNORECASE)
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
