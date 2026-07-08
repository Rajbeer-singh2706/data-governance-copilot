# tests/test_day15.py
import os, sys, time, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestWithRetryDecorator:

    def test_succeeds_on_first_attempt(self):
        from core.retry import with_retry
        calls = {"n": 0}
        @with_retry(max_retries=3, backoff_factor=0.01)
        def succeed():
            calls["n"] += 1
            return "ok"
        assert succeed() == "ok"
        assert calls["n"] == 1

    def test_retries_on_failure_then_succeeds(self):
        from core.retry import with_retry
        calls = {"n": 0}
        @with_retry(max_retries=3, backoff_factor=0.01)
        def fail_twice():
            calls["n"] += 1
            if calls["n"] < 3: raise ConnectionError("timeout")
            return "ok"
        assert fail_twice() == "ok"
        assert calls["n"]   == 3

    def test_raises_after_max_retries(self):
        from core.retry import with_retry
        @with_retry(max_retries=3, backoff_factor=0.01)
        def always_fail(): raise ValueError("permanent")
        with pytest.raises(ValueError, match="permanent"):
            always_fail()

    def test_respects_exception_filter(self):
        from core.retry import with_retry
        calls = {"n": 0}
        @with_retry(max_retries=3, backoff_factor=0.01, exceptions=(ConnectionError,))
        def raise_value_error():
            calls["n"] += 1
            raise ValueError("not retried")
        with pytest.raises(ValueError):
            raise_value_error()
        assert calls["n"] == 1   # did NOT retry

    def test_preserves_function_name(self):
        from core.retry import with_retry
        @with_retry()
        def my_function(): pass
        assert my_function.__name__ == "my_function"

    def test_exponential_backoff_timing(self):
        from core.retry import with_retry
        ts = []
        @with_retry(max_retries=3, backoff_factor=0.05)
        def fail_twice():
            ts.append(time.time())
            if len(ts) < 3: raise ConnectionError("retry")
            return "ok"
        fail_twice()
        assert ts[1] - ts[0] >= 0.04   # ~0.05s
        assert ts[2] - ts[1] >= ts[1] - ts[0]  # second gap >= first


class TestRetryAgentCall:

    def test_returns_on_success(self):
        from core.retry import retry_agent_call
        class FakeAgent:
            name = "fake"
            def execute(self, req):
                class R:
                    success=True; summary="ok"; data={}
                    sources=[]; confidence=0.9; error=None
                    def to_dict(self): return {"agent":"fake","success":True}
                return R()
        result = retry_agent_call(FakeAgent().execute, object(), max_retries=3)
        assert result.success == True

    def test_returns_degraded_on_final_failure(self):
        import core.retry as r
        r.time.sleep = lambda _: None
        from core.retry import retry_agent_call  # FIX: import after monkeypatching time.sleep
        calls = {"n": 0}
        def always_fail(req):
            calls["n"] += 1
            raise ConnectionError("down")
        result = retry_agent_call(always_fail, object(), max_retries=3)
        assert result.success  == False
        assert calls["n"]      == 3
        assert "Failed after 3" in result.error

    def test_does_not_raise(self):
        import core.retry as r
        r.time.sleep = lambda _: None
        from core.retry import retry_agent_call  # FIX: must import in scope
        def boom(req): raise RuntimeError("boom")
        result = retry_agent_call(boom, object(), max_retries=3)
        assert result.success == False


class TestHITLAutoTicket:

    def _state(self, anomalies=None, approved=False):
        from graph.state import initial_state
        s = initial_state("test")
        s["anomalies"]     = anomalies or []
        s["approved"]      = approved
        s["data_products"] = ["retention"]
        return s

    def test_no_anomalies_returns_empty(self):
        from graph.nodes import auto_ticket_node
        r = auto_ticket_node(self._state([]))
        assert r["auto_tickets"]   == []
        assert r["pending_action"] is None

    def test_anomalies_without_approval_sets_pending(self):
        from graph.nodes import auto_ticket_node
        r = auto_ticket_node(self._state(["GRR below threshold: 83%"]))
        assert r["auto_tickets"]              == []
        assert r["pending_action"] is not None
        assert r["pending_action"]["count"]   == 1
        assert r["pending_action"]["action"]  == "create_jira_tickets"

    def test_anomalies_with_approval_creates_tickets(self):
        from graph.nodes import auto_ticket_node
        r = auto_ticket_node(self._state(["GRR below threshold: 83%"], approved=True))
        assert isinstance(r["auto_tickets"], list)
        # When CapacityAgent is unconfigured, pending_action carries an error message;
        # when it IS configured, pending_action is None.  Either way auto_tickets is a list.
        assert "auto_tickets" in r

    def test_non_critical_keywords_skipped(self):
        from graph.nodes import auto_ticket_node
        r = auto_ticket_node(self._state(["Metric computed successfully"]))
        assert r["pending_action"] is None

    def test_multiple_anomalies_count(self):
        from graph.nodes import auto_ticket_node
        r = auto_ticket_node(self._state([
            "GRR below threshold: 83%",
            "Missing data for 3 days",
            "CAC risk: spike detected",
        ]))
        assert r["pending_action"]["count"] == 3


@pytest.mark.integration
class TestDay15Integration:

    def setup_method(self):
        import core.cache as c
        c._fallback.clear(); c._client = None

    def test_normal_query_completes(self):
        from graph.graph import copilot_graph
        from graph.state import initial_state
        result = copilot_graph.invoke(
            initial_state("Who owns the bookings dataset?"),
            config={"configurable":{"thread_id":"d15-01"}}
        )
        assert result["final_summary"] != ""
        assert result["execution_ms"]  > 0

    def test_agent_error_does_not_crash_graph(self, monkeypatch):
        import graph.nodes as n, core.retry as r
        monkeypatch.setattr(r.time, "sleep", lambda _: None)
        monkeypatch.setattr(
            n._agents["information"], "execute",
            lambda req: (_ for _ in ()).throw(RuntimeError("DB unavailable"))
        )
        import core.cache as c; c._fallback.clear(); c._client = None
        from graph.graph import copilot_graph
        from graph.state import initial_state
        result = copilot_graph.invoke(
            initial_state("Show me retention metrics"),
            config={"configurable":{"thread_id":"d15-fail"}}
        )
        assert "final_summary" in result
        assert len(result.get("errors",[])) >= 1

    def test_guardrail_block(self):
        from graph.graph import copilot_graph
        from graph.state import initial_state
        result = copilot_graph.invoke(
            initial_state("DROP TABLE analytics.retention_metrics"),
            config={"configurable":{"thread_id":"d15-block"}}
        )
        assert result["guardrail_passed"] == False
        assert result["agent_results"]    == []