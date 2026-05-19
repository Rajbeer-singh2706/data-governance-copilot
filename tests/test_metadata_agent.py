# tests/test_metadata_agent.py

import pytest
from core.base_agent import AgentRequest
from agents.metadata_agent import MetadataAgent, MOCK_COLLIBRA_ASSETS


def make_req(query, products=None):
    return AgentRequest(
        query         = query,
        data_products = products or [],
    )


@pytest.fixture
def agent():
    return MetadataAgent(enable_mock=True)


def test_returns_retention_metadata(agent):
    result = agent.execute(make_req("retention metrics", ["retention"]))
    assert result.success
    assert "retention" in result.data
    asset = result.data["retention"]
    assert asset["owner"] == "Jane Smith (VP Customer Success)"


def test_dq_score_present(agent):
    result = agent.execute(make_req("retention dq", ["retention"]))
    dq = result.data["retention"]["data_quality"]
    assert "overall_score" in dq
    assert 0 <= dq["overall_score"] <= 100


def test_all_six_dq_dimensions(agent):
    result = agent.execute(make_req("retention", ["retention"]))
    dq     = result.data["retention"]["data_quality"]
    for dim in ["completeness","accuracy","timeliness",
                "consistency","validity","uniqueness"]:
        assert dim in dq, f"Missing DQ dimension: {dim}"


def test_dq_issues_present(agent):
    result = agent.execute(make_req("retention", ["retention"]))
    issues = result.data["retention"]["data_quality"]["issues"]
    assert isinstance(issues, list)
    assert len(issues) > 0  # retention has known issues


def test_lineage_present(agent):
    result  = agent.execute(make_req("retention", ["retention"]))
    lineage = result.data["retention"]["lineage"]
    assert "source_systems"   in lineage
    assert "etl_pipeline"     in lineage
    assert "last_refresh"     in lineage
    assert "target_tables"    in lineage


def test_multi_product(agent):
    result = agent.execute(
        make_req("CAC and LTV metadata", ["cac", "ltv"])
    )
    assert "cac" in result.data
    assert "ltv" in result.data


def test_sources_use_collibra_label(agent):
    result = agent.execute(make_req("retention", ["retention"]))
    assert any("Collibra" in s for s in result.sources)


def test_dq_icon_logic(agent):
    assert agent._dq_icon(90) == "🟢"
    assert agent._dq_icon(75) == "🟡"
    assert agent._dq_icon(60) == "🔴"
    assert agent._dq_icon(85) == "🟢"
    assert agent._dq_icon(70) == "🟡"


def test_summary_contains_governance_emoji(agent):
    result = agent.execute(make_req("retention", ["retention"]))
    assert "🏛️" in result.summary


def test_overall_dq_in_metadata(agent):
    result = agent.execute(make_req("retention", ["retention"]))
    assert result.metadata.get("overall_dq_score") is not None


def test_all_products_in_mock_data():
    from config.settings import DATA_PRODUCTS
    for product in DATA_PRODUCTS:
        assert product in MOCK_COLLIBRA_ASSETS, \
            f"Missing Collibra mock data for {product}"
        asset = MOCK_COLLIBRA_ASSETS[product]
        assert "owner"        in asset
        assert "data_quality" in asset
        assert "lineage"      in asset


def test_health_check(agent):
    health = agent.health_check()
    assert health["agent"]     == "metadata_agent"
    assert health["healthy"]   == True
    assert health["mock_mode"] == True


# uv run pytest tests/test_metadata_agent.py -v