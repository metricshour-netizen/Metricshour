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
