"""
src/graph/intent.py
Day 13: Structured output intent classifier.

Uses the LLM factory (get_structured_llm) — works with Groq OR OpenAI,
controlled by LLM_PROVIDER env var.

Flow:
  1. No API key found → keyword fallback immediately (dev / CI friendly)
  2. LLM succeeds     → return IntentClassification
  3. LLM fails        → keyword fallback + log reason

LangSmith traces every call automatically via LANGCHAIN_TRACING_V2=true.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import List

from pydantic import BaseModel, Field


# ── 1. Intent enum (unchanged — routing.py depends on these values) ────────

class QueryIntent(str, Enum):
    WRITE_TICKET     = "write_ticket"
    WRITE_METADATA   = "write_metadata"
    WRITE_RULE       = "write_rule"
    FULL_DIAGNOSTIC  = "full_diagnostic"
    DATA_QUALITY     = "data_quality"
    GOVERNANCE       = "governance"
    INCIDENT_REVIEW  = "incident_review"
    KNOWLEDGE_LOOKUP = "knowledge_lookup"
    METRIC_ANALYSIS  = "metric_analysis"
    UNKNOWN          = "unknown"


# ── 2. Structured output schema ────────────────────────────────────────────

class IntentClassification(BaseModel):
    """
    Structured output schema for intent classification.
    Returned by both the LLM chain and the keyword fallback.
    """
    intent: QueryIntent = Field(
        description="Primary intent of the user's query."
    )
    data_products: List[str] = Field(
        default_factory=list,
        description=(
            "Data products referenced or implied. "
            "Allowed values: retention, bookings, cac, ltv."
        ),
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Classifier confidence 0.0–1.0.",
    )
    reasoning: str = Field(
        default="",
        description="One-sentence rationale for the intent chosen.",
    )


# ── 3. System prompt ───────────────────────────────────────────────────────

_SYSTEM = """\
You are an intent classifier for an enterprise Data Governance AI Copilot.

Available data products:
  • retention  — customer renewal / churn metrics  (GRR, NRR, churn rate)
  • bookings   — signed-contract revenue           (ARR, MRR, net-new bookings)
  • cac        — customer acquisition cost         (blended CAC, payback period)
  • ltv        — customer lifetime value            (avg LTV, LTV:CAC ratio)

Intent taxonomy — pick EXACTLY ONE:
  write_ticket      create / file a Jira ticket, bug report, or incident
  write_metadata    update owner, description, or classification in Collibra
  write_rule        create a new data-quality rule
  full_diagnostic   root-cause analysis, investigation, "why did X happen"
  data_quality      DQ scores, completeness, accuracy, validation results
  governance        ownership, lineage, stewardship, certification status
  incident_review   check open Jira bugs, incidents, blockers
  knowledge_lookup  definitions, explanations, "what is X / how does X work"
  metric_analysis   metric values, trends, comparisons, anomalies
  unknown           cannot determine intent from the query

Rules:
  1. Return exactly ONE intent.
  2. Populate data_products only when clearly referenced; else leave empty.
  3. Set confidence ≥ 0.90 when the intent is unambiguous.
  4. Set confidence 0.60–0.89 when moderately certain.
  5. Set confidence < 0.60 and intent = unknown when genuinely uncertain.
"""

# ── 4. Helper: resolve active API key ─────────────────────────────────────

def _get_active_api_key() -> str:
    """
    Return whichever API key is configured based on LLM_PROVIDER.
    Supports groq and openai providers.
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "groq":
        return os.getenv("GROQ_API_KEY", "")
    return os.getenv("OPENAI_API_KEY", "")


# ── 5. Lazy singleton chain ────────────────────────────────────────────────

_chain = None  # type: ignore[assignment]


def _build_chain():
    """Construct prompt | llm.with_structured_output chain."""
    from core.llm_factory import get_structured_llm
    from config.settings  import config
    from langchain_core.prompts import ChatPromptTemplate

    # get_structured_llm now returns llm.with_structured_output(schema)
    structured_llm = get_structured_llm(config.llm, IntentClassification)

    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM),
        ("human", "Classify this query:\n{query}"),
    ])
    return prompt | structured_llm


# ── 6. Public API ──────────────────────────────────────────────────────────

def classify_intent_gpt(query: str) -> IntentClassification:
    """
    Classify intent via structured LLM output (Groq or OpenAI).

    Flow:
      1. No API key → keyword fallback immediately (dev / CI friendly)
      2. LLM succeeds → return IntentClassification
      3. LLM fails    → keyword fallback + log reason
    """
    global _chain

    # Check the correct API key based on configured provider
    if not _get_active_api_key():
        provider = os.getenv("LLM_PROVIDER", "openai")
        return _keyword_fallback(query, reason=f"No API key set for provider '{provider}'")

    try:
        if _chain is None:
            _chain = _build_chain()
        result: IntentClassification = _chain.invoke({"query": query})
        return result

    except Exception as exc:  # noqa: BLE001
        print(f"[intent] LLM classification failed — falling back to keywords. Error: {exc}")
        return _keyword_fallback(query, reason=str(exc))


# ── Backward-compat shims (nodes.py + tests import these) ─────────────────

def classify_intent(query: str) -> str:
    """Return intent string — used by supervisor_node."""
    return classify_intent_gpt(query).intent.value


def extract_products(query: str) -> List[str]:
    """Return product list — used by supervisor_node."""
    return classify_intent_gpt(query).data_products


# ── 7. Keyword fallback (Day 12 logic, hardened) ──────────────────────────

_INTENT_RULES: dict = {
    QueryIntent.WRITE_TICKET:     [
        "create ticket", "create a bug", "open bug",
        "raise issue", "log incident", "file a ticket",
    ],
    QueryIntent.WRITE_METADATA:   [
        "update owner", "set owner", "update metadata",
        "classify", "update description",
    ],
    QueryIntent.WRITE_RULE:       [
        "create rule", "add rule", "define rule",
        "new rule", "create dq rule",
    ],
    QueryIntent.FULL_DIAGNOSTIC:  [
        "why did", "root cause", "investigate",
        "explain why", "diagnose", "what happened",
    ],
    QueryIntent.DATA_QUALITY:     [
        "data quality", "dq score", "completeness",
        "accuracy", "quality score",
    ],
    QueryIntent.GOVERNANCE:       [
        "who owns", "owner", "steward", "lineage",
        "governance", "certified",
    ],
    QueryIntent.INCIDENT_REVIEW:  [
        "jira", "open bugs", "open issues",
        "incidents", "blockers",
    ],
    QueryIntent.KNOWLEDGE_LOOKUP: [
        "what is", "what are", "how does", "how do",
        "explain", "describe", "define",
    ],
    QueryIntent.METRIC_ANALYSIS:  [
        "how much", "compare", "trend",
        "pattern", "anomaly", "metrics",
    ],
}

_PRODUCT_KEYWORDS: dict = {
    "retention": "retention", "churn": "retention",
    "grr": "retention",       "nrr": "retention",
    "bookings": "bookings",   "revenue": "bookings",
    "arr": "bookings",        "mrr": "bookings",
    "cac": "cac",             "payback": "cac",
    "ltv": "ltv",             "lifetime": "ltv",
}


def _keyword_fallback(query: str, reason: str = "") -> IntentClassification:
    """Pure keyword matching — O(n) scan, no API call."""
    q = query.lower()

    intent = QueryIntent.UNKNOWN
    for candidate, keywords in _INTENT_RULES.items():
        if any(kw in q for kw in keywords):
            intent = candidate
            break

    products = list({p for kw, p in _PRODUCT_KEYWORDS.items() if kw in q})

    return IntentClassification(
        intent=intent,
        data_products=products or [],
        confidence=0.50,
        reasoning=f"Keyword fallback. Reason: {reason or 'no reason given'}",
    )