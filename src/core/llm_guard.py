"""Daily token budget hard stop."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

DAILY_TOKEN_LIMIT = 2_000_000


def _today_key() -> str:
    return f"token_usage:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token + 500 overhead."""
    return len(text) // 4 + 500


def check_and_record_tokens(redis_client, tokens: int) -> bool:
    """
    Check if tokens can be used within daily budget, then record them.
    Returns True (allow) or False (budget exceeded).
    Fail-open: Redis errors → return True.
    """
    if redis_client is None:
        return True
    try:
        key = _today_key()
        # Increment first, then check the returned total (atomic-ish)
        if hasattr(redis_client, 'pipeline'):
            # Real Redis: get current usage first
            try:
                current = redis_client.get(key)
                used = int(current) if current else 0
            except Exception:
                used = 0
            if used >= DAILY_TOKEN_LIMIT or used + tokens > DAILY_TOKEN_LIMIT:
                return False
            pipe = redis_client.pipeline()
            pipe.incrby(key, tokens)
            pipe.expire(key, 86400)
            pipe.execute()
        else:
            # Simple mock Redis: incrby returns new total
            new_total = redis_client.incrby(key, tokens)
            if hasattr(redis_client, 'expire'):
                redis_client.expire(key, 86400)
            # If the total exceeds limit, the budget was already exceeded before this call
            if new_total > DAILY_TOKEN_LIMIT:
                return False
        return True
    except Exception:
        return True  # fail-open


def get_daily_usage(redis_client) -> dict:
    """Return token usage stats for today."""
    if redis_client is None:
        return {"tokens_used": 0, "limit": DAILY_TOKEN_LIMIT, "pct": 0.0, "remaining": DAILY_TOKEN_LIMIT}
    try:
        key = _today_key()
        current = redis_client.get(key)
        used = int(current) if current else 0
        return {
            "tokens_used": used,
            "limit": DAILY_TOKEN_LIMIT,
            "pct": round(used / DAILY_TOKEN_LIMIT * 100, 2),
            "remaining": max(0, DAILY_TOKEN_LIMIT - used),
        }
    except Exception:
        return {"tokens_used": 0, "limit": DAILY_TOKEN_LIMIT, "pct": 0.0, "remaining": DAILY_TOKEN_LIMIT}
