# tests/test_day16.py
import os, sys, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("ENABLE_MOCK", "true")
os.environ.setdefault("OPENAI_API_KEY", "")


class TestLLMGuard:

    def test_allows_when_no_redis(self):
        from core.llm_guard import check_and_record_tokens
        assert check_and_record_tokens(None, 1000) == True

    def test_estimate_tokens(self):
        from core.llm_guard import estimate_tokens
        assert estimate_tokens("a" * 400) == 400 // 4 + 500

    def test_get_daily_usage_no_redis(self):
        from core.llm_guard import get_daily_usage, DAILY_TOKEN_LIMIT
        u = get_daily_usage(None)
        assert u["tokens_used"] == 0
        assert u["limit"]       == DAILY_TOKEN_LIMIT

    def test_exceeds_limit(self):
        from core.llm_guard import check_and_record_tokens, DAILY_TOKEN_LIMIT
        class MockRedis:
            _store = {}
            def incrby(self, k, v):
                self._store[k] = self._store.get(k,0)+v
                return self._store[k]
            def expire(self,k,t): pass
        r = MockRedis()
        assert check_and_record_tokens(r, 100) == True
        assert check_and_record_tokens(r, DAILY_TOKEN_LIMIT) == False

    def test_fails_open_on_redis_error(self):
        from core.llm_guard import check_and_record_tokens
        class BrokenRedis:
            def incrby(self,*a,**kw): raise ConnectionError()
            def expire(self,*a,**kw): raise ConnectionError()
        assert check_and_record_tokens(BrokenRedis(), 100) == True


@pytest.fixture(scope="module")
def client():
    from starlette.testclient import TestClient
    from api.app import app
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_returns_200(self, client):
        assert client.get("/health").status_code == 200
    def test_has_status_ok(self, client):
        assert client.get("/health").json()["status"] == "ok"


class TestQueryEndpoint:
    def test_valid_query_200(self, client):
        r = client.post("/query", json={"query":"Who owns bookings?"})
        assert r.status_code == 200
    def test_required_fields(self, client):
        r = client.post("/query", json={"query":"What is GRR?"})
        for f in ["query_id","thread_id","intent","summary","confidence",
                  "sources","auto_tickets","anomalies","errors","execution_ms"]:
            assert f in r.json()
    def test_empty_query_400(self, client):
        assert client.post("/query",json={"query":""}).status_code == 400
    def test_whitespace_query_400(self, client):
        assert client.post("/query",json={"query":"   "}).status_code == 400
    def test_custom_thread_id(self, client):
        r = client.post("/query",json={"query":"test","thread_id":"my-thread"})
        assert r.json()["thread_id"] == "my-thread"
    def test_execution_ms_positive(self, client):
        r = client.post("/query",json={"query":"Show open bugs"})
        assert r.json()["execution_ms"] > 0


class TestQueryStream:
    def test_returns_200(self, client):
        with client.stream("POST","/query/stream",json={"query":"Who owns data?"}) as r:
            assert r.status_code == 200
    def test_content_type_sse(self, client):
        with client.stream("POST","/query/stream",json={"query":"What is LTV?"}) as r:
            assert "text/event-stream" in r.headers["content-type"]
    def test_emits_start_result_done(self, client):
        events = []
        with client.stream("POST","/query/stream",json={"query":"What is GRR?"}) as r:
            for line in r.iter_lines():
                if line.startswith("data:"):
                    import json as j
                    events.append(j.loads(line[5:].strip()))
        types = [e.get("type") for e in events]
        assert "start" in types
        assert "result" in types or "error" in types


class TestHistoryEndpoint:
    def test_unknown_thread_empty(self, client):
        r = client.get("/history/nonexistent-xyz")
        assert r.status_code == 200
        assert r.json()["turns"] == 0

class TestAgentsStatus:
    def test_returns_200(self, client):
        assert client.get("/agents/status").status_code == 200
    def test_required_fields(self, client):
        r = client.get("/agents/status").json()
        for f in ["status","version","environment","mock_mode",
                  "redis_ok","agents","daily_tokens","timestamp"]:
            assert f in r
    def test_five_agents(self, client):
        assert len(client.get("/agents/status").json()["agents"]) == 5
    def test_all_agents_ready(self, client):
        for a in client.get("/agents/status").json()["agents"]:
            assert a["status"] == "ready"