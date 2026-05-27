"""
src/core/vector_store.py
Day 18: pgvector-backed vector store — replaces ChromaDB / FAISS.

Why pgvector over ChromaDB on ECS Fargate:
  ChromaDB needs a persistent EBS volume that survives task restarts.
  pgvector runs inside the existing PostgreSQL instance (same RDS),
  so there's no extra infrastructure, no EBS mount, and no cold-start
  delay when Fargate replaces a task.

Two public functions:
  get_vector_store(config)          → PGVector instance
  similarity_search(store, query)   → [(Document, score), ...]  score 0–1

Run init_pgvector.sql once before using:
  psql $DATABASE_URL < scripts/init_pgvector.sql
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Main public API ────────────────────────────────────────────────────────

def get_vector_store(config):
    """
    Return a LangChain PGVector store connected to the governance_db.

    Falls back to a NullVectorStore (mock) when:
      • ENABLE_MOCK=true
      • OPENAI_API_KEY is absent (embeddings need the API)
      • psycopg2 / langchain-postgres are not installed
      • PostgreSQL is unreachable

    Args:
        config: VectorDBConfig from AppConfig

    Returns:
        PGVector | NullVectorStore
    """
    enable_mock = os.getenv("ENABLE_MOCK", "true").lower() == "true"
    api_key     = os.getenv("OPENAI_API_KEY", "")

    if enable_mock or not api_key:
        logger.info("[vector_store] mock mode — using NullVectorStore")
        return _NullVectorStore()

    try:
        from langchain_openai   import OpenAIEmbeddings
        from langchain_postgres import PGVector

        embeddings = OpenAIEmbeddings(
            model   = "text-embedding-3-small",
            api_key = api_key,
        )

        store = PGVector(
            embeddings      = embeddings,
            collection_name = config.table_name,
            connection      = config.connection_string,
            use_jsonb       = True,   # structured metadata filtering
        )
        logger.info("[vector_store] pgvector connected: %s", config.connection_string)
        return store

    except ImportError as exc:
        logger.warning(
            "[vector_store] missing packages (%s) — using NullVectorStore. "
            "Run: uv pip install langchain-postgres psycopg2-binary", exc
        )
        return _NullVectorStore()

    except Exception as exc:
        logger.warning(
            "[vector_store] connection failed (%s) — using NullVectorStore", exc
        )
        return _NullVectorStore()


def similarity_search(
    store,
    query:  str,
    k:      int             = 5,
    filter: Optional[dict]  = None,
) -> List[Tuple]:
    """
    Run a similarity search and return (Document, relevance_score) pairs.

    Score range: 0.0 (unrelated) → 1.0 (identical).
    In knowledge_agent.py we filter: docs where score > 0.7

    Args:
        store:  Result of get_vector_store()
        query:  Natural-language query string
        k:      Max results to return
        filter: Optional metadata filter dict (e.g. {"product": "retention"})

    Returns:
        List of (Document, float) tuples, ordered by relevance (highest first)
    """
    if isinstance(store, _NullVectorStore):
        return store.similarity_search_with_relevance_scores(query, k=k)

    try:
        if filter:
            return store.similarity_search_with_relevance_scores(
                query, k=k, filter=filter
            )
        return store.similarity_search_with_relevance_scores(query, k=k)

    except Exception as exc:
        logger.warning("[vector_store] similarity_search failed: %s", exc)
        return []


# ── Mock fallback ──────────────────────────────────────────────────────────

class _NullVectorStore:
    """
    In-memory mock vector store for dev / no-API-key environments.

    Returns a small set of pre-written governance documents that cover
    the four data products. Scores are fixed at 0.85 so they pass the
    > 0.7 threshold in knowledge_agent.py.
    """

    _MOCK_DOCS = [
        {
            "content": (
                "Gross Retention Rate (GRR) measures the percentage of recurring revenue "
                "retained from existing customers, excluding upsells. "
                "Formula: (Starting MRR - Churn MRR) / Starting MRR. "
                "Owned by the Customer Success team. Table: analytics.retention_metrics."
            ),
            "metadata": {"product": "retention", "topic": "definition"},
        },
        {
            "content": (
                "Net Revenue Retention (NRR) includes expansion revenue from upsells and "
                "cross-sells in addition to GRR. NRR > 100% means the cohort is growing. "
                "Data refreshed daily at 02:00 UTC via Databricks job retention_daily_etl."
            ),
            "metadata": {"product": "retention", "topic": "pipeline"},
        },
        {
            "content": (
                "Bookings represent the total value of signed contracts in a period. "
                "Net-new bookings exclude renewals. ARR = Annual Recurring Revenue. "
                "Owned by Revenue Operations. Table: analytics.bookings_fact. "
                "Certified in Collibra on 2024-01-10."
            ),
            "metadata": {"product": "bookings", "topic": "definition"},
        },
        {
            "content": (
                "Customer Acquisition Cost (CAC) is the average spend to acquire one customer. "
                "Blended CAC = Total S&M Spend / New Customers. "
                "Payback period = CAC / Monthly Gross Margin per Customer. "
                "Owned by Marketing Analytics. Table: analytics.cac_metrics."
            ),
            "metadata": {"product": "cac", "topic": "definition"},
        },
        {
            "content": (
                "Customer Lifetime Value (LTV) predicts the total revenue a customer generates. "
                "LTV = ARPU × Gross Margin × (1 / Churn Rate). "
                "LTV:CAC ratio > 3 is considered healthy. "
                "Owned by Data Science. Table: analytics.customer_ltv."
            ),
            "metadata": {"product": "ltv", "topic": "definition"},
        },
        {
            "content": (
                "Data quality rules enforce completeness, uniqueness, and validity. "
                "The DQ rule registry tracks rule ID, expression, threshold, and severity. "
                "Rules run on a schedule via Databricks DLT expectations. "
                "Failed rules trigger alerts to the owning team's Slack channel."
            ),
            "metadata": {"product": "all", "topic": "data_quality"},
        },
    ]

    def similarity_search_with_relevance_scores(
        self, query: str, k: int = 5, **kwargs
    ) -> List[Tuple]:
        from langchain_core.documents import Document

        # Simple keyword relevance: count query-word matches
        q_words  = set(query.lower().split())
        scored   = []

        for doc_data in self._MOCK_DOCS:
            content    = doc_data["content"]
            word_hits  = sum(1 for w in q_words if w in content.lower())
            base_score = 0.75 + min(word_hits * 0.04, 0.20)  # 0.75 – 0.95

            scored.append((
                Document(page_content=content, metadata=doc_data["metadata"]),
                round(base_score, 2),
            ))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]