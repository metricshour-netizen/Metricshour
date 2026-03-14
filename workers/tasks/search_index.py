"""
Meilisearch index sync — pushes countries + assets from Postgres into Meilisearch.

Runs daily at 7:15am UTC (after R2 snapshots complete at 7am).
Can also be triggered manually: celery call tasks.search_index.reindex_search
"""

import os
import logging

import meilisearch
from celery import shared_task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import sys
sys.path.insert(0, '/root/metricshour/backend')

from app.models import Country, Asset  # noqa: E402 — needs sys.path above

log = logging.getLogger(__name__)

_MEILI_URL = os.environ.get("MEILI_URL", "http://127.0.0.1:7700")
_MEILI_KEY = os.environ.get("MEILI_MASTER_KEY", "")
_DB_URL = os.environ.get("DATABASE_URL", "")


def _client() -> meilisearch.Client:
    return meilisearch.Client(_MEILI_URL, _MEILI_KEY)


def _configure_indexes(client: meilisearch.Client) -> None:
    """Set up index settings (idempotent)."""
    # Countries
    client.create_index("countries", {"primaryKey": "id"})
    client.index("countries").update_settings({
        "searchableAttributes": [
            "name", "code", "name_official",
            "region", "subregion",
            "currency_code", "currency_name",
            "capital_city",
        ],
        "sortableAttributes": ["is_g20", "name"],
        "filterableAttributes": [],
        "rankingRules": ["words", "typo", "proximity", "attribute", "sort", "exactness"],
        "typoTolerance": {
            "enabled": True,
            "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 8},
        },
    })

    # Assets
    client.create_index("assets", {"primaryKey": "id"})
    client.index("assets").update_settings({
        "searchableAttributes": ["symbol", "name", "sector"],
        "sortableAttributes": ["market_cap_usd"],
        "filterableAttributes": ["is_active", "asset_type"],
        "rankingRules": ["words", "typo", "proximity", "attribute", "sort", "exactness"],
        "typoTolerance": {
            "enabled": True,
            "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 8},
        },
    })


@shared_task(
    name="tasks.search_index.reindex_search",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def reindex_search(self):
    """Full reindex of countries + assets into Meilisearch."""
    if not _MEILI_KEY:
        log.warning("MEILI_MASTER_KEY not set — skipping search reindex")
        return {"skipped": True}

    engine = create_engine(_DB_URL, pool_pre_ping=True)

    try:
        client = _client()
        _configure_indexes(client)

        with Session(engine) as db:
            # --- Countries ---
            countries = db.execute(select(Country)).scalars().all()
            country_docs = [
                {
                    "id": c.id,
                    "code": c.code,
                    "name": c.name,
                    "name_official": c.name_official or c.name,
                    "flag_emoji": c.flag_emoji or "",
                    "region": c.region or "",
                    "subregion": c.subregion or "",
                    "currency_code": c.currency_code or "",
                    "currency_name": c.currency_name or "",
                    "capital_city": c.capital_city or "",
                    "is_g20": 1 if c.is_g20 else 0,
                }
                for c in countries
            ]
            client.index("countries").add_documents(country_docs)
            log.info(f"Indexed {len(country_docs)} countries")

            # --- Assets ---
            assets = db.execute(
                select(Asset).where(Asset.is_active == True)
            ).scalars().all()
            asset_docs = [
                {
                    "id": a.id,
                    "symbol": a.symbol,
                    "name": a.name,
                    "sector": a.sector or "",
                    "industry": a.industry or "",
                    "asset_type": a.asset_type.value,
                    "is_active": True,
                    "market_cap_usd": float(a.market_cap_usd) if a.market_cap_usd else 0.0,
                }
                for a in assets
            ]
            client.index("assets").add_documents(asset_docs)
            log.info(f"Indexed {len(asset_docs)} assets")

        return {
            "countries": len(country_docs),
            "assets": len(asset_docs),
        }

    except Exception as exc:
        log.error(f"Search reindex failed: {exc}")
        raise self.retry(exc=exc)
    finally:
        engine.dispose()
