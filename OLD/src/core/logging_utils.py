"""Structured JSON logging, decorators, error hierarchy."""
from __future__ import annotations

import functools
import logging
import time
import traceback
from typing import Any, Callable


class GovernanceError(Exception):
    """Base error for governance copilot."""


class AgentError(GovernanceError):
    """Raised when an agent fails."""


class ServiceError(GovernanceError):
    """Raised when a downstream service fails."""


class ConfigurationError(GovernanceError):
    """Raised for misconfiguration."""


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                '{"time": "%(asctime)s", "level": "%(levelname)s", '
                '"logger": "%(name)s", "message": "%(message)s"}'
            )
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def log_execution(logger: logging.Logger | None = None):
    """Decorator: log entry, exit, duration, and errors for any function."""
    def decorator(fn: Callable) -> Callable:
        _log = logger or get_logger(fn.__module__)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            _log.info(f"START {fn.__qualname__}")
            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed = (time.perf_counter() - t0) * 1000
                _log.info(f"END {fn.__qualname__} duration_ms={elapsed:.1f}")
                return result
            except Exception as exc:
                elapsed = (time.perf_counter() - t0) * 1000
                _log.error(
                    f"ERROR {fn.__qualname__} duration_ms={elapsed:.1f} "
                    f"error={type(exc).__name__}: {exc}"
                )
                raise

        return wrapper
    return decorator
