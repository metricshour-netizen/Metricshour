"""
Auto-fetch a cover image from Unsplash for a blog post.

Usage:
    from app.utils.fetch_cover import attach_cover
    url = attach_cover(post_id, post_title, db)  # returns CDN URL or None
"""
import re
import uuid
import logging
import httpx

from app.config import settings
from app.storage import r2_upload, r2_public_url

log = logging.getLogger(__name__)

# Words that add no search value
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "not", "no", "nor",
    "so", "yet", "both", "either", "neither", "each", "few", "more", "most",
    "other", "some", "such", "than", "too", "very", "just", "about", "above",
    "into", "through", "during", "before", "after", "between", "against",
    "how", "what", "which", "who", "when", "where", "why", "your", "its",
    "their", "our", "my", "his", "her", "us", "we", "they", "it", "this",
    "that", "these", "those", "any", "all", "both", "half", "vs",
}

# Map common financial topic words → better Unsplash search queries
_TOPIC_MAP = {
    "gdp": "economy growth chart",
    "tariff": "trade war shipping container",
    "tariffs": "trade war shipping container",
    "fed": "federal reserve building",
    "federal reserve": "federal reserve building",
    "fomc": "federal reserve meeting",
    "ecb": "european central bank",
    "boe": "bank of england",
    "boj": "bank of japan",
    "inflation": "inflation economy prices",
    "interest rate": "interest rate finance",
    "crypto": "cryptocurrency bitcoin",
    "bitcoin": "bitcoin cryptocurrency",
    "gold": "gold bars finance",
    "oil": "oil refinery energy",
    "stock": "stock market trading",
    "stocks": "stock market trading",
    "s&p 500": "stock market wall street",
    "sp500": "stock market wall street",
    "china": "china economy skyline",
    "india": "india economy city",
    "europe": "europe finance city",
    "trade": "shipping containers port trade",
    "earnings": "financial earnings report",
    "revenue": "business revenue finance",
    "pharma": "pharmaceutical medicine lab",
    "semiconductor": "semiconductor chip technology",
    "luxury": "luxury brand fashion",
    "automotive": "car factory automotive",
    "casino": "casino macau gaming",
    "reshoring": "factory manufacturing usa",
    "nearshoring": "mexico factory nearshoring",
    "vietnam": "vietnam manufacturing factory",
    "yield curve": "bond yield curve finance",
    "screener": "stock market data analysis",
    "nigeria": "nigeria oil energy stock exchange",
    "seplat": "nigeria oil energy stock exchange",
    "nse": "nigeria stock exchange finance",
    "africa": "africa economy business city",
    "opec": "oil refinery energy production",
    "energy": "energy industry power plant",
    "bank": "bank finance building",
    "merger": "business merger finance deal",
    "acquisition": "business acquisition deal finance",
    "ipo": "stock market ipo listing",
    "debt": "finance debt economy",
    "bonds": "bonds finance treasury",
    "currency": "currency exchange finance",
    "dollar": "dollar currency finance",
    "euro": "euro currency europe finance",
    "japan": "japan economy tokyo finance",
    "germany": "germany economy frankfurt finance",
    "uk": "united kingdom london finance",
    "brazil": "brazil economy finance city",
    "mexico": "mexico economy finance city",
    "portfolio": "investment portfolio finance",
    "market cap": "stock market capitalization finance",
}


def _keywords_from_title(title: str) -> str:
    """Extract 2-3 search keywords from a blog post title."""
    title_lower = title.lower()

    # Check topic map for known phrases first (longest match wins)
    for phrase in sorted(_TOPIC_MAP, key=len, reverse=True):
        if phrase in title_lower:
            return _TOPIC_MAP[phrase]

    # Fall back to stripping stopwords and taking top 3 meaningful words
    words = re.sub(r"[^a-z0-9 ]", " ", title_lower).split()
    keywords = [w for w in words if w not in _STOPWORDS and len(w) > 3][:3]
    return " ".join(keywords) if keywords else "finance economy"


def fetch_unsplash_image(query: str) -> bytes | None:
    """Query Unsplash and return raw image bytes of the first result (regular size)."""
    if not settings.unsplash_access_key:
        log.warning("fetch_cover: UNSPLASH_ACCESS_KEY not set")
        return None

    try:
        resp = httpx.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {settings.unsplash_access_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            log.warning("fetch_cover: no Unsplash results for query %r", query)
            return None

        # Use 'regular' size (~1080px wide) — good balance of quality vs size
        img_url = results[0]["urls"]["regular"]
        img_resp = httpx.get(img_url, timeout=20, follow_redirects=True)
        img_resp.raise_for_status()
        return img_resp.content

    except Exception as exc:
        log.error("fetch_cover: Unsplash fetch failed for %r: %s", query, exc)
        return None


def attach_cover(post_id: int, post_title: str, db) -> str | None:
    """
    Fetch an Unsplash image for post_title, upload to R2, update post.cover_image_url.
    Returns the CDN URL on success, None on failure.
    db must be an open SQLAlchemy Session.
    """
    from app.models.feed import BlogPost

    query = _keywords_from_title(post_title)
    log.info("fetch_cover: post %d — query %r", post_id, query)

    image_bytes = fetch_unsplash_image(query)
    if not image_bytes:
        return None

    key = f"blog-covers/{post_id}/{uuid.uuid4().hex}.jpg"
    r2_upload(key, image_bytes, content_type="image/jpeg",
              cache_control="public, max-age=2592000, s-maxage=2592000")
    url = r2_public_url(key)

    post = db.get(BlogPost, post_id)
    if post:
        post.cover_image_url = url
        db.commit()
        log.info("fetch_cover: post %d cover set → %s", post_id, url)

    return url
