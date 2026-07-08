# tests/test_day17.py
# Day 17: Teams bot — Adaptive Cards, webhook handler, HITL invoke
#
# Run: uv run pytest tests/test_day17.py -v
# Mock: ENABLE_MOCK=true OPENAI_API_KEY="" pytest tests/test_day17.py -v

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("ENABLE_MOCK", "true")
os.environ.setdefault("OPENAI_API_KEY", "")


# ══════════════════════════════════════════════════════════════════════════
# 1. cards.py — Adaptive Card builders
# ══════════════════════════════════════════════════════════════════════════

class TestBuildResponseCard:

    def _result(self, **kwargs):
        defaults = {
            "final_summary": "GRR is 87% — slightly above the 85% threshold.",
            "intent": "metric_analysis",
            "confidence": 0.91,
            "execution_ms": 342.0,
            "anomalies": [],
            "auto_tickets": [],
            "errors": [],
            "agent_results": [],
        }
        defaults.update(kwargs)
        return defaults

    def test_returns_teams_message_type(self):
        from teams.cards import build_response_card
        card = build_response_card(self._result())
        assert card["type"] == "message"

    def test_has_adaptive_card_attachment(self):
        from teams.cards import build_response_card
        card = build_response_card(self._result())
        assert len(card["attachments"]) == 1
        assert card["attachments"][0]["contentType"] == \
               "application/vnd.microsoft.card.adaptive"

    def test_card_has_body(self):
        from teams.cards import build_response_card
        card    = build_response_card(self._result())
        content = card["attachments"][0]["content"]
        assert "body" in content
        assert len(content["body"]) > 0

    def test_adaptive_card_version(self):
        from teams.cards import build_response_card
        card    = build_response_card(self._result())
        content = card["attachments"][0]["content"]
        assert content["version"] == "1.4"
        assert content["type"]    == "AdaptiveCard"

    def test_anomalies_shown_in_card(self):
        from teams.cards import build_response_card
        result  = self._result(anomalies=["GRR below threshold: 83%"])
        card    = build_response_card(result)
        content = card["attachments"][0]["content"]
        body_text = json.dumps(content["body"])
        assert "83%" in body_text or "Anomaly" in body_text

    def test_no_anomalies_no_warning_block(self):
        from teams.cards import build_response_card
        result  = self._result(anomalies=[])
        card    = build_response_card(result)
        content = card["attachments"][0]["content"]
        body_text = json.dumps(content["body"])
        assert "Anomaly" not in body_text

    def test_tickets_shown_in_card(self):
        from teams.cards import build_response_card
        result  = self._result(auto_tickets=["DATA-4821", "DATA-4822"])
        card    = build_response_card(result)
        content = card["attachments"][0]["content"]
        body_text = json.dumps(content["body"])
        assert "DATA-4821" in body_text

    def test_errors_shown_in_card(self):
        from teams.cards import build_response_card
        result  = self._result(errors=[{"node": "information_node",
                                         "error": "DB timeout"}])
        card    = build_response_card(result)
        content = card["attachments"][0]["content"]
        body_text = json.dumps(content["body"])
        assert "error" in body_text.lower()


class TestBuildHITLCard:

    def test_returns_teams_message_type(self):
        from teams.cards import build_hitl_card
        card = build_hitl_card(
            pending_action={"anomalies": ["GRR below 85%"],
                            "products": ["retention"], "count": 1,
                            "message": "Approve ticket creation?"},
            thread_id="thread-123",
            query="why did retention drop?",
        )
        assert card["type"] == "message"

    def test_has_approve_reject_actions(self):
        from teams.cards import build_hitl_card
        card    = build_hitl_card(
            pending_action={"anomalies": ["GRR below 85%"],
                            "products": ["retention"], "count": 1,
                            "message": "Approve?"},
            thread_id="thread-123", query="test",
        )
        content = card["attachments"][0]["content"]
        # Actions can be top-level or in body
        all_text = json.dumps(content)
        assert "approve_tickets" in all_text
        assert "reject_tickets"  in all_text

    def test_action_data_has_thread_id(self):
        from teams.cards import build_hitl_card
        card    = build_hitl_card(
            pending_action={"anomalies": ["drop"], "products": [],
                            "count": 1, "message": "Approve?"},
            thread_id="my-thread-abc", query="test query",
        )
        all_text = json.dumps(card)
        assert "my-thread-abc" in all_text

    def test_action_data_has_query(self):
        from teams.cards import build_hitl_card
        card = build_hitl_card(
            pending_action={"anomalies":["drop"],"products":[],"count":1,"message":"x"},
            thread_id="t", query="retention question",
        )
        assert "retention question" in json.dumps(card)


class TestUtilityCards:

    def test_error_card_structure(self):
        from teams.cards import build_error_card
        card = build_error_card("Something went wrong")
        assert card["type"] == "message"
        assert "Something went wrong" in json.dumps(card)

    def test_welcome_card_structure(self):
        from teams.cards import build_welcome_card
        card = build_welcome_card()
        assert card["type"] == "message"
        assert "Copilot" in json.dumps(card)

    def test_thinking_card_structure(self):
        from teams.cards import build_thinking_card
        card = build_thinking_card()
        assert card["type"] == "message"
        assert "naly" in json.dumps(card).lower() or "Analysing" in json.dumps(card)


# ══════════════════════════════════════════════════════════════════════════
# 2. models.py — Teams Activity parsing
# ══════════════════════════════════════════════════════════════════════════

class TestTeamsActivity:

    def test_parse_message_activity(self):
        from teams.models import TeamsActivity
        payload = {
            "type": "message",
            "id":   "msg-001",
            "text": "Who owns the bookings dataset?",
            "from": {"id": "user-123", "name": "John"},
            "conversation": {"id": "conv-456"},
        }
        activity = TeamsActivity(**payload)
        assert activity.type         == "message"
        assert activity.text         == "Who owns the bookings dataset?"
        assert activity.from_.id     == "user-123"
        assert activity.from_.name   == "John"
        assert activity.conversation.id == "conv-456"

    def test_parse_invoke_activity(self):
        from teams.models import TeamsActivity
        payload = {
            "type":  "invoke",
            "from":  {"id": "user-123"},
            "value": {"action": "approve_tickets", "thread_id": "t-1",
                      "query": "why did retention drop?"},
            "conversation": {"id": "conv-1"},
        }
        activity = TeamsActivity(**payload)
        assert activity.type  == "invoke"
        assert activity.value["action"] == "approve_tickets"

    def test_parse_conversation_update(self):
        from teams.models import TeamsActivity
        payload = {
            "type": "conversationUpdate",
            "from": {"id": "bot-id"},
            "membersAdded": [{"id": "user-new"}],
            "conversation": {"id": "conv-1"},
        }
        activity = TeamsActivity(**payload)
        assert activity.type                == "conversationUpdate"
        assert len(activity.membersAdded)   == 1
        assert activity.membersAdded[0].id  == "user-new"

    def test_missing_optional_fields_default_none(self):
        from teams.models import TeamsActivity
        activity = TeamsActivity(type="message")
        assert activity.text         is None
        assert activity.from_        is None
        assert activity.conversation is None


# ══════════════════════════════════════════════════════════════════════════
# 3. Webhook endpoint — TestClient
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def client():
    from starlette.testclient import TestClient
    from api.app import app
    with TestClient(app) as c:
        yield c


def _message_payload(text: str, user_id: str = "user-1",
                     conv_id: str = "conv-1") -> dict:
    return {
        "type": "message",
        "id":   "msg-001",
        "text": text,
        "from": {"id": user_id, "name": "Test User"},
        "conversation": {"id": conv_id},
        "channelId": "msteams",
    }


class TestTeamsWebhook:

    def test_health_returns_200(self, client):
        r = client.get("/teams/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_message_returns_200(self, client):
        r = client.post("/teams/webhook",
                        json=_message_payload("Who owns bookings data?"))
        assert r.status_code == 200

    def test_message_returns_adaptive_card(self, client):
        r = client.post("/teams/webhook",
                        json=_message_payload("What is GRR?"))
        body = r.json()
        assert body["type"] == "message"
        assert len(body["attachments"]) > 0
        assert body["attachments"][0]["contentType"] == \
               "application/vnd.microsoft.card.adaptive"

    def test_empty_message_returns_error_card(self, client):
        r    = client.post("/teams/webhook", json=_message_payload(""))
        body = r.json()
        assert body["type"] == "message"
        # Error card should mention the issue
        assert "error" in json.dumps(body).lower() or \
               "question" in json.dumps(body).lower()

    def test_unknown_activity_type_returns_200(self, client):
        r = client.post("/teams/webhook",
                        json={"type": "typing", "from": {"id": "u1"},
                              "conversation": {"id": "c1"}})
        assert r.status_code == 200

    def test_conversation_update_returns_welcome_card(self, client):
        payload = {
            "type": "conversationUpdate",
            "from": {"id": "bot-id"},
            "membersAdded": [{"id": "new-user-1", "name": "New User"}],
            "conversation": {"id": "conv-new"},
        }
        r    = client.post("/teams/webhook", json=payload)
        body = r.json()
        if body:  # might be empty if only bot was added
            assert body.get("type") == "message"

    def test_invoke_approve_returns_card(self, client):
        payload = {
            "type":  "invoke",
            "from":  {"id": "user-1", "name": "User"},
            "value": {
                "action":    "approve_tickets",
                "thread_id": "conv-1",
                "query":     "Why did retention drop?",
            },
            "conversation": {"id": "conv-1"},
        }
        r    = client.post("/teams/webhook", json=payload)
        body = r.json()
        assert r.status_code == 200
        assert body.get("type") == "message"

    def test_invoke_reject_returns_error_card(self, client):
        payload = {
            "type":  "invoke",
            "from":  {"id": "user-1"},
            "value": {"action": "reject_tickets", "thread_id": "conv-1"},
            "conversation": {"id": "conv-1"},
        }
        r    = client.post("/teams/webhook", json=payload)
        body = r.json()
        assert r.status_code == 200
        assert "rejected" in json.dumps(body).lower() or \
               body.get("type") == "message"

    def test_invalid_json_returns_400(self, client):
        r = client.post("/teams/webhook",
                        content=b"not json",
                        headers={"Content-Type": "application/json"})
        assert r.status_code in [400, 422]

    def test_user_id_header_accepted(self, client):
        """X-User-Id header should be accepted for rate limiting."""
        r = client.post(
            "/teams/webhook",
            json=_message_payload("What is LTV?"),
            headers={"X-User-Id": "teams-user-abc"},
        )
        assert r.status_code == 200