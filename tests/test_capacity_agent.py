"""
tests/test_capacity_agent.py

Tests for CapacityAgent with JiraClient patched.
Covers read (issue listing) and write (ticket creation) paths.
"""
import pytest
from unittest.mock import MagicMock, patch
from core.base_agent import AgentRequest


def make_req(query, products=None, context=None):
    return AgentRequest(
        query=query,
        data_products=products or [],
        context=context or {},
    )


# Realistic Jira REST search response
_FAKE_ISSUES = [
    {
        "key": "DATA-4821",
        "fields": {
            "summary":  "EU region retention data missing — pipeline failure",
            "status":   {"name": "In Progress"},
            "priority": {"name": "High"},
            "issuetype": {"name": "Bug"},
            "assignee": {"emailAddress": "data-eng-eu@company.com"},
            "labels":   ["data-quality", "retention"],
        },
    },
    {
        "key": "DATA-4890",
        "fields": {
            "summary":  "GRR/NRR discrepancy between Salesforce and DWH",
            "status":   {"name": "Open"},
            "priority": {"name": "Medium"},
            "issuetype": {"name": "Bug"},
            "assignee": {"emailAddress": "data-eng-core@company.com"},
            "labels":   ["retention"],
        },
    },
]
_FAKE_CREATE_RESPONSE = {"key": "DATA-5001", "id": "12345"}


@pytest.fixture
def agent():
    """CapacityAgent with JiraClient patched."""
    mock_client = MagicMock()
    mock_client.search_issues.return_value = _FAKE_ISSUES
    mock_client.create_issue.return_value = _FAKE_CREATE_RESPONSE

    with patch("agents.capacity_agent.JiraClient", return_value=mock_client), \
         patch("agents.capacity_agent.get_mcp_tools", return_value=[]):
        from agents.capacity_agent import CapacityAgent
        return CapacityAgent()


def test_returns_issues_for_product(agent):
    result = agent.execute(make_req("What retention issues are open?", ["retention"]))
    assert result.success
    assert "retention" in result.data
    assert len(result.data["retention"]) == 2


def test_issue_fields_present(agent):
    result = agent.execute(make_req("retention issues", ["retention"]))
    issue = result.data["retention"][0]
    assert "id" in issue
    assert "summary" in issue
    assert "status" in issue
    assert "priority" in issue


def test_open_count_in_metadata(agent):
    result = agent.execute(make_req("retention issues", ["retention"]))
    assert "open_issues" in result.metadata
    assert result.metadata["open_issues"] == 2


def test_create_ticket(agent):
    result = agent.execute(make_req(
        "create ticket for retention pipeline failure",
        context={
            "ticket_summary":     "EU region data missing",
            "ticket_description": "Pipeline failure 2024-09-12 to 2024-09-14",
            "issue_type":         "Bug",
            "priority":           "High",
            "labels":             ["retention", "etl"],
        },
    ))
    assert result.success
    assert result.data["ticket_id"] == "DATA-5001"
    assert "✅" in result.summary


def test_sources_populated(agent):
    result = agent.execute(make_req("retention issues", ["retention"]))
    assert len(result.sources) > 0
    assert "Jira" in result.sources[0]


def test_no_issues_returns_success(agent):
    agent._client.search_issues.return_value = []
    result = agent.execute(make_req("ltv issues", ["ltv"]))
    assert result.success
    assert result.data["ltv"] == []


def test_confidence(agent):
    result = agent.execute(make_req("retention issues", ["retention"]))
    assert result.confidence == 0.90


def test_summary_contains_markdown(agent):
    result = agent.execute(make_req("retention issues", ["retention"]))
    assert "🎫" in result.summary
    assert "DATA-4821" in result.summary


def test_create_ticket_from_anomaly(agent):
    result = agent.create_ticket_from_anomaly(
        "GRR dropped below 85% threshold", "retention", priority="High"
    )
    assert result.success
    assert result.data["ticket_id"] == "DATA-5001"


def test_product_keyword_detection(agent):
    result = agent.execute(make_req("Are there any churn-related issues?"))
    assert result.success
    # "churn" → resolves to retention
    assert "retention" in result.data


def test_health_check(agent):
    health = agent.health_check()
    assert health["agent"] == "capacity_agent"
    assert health["healthy"] is True
