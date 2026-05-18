# tests/test_knowledge_agent.py

import pytest
from core.base_agent import AgentRequest
from agents.knowledge_agent import KnowledgeAgent, MOCK_KNOWLEDGE_BASE


def make_req(query, products=None):
    return AgentRequest(
        query         = query,
        data_products = products or [],
    )


@pytest.fixture
def agent():
    return KnowledgeAgent(enable_mock=True)


def test_returns_retention_context(agent):
    result = agent.execute(make_req("Why did retention drop?"))
    assert result.success
    assert "knowledge" in result.data
    topics = [e["topic"] for e in result.data["knowledge"]]
    assert "retention" in topics


def test_definition_is_present(agent):
    result = agent.execute(make_req("What is GRR?"))
    assert result.success
    entries = result.data.get("knowledge", [])
    assert len(entries) > 0
    assert "definition" in entries[0]
    assert len(entries[0]["definition"]) > 10


def test_business_context_present(agent):
    result = agent.execute(make_req("retention churn context"))
    entries = result.data.get("knowledge", [])
    assert any("business_context" in e for e in entries)


def test_multi_topic_detection(agent):
    result = agent.execute(
        make_req("What is our CAC and LTV ratio?")
    )
    topics = [e["topic"] for e in result.data.get("knowledge", [])]
    assert "cac" in topics
    assert "ltv" in topics


def test_sources_populated(agent):
    result = agent.execute(make_req("retention metrics"))
    assert len(result.sources) > 0


def test_confidence_value(agent):
    result = agent.execute(make_req("bookings revenue"))
    assert 0.0 <= result.confidence <= 1.0


def test_unknown_query_returns_default(agent):
    result = agent.execute(
        make_req("tell me about quantum computing")
    )
    assert result.success
    # Falls back to retention as default topic
    assert result.summary != ""


def test_summary_contains_markdown(agent):
    result = agent.execute(make_req("retention definition"))
    assert "📚" in result.summary
    assert "**" in result.summary


def test_all_products_in_mock_kb():
    from config.settings import DATA_PRODUCTS
    for product in DATA_PRODUCTS:
        assert product in MOCK_KNOWLEDGE_BASE, \
            f"Missing KB entry for {product}"
        entry = MOCK_KNOWLEDGE_BASE[product]
        assert "definition"        in entry
        assert "business_context"  in entry
        assert "source"            in entry

def test_health_check(agent):
    health = agent.health_check()
    assert health["agent"]    == "knowledge_agent"
    assert health["healthy"]  == True
    assert health["mock_mode"] == True

