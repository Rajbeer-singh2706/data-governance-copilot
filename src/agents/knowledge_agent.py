"""
src/agents/knowledge_agent.py
Retrieves business context from the knowledge base.

Mock mode  : keyword-scored in-memory lookup.
Production : pgvector similarity search via get_vector_store / similarity_search.
"""

from typing import Any, Dict, List, Optional
from core.base_agent import BaseAgent, AgentRequest, AgentResult
from config.settings import AppConfig

# ── Mock knowledge base ──────────────────────────────────────────────────────
MOCK_KNOWLEDGE_BASE = {
    "retention": {
        "topic": "retention",
        "definition": (
            "Gross Retention Rate (GRR) measures the percentage of "
            "recurring revenue retained from existing customers, "
            "excluding expansion. Net Retention Rate (NRR) includes "
            "upsells. Benchmarks: GRR >85% (SMB), >90% (Enterprise)."
        ),
        "business_context": (
            "Retention declines in Q3 2024 were attributed to: "
            "(1) product gaps in the reporting module cited in 34% "
            "of churn surveys, (2) competitive displacement by Vendor X "
            "in SMB, (3) a 2-week SLA breach in EU affecting 12 accounts."
        ),
        "runbook": "See: Retention Recovery Playbook v2.1 (SharePoint/CS/Playbooks/)",
        "source":  "SharePoint: CS Strategy Deck Q3 2024",
    },
    "bookings": {
        "topic": "bookings",
        "definition": (
            "Bookings = total value of new signed contracts in a period. "
            "Net New Bookings = New Logo + Expansion - Contraction. "
            "Bookings differ from Revenue recognised over the contract term."
        ),
        "business_context": (
            "The bookings methodology was updated in FY2024 to exclude "
            "multi-year prepayments from current-period totals. This "
            "created a ~12% YoY comparison distortion in Q1 2024."
        ),
        "runbook": "See: Revenue Metrics Glossary v3.0 (Confluence/RevOps/)",
        "source":  "Confluence: Revenue Metrics Glossary",
    },
    "cac": {
        "topic": "cac",
        "definition": (
            "CAC = Total Sales & Marketing Spend / New Customers Acquired. "
            "Blended CAC includes all channels. "
            "CAC Payback = CAC / (ARR per Customer / 12)."
        ),
        "business_context": (
            "CAC increased 18% YoY due to higher LinkedIn CPM rates and "
            "expanded SDR headcount. Target: $9,500 blended CAC by Q4 FY2025."
        ),
        "runbook": "See: Marketing Analytics Handbook (Confluence/Marketing/)",
        "source":  "Confluence: Marketing Analytics Handbook",
    },
    "ltv": {
        "topic": "ltv",
        "definition": (
            "LTV = (ARR x Gross Margin) / Churn Rate. "
            "Data Science updates the predictive LTV model quarterly "
            "using XGBoost on product usage and billing signals."
        ),
        "business_context": (
            "LTV/CAC ratio of 3.5x is below the 5x Enterprise target. "
            "Project Helix (Q2 2025) will add expansion revenue signals "
            "to the LTV model."
        ),
        "runbook": "See: LTV Model Docs (Confluence/DS/Models/LTV/)",
        "source":  "Confluence: Data Science Model Registry",
    },
}

# ── Knowledge Agent ──────────────────────────────────────────────────────────
class KnowledgeAgent(BaseAgent):
    """
    Retrieves business context and definitions.

    FIX: `config` is now Optional with a default of None so that unit tests
    can instantiate with just `KnowledgeAgent(enable_mock=True)` without
    needing a real AppConfig object.  When config is None (or enable_mock is
    True), the agent uses the in-memory MOCK_KNOWLEDGE_BASE and skips the
    pgvector store entirely.
    """
    name         = "knowledge_agent"
    description  = "Retrieves business context and definitions"
    capabilities = [
        "business_definitions",
        "contextual_explanation",
        "runbook_retrieval",
    ]

    TOPIC_KEYWORDS = {
        "retention": ["retention", "churn", "grr", "nrr", "renewal"],
        "bookings":  ["bookings", "revenue", "arr", "mrr", "contract"],
        "cac":       ["cac", "acquisition cost", "payback", "marketing spend"],
        "ltv":       ["ltv", "lifetime value", "customer value"],
    }

    def __init__(self, config: Optional[Any] = None, enable_mock: bool = True):
        # FIX: config defaults to None so tests can do KnowledgeAgent(enable_mock=True)
        super().__init__(config=config, enable_mock=enable_mock)
        self._store = None
        # Only initialise the vector store when running in production mode
        # with a real config that has vector_db settings.
        if not enable_mock and config is not None:
            try:
                from core.vector_store import get_vector_store
                self._store = get_vector_store(config.vector_db)
            except Exception:
                pass  # fall back to mock if store unavailable

    # ── helpers ──────────────────────────────────────────────────────────────

    def _detect_topics(self, query: str) -> list:
        q      = query.lower()
        topics = [
            topic
            for topic, keywords in self.TOPIC_KEYWORDS.items()
            if any(kw in q for kw in keywords)
        ]
        return topics if topics else ["retention"]

    def _mock_search(self, query: str) -> List[Dict]:
        """Keyword-scored mock retrieval from MOCK_KNOWLEDGE_BASE."""
        topics  = self._detect_topics(query)
        entries = []
        for topic in topics:
            if topic in MOCK_KNOWLEDGE_BASE:
                entries.append(MOCK_KNOWLEDGE_BASE[topic])
        return entries if entries else [MOCK_KNOWLEDGE_BASE["retention"]]

    def _build_summary(self, entries: List[Dict]) -> str:
        parts = ["📚 **Business Context**"]
        for entry in entries:
            topic = entry.get("topic", "").upper()
            parts.append(f"\n**{topic}**")
            if "definition" in entry:
                parts.append(f"  _Definition:_ {entry['definition']}")
            if "business_context" in entry:
                parts.append(f"  _Context:_ {entry['business_context']}")
            if "runbook" in entry:
                parts.append(f"  _Reference:_ {entry['runbook']}")
        return "\n".join(parts)

    # ── BaseAgent contract ────────────────────────────────────────────────────

    def _execute(self, request: AgentRequest) -> AgentResult:
        # Mock / no vector store → use keyword lookup
        if self.enable_mock or self._store is None:
            entries  = self._mock_search(request.query)
            summary  = self._build_summary(entries)
            sources  = [e.get("source", "Knowledge Base") for e in entries]
            return AgentResult(
                agent_name = self.name,
                success    = True,
                summary    = summary,
                data       = {"knowledge": entries},
                sources    = sources,
                confidence = 0.82,
            )

        # Production: pgvector similarity search
        from core.vector_store import similarity_search
        results  = similarity_search(self._store, request.query, k=5)
        relevant = [(doc, score) for doc, score in results if score >= 0.70]

        if not relevant:
            return AgentResult(
                agent_name = self.name,
                success    = True,
                summary    = "No relevant documents found.",
                confidence = 0.0,
            )

        docs_text = "\n\n".join(
            f"[{i+1}] (score={s:.2f})\n{d.page_content}"
            for i, (d, s) in enumerate(relevant)
        )
        avg_conf = round(sum(s for _, s in relevant) / len(relevant), 2)
        sources  = [
            f"{d.metadata.get('product', '?')} — {d.metadata.get('topic', '?')}"
            for d, _ in relevant
        ]
        return AgentResult(
            agent_name = self.name,
            success    = True,
            summary    = docs_text,
            confidence = avg_conf,
            sources    = sources,
        )