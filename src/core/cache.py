"""
src/core/cache.py
Day 14: Redis-backed cache with transparent in-memory fallback.

Design decisions:
  • Cache key  = SHA-256(query + data_products + time_range)
    Same query with different products → different key.
  • JSON serialisation — all cached values must be JSON-serialisable.
    AgentResult.to_dict() already satisfies this.
  • Fallback dict — when Redis is down the app never crashes.
    Fallback is process-local (lost on restart), Redis is shared + persistent.
  • TTLs are chosen per node based on how often the underlying data changes.

TTL reference:
  information_agent   1800s  (30 min) — SQL query results
  knowledge_agent     7200s  (2 hrs)  — document embeddings / RAG
  metadata_agent      3600s  (1 hr)   — Collibra metadata

DO NOT cache:
  capacity_node     — Jira is live data, tickets open/close constantly
  auto_ticket_node  — write operation
  synthesizer_node  — must combine fresh agent results every time
"""
from __future__ import annotations

import hashlib
import inspect
import json
import logging
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ── Module-level singletons ────────────────────────────────────────────────
_client = None          # redis.Redis | None
_fallback: dict = {}    # in-memory fallback when Redis unavailable


# ── Connection ─────────────────────────────────────────────────────────────

def get_client(config):
    """
    Connect to Redis once and reuse the connection.
    Returns None silently if Redis is disabled or unreachable.
    """
    global _client

    if not config.enabled:
        return None

    if _client is not None:
        return _client

    try:
        import redis as _redis
        _client = _redis.from_url(config.url, decode_responses=True)
        _client.ping()
        logger.info("Redis connected: %s", config.url)
    except Exception as exc:
        logger.warning(
            "Redis unavailable — using in-memory fallback. Error: %s", exc
        )
        _client = None

    return _client

# ── Key building ───────────────────────────────────────────────────────────
def make_key(prefix: str, **kwargs) -> str:
    """
    Build a deterministic cache key.
    First 16 hex chars of SHA-256 — collision probability is negligible.

    Example:
        make_key("information_agent", query="retention drop?", data_products=["retention"])
        → "information_agent:a3f91bc204e87d11"
    """
    raw    = json.dumps(kwargs, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{prefix}:{digest}"


# ── Get / Set ──────────────────────────────────────────────────────────────
def cache_get(client, key: str) -> Any | None:
    """Fetch from Redis or in-memory fallback. Returns None on miss."""
    if client:
        try:
            val = client.get(key)
            return json.loads(val) if val else None
        except Exception as exc:
            logger.warning("cache_get error: %s", exc)
            return None
    return _fallback.get(key)

def cache_set(client, key: str, value: Any, ttl: int) -> None:
    """Store to Redis (with TTL) or in-memory fallback."""
    if client:
        try:
            client.setex(key, ttl, json.dumps(value, default=str))
        except Exception as exc:
            logger.warning("cache_set error: %s", exc)
    else:
        _fallback[key] = value


# ── Invalidation ───────────────────────────────────────────────────────────
def invalidate_pattern(client, pattern: str) -> int:
    """
    Delete all keys matching a glob pattern.
    Returns count of deleted keys.

    Example: invalidate_pattern(client, "information_agent:*")
    """
    if not client:
        prefix = pattern.rstrip("*")
        keys   = [k for k in _fallback if k.startswith(prefix)]
        for k in keys:
            del _fallback[k]
        return len(keys)
    try:
        keys = client.keys(pattern)
        return client.delete(*keys) if keys else 0
    except Exception as exc:
        logger.warning("invalidate_pattern error: %s", exc)
        return 0


# ── Decorator ──────────────────────────────────────────────────────────────
def cached_node(prefix: str, ttl: int = 3600):
    """
    Decorator for read-only LangGraph node functions.

    Wraps the node with a Redis cache lookup before calling the agent.
    Works with both sync (def) and async (async def) node functions.

    Args:
        prefix:  Cache key prefix, e.g. "information_agent"
        ttl:     Time-to-live in seconds

    Usage:
        @cached_node("information_agent", ttl=1800)
        def information_node(state: AgentState) -> dict:
            ...  # existing code unchanged

    Cache key is built from: query + data_products + time_range
    """
    def decorator(func: Callable) -> Callable:

        if inspect.iscoroutinefunction(func):
            # ── async node ────────────────────────────────────────────
            @wraps(func)
            async def async_wrapper(state: dict, *args, **kwargs):
                from config.settings import AppConfig
                client = get_client(AppConfig().redis)
                key    = make_key(
                    prefix,
                    query         = state.get("query", ""),
                    data_products = state.get("data_products", []),
                    time_range    = state.get("time_range", ""),
                )
                hit = cache_get(client, key)
                if hit is not None:
                    logger.info("Cache HIT  [%s]", prefix)
                    return hit
                logger.info("Cache MISS [%s] — calling agent", prefix)
                result = await func(state, *args, **kwargs)
                cache_set(client, key, result, ttl)
                logger.info("Cache SET  [%s] ttl=%ds", prefix, ttl)
                return result
            return async_wrapper

        else:
            # ── sync node (current default) ───────────────────────────
            @wraps(func)
            def sync_wrapper(state: dict, *args, **kwargs):
                from config.settings import AppConfig
                client = get_client(AppConfig().redis)
                key    = make_key(
                    prefix,
                    query         = state.get("query", ""),
                    data_products = state.get("data_products", []),
                    time_range    = state.get("time_range", ""),
                )
                hit = cache_get(client, key)
                if hit is not None:
                    logger.info("Cache HIT  [%s]", prefix)
                    return hit
                logger.info("Cache MISS [%s] — calling agent", prefix)
                result = func(state, *args, **kwargs)
                cache_set(client, key, result, ttl)
                logger.info("Cache SET  [%s] ttl=%ds", prefix, ttl)
                return result
            return sync_wrapper

    return decorator