"""Retry decorator and retry_agent_call helper."""
from __future__ import annotations

import functools
import time
from typing import Any, Callable, Tuple, Type


def with_retry(
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """Exponential backoff retry decorator."""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries - 1:
                        sleep = backoff_factor * (2 ** attempt)
                        time.sleep(sleep)
            raise last_exc
        return wrapper
    return decorator


def retry_agent_call(execute_fn: Callable, request: Any, max_retries: int = 3) -> Any:
    """
    Call execute_fn(request) with retries.
    Makes exactly max_retries attempts total.
    Returns AgentResult(success=False) on final failure rather than raising.
    """
    from core.base_agent import AgentResult

    last_exc = None
    for attempt in range(max_retries):
        try:
            return execute_fn(request)
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(1.0 * (2 ** attempt))

    error_msg = str(last_exc)
    return AgentResult(
        success=False,
        message=f"Failed after {max_retries} attempts: {error_msg}",
        errors=[error_msg],
    )
