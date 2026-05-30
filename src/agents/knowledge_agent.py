"""Knowledge Agent — delegates to IVectorService."""
from __future__ import annotations

from typing import Optional

from src.core.base_agent import AgentRequest, AgentResult, BaseAgent
from src.core.mcp_client import get_mcp_tools

RELEVANCE_THRESHOLD = 0.70


class KnowledgeAgent(BaseAgent):
    def __init__(self, config: Optional[object] = None, vector_service=None):
        from src.services.factory import get_vector_service
        self._svc = vector_service or get_vector_service(config)
        self._mcp_tools = get_mcp_tools("knowledge")

    def execute(self, request: AgentRequest) -> AgentResult:
        try:
            results = self._svc.similarity_search(request.query, k=5)
            relevant = [(doc, score) for doc, score in results if score >= RELEVANCE_THRESHOLD]

            knowledge = [
                {
                    "topic": doc.metadata.get("topic", "Governance Policy"),
                    "definition": doc.page_content,
                    "source": doc.metadata.get("source", "governance-docs"),
                }
                for doc, _ in relevant
            ]

            avg_score = (
                sum(score for _, score in relevant) / len(relevant) if relevant else 0.0
            )

            return AgentResult(
                success=True,
                data={"knowledge": knowledge},
                message=f"Found {len(knowledge)} relevant governance documents",
                confidence=round(avg_score, 4),
                sources=[k["source"] for k in knowledge],
                metadata={"docs_retrieved": len(relevant), "threshold": RELEVANCE_THRESHOLD},
            )
        except Exception as exc:
            return AgentResult.failure(f"KnowledgeAgent error: {exc}", str(exc))
