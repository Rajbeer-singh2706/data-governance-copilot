"""Real PGVector service wrapping LangChain PGVector."""
from __future__ import annotations

import os
from typing import List, Tuple

from langchain_core.documents import Document


class PGVectorService:
    def __init__(self, config=None):
        self._host = os.getenv("POSTGRES_HOST", "localhost")
        self._port = os.getenv("POSTGRES_PORT", "5432")
        self._db = os.getenv("POSTGRES_DB", "governance_db")
        self._user = os.getenv("POSTGRES_USER", "postgres")
        self._password = os.getenv("POSTGRES_PASSWORD", "")
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        if not self._api_key:
            raise EnvironmentError("OPENAI_API_KEY is required for PGVectorService")
        self._store = None

    def _get_store(self):
        if self._store is None:
            from langchain_postgres import PGVector
            from langchain_openai import OpenAIEmbeddings
            conn = (f"postgresql+psycopg2://{self._user}:{self._password}"
                    f"@{self._host}:{self._port}/{self._db}")
            self._store = PGVector(
                embeddings=OpenAIEmbeddings(model="text-embedding-3-small"),
                collection_name="governance_docs",
                connection=conn,
            )
        return self._store

    def similarity_search(self, query: str, k: int = 5) -> List[Tuple[Document, float]]:
        store = self._get_store()
        return store.similarity_search_with_relevance_scores(query, k=k)
