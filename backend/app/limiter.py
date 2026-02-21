import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Use Redis as storage so rate limit counters are shared across gunicorn workers.
# Falls back to in-memory if REDIS_URL is not set (dev mode).
_redis_url = os.environ.get("REDIS_URL", "")
# slowapi needs redis:// or rediss:// URI — Upstash uses rediss://
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_redis_url if _redis_url else "memory://",
)
