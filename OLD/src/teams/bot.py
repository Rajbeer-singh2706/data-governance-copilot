"""Teams bot — webhook router + HMAC verification + activity routing."""
from __future__ import annotations

import hashlib
import hmac
import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from teams.cards import build_error_card, build_hitl_card, build_response_card, build_welcome_card
from teams.models import TeamsActivity

router = APIRouter(prefix="/teams")

_SECRET = os.getenv("TEAMS_APP_SECRET", "")
_MOCK_MODE = os.getenv("ENABLE_MOCK", "true").lower() == "true"


def _verify_hmac(body: bytes, signature: str) -> bool:
    if not _SECRET:
        return True  # disabled in dev
    expected = hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.lstrip("sha256="))


async def _handle_message(activity: TeamsActivity) -> dict:
    query = (activity.text or "").strip()
    thread_id = activity.conversation.id if activity.conversation else "teams-default"
    user_id = activity.from_user.id if activity.from_user else "anonymous"

    if not query:
        return build_error_card("Please include a question or command.")

    from graph.graph import get_graph
    graph = get_graph()
    state = {
        "query": query, "thread_id": thread_id, "user_id": user_id,
        "time_range": "last_30_days", "data_products": [], "approved": False,
    }
    try:
        result = graph.invoke(state, config={"configurable": {"thread_id": thread_id}})
        if result.get("pending_action"):
            return build_hitl_card(result["pending_action"], thread_id, query)
        return build_response_card(result)
    except Exception as exc:
        return build_error_card(str(exc))


async def _handle_invoke(activity: TeamsActivity) -> dict:
    value = activity.value or {}
    action = value.get("action", "")
    thread_id = value.get("thread_id", "teams-default")
    query = value.get("query", "")

    if action == "approve_tickets":
        from graph.graph import get_graph
        graph = get_graph()
        state = {
            "approved": True, "query": query, "thread_id": thread_id,
            "data_products": [], "time_range": "last_30_days",
        }
        try:
            result = graph.invoke(state, config={"configurable": {"thread_id": thread_id}})
            return build_response_card(result)
        except Exception as exc:
            return build_error_card(str(exc))
    else:
        return build_error_card("Action rejected. No tickets were created.")


async def _handle_conversation_update(activity: TeamsActivity) -> dict:
    members = activity.members_added or []
    if not members:
        return {}
    return build_welcome_card()


async def handle_activity(body: bytes) -> dict:
    """Standalone callable — used by api/app.py if router is not included."""
    try:
        activity = TeamsActivity.model_validate_json(body)
    except Exception as exc:
        return {"error": f"Invalid JSON: {exc}"}

    if activity.type == "message":
        return await _handle_message(activity)
    elif activity.type == "invoke":
        return await _handle_invoke(activity)
    elif activity.type == "conversationUpdate":
        return await _handle_conversation_update(activity)
    return {}


@router.post("/webhook")
async def teams_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("Authorization", "")
    if not _verify_hmac(body, sig):
        return JSONResponse(status_code=401, content={"detail": "Invalid HMAC signature"})

    try:
        activity = TeamsActivity.model_validate_json(body)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"detail": f"Invalid JSON: {exc}"})

    if activity.type == "message":
        resp = await _handle_message(activity)
    elif activity.type == "invoke":
        resp = await _handle_invoke(activity)
    elif activity.type == "conversationUpdate":
        resp = await _handle_conversation_update(activity)
    else:
        resp = {}

    return JSONResponse(content=resp)


@router.get("/health")
async def teams_health():
    return {"status": "ok", "mock_mode": _MOCK_MODE}
