
import pytest
from core.base_agent import AgentRequest
from agents.information_agent import InformationAgent, MOCK_GENERATORS
from config.settings import DATA_PRODUCTS

def make_req(query, products=None, time_range=None):
    return AgentRequest(
        query         = query,
        data_products = products or [],
        time_range    = time_range,
    )

@pytest.fixture
def agent():
    return InformationAgent(enable_mock=True)


def test_retention_metrics_returned(agent):
    result = agent.execute(make_req("Why did retention drop?", ["retention"]))
    assert result.success
    assert "retention" in result.data["metrics"]
    m = result.data["metrics"]["retention"]
    assert "gross_retention_rate" in m
    assert "churn_rate" in m
    assert "at_risk_accounts" in m


def test_multi_product_query(agent):
    result = agent.execute(make_req("Show bookings and CAC", ["bookings", "cac"]))
    assert result.success
    assert len(result.data["metrics"]) == 2
    assert "bookings" in result.data["metrics"]
    assert "cac"      in result.data["metrics"]


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


def test_confidence_in_mock_mode(agent):
    result = agent.execute(make_req("retention check", ["retention"]))
    assert result.confidence == 0.85


def test_sources_populated(agent):
    result = agent.execute(make_req("retention check", ["retention"]))
    assert len(result.sources) > 0
    assert "[MOCK]" in result.sources[0]


def test_health_check(agent):
    health = agent.health_check()
    assert health["agent"]     == "information_agent"
    assert health["healthy"]   == True
    assert health["mock_mode"] == True


def test_all_products_have_mock_generators(agent):
    for product in DATA_PRODUCTS:
        assert product in MOCK_GENERATORS, \
            f"Missing mock generator for {product}"
        metrics = MOCK_GENERATORS[product]("last_month")
        assert isinstance(metrics, dict)
        assert len(metrics) > 0
