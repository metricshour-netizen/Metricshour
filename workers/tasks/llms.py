"""
tasks/llms.py — Daily regeneration of /llms-full.txt

Pulls all published blog posts from the DB and writes a machine-readable
full-content file at frontend/public/llms-full.txt following the llmstxt.org spec.
Runs daily at 02:30 UTC via Celery beat.
"""
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from celery_app import app
from sqlalchemy import text
from app.database import SessionLocal

log = logging.getLogger(__name__)

BASE_URL = "https://metricshour.com"
OUT_PATH = Path(__file__).parents[2] / "frontend" / "public" / "llms-full.txt"


def _strip_markdown(text: str) -> str:
    """Strip markdown syntax, keeping clean prose for LLM consumption."""
    # Remove markdown links but keep link text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove images
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)
    # Remove headers markers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', text)
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Remove blockquote markers
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    # Collapse excess blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def generate_llms_full() -> int:
    """Generate llms-full.txt. Returns number of posts written."""
    db = SessionLocal()
    try:
        posts = db.execute(text(
            "SELECT title, slug, body, excerpt, published_at, category "
            "FROM blog_posts WHERE status='published' "
            "ORDER BY published_at DESC"
        )).fetchall()
    finally:
        db.close()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "# MetricsHour",
        "",
        "> MetricsHour is a financial intelligence platform that maps geographic revenue exposure "
        "for stocks, tracks macro data for 250 countries, and surfaces bilateral trade flows "
        "between 2,700+ country pairs. Built for investors who need to understand where companies "
        "actually earn their money.",
        "",
        f"> Generated: {now} | Posts: {len(posts)} | Source: {BASE_URL}/llms-full.txt",
        "",
        "---",
        "",
    ]

    for post in posts:
        title, slug, body, excerpt, published_at, category = post
        url = f"{BASE_URL}/blog/{slug}"
        date_str = published_at.strftime("%Y-%m-%d") if published_at else "unknown"
        cat_str = f" | Category: {category}" if category else ""

        lines.append(f"## {title}")
        lines.append(f"URL: {url}")
        lines.append(f"Date: {date_str}{cat_str}")
        lines.append("")
        if excerpt:
            lines.append(_strip_markdown(excerpt))
            lines.append("")
        if body:
            lines.append(_strip_markdown(body))
        lines.append("")
        lines.append("---")
        lines.append("")

    content = "\n".join(lines)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(content, encoding="utf-8")
    log.info("llms-full.txt written: %d posts, %d KB", len(posts), len(content) // 1024)
    return len(posts)


@app.task(name="tasks.llms.generate_llms_full", bind=True, max_retries=2)
def generate_llms_full_task(self):
    try:
        count = generate_llms_full()
        return {"posts": count}
    except Exception as exc:
        log.error("generate_llms_full failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)
