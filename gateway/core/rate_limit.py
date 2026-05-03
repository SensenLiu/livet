"""Rate limit configuration shared across routers.

Tier-based limits (per device_id, falls back to remote IP):
  free   : 60 requests/min, 1k requests/day
  paid   : 600 requests/min, 50k/day

Storage:
  - prod: Redis (REDIS_URL in .env)
  - dev:  in-memory (when REDIS_URL is empty or env=dev)
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from core.settings import settings


def _storage_uri() -> str:
    if settings.env == "dev" or not settings.redis_url:
        return "memory://"
    return settings.redis_url


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri(),
    default_limits=["60/minute", "1000/day"],
)


# Convenience decorators expected by the routers (kept thin so tests can patch).
def limit(rate: str):
    return limiter.limit(rate)
