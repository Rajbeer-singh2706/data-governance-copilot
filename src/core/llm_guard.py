"""
src/core/llm_guard.py  — NEW file (Day 16)
Daily OpenAI token budget hard stop via Redis counter.
"""

import logging
from datetime import date

logger = logging.getLogger(__name__)

DAILY_TOKEN_LIMIT = int(2_000_000)   # adjust to your OpenAI tier

def check_and_record_tokens(redis_client, tokens_used: int) -> bool:
    """
    Increment daily counter and check against limit.
    Returns True = within budget, False = exceeded → caller raises 429.
    Fail-open: Redis error returns True (never blocks on infra failure).
    """
    if not redis_client:
        return True   # dev mode — no guard

    key = f"token_usage:{date.today().isoformat()}"
    try:
        current = redis_client.incrby(key, tokens_used)
        redis_client.expire(key, 86_400)          # reset at midnight
        if current > DAILY_TOKEN_LIMIT:
            logger.warning("Daily token limit exceeded: %d / %d",
                           current, DAILY_TOKEN_LIMIT)
            return False
        return True
    except Exception as exc:
        logger.warning("llm_guard Redis error (fail open): %s", exc)
        return True   # fail open


def get_daily_usage(redis_client) -> dict:
    """Return token stats for /agents/status dashboard."""
    if not redis_client:
        return {"tokens_used":0,"limit":DAILY_TOKEN_LIMIT,"pct":0.0,
                "remaining":DAILY_TOKEN_LIMIT,"redis_ok":False}
    key = f"token_usage:{date.today().isoformat()}"
    try:
        current = int(redis_client.get(key) or 0)
        return {"tokens_used":current,"limit":DAILY_TOKEN_LIMIT,
                "pct":round(current/DAILY_TOKEN_LIMIT*100,1),
                "remaining":max(0,DAILY_TOKEN_LIMIT-current),"redis_ok":True}
    except Exception:
        return {"tokens_used":0,"limit":DAILY_TOKEN_LIMIT,"pct":0.0,
                "remaining":DAILY_TOKEN_LIMIT,"redis_ok":False}


def estimate_tokens(text: str) -> int:
    """Rough estimate: 4 chars ≈ 1 token + 500 prompt overhead."""
    return len(text) // 4 + 500