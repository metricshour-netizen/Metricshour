"""Cloudflare R2 (object storage) and KV (edge cache) clients."""
import boto3
import httpx
from botocore.client import Config
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def r2_upload(key: str, body: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to R2. Returns the object key."""
    get_r2_client().put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=body,
        ContentType=content_type,
    )
    return key


def r2_download(key: str) -> bytes:
    obj = get_r2_client().get_object(Bucket=settings.r2_bucket_name, Key=key)
    return obj["Body"].read()


def r2_delete(key: str) -> None:
    get_r2_client().delete_object(Bucket=settings.r2_bucket_name, Key=key)


def r2_public_url(key: str) -> str:
    """Returns public URL if bucket has public access configured, else empty string."""
    if settings.r2_public_url:
        return f"{settings.r2_public_url.rstrip('/')}/{key}"
    return ""


# ── Cloudflare KV ────────────────────────────────────────────────────────────

_KV_BASE = "https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{ns_id}"


def _kv_headers() -> dict:
    return {"Authorization": f"Bearer {settings.cf_api_token}"}


def _kv_url(key: str) -> str:
    base = _KV_BASE.format(
        account_id=settings.cf_account_id,
        ns_id=settings.cf_kv_namespace_id,
    )
    return f"{base}/values/{key}"


def kv_set(key: str, value: str, ttl_seconds: int = 300) -> None:
    """Write a string value to KV with optional TTL (default 5 min)."""
    with httpx.Client() as client:
        client.put(
            _kv_url(key),
            content=value.encode(),
            headers={**_kv_headers(), "Content-Type": "text/plain"},
            params={"expiration_ttl": ttl_seconds},
        )


def kv_get(key: str) -> str | None:
    """Read a value from KV. Returns None if key doesn't exist."""
    with httpx.Client() as client:
        r = client.get(_kv_url(key), headers=_kv_headers())
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.text


def kv_delete(key: str) -> None:
    with httpx.Client() as client:
        client.delete(_kv_url(key), headers=_kv_headers())


# ── KV + Redis JSON helpers ────────────────────────────────────────────────────

import json
import logging
from functools import lru_cache

import redis as redis_lib

_kv_log = logging.getLogger(__name__)


# ── Redis (L1 — app-level, ~10ms) ─────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_redis() -> redis_lib.Redis:
    return redis_lib.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)


def redis_json_get(key: str) -> list | dict | None:
    """Read JSON from Redis. Returns None on miss or any error."""
    if not settings.redis_url:
        return None
    try:
        raw = _get_redis().get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        _kv_log.warning("Redis get failed for %s: %s", key, exc)
        return None


def redis_json_set(key: str, value: list | dict, ttl_seconds: int = 3600) -> None:
    """Write JSON to Redis with TTL. Silently swallows errors."""
    if not settings.redis_url:
        return
    try:
        _get_redis().setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception as exc:
        _kv_log.warning("Redis set failed for %s: %s", key, exc)


def redis_json_del(key: str) -> None:
    """Delete a key from Redis."""
    if not settings.redis_url:
        return
    try:
        _get_redis().delete(key)
    except Exception as exc:
        _kv_log.warning("Redis del failed for %s: %s", key, exc)


# ── KV (L2 — Cloudflare edge, pushed for CF Worker to serve) ──────────────────

def kv_json_get(key: str) -> list | dict | None:
    """Read a JSON value from KV. Returns None on miss or any error."""
    if not (settings.cf_api_token and settings.cf_kv_namespace_id):
        return None
    try:
        raw = kv_get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        _kv_log.warning("KV get failed for %s: %s", key, exc)
        return None


def kv_json_set(key: str, value: list | dict, ttl_seconds: int = 3600) -> None:
    """Write a JSON value to KV. Silently swallows errors."""
    if not (settings.cf_api_token and settings.cf_kv_namespace_id):
        return
    try:
        kv_set(key, json.dumps(value, default=str), ttl_seconds=ttl_seconds)
    except Exception as exc:
        _kv_log.warning("KV set failed for %s: %s", key, exc)


# ── L0: process-level memory cache (per Gunicorn worker, 30s TTL) ─────────────
# Absorbs burst traffic inside the worker — eliminates redundant Redis/KV calls
# for hot keys requested multiple times within the same 30s window.

import time as _time

_L0: dict[str, tuple[float, list | dict]] = {}  # key → (expires_at, value)
_L0_TTL = 30  # seconds


def _l0_get(key: str) -> list | dict | None:
    entry = _L0.get(key)
    if entry and _time.monotonic() < entry[0]:
        return entry[1]
    if entry:
        del _L0[key]
    return None


def _l0_set(key: str, value: list | dict) -> None:
    _L0[key] = (_time.monotonic() + _L0_TTL, value)


def _l0_del(key: str) -> None:
    _L0.pop(key, None)


# ── Three-layer cache: L0 memory → L1 Redis → L2 KV ──────────────────────────

def cache_get(key: str) -> list | dict | None:
    """L0 memory → L1 Redis → L2 KV. Returns first hit or None."""
    hit = _l0_get(key)
    if hit is not None:
        return hit
    hit = redis_json_get(key)
    if hit is not None:
        _l0_set(key, hit)
        return hit
    hit = kv_json_get(key)
    if hit is not None:
        _l0_set(key, hit)
    return hit


def cache_set(key: str, value: list | dict, ttl_seconds: int = 3600) -> None:
    """Write to L0 memory, L1 Redis, and L2 KV."""
    _l0_set(key, value)
    redis_json_set(key, value, ttl_seconds=ttl_seconds)
    kv_json_set(key, value, ttl_seconds=ttl_seconds)


def cache_del(key: str) -> None:
    """Invalidate from all three layers."""
    _l0_del(key)
    try:
        redis_json_del(key)
    except Exception:
        pass
    try:
        kv_delete(key)
    except Exception:
        pass
