"""
src/core/retry.py  — NEW file (Day 15)
Retry decorator with exponential backoff + agent-safe retry helper.
"""
from __future__ import annotations
import logging, time
from functools import wraps
from typing import Callable, Tuple, Type

logger = logging.getLogger(__name__)


def with_retry(
    max_retries:    int   = 3,
    backoff_factor: float = 1.0,
    exceptions:     Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator: retry with exponential backoff.
    Backoff: 1s → 2s → 4s  (factor * 2^attempt)

    Usage:
        @with_retry(max_retries=3, backoff_factor=1.0)
        def call_external_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        wait = backoff_factor * (2 ** (attempt - 1))
                        logger.warning(
                            "[retry] %s — attempt %d/%d failed. "
                            "Retrying in %.1fs. Error: %s",
                            func.__name__, attempt, max_retries, wait, exc,
                        )
                        time.sleep(wait)
                    else:
                        logger.error(
                            "[retry] %s — all %d attempts failed. Error: %s",
                            func.__name__, max_retries, exc,
                        )
            raise last_exc
        return wrapper
    return decorator


def retry_agent_call(agent_execute: Callable, request, max_retries: int = 3):
    """
    Retry agent.execute(request) with backoff.
    Returns degraded AgentResult (success=False) on final failure
    instead of raising — so the graph node never crashes.

    Usage in any agent node:
        result = retry_agent_call(
            _agents["information"].execute,
            _build_request(state),
            max_retries=3,
        )
    """
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return agent_execute(request)
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = 1.0 * (2 ** (attempt - 1))
                logger.warning(
                    "[retry_agent] attempt %d/%d failed — %.1fs. %s",
                    attempt, max_retries, wait, exc,
                )
                time.sleep(wait)

    from core.base_agent import AgentResult
    agent_name = getattr(
        getattr(agent_execute, "__self__", None), "name", "unknown_agent"
    )
    return AgentResult(
        agent_name = agent_name,
        success    = False,
        error      = f"Failed after {max_retries} attempts: {last_exc}",
        summary    = f"⚠️ {agent_name} unavailable after {max_retries} retries.",
        data       = {}, sources=[], confidence=0.0,
    )