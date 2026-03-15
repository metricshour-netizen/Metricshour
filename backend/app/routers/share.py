"""
/s/{event_id}  — social share preview endpoint.

Serves a lightweight HTML page with full OG + Twitter Card meta tags so
social crawlers (Twitterbot, LinkedIn, WhatsApp, Telegram, Discord, etc.)
get rich link previews.

Real browsers are immediately redirected to the canonical feed page via JS.
Cloudflare Bot Fight Mode blocks crawlers on the Nuxt Pages origin before
the worker even runs, so we serve previews from the FastAPI backend where
Bot Fight Mode is not active.
"""
import html as _html

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.feed import FeedEvent

router = APIRouter(tags=["share"])

_SITE_NAME = "MetricsHour"
_SITE_TWITTER = "@metricshour"
_CANONICAL_BASE = "https://metricshour.com"
_CDN_BASE = "https://cdn.metricshour.com"


def _description(body: str | None) -> str:
    fallback = "Global financial intelligence — stocks, macro, trade, crypto, FX, commodities."
    if not body:
        return fallback
    text = body.strip()
    if len(text) <= 200:
        return text
    # Break at word boundary
    trimmed = text[:200].rsplit(" ", 1)[0]
    return trimmed + "…"


def _esc(value: str) -> str:
    """HTML-escape for attribute and text content (escapes quotes too)."""
    return _html.escape(value, quote=True)


@router.get("/s/{event_id}", response_class=HTMLResponse, include_in_schema=False)
def share_preview(event_id: int, db: Session = Depends(get_db)):
    """
    OG / Twitter Card preview page for a single feed event.

    Social bots read the <meta> tags; real browsers are JS-redirected
    to the canonical feed page at metricshour.com.
    """
    event = db.execute(
        select(FeedEvent).where(FeedEvent.id == event_id)
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    canonical = f"{_CANONICAL_BASE}/feed/{event_id}"
    title = _esc(event.title.strip())
    desc = _esc(_description(event.body))
    # Use pre-generated R2 image if available, otherwise fall back to CDN path
    og_image = event.image_url or f"{_CDN_BASE}/og/feed/{event_id}.png"
    image = _esc(og_image)

    # canonical_url contains no HTML-special chars so safe to inline in <script>
    html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title} — {_SITE_NAME}</title>
  <meta name="robots" content="noindex">

  <!-- Open Graph ─────────────────────────────────────── -->
  <meta property="og:type"         content="article">
  <meta property="og:site_name"    content="{_SITE_NAME}">
  <meta property="og:url"          content="{canonical}">
  <meta property="og:title"        content="{title}">
  <meta property="og:description"  content="{desc}">
  <meta property="og:image"        content="{image}">
  <meta property="og:image:width"  content="1200">
  <meta property="og:image:height" content="630">

  <!-- Twitter Card ───────────────────────────────────── -->
  <meta name="twitter:card"        content="summary_large_image">
  <meta name="twitter:site"        content="{_SITE_TWITTER}">
  <meta name="twitter:url"         content="{canonical}">
  <meta name="twitter:title"       content="{title}">
  <meta name="twitter:description" content="{desc}">
  <meta name="twitter:image"       content="{image}">

  <!-- Redirect real browsers immediately (bots don't run JS) -->
  <script>window.location.replace("{canonical}")</script>
  <noscript><meta http-equiv="refresh" content="0;url={canonical}"></noscript>
</head>
<body style="font-family:sans-serif;color:#ccc;background:#050505;padding:2rem">
  <p>Redirecting to <a href="{canonical}" style="color:#10b981">MetricsHour Feed</a>…</p>
</body>
</html>"""

    return HTMLResponse(
        content=html_page,
        status_code=200,
        headers={"Cache-Control": "public, max-age=300, s-maxage=300"},
    )
