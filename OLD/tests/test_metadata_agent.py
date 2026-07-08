"""
tests/test_metadata_agent.py

Tests for MetadataAgent using injected MockCollibraService.
No patching of internals needed — just pass the service directly.
"""
import pytest
from unittest.mock import patch
from core.base_agent import AgentRequest
from services.collibra.mock import MockCollibraService


def make_req(query, products=None):
    return AgentRequest(query=query, data_products=products or [])


@pytest.fixture
def agent():
    from agents.metadata_agent import MetadataAgent
    with patch("agents.metadata_agent.get_mcp_tools", return_value=[]):
        return MetadataAgent(metadata_service=MockCollibraService())


def test_returns_retention_metadata(agent):
    result = agent.execute(make_req("retention metrics", ["retention"]))
    assert result.success
    assert "retention" in result.data
    assert "asset_name" in result.data["retention"]


def test_dq_score_present(agent):
    result = agent.execute(make_req("retention dq", ["retention"]))
    assert result.success
    dq = result.data["retention"].get("data_quality", {})
    assert "score" in dq
    assert 0 <= dq["score"] <= 100


def test_status_present(agent):
    result = agent.execute(make_req("retention metadata", ["retention"]))
    assert result.success
    assert "status" in result.data["retention"]


def test_domain_present(agent):
    result = agent.execute(make_req("retention metadata", ["retention"]))
    assert result.success
    assert "domain" in result.data["retention"]


def test_multi_product(agent):
    result = agent.execute(make_req("bookings and cac", ["bookings", "cac"]))
    assert result.success
    assert "bookings" in result.data
    assert "cac" in result.data


def test_no_assets_found():
    """When service returns empty list, agent returns success with empty summary."""
    from agents.metadata_agent import MetadataAgent
    from unittest.mock import MagicMock

    empty_svc = MagicMock()
    empty_svc.search_assets.return_value = []

    with patch("agents.metadata_agent.get_mcp_tools", return_value=[]):
        agent = MetadataAgent(metadata_service=empty_svc)

    result = agent.execute(make_req("unknown product", ["unknown"]))
    assert result.success
    assert result.confidence == 0.5


def test_sources_populated(agent):
    result = agent.execute(make_req("ltv metrics", ["ltv"]))
    assert result.success
    assert len(result.sources) > 0
    assert "Collibra" in result.sources[0]


def test_confidence(agent):
    result = agent.execute(make_req("retention check", ["retention"]))
    assert result.confidence == 0.93


def test_summary_contains_markdown(agent):
    result = agent.execute(make_req("retention metadata", ["retention"]))
    assert "**" in result.summary


def test_health_check(agent):
    health = agent.health_check()
    assert health["agent"] == "metadata_agent"
    assert health["healthy"] is True


def test_product_alias_churn_maps_to_retention(agent):
    result = agent.execute(make_req("Why is churn so high?"))
    assert result.success
    assert "retention" in result.data