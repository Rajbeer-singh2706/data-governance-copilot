"""
tests/test_information_agent.py

Tests for InformationAgent using monkeypatched DatabricksConnector.
No mock data — the agent is exercised with a patched connector that
returns realistic row data, matching the real _fetch_live() path.
"""
import pytest
from unittest.mock import MagicMock, patch
from core.base_agent import AgentRequest
from config.settings import DATA_PRODUCTS


def make_req(query, products=None, time_range=None):
    return AgentRequest(
        query=query,
        data_products=products or [],
        time_range=time_range,
    )


@pytest.fixture
def agent(monkeypatch):
    """InformationAgent with DatabricksConnector patched out."""
    # Patch the connector so no real Databricks creds are needed
    mock_connector = MagicMock()
    mock_connector.query.return_value = [{
        "gross_retention_rate": 87.3,
        "churn_rate": 12.7,
        "at_risk_accounts": 22,
        "total_accounts": 412,
        "net_retention_rate": 107.4,
        "time_range": "last_month",
    }]

    from agents import information_agent as ia_module
    monkeypatch.setattr(ia_module, "DatabricksConnector",
                        lambda cfg: mock_connector)

    # Patch EnvironmentError check by supplying a fake config
    fake_db = MagicMock()
    fake_db.host = "https://fake.databricks.net"
    fake_db.token = "fake-token"
    fake_db.http_path = "/sql/1.0/warehouses/fake"
    fake_config = MagicMock()
    fake_config.databricks = fake_db

    from agents.information_agent import InformationAgent
    return InformationAgent(config=fake_config)


def test_retention_metrics_returned(agent):
    result = agent.execute(make_req("Why did retention drop?", ["retention"]))
    assert result.success
    assert "retention" in result.data["metrics"]
    m = result.data["metrics"]["retention"]
    assert "gross_retention_rate" in m


def test_multi_product_query(agent, monkeypatch):
    from agents.information_agent import InformationAgent
    fake_db = MagicMock()
    fake_db.host = "https://fake.databricks.net"
    fake_db.token = "fake-token"
    fake_db.http_path = "/sql/1.0/warehouses/fake"
    fake_config = MagicMock()
    fake_config.databricks = fake_db

    mock_connector = MagicMock()
    mock_connector.query.return_value = [{"total_bookings_usd": 4500000, "bookings_vs_target_pct": 3.0}]

    from agents import information_agent as ia_module
    monkeypatch.setattr(ia_module, "DatabricksConnector", lambda cfg: mock_connector)

    agent2 = InformationAgent(config=fake_config)
    result = agent2.execute(make_req("Show bookings and CAC", ["bookings", "cac"]))
    assert result.success
    assert "bookings" in result.data["metrics"]
    assert "cac" in result.data["metrics"]


def test_product_detection_churn(agent):
    detected = set(agent._detect_products("Why did churn increase?"))
    assert "retention" in detected


def test_product_detection_arr(agent):
    detected = set(agent._detect_products("Show me our ARR growth"))
    assert "bookings" in detected


def test_product_detection_ltv_cac(agent):
    detected = set(agent._detect_products("What is the LTV/CAC ratio?"))
    assert "ltv" in detected
    assert "cac" in detected


def test_execution_timing(agent):
    result = agent.execute(make_req("retention check", ["retention"]))
    assert result.execution_time_ms >= 0
    assert isinstance(result.execution_time_ms, float)


def test_anomalies_field_present(agent):
    result = agent.execute(make_req("Why did retention drop?", ["retention"]))
    assert "anomalies" in result.data
    assert isinstance(result.data["anomalies"], list)


def test_confidence_live_mode(agent):
    result = agent.execute(make_req("retention check", ["retention"]))
    assert result.confidence == 0.95


def test_sources_populated(agent):
    result = agent.execute(make_req("retention check", ["retention"]))
    assert len(result.sources) > 0
    # No [MOCK] prefix in live mode
    assert "[MOCK]" not in result.sources[0]


def test_health_check(agent):
    health = agent.health_check()
    assert health["agent"] == "information_agent"
    assert health["healthy"] is True


def test_anomaly_detection_low_grr():
    """Anomaly detector logic — no connector needed."""
    from agents.information_agent import InformationAgent
    from unittest.mock import MagicMock
    fake_db = MagicMock()
    fake_db.host = "h"
    fake_db.token = "t"
    fake_db.http_path = "p"
    fake_config = MagicMock()
    fake_config.databricks = fake_db

    with patch("agents.information_agent.DatabricksConnector", return_value=MagicMock()):
        agent = InformationAgent(config=fake_config)

    anomalies = agent._detect_anomalies("retention", {
        "gross_retention_rate": 80.0,
        "at_risk_accounts": 10,
    })
    assert any("GRR" in a for a in anomalies)


def test_anomaly_detection_high_at_risk():
    from agents.information_agent import InformationAgent
    with patch("agents.information_agent.DatabricksConnector", return_value=MagicMock()):
        fake_db = MagicMock()
        fake_db.host = "h"; fake_db.token = "t"; fake_db.http_path = "p"
        fake_config = MagicMock()
        fake_config.databricks = fake_db
        agent = InformationAgent(config=fake_config)

    anomalies = agent._detect_anomalies("retention", {
        "gross_retention_rate": 90.0,
        "at_risk_accounts": 35,
    })
    assert any("at-risk" in a for a in anomalies)
