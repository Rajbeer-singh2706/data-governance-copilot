"""slowapi rate limiter — Redis if available, memory:// fallback."""
from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

_storage_uri = "memory://"
try:
    import redis as _redis
    _host = os.getenv("REDIS_HOST", "localhost")
    _port = int(os.getenv("REDIS_PORT", "6379"))
    _r = _redis.Redis(host=_host, port=_port, socket_connect_timeout=1)
    _r.ping()
    _pw = os.getenv("REDIS_PASSWORD", "")
    _auth = f":{_pw}@" if _pw else ""
    _storage_uri = f"redis://{_auth}{_host}:{_port}"
except Exception:
    _storage_uri = "memory://"


def get_user_id(request) -> str:
    return request.headers.get("X-User-Id", get_remote_address(request))


limiter = Limiter(key_func=get_remote_address, storage_uri=_storage_uri)
user_limiter = Limiter(key_func=get_user_id, storage_uri=_storage_uri)
