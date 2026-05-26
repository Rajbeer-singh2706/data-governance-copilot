"""
src/api/middleware.py  — NEW file (Day 16)
slowapi rate limiter setup for FastAPI.
"""

import os
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

def get_user_id(request: Request) -> str:
    """
    Rate-limit key for Teams bot integration.

    Teams sends all messages from ONE IP — rate limiting by IP
    would block the entire org. Key on X-User-Id header instead
    so each Teams user gets their own quota.
    Falls back to IP for regular web/API clients.
    """
    return request.headers.get("X-User-Id", get_remote_address(request))


_redis_uri = (
    f"redis://{os.getenv('REDIS_HOST','localhost')}"
    f":{os.getenv('REDIS_PORT','6379')}"
)

# IP-based limiter — default for web + API clients
limiter = Limiter(
    key_func       = get_remote_address,
    default_limits = ["100/minute"],
    storage_uri    = _redis_uri,
)

# User-based limiter — Teams bot endpoints
user_limiter = Limiter(
    key_func    = get_user_id,
    storage_uri = _redis_uri,
)