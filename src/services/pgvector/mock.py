"""
src/services/pgvector/mock.py
NullVectorService — keyword-scored governance docs for dev / CI.

No Postgres, no OpenAI key, no network calls required.
Satisfies IVectorService protocol.
"""
from __future__ import annotations

from typing import Any, List, Tuple

try:
    from langchain_core.documents import Document
except ImportError:
    # Fallback if langchain_core not installed (shouldn't happen in normal usage)
    class Document:  # type: ignore
        def __init__(self, page_content: str, metadata: dict):
            self.page_content = page_content
            self.metadata = metadata


_GOVERNANCE_DOCS = [
    Document(
        page_content=(
            "Gross Revenue Retention (GRR) measures the percentage of recurring revenue "
            "retained from existing customers, excluding expansions. A healthy GRR is "
            "above 85% for SaaS businesses. Values below this threshold indicate churn "
            "risk and require immediate investigation."
        ),
        metadata={"source": "governance_policy_v2.pdf", "topic": "GRR", "product": "retention"},
    ),
    Document(
        page_content=(
            "Customer Acquisition Cost (CAC) is calculated as total sales and marketing "
            "spend divided by the number of new customers acquired in a given period. "
            "CAC should be evaluated alongside LTV to determine payback period efficiency."
        ),
        metadata={"source": "metrics_handbook.pdf", "topic": "CAC", "product": "cac"},
    ),
    Document(
        page_content=(
            "Lifetime Value (LTV) represents the total revenue a business can expect from "
            "a single customer account throughout the business relationship. The LTV:CAC "
            "ratio should exceed 3:1 for sustainable unit economics."
        ),
        metadata={"source": "metrics_handbook.pdf", "topic": "LTV", "product": "ltv"},
    ),
    Document(
        page_content=(
            "Net Revenue Retention (NRR) includes expansion revenue from upsells and "
            "cross-sells in addition to base retention. Best-in-class SaaS companies "
            "achieve NRR above 120%, meaning their existing customer base grows without "
            "acquiring new customers."
        ),
        metadata={"source": "governance_policy_v2.pdf", "topic": "NRR", "product": "retention"},
    ),
    Document(
        page_content=(
            "Annual Recurring Revenue (ARR) is the annualised value of all active "
            "subscription contracts. Bookings are new ARR commitments signed in a period "
            "and should be reconciled against the target set at the start of each quarter."
        ),
        metadata={"source": "revenue_runbook.pdf", "topic": "ARR / Bookings", "product": "bookings"},
    ),
    Document(
        page_content=(
            "Data quality rules are enforced via automated checks on every pipeline run. "
            "Failed rules trigger alerts in Collibra and may block downstream consumption. "
            "The data steward is responsible for triaging failures within 24 hours."
        ),
        metadata={"source": "data_quality_sop.pdf", "topic": "Data Quality", "product": "governance"},
    ),
]

# Keywords per doc index for scoring
_DOC_KEYWORDS: List[List[str]] = [
    ["grr", "gross revenue retention", "retention", "churn", "threshold"],
    ["cac", "customer acquisition cost", "marketing", "spend", "payback"],
    ["ltv", "lifetime value", "unit economics", "ratio"],
    ["nrr", "net revenue retention", "expansion", "upsell", "cross"],
    ["arr", "bookings", "annual recurring revenue", "subscription", "quarter"],
    ["data quality", "dq", "rules", "pipeline", "collibra", "steward", "governance"],
]


class NullVectorService:
    """
    Keyword-scored in-memory vector service.
    Returns (Document, score) tuples where score is 0.0–1.0.
    All scores >= KnowledgeAgent.RELEVANCE_THRESHOLD (0.70).
    """

    def similarity_search(
        self, query: str, k: int = 5
    ) -> List[Tuple[Any, float]]:
        q = query.lower()
        scored: List[Tuple[Any, float, int]] = []

        for idx, doc in enumerate(_GOVERNANCE_DOCS):
            keywords = _DOC_KEYWORDS[idx]
            hits = sum(1 for kw in keywords if kw in q)
            # Base score 0.75; each keyword hit adds 0.05, capped at 0.95
            score = min(0.95, 0.75 + hits * 0.05)
            scored.append((doc, score, hits))

        # Sort by hits desc, then original order
        scored.sort(key=lambda x: x[2], reverse=True)
        return [(doc, score) for doc, score, _ in scored[:k]]