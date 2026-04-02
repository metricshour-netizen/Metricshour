"""
News router — Tiingo news API.
GET /api/news/{symbol} — latest news articles for a stock/crypto ticker.
Cached 15 min in Redis.
"""
import logging
import requests
from fastapi import APIRouter, Request

from app.config import settings
from app.limiter import limiter
from app.storage import cache_get, cache_set

log = logging.getLogger(__name__)
router = APIRouter(prefix="/news", tags=["news"])

TIINGO_NEWS_URL = "https://api.tiingo.com/tiingo/news"

_SKIP_DOMAINS = {
    'tomsguide.com', 'variety.com', 'hollywoodreporter.com',
    'rottentomatoes.com', 'imdb.com', 'ign.com', 'polygon.com',
}


@router.get("/{symbol}")
@limiter.limit("60/minute")
def get_news(request: Request, symbol: str) -> list[dict]:
    sym = symbol.upper()
    cache_key = f"api:news:{sym}:v1"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    if not settings.tiingo_api_key:
        return []

    try:
        resp = requests.get(
            TIINGO_NEWS_URL,
            params={"tickers": sym, "limit": 20},
            headers={
                "Authorization": f"Token {settings.tiingo_api_key}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()
    except Exception as exc:
        log.warning("Tiingo news fetch failed for %s: %s", sym, exc)
        return []

    articles = []
    for a in raw:
        title = a.get("title", "")
        url = a.get("url", "")
        desc = a.get("description") or ""
        source = a.get("source", "")

        if not title or not url:
            continue
        if len(desc) < 80:
            continue
        if any(d in url for d in _SKIP_DOMAINS):
            continue

        articles.append({
            "id": a.get("id"),
            "title": title,
            "url": url,
            "source": source,
            "description": desc,
            "published_at": a.get("publishedDate", ""),
        })

        if len(articles) >= 8:
            break

    cache_set(cache_key, articles, ttl_seconds=900)
    return articles
