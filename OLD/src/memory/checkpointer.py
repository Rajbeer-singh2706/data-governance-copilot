"""LangGraph checkpointer — MemorySaver (dev) / PostgresSaver (prod).
Neon-compatible: reads DATABASE_URL or individual POSTGRES_* env vars.
"""
from __future__ import annotations

import os


def _pg_url() -> str:
    """Build PostgreSQL URL. Prefers DATABASE_URL (Neon), falls back to parts."""
    raw = os.getenv("DATABASE_URL", "")
    if raw:
        # Ensure sync psycopg2 scheme for LangGraph PostgresSaver
        raw = raw.replace("postgresql+asyncpg://", "postgresql://")
        raw = raw.replace("postgresql+psycopg2://", "postgresql://")
        raw = raw.replace("postgres://", "postgresql://")
        if "sslmode" not in raw:
            raw += "?sslmode=require"
        return raw
    user = os.getenv("POSTGRES_USER", "postgres")
    pw = os.getenv("POSTGRES_PASSWORD", "")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "governance_db")
    ssl = os.getenv("POSTGRES_SSLMODE", "")
    ssl_part = f"?sslmode={ssl}" if ssl else ""
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}{ssl_part}"


def get_checkpointer():
    """Return appropriate checkpointer based on environment."""
    env = os.getenv("ENVIRONMENT", "development")

    if env == "production":
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            pg_url = _pg_url()
            saver = PostgresSaver.from_conn_string(pg_url)
            saver.setup()  # creates tables if they don't exist
            return saver
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "PostgresSaver failed (%s), falling back to MemorySaver", exc
            )

    # Dev: try SQLite → MemorySaver
    sqlite_path = os.getenv("SQLITE_PATH", "./data/memory.db")
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        return SqliteSaver.from_conn_string(sqlite_path)
    except (ImportError, Exception):
        pass

    try:
        from langgraph_checkpoint_sqlite import SqliteSaver
        return SqliteSaver.from_conn_string(sqlite_path)
    except (ImportError, Exception):
        pass

    from langgraph.checkpoint.memory import MemorySaver
    return MemorySaver()
