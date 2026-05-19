
# tests/test_capacity_agent.py

import pytest
from core.base_agent import AgentRequest
from agents.capacity_agent import CapacityAgent, MOCK_JIRA_ISSUES


def make_req(query, products=None, context=None):
    return AgentRequest(
        query         = query,
        data_products = products or [],
        context       = context or {},
    )


@pytest.fixture
def agent():
    return CapacityAgent(enable_mock=True)


def test_read_returns_retention_issues(agent):
    result = agent.execute(make_req("retention issues",
                                    ["retention"]))
    assert result.success
    issues = result.data.get("retention", [])
    assert len(issues) > 0


def test_issue_has_required_fields(agent):
    result = agent.execute(make_req("retention tickets",
                                    ["retention"]))
    for issue in result.data.get("retention", []):
        assert "id"      in issue
        assert "summary" in issue
        assert "status"  in issue
        assert "type"    in issue


def test_open_issue_count_in_metadata(agent):
    result = agent.execute(make_req("retention issues",
                                    ["retention"]))
    assert "open_issues" in result.metadata
    assert result.metadata["open_issues"] >= 0


def test_ltv_has_no_issues(agent):
    result = agent.execute(make_req("ltv issues", ["ltv"]))
    issues = result.data.get("ltv", [])
    assert issues == []
    assert "No open issues" in result.summary


def test_multi_product_read(agent):
    result = agent.execute(
        make_req("retention and bookings issues",
                 ["retention", "bookings"])
    )
    assert "retention" in result.data
    assert "bookings"  in result.data


def test_create_ticket_from_anomaly(agent):
    result = agent.create_ticket_from_anomaly(
        anomaly_description = "GRR 83.1% below 85% threshold",
        product             = "retention",
        priority            = "High",
    )
    assert result.success
    assert result.data.get("ticket_id", "").startswith("DATA-")
    assert result.data.get("type") == "Bug"
    assert result.data.get("priority") == "High"


def test_auto_ticket_id_format(agent):
    result = agent.create_ticket_from_anomaly(
        "test anomaly", "cac"
    )
    ticket_id = result.data.get("ticket_id", "")
    assert ticket_id.startswith("DATA-")
    num = int(ticket_id.split("-")[1])
    assert 5000 <= num <= 6000


def test_write_detected_from_query(agent):
    result = agent.execute(
        make_req("create ticket for EU data missing",
                 context={
                     "ticket_summary": "EU data gap",
                     "issue_type":     "Bug",
                 })
    )
    assert result.success
    assert "DATA-" in result.summary


def test_sources_populated(agent):
    result = agent.execute(make_req("retention tickets",
                                    ["retention"]))
    assert len(result.sources) > 0
    assert "Jira" in result.sources[0]


def test_confidence_value(agent):
    result = agent.execute(make_req("retention issues",
                                    ["retention"]))
    assert result.confidence == 0.90


def test_health_check(agent):
    health = agent.health_check()
    assert health["agent"]     == "capacity_agent"
    assert health["healthy"]   == True
    assert health["mock_mode"] == True


def test_all_products_in_mock_data():
    from config.settings import DATA_PRODUCTS
    for product in DATA_PRODUCTS:
        assert product in MOCK_JIRA_ISSUES, \
            f"Missing Jira mock data for {product}"


## uv run pytest tests/test_capacity_agent.py -v