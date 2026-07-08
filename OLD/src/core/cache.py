"""Redis cache with in-memory fallback and @cached_node decorator."""
from __future__ import annotations

import fnmatch
import functools
import hashlib
import json
import os
import time
from typing import Any, Optional

_in_memory: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)
_fallback = _in_memory   # alias used by tests
_client = None  # Redis client singleton


def get_client(config=None):
    """Connect to Redis; return None if unavailable."""
    global _client
    if _client is not None:
        return _client

    enabled = os.getenv("REDIS_ENABLED", "true").lower() == "true"
    if not enabled:
        return None

    try:
        import redis

        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        password = os.getenv("REDIS_PASSWORD") or None
        r = redis.Redis(host=host, port=port, password=password, socket_connect_timeout=1)
        r.ping()
        _client = r
        return _client
    except Exception:
        return None


def make_key(prefix: str, **kwargs) -> str:
    payload = json.dumps(kwargs, sort_keys=True, default=str)
    h = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"{prefix}:{h}"


def cache_get(client, key: str) -> Optional[Any]:
    if client is not None:
        try:
            raw = client.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    # in-memory fallback
    if key in _in_memory:
        value, expires_at = _in_memory[key]
        if expires_at > time.time():
            return value
        del _in_memory[key]
    return None


def cache_set(client, key: str, value: Any, ttl: int = 300) -> None:
    if client is not None:
        try:
            client.setex(key, ttl, json.dumps(value, default=str))
            return
        except Exception:
            pass
    _in_memory[key] = (value, time.time() + ttl)


def invalidate_pattern(client, pattern: str) -> int:
    count = 0
    if client is not None:
        try:
            keys = client.keys(pattern)
            if keys:
                count = client.delete(*keys)
            return count
        except Exception:
            pass
    to_del = [k for k in _in_memory if fnmatch.fnmatch(k, pattern)]
    for k in to_del:
        del _in_memory[k]
    return len(to_del)


def cached_node(prefix: str, ttl: int = 300):
    """Decorator for caching LangGraph node results."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(state: dict) -> dict:
            from config.settings import get_config
            client = get_client(get_config())
            key = make_key(
                prefix,
                query=state.get("query", ""),
                data_products=state.get("data_products", []),
                time_range=state.get("time_range", ""),
            )
            cached = cache_get(client, key)
            if cached is not None:
                return cached
            result = fn(state)
            cache_set(client, key, result, ttl)
            return result
        return wrapper
    return decorator
