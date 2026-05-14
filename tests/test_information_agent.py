# tests/test_information_agent.py

from core.base_agent import AgentRequest
from agents.information_agent import InformationAgent, MOCK_GENERATORS


def make_req(query, products=None, time_range=None):
    return AgentRequest(
        query         = query,
        data_products = products or [],
        time_range    = time_range,
    )

agent = InformationAgent(enable_mock=True)

# ── Test 1: basic retention query ────────────────────────
print("=== Test 1: retention metrics returned ===")
result = agent.execute(make_req("Why did retention drop?",
                                ["retention"]))
assert result.success
assert "retention" in result.data["metrics"]
m = result.data["metrics"]["retention"]
assert "gross_retention_rate" in m
assert "churn_rate" in m
assert "at_risk_accounts" in m
print(f"✓ GRR={m['gross_retention_rate']}% "
      f"churn={m['churn_rate']}% "
      f"at_risk={m['at_risk_accounts']}")

# ── Test 2: multi-product query ──────────────────────────
print("\n=== Test 2: multi-product query ===")
result2 = agent.execute(make_req("Show bookings and CAC",
                                  ["bookings", "cac"]))
assert result2.success
assert len(result2.data["metrics"]) == 2
assert "bookings" in result2.data["metrics"]
assert "cac"      in result2.data["metrics"]
print(f"✓ Products fetched: {list(result2.data['metrics'].keys())}")

# ── Test 3: keyword-based product detection ──────────────
print("\n=== Test 3: product detection from keywords ===")
tests = [
    ("Why did churn increase?",    {"retention"}),
    ("Show me our ARR growth",     {"bookings"}),
    ("What is the LTV/CAC ratio?", {"ltv", "cac"}),
]
for query, expected in tests:
    detected = set(agent._detect_products(query))
    assert expected.issubset(detected), \
        f"Expected {expected}, got {detected}"
    print(f"✓ '{query[:35]}...' → {detected}")

# ── Test 4: execution timing works ───────────────────────
print("\n=== Test 4: execution timing works ===")
result4 = agent.execute(make_req("retention check", ["retention"]))
assert result4.execution_time_ms >= 0               # >= not > (mock runs in microseconds)
assert isinstance(result4.execution_time_ms, float) # is a proper number
print(f"✓ Executed in {result4.execution_time_ms}ms")

# ── Test 5: anomalies list is present ───────────────────
print("\n=== Test 5: anomalies field is always present ===")
assert "anomalies" in result.data
assert isinstance(result.data["anomalies"], list)
print(f"✓ Anomalies found: {len(result.data['anomalies'])}")
if result.data["anomalies"]:
    print(f"  → {result.data['anomalies'][0]}")

# ── Test 6: confidence is correct ───────────────────────
print("\n=== Test 6: confidence is 0.85 in mock mode ===")
assert result.confidence == 0.85
print(f"✓ Confidence = {result.confidence}")

# ── Test 7: sources list is populated ───────────────────
print("\n=== Test 7: sources are recorded ===")
assert len(result.sources) > 0
assert "[MOCK]" in result.sources[0]
print(f"✓ Sources: {result.sources}")

# ── Test 8: health check ────────────────────────────────
print("\n=== Test 8: health check ===")
health = agent.health_check()
assert health["agent"]     == "information_agent"
assert health["healthy"]   == True
assert health["mock_mode"] == True
print(f"✓ Health: {health}")

# ── Test 9: MOCK_GENERATORS covers all products ─────────
print("\n=== Test 9: all products have mock generators ===")
from config.settings import DATA_PRODUCTS
for product in DATA_PRODUCTS:
    assert product in MOCK_GENERATORS, \
        f"Missing mock generator for {product}"
    metrics = MOCK_GENERATORS[product]("last_month")
    assert isinstance(metrics, dict)
    print(f"✓ {product}: {list(metrics.keys())[:3]}...")

print("\n" + "=" * 50)
print("✅ All 9 tests passed! Day 6 complete.")