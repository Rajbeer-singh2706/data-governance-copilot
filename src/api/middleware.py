"""
src/api/middleware.py  — Day 16
slowapi rate limiter setup for FastAPI.

The limiter was unconditionally configured with a Redis storage_uri. 
When Redis is unavailable (e.g. in the test environment) slowapi raises a ConnectionRefusedError 
on the FIRST request, crashing every endpoint.

Solution: probe Redis at startup. If it's reachable, use Redis storage so rate-limit state is shared 
across ECS tasks. If not (dev/test/CI), fall back to in-memory storage which is always available.
"""

import logging
import os

import redis as _redis
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

log = logging.getLogger(__name__)


def get_user_id(request: Request) -> str:
    """
    Rate-limit key for Teams bot integration.

    Teams sends all messages from ONE IP — rate limiting by IP
    would block the entire org. Key on X-User-Id header instead
    so each Teams user gets their own quota.
    Falls back to IP for regular web/API clients.
    """
    return request.headers.get("X-User-Id", get_remote_address(request))


def _redis_available(host: str, port: int) -> bool:
    """Probe Redis with a short timeout. Return True if reachable."""
    try:
        c = _redis.Redis(host=host, port=port, socket_connect_timeout=1)
        c.ping()
        c.close()
        return True
    except Exception:
        return False


_host = os.getenv("REDIS_HOST", "localhost")
_port = int(os.getenv("REDIS_PORT", "6379"))
_redis_uri = f"redis://{_host}:{_port}"

# FIX: choose storage backend at import time based on Redis availability
if _redis_available(_host, _port):
    _storage_uri = _redis_uri
    log.info("Rate limiter: using Redis storage (%s)", _redis_uri)
else:
    _storage_uri = "memory://"
    log.warning(
        "Rate limiter: Redis unavailable — using in-memory storage "
        "(rate limits are per-process only; acceptable for dev/test)"
    )

# IP-based limiter — default for web + API clients
limiter = Limiter(
    key_func       = get_remote_address,
    default_limits = ["100/minute"],
    storage_uri    = _storage_uri,
)

# User-based limiter — Teams bot endpoints
user_limiter = Limiter(
    key_func    = get_user_id,
    storage_uri = _storage_uri,
)