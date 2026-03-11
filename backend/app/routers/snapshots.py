"""
Serve R2 JSON snapshots via the API so Cloudflare CDN caches them at the edge.

Route: GET /snapshots/{key}
  key = path without the "snapshots/" prefix, e.g. "countries/us.json"
  R2 key = "snapshots/countries/us.json"

Cloudflare caches responses based on Cache-Control headers set in main.py middleware.
Redis warms on first hit so subsequent requests in the same worker skip R2.
"""

import json
import logging

import botocore.exceptions
from fastapi import APIRouter, HTTPException, Response

from app.config import settings
from app.storage import get_r2_client, redis_json_get, redis_json_set

router = APIRouter(prefix="/snapshots", tags=["cdn"])

log = logging.getLogger(__name__)

# Allowlist of key prefixes — prevents arbitrary R2 enumeration
_ALLOWED_PREFIXES = (
    "snapshots/countries/",
    "snapshots/stocks/",
    "snapshots/trade/",
    "snapshots/lists/",
    "snapshots/rankings/",
    "snapshots/meta/",
)

# Redis TTL for snapshot cache — 1 hour (snapshots regenerate daily at 7am)
_REDIS_TTL = 3600


@router.get("/{key:path}")
def serve_snapshot(key: str) -> Response:
    """Return a pre-built JSON snapshot from R2. Cloudflare caches the response at the edge."""
    r2_key = f"snapshots/{key}"

    if not any(r2_key.startswith(p) for p in _ALLOWED_PREFIXES):
        raise HTTPException(status_code=404, detail="Not found")

    if not r2_key.endswith(".json"):
        raise HTTPException(status_code=404, detail="Not found")

    # L1: Redis cache — avoids hitting R2 on repeated requests within the worker lifetime
    redis_key = f"cdn:snap:{r2_key}"
    cached_raw = redis_json_get(redis_key)
    if cached_raw is not None:
        return Response(
            content=json.dumps(cached_raw, default=str),
            media_type="application/json",
        )

    # R2 fetch
    if not (settings.r2_endpoint and settings.r2_access_key_id and settings.r2_secret_access_key):
        raise HTTPException(status_code=503, detail="R2 storage not configured")

    try:
        obj = get_r2_client().get_object(Bucket=settings.r2_bucket_name, Key=r2_key)
        body: bytes = obj["Body"].read()
    except botocore.exceptions.ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("NoSuchKey", "404"):
            raise HTTPException(status_code=404, detail="Snapshot not found")
        log.warning("R2 fetch error for %s: %s", r2_key, exc)
        raise HTTPException(status_code=503, detail="Upstream unavailable")
    except Exception as exc:
        log.warning("R2 fetch failed for %s: %s", r2_key, exc)
        raise HTTPException(status_code=503, detail="Upstream unavailable")

    # Warm Redis so the next request in this worker skips R2
    try:
        redis_json_set(redis_key, json.loads(body), ttl_seconds=_REDIS_TTL)
    except Exception:
        pass  # Non-fatal — just means no Redis warm

    return Response(content=body, media_type="application/json")
