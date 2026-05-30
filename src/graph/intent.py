"""Intent classification — structured LLM output with keyword fallback."""
from __future__ import annotations

import re
from enum import Enum
from typing import List

from pydantic import BaseModel

KEYWORD_MAP = {
    "full_diagnostic": ["full", "diagnostic", "overview", "all", "everything"],
    "data_quality": ["quality", "dq", "score", "rules", "validation"],
    "governance": ["governance", "policy", "compliance", "standard", "framework"],
    "incident_review": ["incident", "outage", "issue", "problem", "alert"],
    "knowledge_lookup": ["what is", "define", "explain", "how does", "what are"],
    "metric_analysis": ["metric", "kpi", "trend", "analysis", "performance", "grr", "arr", "cac", "ltv"],
    "write_ticket": ["create ticket", "open ticket", "file ticket", "raise issue"],
    "write_metadata": ["update metadata", "edit asset", "set owner", "assign steward"],
    "write_rule": ["create rule", "add rule", "define rule", "new rule"],
}


class QueryIntent(str, Enum):
    full_diagnostic = "full_diagnostic"
    data_quality = "data_quality"
    governance = "governance"
    incident_review = "incident_review"
    knowledge_lookup = "knowledge_lookup"
    metric_analysis = "metric_analysis"
    write_ticket = "write_ticket"
    write_metadata = "write_metadata"
    write_rule = "write_rule"
    unknown = "unknown"


class IntentClassification(BaseModel):
    intent: QueryIntent
    data_products: List[str]
    confidence: float
    reasoning: str


def _keyword_fallback(query: str) -> IntentClassification:
    q = query.lower()
    for intent, keywords in KEYWORD_MAP.items():
        if any(kw in q for kw in keywords):
            products = [p for p in ["retention", "bookings", "cac", "ltv"] if p in q]
            return IntentClassification(
                intent=QueryIntent(intent),
                data_products=products,
                confidence=0.65,
                reasoning=f"Keyword match: {intent}",
            )
    return IntentClassification(
        intent=QueryIntent.unknown,
        data_products=[],
        confidence=0.3,
        reasoning="No keyword match found",
    )


def classify_intent(query: str, config=None) -> IntentClassification:
    """Classify query intent using structured LLM output, falling back to keywords."""
    try:
        from src.core.llm_factory import get_structured_llm
        llm = get_structured_llm(config, schema=IntentClassification)
        prompt = (
            f"Classify this data governance query. "
            f"Identify the intent, relevant data products (retention/bookings/cac/ltv), "
            f"confidence (0-1), and one-sentence reasoning.\n\nQuery: {query}"
        )
        result = llm.invoke(prompt)
        if isinstance(result, IntentClassification):
            return result
    except Exception:
        pass
    return _keyword_fallback(query)
