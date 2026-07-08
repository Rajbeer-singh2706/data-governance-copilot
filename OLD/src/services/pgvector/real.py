"""Real PGVector service — Neon-compatible (SSL, connection string or DATABASE_URL)."""
from __future__ import annotations

import os
from typing import List, Tuple

from langchain_core.documents import Document


class PGVectorService:
    def __init__(self, config=None):
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        if not self._api_key:
            raise EnvironmentError("OPENAI_API_KEY is required for PGVectorService")
        self._config = config
        self._store = None

    def _conn_str(self) -> str:
        """Build psycopg2 connection string. Prefers DATABASE_URL (Neon)."""
        if self._config and hasattr(self._config, "connection_string"):
            return self._config.connection_string
        raw = os.getenv("DATABASE_URL", "")
        if raw:
            raw = raw.replace("postgresql://", "postgresql+psycopg2://")
            raw = raw.replace("postgres://", "postgresql+psycopg2://")
            if "sslmode" not in raw:
                raw += "?sslmode=require"
            return raw
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "governance_db")
        user = os.getenv("POSTGRES_USER", "postgres")
        pw = os.getenv("POSTGRES_PASSWORD", "")
        ssl = os.getenv("POSTGRES_SSLMODE", "require")
        return f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}?sslmode={ssl}"

    def _get_store(self):
        if self._store is None:
            from langchain_postgres import PGVector
            from langchain_openai import OpenAIEmbeddings
            collection = os.getenv("VECTOR_COLLECTION", "governance_docs")
            self._store = PGVector(
                embeddings=OpenAIEmbeddings(model="text-embedding-3-small"),
                collection_name=collection,
                connection=self._conn_str(),
                use_jsonb=True,  # required for Neon/modern pgvector
            )
        return self._store

    def similarity_search(self, query: str, k: int = 5) -> List[Tuple[Document, float]]:
        store = self._get_store()
        return store.similarity_search_with_relevance_scores(query, k=k)
