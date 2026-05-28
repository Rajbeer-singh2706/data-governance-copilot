"""
src/core/vector_store.py
Backwards-compatibility shim.

The real implementation has moved to:
  services/pgvector/real.py   → PGVectorService
  services/pgvector/mock.py   → NullVectorService
  services/factory.py         → get_vector_service()

This module re-exports the two functions that were used in Day 18
so that any existing code importing from core.vector_store still works.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def get_vector_store(config):
    """
    Return a store-like object that exposes
    similarity_search_with_relevance_scores().

    Delegates to services.factory.get_vector_service() which reads
    ENABLE_MOCK and handles fallback automatically.
    """
    from services.factory import get_vector_service
    # Wrap the IVectorService so it exposes the old method name
    svc = get_vector_service(config)
    return _ServiceAdapter(svc)


def similarity_search(store, query: str, k: int = 5, filter: Optional[dict] = None) -> List[Tuple]:
    """
    Run similarity search against the store returned by get_vector_store().
    """
    if isinstance(store, _ServiceAdapter):
        return store.similarity_search_with_relevance_scores(query, k=k)
    # Direct IVectorService (injected in tests)
    return store.similarity_search(query, k=k)


class _ServiceAdapter:
    """Wraps IVectorService to expose the legacy method name."""
    def __init__(self, svc):
        self._svc = svc

    def similarity_search_with_relevance_scores(self, query: str, k: int = 5, **kwargs):
        return self._svc.similarity_search(query, k=k)

    def similarity_search(self, query: str, k: int = 5):
        return self._svc.similarity_search(query, k=k)