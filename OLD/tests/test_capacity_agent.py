"""
tests/test_capacity_agent.py

Tests for CapacityAgent using injected MockJiraService.
No patching of internals needed — just pass the service directly.
"""
import pytest
from unittest.mock import patch
from core.base_agent import AgentRequest
from services.jira.mock import MockJiraService


def make_req(query, products=None):
    return AgentRequest(query=query, data_products=products or [])


@pytest.fixture
def agent():
    from agents.capacity_agent import CapacityAgent
    with patch("agents.capacity_agent.get_mcp_tools", return_value=[]):
        return CapacityAgent(ticket_service=MockJiraService())


def test_returns_issues_for_product(agent):
    result = agent.execute(make_req("Show retention incidents", ["retention"]))
    assert result.success
    assert "retention" in result.data


def test_issue_fields_present(agent):
    result = agent.execute(make_req("Show incidents", ["retention"]))
    issues = result.data.get("retention", [])
    assert len(issues) > 0
    issue = issues[0]
    assert "id" in issue
    assert "summary" in issue
    assert "status" in issue
    assert "priority" in issue


def test_open_count_in_metadata(agent):
    result = agent.execute(make_req("Show open incidents", ["retention"]))
    assert "open_issues" in result.metadata
    assert isinstance(result.metadata["open_issues"], int)


def test_create_ticket(agent):
    result = agent.execute(make_req(
        "create ticket for retention issue",
        ["retention"],
    ))
    assert result.success
    assert "ticket_id" in result.data
    assert result.data["ticket_id"].startswith("DGC-")


def test_sources_populated(agent):
    result = agent.execute(make_req("Show retention incidents", ["retention"]))
    assert len(result.sources) > 0
    assert "Jira" in result.sources[0]


def test_no_issues_returns_success(agent):
    """Agent succeeds even if search returns empty (it doesn't in mock, but test the shape)."""
    result = agent.execute(make_req("Show incidents", ["retention"]))
    assert result.success


def test_confidence(agent):
    result = agent.execute(make_req("Show incidents", ["retention"]))
    assert result.confidence == 0.90


def test_summary_contains_markdown(agent):
    result = agent.execute(make_req("Show incidents", ["retention"]))
    assert "**" in result.summary


def test_create_ticket_from_anomaly():
    from agents.capacity_agent import CapacityAgent
    svc = MockJiraService()
    with patch("agents.capacity_agent.get_mcp_tools", return_value=[]):
        agent = CapacityAgent(ticket_service=svc)
    result = agent.create_ticket_from_anomaly(
        anomaly_description="GRR dropped to 78%",
        product="retention",
        priority="High",
    )
    assert result.success
    assert len(svc.tickets) == 1
    ticket = svc.tickets[0]
    assert "retention" in ticket["fields"]["labels"]
    assert "[Auto-DQ]" in ticket["fields"]["summary"]


def test_product_keyword_detection(agent):
    products = agent._resolve_products("Why did churn spike this quarter?")
    assert "retention" in products


def test_health_check(agent):
    health = agent.health_check()
    assert health["agent"] == "capacity_agent"
    assert health["healthy"] is True