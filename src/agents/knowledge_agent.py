from typing import Any, Dict, List
from core.base_agent import BaseAgent, AgentRequest, AgentResult

# ── Mock knowledge base ──────────────────────────────────
MOCK_KNOWLEDGE_BASE = {
    "retention": {
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

# ── Knowledge Agent ──────────────────────────────────────
class KnowledgeAgent(BaseAgent):
    """
    Retrieves business context from the knowledge base.
    Mock mode: searches MOCK_KNOWLEDGE_BASE dict.
    Production: searches FAISS/Chroma vector store.
    """
    name         = "knowledge_agent"
    description  = "Retrieves business context and definitions"
    capabilities = [
        "business_definitions",
        "contextual_explanation",
        "runbook_retrieval",
    ]

    TOPIC_KEYWORDS = {
        "retention": ["retention","churn","grr","nrr","renewal"],
        "bookings":  ["bookings","revenue","arr","mrr","contract"],
        "cac":       ["cac","acquisition cost","payback",
                      "marketing spend"],
        "ltv":       ["ltv","lifetime value","customer value"],
    }

    def __init__(self, config=None, enable_mock: bool = True):
        super().__init__(config, enable_mock)

    def _detect_topics(self, query: str) -> list:
        q      = query.lower()
        topics = [
            topic
            for topic, keywords in self.TOPIC_KEYWORDS.items()
            if any(kw in q for kw in keywords)
        ]
        return topics if topics else ["retention"]

    def _execute(self, request: AgentRequest) -> AgentResult:
        topics  = self._detect_topics(request.query)
        entries = []
        sources = []

        for topic in topics:
            if self.enable_mock:
                entry = MOCK_KNOWLEDGE_BASE.get(topic)
                if entry:
                    entries.append({"topic": topic, **entry})
                    sources.append(entry.get("source", topic))
            # production: vector store search goes here

        if not entries:
            return AgentResult(
                agent_name = self.name,
                success    = True,
                summary    = "No knowledge base entries found "
                             "for this query.",
                sources    = [],
                confidence = 0.5,
            )

        summary = self._build_summary(entries)

        return AgentResult(
            agent_name = self.name,
            success    = True,
            data       = {"knowledge": entries},
            summary    = summary,
            sources    = sources,
            confidence = 0.88,
            metadata   = {"topics_found": topics},
        )

    def _build_summary(self, entries: List[Dict]) -> str:
        parts = ["📚 **Business Context**"]
        for entry in entries:
            topic = entry.get("topic", "").upper()
            parts.append(f"\n**{topic}**")
            if "definition" in entry:
                parts.append(
                    f"  _Definition:_ {entry['definition']}"
                )
            if "business_context" in entry:
                parts.append(
                    f"  _Context:_ {entry['business_context']}"
                )
            if "runbook" in entry:
                parts.append(
                    f"  _Reference:_ {entry['runbook']}"
                )
        return "\n".join(parts)