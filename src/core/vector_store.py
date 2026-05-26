"""
src/core/vector_store.py  — NEW file (Day 18)
pgvector store replacing FAISS/ChromaDB.
"""
from __future__ import annotations
import logging, os
from typing import List, Optional, Tuple
logger = logging.getLogger(__name__)

def get_vector_store(config):
    """
    Return PGVector | NullVectorStore.
    Falls back to NullVectorStore when ENABLE_MOCK=true or no API key.
    """
    enable_mock = os.getenv("ENABLE_MOCK","true").lower()=="true"
    api_key     = os.getenv("OPENAI_API_KEY","")

    if enable_mock or not api_key:
        return _NullVectorStore()

    try:
        from langchain_openai   import OpenAIEmbeddings
        from langchain_postgres import PGVector

        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        store = PGVector(
            embeddings      = embeddings,
            collection_name = config.table_name,
            connection      = config.connection_string,
            use_jsonb       = True,
        )
        return store
    except (ImportError, Exception) as exc:
        logger.warning("[vector_store] falling back to NullVectorStore: %s", exc)
        return _NullVectorStore()


def similarity_search(store, query, k=5, filter=None) -> List[Tuple]:
    """
    Returns (Document, relevance_score) pairs, score 0–1.
    knowledge_agent.py filters: docs where score > 0.7
    """
    if isinstance(store, _NullVectorStore):
        return store.similarity_search_with_relevance_scores(query, k=k)
    try:
        return store.similarity_search_with_relevance_scores(
            query, k=k, filter=filter
        )
    except Exception as exc:
        logger.warning("[vector_store] search failed: %s", exc)
        return []


class _NullVectorStore:
    """Mock store — returns pre-written governance docs scored 0.75–0.95."""
    _MOCK_DOCS = [
        {"content": "GRR measures recurring revenue retained from existing customers. "
                    "Formula: (Starting MRR - Churn MRR) / Starting MRR. "
                    "Table: analytics.retention_metrics. Owner: Customer Success.",
         "metadata": {"product":"retention","topic":"definition"}},
        {"content": "NRR includes expansion revenue from upsells above GRR. "
                    "NRR > 100% means the cohort is growing. "
                    "Refreshed daily at 02:00 UTC via retention_daily_etl.",
         "metadata": {"product":"retention","topic":"pipeline"}},
        {"content": "Bookings = total value of signed contracts. "
                    "Net-new bookings exclude renewals. Certified in Collibra 2024-01-10. "
                    "Table: analytics.bookings_fact. Owner: Revenue Operations.",
         "metadata": {"product":"bookings","topic":"definition"}},
        {"content": "CAC = Total S&M Spend / New Customers. "
                    "Payback = CAC / Monthly Gross Margin per Customer. "
                    "Table: analytics.cac_metrics. Owner: Marketing Analytics.",
         "metadata": {"product":"cac","topic":"definition"}},
        {"content": "LTV = ARPU × Gross Margin × (1 / Churn Rate). "
                    "LTV:CAC > 3 is healthy. Owner: Data Science. "
                    "Table: analytics.customer_ltv.",
         "metadata": {"product":"ltv","topic":"definition"}},
        {"content": "DQ rules enforce completeness, uniqueness, validity. "
                    "Registry tracks rule ID, expression, threshold, severity. "
                    "Failed rules alert owning team Slack channel.",
         "metadata": {"product":"all","topic":"data_quality"}},
    ]
    
    def similarity_search_with_relevance_scores(self, query, k=5, **kw):
        from langchain_core.documents import Document
        q_words = set(query.lower().split())
        scored  = []
        for d in self._MOCK_DOCS:
            hits  = sum(1 for w in q_words if w in d["content"].lower())
            score = 0.75 + min(hits*0.04, 0.20)
            scored.append((Document(page_content=d["content"],
                                    metadata=d["metadata"]), round(score,2)))
        scored.sort(key=lambda x:x[1], reverse=True)
        return scored[:k]