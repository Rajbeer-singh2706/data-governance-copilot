"""Backwards-compat shim — delegates to services/pgvector/."""
from __future__ import annotations

from typing import List, Tuple


class _ServiceAdapter:
    """Wraps IVectorService to expose legacy method names."""

    def __init__(self, svc):
        self._svc = svc

    def similarity_search_with_relevance_scores(self, query: str, k: int = 5):
        return self._svc.similarity_search(query, k=k)


def get_vector_store(config=None) -> _ServiceAdapter:
    from src.services.factory import get_vector_service
    svc = get_vector_service(config)
    return _ServiceAdapter(svc)


def similarity_search(store, query: str, k: int = 5) -> List[Tuple]:
    if isinstance(store, _ServiceAdapter):
        return store._svc.similarity_search(query, k=k)
    return store.similarity_search(query, k=k)
