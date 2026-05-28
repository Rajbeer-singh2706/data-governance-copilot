"""
src/agents/knowledge_agent.py

Retrieves business context via IVectorService (pgvector or NullVectorService).
All pgvector/embedding logic lives in services/pgvector/.
This agent only owns:
  - relevance threshold filtering
  - entry formatting
  - summary building
"""
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, AgentRequest, AgentResult
from services.base import IVectorService
from services.factory import get_vector_service


class KnowledgeAgent(BaseAgent):
    """
    Retrieves business context and definitions via IVectorService.
    In mock mode: NullVectorService (no Postgres/OpenAI key needed).
    In prod mode: PGVectorService (requires POSTGRES_* + OPENAI_API_KEY).
    """
    name = "knowledge_agent"
    description = "Retrieves business context and definitions"
    capabilities = [
        "business_definitions",
        "contextual_explanation",
        "runbook_retrieval",
    ]

    RELEVANCE_THRESHOLD = 0.70

    def __init__(
        self,
        config=None,
        vector_service: Optional[IVectorService] = None,
        **kwargs,
    ) -> None:
        """
        Args:
            config:         AppConfig (used by factory if vector_service not provided)
            vector_service: Explicit IVectorService injection (useful in tests)
        """
        kwargs.pop("enable_mock", None)
        super().__init__(config=config, enable_mock=False)
        self._vec: IVectorService = vector_service or get_vector_service(config)

    # ── IAgent ────────────────────────────────────────────────────────────

    def _execute(self, request: AgentRequest) -> AgentResult:
        results  = self._vec.similarity_search(request.query, k=5)
        relevant = [(doc, score) for doc, score in results if score >= self.RELEVANCE_THRESHOLD]

        if not relevant:
            return AgentResult(
                agent_name=self.name,
                success=True,
                summary="No relevant documents found for this query.",
                data={"knowledge": []},
                confidence=0.0,
            )

        avg_conf = round(sum(s for _, s in relevant) / len(relevant), 2)
        sources  = [
            f"{d.metadata.get('source', '?')} — {d.metadata.get('topic', '?')}"
            for d, _ in relevant
        ]
        entries = [
            {
                "topic":      d.metadata.get("topic", ""),
                "definition": d.page_content,
                "source":     d.metadata.get("source", ""),
            }
            for d, _ in relevant
        ]

        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=self._build_summary(entries),
            data={"knowledge": entries},
            confidence=avg_conf,
            sources=sources,
        )

    # ── Summary formatting ────────────────────────────────────────────────

    @staticmethod
    def _build_summary(entries: List[Dict]) -> str:
        parts = ["📚 **Business Context**"]
        for entry in entries:
            topic = entry.get("topic", "").upper()
            parts.append(f"\n**{topic}**")
            parts.append(f"  {entry.get('definition', '')}")
            if entry.get("source"):
                parts.append(f"  _Source: {entry['source']}_")
        return "\n".join(parts)