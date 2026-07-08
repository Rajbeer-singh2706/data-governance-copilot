"""NullVectorService — keyword-scored governance docs for dev/test."""
from __future__ import annotations

from typing import List, Tuple

from langchain_core.documents import Document

RELEVANCE_THRESHOLD = 0.70

_DOCS = [
    ("Data Retention Policy", "retention",
     "Customer retention metrics must maintain a GRR above 85%. Churn above 15% triggers automatic escalation to Customer Success."),
    ("Bookings Governance Standard", "bookings",
     "Bookings data must reconcile with CRM within 24 hours. ARR calculations follow ASC 606 revenue recognition standards."),
    ("CAC Data Quality Rules", "cac",
     "Customer acquisition cost must be calculated monthly. Blended CAC should not exceed 36-month payback period."),
    ("LTV Calculation Standard", "ltv",
     "Lifetime value predictions use 24-month cohort analysis. LTV:CAC ratio below 3x triggers review by Data Science."),
    ("Data Governance Framework", "general",
     "All data assets must be registered in Collibra within 30 days of creation. Data owners are accountable for quality scores above 90%."),
    ("Incident Response Playbook", "general",
     "Data quality incidents must be logged in Jira within 4 hours. Critical incidents require executive notification within 24 hours."),
]


class NullVectorService:
    """Keyword-scored vector service for development — no embeddings required."""

    def similarity_search(self, query: str, k: int = 5) -> List[Tuple[Document, float]]:
        query_lower = query.lower()
        results = []
        for title, product, content in _DOCS:
            score = 0.75  # base score
            if product in query_lower or product == "general":
                score += 0.10
            words = query_lower.split()
            hits = sum(1 for w in words if w in content.lower() or w in title.lower())
            score = min(0.99, score + hits * 0.03)
            if score >= RELEVANCE_THRESHOLD:
                doc = Document(
                    page_content=content,
                    metadata={"source": f"governance://{title.replace(' ', '_')}", "product": product, "topic": title},
                )
                results.append((doc, round(score, 4)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]
