# tests/test_day17.py
import json, os, sys, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("ENABLE_MOCK","true")
os.environ.setdefault("OPENAI_API_KEY","")


class TestBuildResponseCard:
    def _r(self, **kw):
        d={"final_summary":"GRR is 87%.","intent":"metric_analysis",
           "confidence":0.91,"execution_ms":342.0,"anomalies":[],
           "auto_tickets":[],"errors":[],"agent_results":[]}
        d.update(kw); return d

    def test_returns_teams_type(self):
        from teams.cards import build_response_card
        assert build_response_card(self._r())["type"] == "message"

    def test_has_adaptive_card(self):
        from teams.cards import build_response_card
        c = build_response_card(self._r())
        assert c["attachments"][0]["contentType"] ==                "application/vnd.microsoft.card.adaptive"

    def test_anomalies_in_card(self):
        from teams.cards import build_response_card
        c = build_response_card(self._r(anomalies=["GRR below 83%"]))
        assert "83%" in json.dumps(c)

    def test_tickets_in_card(self):
        from teams.cards import build_response_card
        c = build_response_card(self._r(auto_tickets=["DATA-4821"]))
        assert "DATA-4821" in json.dumps(c)


class TestBuildHITLCard:
    def test_has_approve_reject(self):
        from teams.cards import build_hitl_card
        c = build_hitl_card(
            {"anomalies":["drop"],"products":["retention"],
             "count":1,"message":"Approve?"},
            "thread-1","test query")
        s = json.dumps(c)
        assert "approve_tickets" in s and "reject_tickets" in s

    def test_thread_id_in_card(self):
        from teams.cards import build_hitl_card
        c = build_hitl_card(
            {"anomalies":["x"],"products":[],"count":1,"message":"y"},
            "my-thread","q")
        assert "my-thread" in json.dumps(c)


class TestTeamsActivityParsing:
    def test_parse_message(self):
        from teams.models import TeamsActivity
        a = TeamsActivity(**{"type":"message","text":"hello",
            "from":{"id":"u1","name":"User"},
            "conversation":{"id":"c1"}})
        assert a.text == "hello"
        assert a.from_.id == "u1"

    def test_parse_invoke(self):
        from teams.models import TeamsActivity
        a = TeamsActivity(**{"type":"invoke",
            "from":{"id":"u1"},
            "value":{"action":"approve_tickets","thread_id":"t1","query":"q"},
            "conversation":{"id":"c1"}})
        assert a.value["action"] == "approve_tickets"

    def test_from_alias_works(self):
        from teams.models import TeamsActivity
        a = TeamsActivity(**{"type":"message",
            "from":{"id":"user-abc"},"conversation":{"id":"c"}})
        assert a.from_.id == "user-abc"


@pytest.fixture(scope="module")
def client():
    from starlette.testclient import TestClient
    from api.app import app
    with TestClient(app) as c: yield c


def _msg(text,uid="u1",cid="c1"):
    return {"type":"message","id":"m1","text":text,
            "from":{"id":uid,"name":"User"},"conversation":{"id":cid}}


class TestTeamsWebhook:
    def test_health(self, client):
        r = client.get("/teams/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_message_200(self, client):
        r = client.post("/teams/webhook", json=_msg("Who owns bookings?"))
        assert r.status_code == 200

    def test_message_adaptive_card(self, client):
        r = client.post("/teams/webhook", json=_msg("What is GRR?"))
        b = r.json()
        assert b["type"] == "message"
        assert b["attachments"][0]["contentType"] ==                "application/vnd.microsoft.card.adaptive"

    def test_empty_message_returns_error_card(self, client):
        r = client.post("/teams/webhook", json=_msg(""))
        assert r.status_code == 200
        assert r.json()["type"] == "message"

    def test_invoke_approve(self, client):
        payload = {"type":"invoke","from":{"id":"u1"},
                   "value":{"action":"approve_tickets",
                            "thread_id":"c1","query":"retention drop?"},
                   "conversation":{"id":"c1"}}
        r = client.post("/teams/webhook", json=payload)
        assert r.status_code == 200
        assert r.json()["type"] == "message"

    def test_invoke_reject(self, client):
        payload = {"type":"invoke","from":{"id":"u1"},
                   "value":{"action":"reject_tickets","thread_id":"c1"},
                   "conversation":{"id":"c1"}}
        r = client.post("/teams/webhook", json=payload)
        assert r.status_code == 200

    def test_unknown_type_returns_200(self, client):
        r = client.post("/teams/webhook",
                        json={"type":"typing","from":{"id":"u1"},
                              "conversation":{"id":"c1"}})
        assert r.status_code == 200

    def test_x_user_id_header_accepted(self, client):
        r = client.post("/teams/webhook", json=_msg("What is LTV?"),
                        headers={"X-User-Id":"teams-user-abc"})
        assert r.status_code == 200