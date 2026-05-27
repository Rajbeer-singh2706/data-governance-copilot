"""
src/core/vector_store.py

pgvector store for knowledge_agent RAG.
Requires OPENAI_API_KEY for embeddings and POSTGRES_* for the DB.
Raises EnvironmentError when prerequisites are missing so callers
get a clear failure rather than silent mock data.
"""
from __future__ import annotations
import logging
import os
from typing import List, Tuple

logger = logging.getLogger(__name__)


def get_vector_store(config):
    """
    Return a PGVector store.
    Raises EnvironmentError if OPENAI_API_KEY is absent.
    Raises on connection failure so the calling agent can handle it.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "KnowledgeAgent requires OPENAI_API_KEY for pgvector embeddings. "
            "Set OPENAI_API_KEY in your .env file."
        )

    from langchain_openai import OpenAIEmbeddings
    from langchain_postgres import PGVector

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    store = PGVector(
        embeddings=embeddings,
        collection_name=config.table_name,
        connection=config.connection_string,
        use_jsonb=True,
    )
    logger.info("[vector_store] Connected to pgvector at %s", config.connection_string)
    return store


def similarity_search(store, query: str, k: int = 5, filter=None) -> List[Tuple]:
    """
    Returns (Document, relevance_score) pairs, score 0–1.
    knowledge_agent filters: docs where score > 0.7
    """
    try:
        return store.similarity_search_with_relevance_scores(
            query, k=k, filter=filter
        )
    except Exception as exc:
        logger.warning("[vector_store] search failed: %s", exc)
        return []
