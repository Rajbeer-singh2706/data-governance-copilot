"""
tests/test_knowledge_agent.py

Tests for KnowledgeAgent using injected NullVectorService or a custom mock.
No patching of internals needed — just pass the service directly.
"""
import pytest
from unittest.mock import MagicMock
from core.base_agent import AgentRequest
from langchain_core.documents import Document
from services.pgvector.mock import NullVectorService


def make_req(query, products=None):
    return AgentRequest(query=query, data_products=products or [])


def _make_doc(content: str, topic: str = "definition", source: str = "Test Doc"):
    return Document(page_content=content, metadata={"topic": topic, "source": source})


class _FixedVectorService:
    """Returns a fixed list of (Document, score) tuples."""
    def __init__(self, results):
        self._results = results

    def similarity_search(self, query, k=5):
        return self._results[:k]


@pytest.fixture
def agent():
    """KnowledgeAgent with injected NullVectorService."""
    from agents.knowledge_agent import KnowledgeAgent
    return KnowledgeAgent(vector_service=NullVectorService())


@pytest.fixture
def agent_with_retention_docs():
    from agents.knowledge_agent import KnowledgeAgent
    docs = [
        (_make_doc("GRR measures recurring revenue retained.", "definition", "Policy v2"), 0.92),
        (_make_doc("NRR includes expansion revenue.", "pipeline", "Runbook v3"), 0.87),
    ]
    return KnowledgeAgent(vector_service=_FixedVectorService(docs))


def test_returns_knowledge_entries(agent):
    result = agent.execute(make_req("Why did retention drop?"))
    assert result.success
    assert "knowledge" in result.data
    assert len(result.data["knowledge"]) > 0


def test_definition_content_present(agent_with_retention_docs):
    result = agent_with_retention_docs.execute(make_req("What is GRR?"))
    assert result.success
    entries = result.data.get("knowledge", [])
    assert len(entries) > 0
    assert "definition" in entries[0]
    assert len(entries[0]["definition"]) > 10


def test_sources_populated(agent_with_retention_docs):
    result = agent_with_retention_docs.execute(make_req("retention metrics"))
    assert len(result.sources) > 0


def test_confidence_value(agent):
    result = agent.execute(make_req("bookings revenue"))
    assert 0.0 <= result.confidence <= 1.0


def test_no_results_returns_empty():
    from agents.knowledge_agent import KnowledgeAgent
    # Score below threshold → filtered out
    low_score_svc = _FixedVectorService([
        (_make_doc("unrelated content"), 0.30),
    ])
    agent = KnowledgeAgent(vector_service=low_score_svc)
    result = agent.execute(make_req("quantum computing"))
    assert result.success
    assert result.data["knowledge"] == []


def test_execution_timing(agent):
    result = agent.execute(make_req("retention check"))
    assert result.execution_time_ms >= 0


def test_multi_product_docs():
    from agents.knowledge_agent import KnowledgeAgent
    docs = [
        (_make_doc("CAC = Total S&M Spend / New Customers.", "definition"), 0.88),
        (_make_doc("LTV = ARPU × Gross Margin × (1/Churn).", "definition"), 0.85),
    ]
    agent = KnowledgeAgent(vector_service=_FixedVectorService(docs))
    result = agent.execute(make_req("What is our CAC and LTV ratio?"))
    assert result.success
    assert len(result.data["knowledge"]) == 2


def test_health_check(agent):
    health = agent.health_check()
    assert health["agent"] == "knowledge_agent"
    assert health["healthy"] is True