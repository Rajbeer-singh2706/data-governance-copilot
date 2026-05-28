"""
tests/test_information_agent.py

Tests for InformationAgent using injected MockDatabricksService.
No patching of internals needed — just pass the service directly.
"""
import pytest
from unittest.mock import MagicMock
from core.base_agent import AgentRequest
from services.databricks.mock import MockDatabricksService


def make_req(query, products=None, time_range=None):
    return AgentRequest(query=query, data_products=products or [], time_range=time_range)


@pytest.fixture
def agent():
    """InformationAgent with injected MockDatabricksService."""
    from agents.information_agent import InformationAgent
    return InformationAgent(data_service=MockDatabricksService())


def test_retention_metrics_returned(agent):
    result = agent.execute(make_req("Why did retention drop?", ["retention"]))
    assert result.success
    assert "retention" in result.data["metrics"]
    assert "gross_retention_rate" in result.data["metrics"]["retention"]


def test_multi_product_query(agent):
    result = agent.execute(make_req("Show bookings and CAC", ["bookings", "cac"]))
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


def test_health_check(agent):
    health = agent.health_check()
    assert health["agent"] == "information_agent"
    assert health["healthy"] is True


def test_anomaly_detection_low_grr(agent):
    anomalies = agent._detect_anomalies("retention", {
        "gross_retention_rate": 80.0,
        "at_risk_accounts": 10,
    })
    assert any("GRR" in a for a in anomalies)


def test_anomaly_detection_high_at_risk(agent):
    anomalies = agent._detect_anomalies("retention", {
        "gross_retention_rate": 90.0,
        "at_risk_accounts": 35,
    })
    assert any("at-risk" in a for a in anomalies)


def test_low_grr_scenario_triggers_anomaly():
    """MockDatabricksService low_grr=True returns GRR < 85 → anomaly detected."""
    from agents.information_agent import InformationAgent
    agent = InformationAgent(data_service=MockDatabricksService(low_grr=True))
    result = agent.execute(make_req("retention check", ["retention"]))
    assert result.success
    assert any("GRR" in a for a in result.data["anomalies"])