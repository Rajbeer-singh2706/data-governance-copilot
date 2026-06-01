"""Knowledge Agent — delegates to IVectorService."""
from __future__ import annotations

import time
from typing import Optional

from core.base_agent import AgentRequest, AgentResult, BaseAgent
from core.mcp_client import get_mcp_tools

RELEVANCE_THRESHOLD = 0.70


class KnowledgeAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "knowledge_agent"

    def __init__(self, config: Optional[object] = None, vector_service=None, enable_mock: bool = False):
        from services.factory import get_vector_service
        self._svc = vector_service or get_vector_service(config)
        self._mcp_tools = get_mcp_tools("knowledge")

    def execute(self, request: AgentRequest) -> AgentResult:
        t0 = time.monotonic()
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
            elapsed = (time.monotonic() - t0) * 1000
            return AgentResult(
                success=True,
                data={"knowledge": knowledge},
                message=f"Found {len(knowledge)} relevant governance documents",
                confidence=round(avg_score, 4),
                sources=[k["source"] for k in knowledge],
                metadata={"docs_retrieved": len(relevant), "threshold": RELEVANCE_THRESHOLD},
                execution_time_ms=elapsed,
            )
        except Exception as exc:
            return AgentResult.failure(f"KnowledgeAgent error: {exc}", str(exc))
