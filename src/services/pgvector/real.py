"""
src/services/pgvector/real.py
PGVectorService — LangChain PGVector wrapper for production.

Requires:
  OPENAI_API_KEY   — for text-embedding-3-small
  POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD

Raises EnvironmentError at construction time if any are missing.
The factory catches this and falls back to NullVectorService.
"""
from __future__ import annotations

import os
from typing import Any, List, Tuple


class PGVectorService:
    """
    Production vector store backed by pgvector + OpenAI embeddings.
    Satisfies IVectorService protocol.
    """

    def __init__(self, config=None):
        openai_key = os.getenv("OPENAI_API_KEY", "")
        pg_host = os.getenv("POSTGRES_HOST", "")
        pg_db = os.getenv("POSTGRES_DB", "")

        if not openai_key:
            raise EnvironmentError("OPENAI_API_KEY is not set — PGVectorService unavailable")
        if not pg_host or not pg_db:
            raise EnvironmentError(
                "POSTGRES_HOST / POSTGRES_DB not set — PGVectorService unavailable"
            )

        # Lazy import so missing packages don't crash dev mode
        try:
            from langchain_openai import OpenAIEmbeddings
            from langchain_postgres import PGVector
        except ImportError as exc:
            raise EnvironmentError(
                f"langchain-openai / langchain-postgres not installed: {exc}"
            ) from exc

        pg_user = os.getenv("POSTGRES_USER", "postgres")
        pg_pass = os.getenv("POSTGRES_PASSWORD", "")
        pg_port = os.getenv("POSTGRES_PORT", "5432")
        connection = (
            f"postgresql+psycopg2://{pg_user}:{pg_pass}"
            f"@{pg_host}:{pg_port}/{pg_db}"
        )

        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=openai_key,
        )
        self._store = PGVector(
            embeddings=embeddings,
            collection_name="governance_docs",
            connection=connection,
        )

    def similarity_search(self, query: str, k: int = 5) -> List[Tuple[Any, float]]:
        """Return (Document, score) tuples; score is 0.0–1.0."""
        return self._store.similarity_search_with_relevance_scores(query, k=k)