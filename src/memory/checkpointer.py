"""
src/memory/checkpointer.py
Persistent conversation memory via LangGraph checkpointers.

Dev:  SqliteSaver (file-based, zero setup) — falls back to MemorySaver
      if the installed langgraph-checkpoint-sqlite is incompatible.
Prod: PostgresSaver (shared across ECS tasks)
"""
from __future__ import annotations

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_checkpointer():
    """
    Return the best available checkpointer for the current environment.

    Priority:
      1. production  → PostgresSaver (if DATABASE_URL set)
      2. development → SqliteSaver   (if langgraph-checkpoint-sqlite compatible)
      3. fallback    → MemorySaver   (in-process, no persistence — dev/CI only)
    """
    env = os.getenv("ENVIRONMENT", "development")

    # ── Production: Postgres ───────────────────────────────────────────
    if env == "production":
        db_url = os.getenv("DATABASE_URL", "")
        if db_url:
            try:
                from langgraph.checkpoint.postgres import PostgresSaver
                saver = PostgresSaver.from_conn_string(db_url)
                logger.info("checkpointer → PostgresSaver")
                return saver
            except Exception as exc:
                logger.warning("PostgresSaver unavailable (%s) — falling back", exc)

    # ── Development: SQLite ───────────────────────────────────────────
    try:
        import sqlite3
        from langgraph.checkpoint.sqlite import SqliteSaver

        db_path = Path(os.getenv("SQLITE_PATH", "./data/memory.db"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        saver = SqliteSaver(conn)
        logger.info("checkpointer → SqliteSaver at %s", db_path)
        print(f"[checkpointer] SqliteSaver at {db_path}")
        return saver
    except Exception as exc:
        logger.warning(
            "SqliteSaver unavailable (%s) — falling back to MemorySaver (no persistence)",
            exc,
        )

    # ── Final fallback: in-memory ──────────────────────────────────────
    from langgraph.checkpoint.memory import MemorySaver
    logger.info("checkpointer → MemorySaver (in-process, not persisted)")
    print("[checkpointer] MemorySaver (conversations will NOT persist across restarts)")
    return MemorySaver()