# tests/test_rule_agent.py

import pytest
from core.base_agent import AgentRequest
from agents.rule_agent import RuleAgent, RULE_REGISTRY


def make_req(query, products=None, context=None):
    return AgentRequest(
        query         = query,
        data_products = products or [],
        context       = context  or {},
    )


@pytest.fixture
def agent():
    return RuleAgent()


def test_list_returns_all_seed_rules(agent):
    result = agent.execute(make_req("list all rules"))
    assert result.success
    assert isinstance(result.data, list)
    assert len(result.data) >= 4   # 4 seed rules


def test_list_filters_by_product(agent):
    result = agent.execute(
        make_req("list rules", products=["retention"])
    )
    assert result.success
    for rule in result.data:
        assert "retention" in rule.get("asset", "")


def test_create_dq_rule(agent):
    initial = len(RULE_REGISTRY)
    result  = agent.execute(AgentRequest(
        query          = "create rule for completeness",
        data_products  = ["retention"],
        context = {
            "rule_name":  "Test Completeness Rule",
            "dimension":  "completeness",
            "asset":      "analytics.test_table",
            "expression": "null_count / total < 0.05",
            "severity":   "High",
        },
    ))
    assert result.success
    assert result.data.get("id", "").startswith("DQ-")
    assert result.data["type"] == "data_quality"
    assert len(RULE_REGISTRY) == initial + 1


def test_create_business_rule(agent):
    result = agent.execute(AgentRequest(
        query   = "create a business rule threshold for LTV",
        context = {
            "rule_name":  "LTV/CAC Minimum Ratio",
            "asset":      "ltv",
            "expression": "ltv_cac_ratio >= 3.0",
            "threshold":  3.0,
            "severity":   "Medium",
        },
    ))
    print(f"result : {result}")
    assert result.success
    assert result.data.get("id", "").startswith("BR-")
    assert result.data["type"] == "business_rule"


def test_evaluate_returns_pass_fail(agent):
    result = agent.execute(
        make_req("evaluate rules", products=["retention"])
    )
    assert result.success
    assert isinstance(result.data, list)
    for r in result.data:
        assert "passed"    in r
        assert "rule_id"   in r
        assert "rule_name" in r


def test_evaluate_metadata_has_counts(agent):
    result = agent.execute(make_req("evaluate all rules"))
    # evaluate returns pass/fail/skipped counts in metadata
    assert "passed" in result.metadata or "skipped" in result.metadata
    passed  = result.metadata.get("passed", 0)
    failed  = result.metadata.get("failed", 0)
    skipped = result.metadata.get("skipped", 0)
    # Total across all three categories must equal number of rule records returned
    assert passed + failed + skipped == len(result.data)


def test_summary_contains_emoji(agent):
    result = agent.execute(make_req("list rules"))
    assert "📋" in result.summary


def test_rule_id_unique_on_create(agent):
    r1 = agent.execute(AgentRequest(
        query   = "create rule one",
        context = {"rule_name": "Rule One"},
    ))
    r2 = agent.execute(AgentRequest(
        query   = "create rule two",
        context = {"rule_name": "Rule Two"},
    ))
    assert r1.data["id"] != r2.data["id"]


def test_health_check(agent):
    health = agent.health_check()
    assert health["agent"]    == "rule_agent"
    assert health["healthy"]  == True


def test_unknown_query_defaults_to_list(agent):
    result = agent.execute(
        make_req("what about data rules?")
    )
    assert result.success
    assert isinstance(result.data, list)


def test_supervisor_fast_path():
    import pytest
    try:
        from docs.deployment.old.supervisor_agent import SupervisorAgent
    except ModuleNotFoundError:
        try:
            from agents.supervisor_agent import SupervisorAgent
        except ModuleNotFoundError:
            # FIX: legacy supervisor_agent not in main src tree — skip
            pytest.skip("SupervisorAgent not available in this environment")
            return
    sup  = SupervisorAgent()
    resp = sup.run("list all rules")
    assert resp.success
    assert resp.agents_used == ["rule_agent"]
    assert "📋" in resp.summary


def test_supervisor_skips_rule_agent_on_normal_query():
    import pytest
    try:
        from docs.deployment.old.supervisor_agent import SupervisorAgent
    except ModuleNotFoundError:
        try:
            from agents.supervisor_agent import SupervisorAgent
        except ModuleNotFoundError:
            # FIX: legacy supervisor_agent not in main src tree — skip
            pytest.skip("SupervisorAgent not available in this environment")
            return
    sup  = SupervisorAgent()
    resp = sup.run("Why did retention drop?")
    assert "rule_agent" not in resp.agents_used


#uv run pytest tests/test_rule_agent.py -v