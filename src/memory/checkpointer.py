"""LangGraph checkpointer — SQLite (dev) / PostgreSQL (prod)."""
from __future__ import annotations

import os


def get_checkpointer():
    """Return appropriate checkpointer based on environment."""
    env = os.getenv("ENVIRONMENT", "development")

    if env == "production":
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            pg_url = (
                f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:"
                f"{os.getenv('POSTGRES_PASSWORD', '')}@"
                f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
                f"{os.getenv('POSTGRES_PORT', '5432')}/"
                f"{os.getenv('POSTGRES_DB', 'governance_db')}"
            )
            return PostgresSaver.from_conn_string(pg_url)
        except Exception:
            pass

    # Try SQLite first, fall back to in-memory
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
