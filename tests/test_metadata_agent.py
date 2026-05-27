"""
tests/test_metadata_agent.py

Tests for MetadataAgent with CollibraClient patched.
Verifies the REST response parsing and summary building logic.
"""
import pytest
from unittest.mock import MagicMock, patch
from core.base_agent import AgentRequest


def make_req(query, products=None):
    return AgentRequest(query=query, data_products=products or [])


# Realistic Collibra REST response shape
_FAKE_ASSET = {
    "id":          "col-ret-001",
    "displayName": "Gross Retention Rate",
    "type":        {"name": "Business Metric"},
    "domain":      {"name": "Customer Success"},
    "status":      {"name": "Accepted"},
}
_FAKE_DQ = {
    "overall_score": 72,
    "completeness": 68,
    "accuracy": 81,
    "timeliness": 74,
}


@pytest.fixture
def agent():
    """MetadataAgent with CollibraClient patched."""
    mock_client = MagicMock()
    mock_client.search_assets.return_value = [_FAKE_ASSET]
    mock_client.get_data_quality.return_value = _FAKE_DQ

    with patch("agents.metadata_agent.CollibraClient", return_value=mock_client), \
         patch("agents.metadata_agent.get_mcp_tools", return_value=[]):
        from agents.metadata_agent import MetadataAgent
        return MetadataAgent()


def test_returns_retention_metadata(agent):
    result = agent.execute(make_req("retention metrics", ["retention"]))
    assert result.success
    assert "retention" in result.data
    asset = result.data["retention"]
    assert asset["asset_name"] == "Gross Retention Rate"


def test_dq_score_present(agent):
    result = agent.execute(make_req("retention dq", ["retention"]))
    dq = result.data["retention"]["data_quality"]
    assert "overall_score" in dq
    assert 0 <= dq["overall_score"] <= 100


def test_status_present(agent):
    result = agent.execute(make_req("retention", ["retention"]))
    assert result.data["retention"]["status"] == "Accepted"


def test_domain_present(agent):
    result = agent.execute(make_req("retention", ["retention"]))
    assert result.data["retention"]["domain"] == "Customer Success"


def test_multi_product(agent):
    result = agent.execute(make_req(
        "compare retention and bookings metadata", ["retention", "bookings"]
    ))
    assert result.success
    # Both products should be fetched (search_assets called twice)
    assert len(result.data) == 2


def test_no_assets_found(agent):
    agent._client.search_assets.return_value = []
    result = agent.execute(make_req("ltv governance", ["ltv"]))
    assert result.success
    assert result.summary == "No governance metadata found for this query."


def test_sources_populated(agent):
    result = agent.execute(make_req("retention\n", ["retention"]))
    assert len(result.sources) > 0
    assert "Collibra" in result.sources[0]


def test_confidence(agent):
    result = agent.execute(make_req("retention", ["retention"]))
    assert result.confidence == 0.93


def test_summary_contains_markdown(agent):
    result = agent.execute(make_req("retention", ["retention"]))
    assert "🏛️" in result.summary
    assert "**" in result.summary


def test_health_check(agent):
    health = agent.health_check()
    assert health["agent"] == "metadata_agent"
    assert health["healthy"] is True


def test_product_alias_churn_maps_to_retention(agent):
    result = agent.execute(make_req("churn rate metadata"))
    assert result.success
    # "churn" → "retention" alias
    assert "retention" in result.data


def test_dq_icon_green():
    with patch("agents.metadata_agent.CollibraClient", return_value=MagicMock()), \
         patch("agents.metadata_agent.get_mcp_tools", return_value=[]):
        from agents.metadata_agent import MetadataAgent
        a = MetadataAgent()
    assert a._dq_icon(90) == "🟢"
    assert a._dq_icon(75) == "🟡"
    assert a._dq_icon(60) == "🔴"
