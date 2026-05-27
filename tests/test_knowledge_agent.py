"""
tests/test_knowledge_agent.py

Tests for KnowledgeAgent using a patched vector store.
Returns realistic scored documents matching the real pgvector path.
"""
import pytest
from unittest.mock import MagicMock, patch
from core.base_agent import AgentRequest


def make_req(query, products=None):
    return AgentRequest(query=query, data_products=products or [])


def _make_doc(content: str, product: str, topic: str = "definition"):
    from langchain_core.documents import Document
    return Document(page_content=content, metadata={"product": product, "topic": topic})


def _retention_docs():
    return [
        (_make_doc(
            "GRR measures recurring revenue retained. Formula: (Start MRR - Churn MRR) / Start MRR. "
            "Table: analytics.retention_metrics. Benchmark: >85% SMB, >90% Enterprise.",
            "retention"), 0.92),
        (_make_doc(
            "NRR includes expansion revenue. NRR > 100% means the cohort is growing. "
            "Refreshed daily via retention_daily_etl.",
            "retention", "pipeline"), 0.87),
    ]


@pytest.fixture
def agent():
    """KnowledgeAgent with get_vector_store patched to return a mock store."""
    mock_store = MagicMock()
    mock_store.similarity_search_with_relevance_scores.return_value = _retention_docs()

    fake_config = MagicMock()

    with patch("agents.knowledge_agent.get_vector_store", return_value=mock_store):
        from agents.knowledge_agent import KnowledgeAgent
        return KnowledgeAgent(config=fake_config)


def test_returns_knowledge_entries(agent):
    result = agent.execute(make_req("Why did retention drop?"))
    assert result.success
    assert "knowledge" in result.data
    assert len(result.data["knowledge"]) > 0


def test_definition_content_present(agent):
    result = agent.execute(make_req("What is GRR?"))
    assert result.success
    entries = result.data.get("knowledge", [])
    assert len(entries) > 0
    # definition field comes from page_content
    assert "definition" in entries[0]
    assert len(entries[0]["definition"]) > 10


def test_sources_populated(agent):
    result = agent.execute(make_req("retention metrics"))
    assert len(result.sources) > 0
    assert "retention" in result.sources[0]


def test_confidence_value(agent):
    result = agent.execute(make_req("bookings revenue"))
    assert 0.0 <= result.confidence <= 1.0


def test_no_results_returns_empty(agent):
    agent._store.similarity_search_with_relevance_scores.return_value = [
        (_make_doc("unrelated content", "other"), 0.30)  # below 0.70 threshold
    ]
    result = agent.execute(make_req("quantum computing"))
    assert result.success
    assert result.data["knowledge"] == []


def test_execution_timing(agent):
    result = agent.execute(make_req("retention check"))
    assert result.execution_time_ms >= 0


def test_multi_product_docs(agent):
    agent._store.similarity_search_with_relevance_scores.return_value = [
        (_make_doc("CAC = Total S&M Spend / New Customers.", "cac"), 0.88),
        (_make_doc("LTV = ARPU × Gross Margin × (1/Churn).", "ltv"), 0.85),
    ]
    result = agent.execute(make_req("What is our CAC and LTV ratio?"))
    topics = [e.get("topic") for e in result.data.get("knowledge", [])]
    assert "cac" in topics
    assert "ltv" in topics


def test_health_check(agent):
    health = agent.health_check()
    assert health["agent"] == "knowledge_agent"
    assert health["healthy"] is True
