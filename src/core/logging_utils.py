"""
Production-grade logging and error handling for Data Governance Copilot.
"""

import logging
import sys,json , traceback 

from datetime import datetime
from pathlib import Path 
from typing import Any
from functools import wraps
import time 



class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production environments."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "agent"):
            log_entry["agent"] = record.agent
        if hasattr(record, "query_id"):
            log_entry["query_id"] = record.query_id
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        return json.dumps(log_entry)
    
def setup_logger(name: str, log_file: str = "./logs/copilot.log", level: str = "INFO") -> logging.Logger:
    """Configure a logger with both console and file handlers."""
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    # Console handler (human-readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)-8s %(name)s | %(message)s", datefmt="%H:%M:%S")
    )
    logger.addHandler(console_handler)

    # File handler (JSON structured)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    return logger


# Module-level root logger — used by non-agent code
# Root application logger
logger = setup_logger("copilot")


class AgentError(Exception):
    """Base exception for all agent errors."""
    def __init__(self, message: str, agent_name: str, recoverable: bool = True):
        super().__init__(message)
        self.agent_name = agent_name
        self.recoverable = recoverable


class DataSourceError(AgentError):
    """Raised when a data source (Databricks, SQL, etc.) is unavailable."""
    pass


class GovernanceToolError(AgentError):
    """Raised when Collibra or similar governance tools fail."""
    pass


class TicketingError(AgentError):
    """Raised when Jira operations fail."""
    pass


class KnowledgeBaseError(AgentError):
    """Raised when knowledge retrieval fails."""
    pass


class OrchestratorError(Exception):
    """Raised when the supervisor agent encounters a routing or aggregation failure."""
    pass


def with_retry(max_retries: int = 3, delay_seconds: float = 1.0, backoff: float = 2.0):
    """Decorator: retry a function on failure with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay_seconds
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"Attempt {attempt}/{max_retries} failed for {func.__name__}: {e}"
                    )
                    if attempt < max_retries:
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exception
        return wrapper
    return decorator


def timed(agent_name: str = "unknown"):
    """Decorator: log execution time for agent methods."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = round((time.time() - start) * 1000, 2)
                logger.info(
                    f"{agent_name}.{func.__name__} completed",
                    extra={"agent": agent_name, "duration_ms": duration_ms}
                )
                return result
            except Exception as e:
                duration_ms = round((time.time() - start) * 1000, 2)
                logger.error(
                    f"{agent_name}.{func.__name__} failed after {duration_ms}ms: {e}",
                    extra={"agent": agent_name, "duration_ms": duration_ms}
                )
                raise
        return wrapper
    return decorator


def safe_execute(func, fallback: Any = None, log_error: bool = True):
    """Execute a function safely, returning a fallback on failure."""
    try:
        return func()
    except Exception as e:
        if log_error:
            logger.error(f"Safe execution failed: {e}\n{traceback.format_exc()}")
        return fallback
