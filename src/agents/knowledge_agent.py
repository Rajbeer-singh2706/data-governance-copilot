"""
src/agents/knowledge_agent.py
Day 18: Replace FAISS / ChromaDB mock with pgvector via vector_store.py.
 
Retrieval logic:
  1. get_vector_store(config.vector_db) → PGVector | NullVectorStore
  2. similarity_search(store, query, k=5)
  3. Filter: keep docs where score > 0.7 (relevance threshold)
  4. Build summary from retrieved documents
 
In ENABLE_MOCK=true mode, NullVectorStore returns pre-written governance
documents with fixed high scores, so the agent works end-to-end without
a PostgreSQL connection or OpenAI embeddings key.
"""
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, AgentRequest, AgentResult
from core.vector_store import get_vector_store, similarity_search
from config.settings import AppConfig


class KnowledgeAgent(BaseAgent):
    """
    Retrieves business context and definitions via pgvector.
    Raises EnvironmentError at init time when config is absent.
    """
    name = "knowledge_agent"
    description = "Retrieves business context and definitions"
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

    def __init__(self, config: Optional[Any] = None, **kwargs):
        kwargs.pop("enable_mock", None)
        super().__init__(config=config, enable_mock=False)
        if config is None:
            raise EnvironmentError(
                "KnowledgeAgent requires a valid AppConfig with "
                "vector_db settings (POSTGRES_* and OPENAI_API_KEY)."
            )
        self._store = get_vector_store(config.vector_db)

    def _detect_topics(self, query: str) -> List[str]:
        q = query.lower()
        topics = [
            topic
            for topic, keywords in self.TOPIC_KEYWORDS.items()
            if any(kw in q for kw in keywords)
        ]
        return topics if topics else ["retention"]

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

    def _execute(self, request: AgentRequest) -> AgentResult:
        results = similarity_search(self._store, request.query, k=5)
        relevant = [(doc, score) for doc, score in results if score >= 0.70]

        if not relevant:
            return AgentResult(
                agent_name=self.name,
                success=True,
                summary="No relevant documents found for this query.",
                data={"knowledge": []},
                confidence=0.0,
            )

        docs_text = "\n\n".join(
            f"[{i+1}] (score={s:.2f})\n{d.page_content}"
            for i, (d, s) in enumerate(relevant)
        )
        avg_conf = round(sum(s for _, s in relevant) / len(relevant), 2)
        sources = [
            f"{d.metadata.get('product', '?')} — {d.metadata.get('topic', '?')}"
            for d, _ in relevant
        ]
        entries = [
            {
                "topic": d.metadata.get("product", ""),
                "definition": d.page_content,
                "source": f"{d.metadata.get('product', '?')} — {d.metadata.get('topic', '?')}",
            }
            for d, _ in relevant
        ]
        return AgentResult(
            agent_name=self.name,
            success=True,
            summary=docs_text,
            data={"knowledge": entries},
            confidence=avg_conf,
            sources=sources,
        )
