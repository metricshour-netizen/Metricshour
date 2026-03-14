"""
Central bank RSS/news feed parser — rate decisions → FeedEvents.
Sources: Federal Reserve, ECB, Bank of England, Bank of Japan.
Runs daily at 8am UTC.

No API key required. Commercial use permitted (public press releases).
"""

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.feed import FeedEvent

log = logging.getLogger(__name__)

# Central bank RSS/Atom/press feeds
FEEDS = [
    {
        "name": "Federal Reserve",
        "country_code": "US",
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "rate_keywords": ["federal funds rate", "interest rate", "fomc", "rate decision",
                          "basis points", "unchanged", "rate increase", "rate decrease"],
    },
    {
        "name": "European Central Bank",
        "country_code": "EU",
        "url": "https://www.ecb.europa.eu/rss/press.html",
        "rate_keywords": ["key interest rates", "deposit facility", "basis points",
                          "rate decision", "monetary policy decision", "interest rate"],
    },
    {
        "name": "Bank of England",
        "country_code": "GB",
        "url": "https://www.bankofengland.co.uk/rss/news",
        "rate_keywords": ["bank rate", "interest rate", "monetary policy committee",
                          "basis points", "rate decision", "mpc"],
    },
    {
        "name": "Bank of Japan",
        "country_code": "JP",
        "url": "https://www.boj.or.jp/en/rss/whatsnew.xml",
        "rate_keywords": ["policy interest rate", "short-term interest rate", "yield curve",
                          "monetary policy", "rate decision", "basis points"],
    },
]

# Importance score bump for rate-decision items
RATE_DECISION_IMPORTANCE = 9
DEFAULT_IMPORTANCE = 5

# Country code → related_country_ids lookup built at runtime
_COUNTRY_ID_CACHE: dict[str, int] = {}


def _is_rate_related(title: str, description: str, keywords: list[str]) -> bool:
    text = (title + " " + description).lower()
    return any(kw in text for kw in keywords)


def _extract_rate_delta(text: str) -> str | None:
    """Try to extract basis points from text, e.g. '25 basis points'."""
    m = re.search(r'(\d+)\s*basis\s*points?', text.lower())
    if m:
        return f"{m.group(1)}bps"
    if "unchanged" in text.lower():
        return "unchanged"
    return None


def _parse_feed(feed_config: dict) -> list[dict]:
    """Parse one RSS/Atom feed and return candidate FeedEvent rows."""
    try:
        r = requests.get(feed_config["url"], timeout=20, headers={"User-Agent": "MetricsHour/1.0"})
        r.raise_for_status()
    except Exception:
        log.exception(f"RSS fetch failed: {feed_config['name']}")
        return []

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        log.warning(f"RSS parse error: {feed_config['name']}")
        return []

    # Handle both RSS and Atom
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item") or root.findall(".//atom:entry", ns)

    results = []
    for item in items:
        title = (
            (item.findtext("title") or item.findtext("atom:title", namespaces=ns) or "").strip()
        )
        link = (
            (item.findtext("link") or item.findtext("atom:link", namespaces=ns) or "").strip()
        )
        description = (
            (item.findtext("description") or item.findtext("atom:summary", namespaces=ns) or "").strip()
        )
        pub_date_raw = (
            item.findtext("pubDate") or item.findtext("atom:published", namespaces=ns) or ""
        ).strip()

        # Try to parse pubDate
        published_at = None
        for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                published_at = datetime.strptime(pub_date_raw, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        if not published_at:
            published_at = datetime.now(timezone.utc)

        if not title:
            continue

        is_rate = _is_rate_related(title, description, feed_config["rate_keywords"])
        rate_delta = _extract_rate_delta(title + " " + description) if is_rate else None

        # Stable dedup key based on source URL or title hash
        source_url = link or f"rss://{feed_config['name']}/{hashlib.md5(title.encode()).hexdigest()[:8]}"

        results.append({
            "title": title[:255],
            "body": description[:1000] if description else title,
            "event_type": "central_bank",
            "event_subtype": "rate_decision" if is_rate else "press_release",
            "source_url": source_url,
            "published_at": published_at,
            "importance_score": RATE_DECISION_IMPORTANCE if is_rate else DEFAULT_IMPORTANCE,
            "_country_code": feed_config["country_code"],
            "_rate_delta": rate_delta,
            "_bank_name": feed_config["name"],
        })

    return results


@app.task(name='tasks.central_bank_rss.fetch_central_bank_news', bind=True, max_retries=3, time_limit=600)
def fetch_central_bank_news(self):
    """Parse central bank RSS feeds and store rate decisions as FeedEvents."""
    db = SessionLocal()
    try:
        # Build country code → id cache
        from app.models.country import Country
        for c in db.execute(select(Country.code, Country.id)).all():
            _COUNTRY_ID_CACHE[c.code] = c.id

        all_events: list[dict] = []
        for feed_config in FEEDS:
            items = _parse_feed(feed_config)
            all_events.extend(items)
            log.info(f"{feed_config['name']}: {len(items)} items found")

        if not all_events:
            return "ok: no new items"

        rows = []
        for evt in all_events:
            country_id = _COUNTRY_ID_CACHE.get(evt.pop("_country_code"))
            rate_delta = evt.pop("_rate_delta")
            bank_name = evt.pop("_bank_name")

            event_data = {"bank": bank_name}
            if rate_delta:
                event_data["rate_delta"] = rate_delta

            rows.append({
                **evt,
                "image_url": None,
                "related_asset_ids": [],
                "related_country_ids": [country_id] if country_id else [],
                "event_data": event_data,
            })

        # Upsert on source_url — skip already-stored items
        stmt = pg_insert(FeedEvent).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["source_url"])
        result = db.execute(stmt)
        db.commit()

        inserted = result.rowcount
        log.info(f"Central bank RSS: {inserted} new events stored")
        return f"ok: {inserted} new events"

    except Exception as exc:
        db.rollback()
        log.exception("Central bank RSS fetch failed")
        raise self.retry(exc=exc, countdown=120)
    finally:
        db.close()
