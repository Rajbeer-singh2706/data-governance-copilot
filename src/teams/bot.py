"""
src/teams/bot.py
Day 17: Microsoft Teams webhook handler.

Teams → POST /teams/webhook → parse Activity → LangGraph → Adaptive Card

Activity types handled:
  message            — user text message → run graph → response card
  invoke             — button click (Approve/Reject HITL) → re-run graph
  conversationUpdate — bot added to channel → welcome card

Rate limiting: user_limiter keyed on X-User-Id (per Teams user, not per IP).
All Teams traffic originates from Microsoft's IPs so IP-based limiting
would block all users simultaneously.

HMAC verification:
  Set TEAMS_APP_SECRET in .env to enable signature validation.
  Leave blank to skip (acceptable in dev / internal deployments).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from teams.cards  import (
    build_error_card,
    build_hitl_card,
    build_response_card,
    build_thinking_card,
    build_welcome_card,
)
from teams.models import TeamsActivity
from api.middleware import user_limiter
from config.settings import config
from graph.graph  import copilot_graph
from graph.state  import initial_state

logger    = logging.getLogger(__name__)
router    = APIRouter(prefix="/teams", tags=["Teams"])
_executor = ThreadPoolExecutor(max_workers=2)

# App secret for HMAC verification (optional)
_APP_SECRET = os.getenv("TEAMS_APP_SECRET", "")


# ── HMAC verification ──────────────────────────────────────────────────────

def _verify_hmac(body: bytes, auth_header: str | None) -> bool:
    """
    Verify Teams request signature.
    Returns True when verification is disabled (no secret configured).
    """
    if not _APP_SECRET:
        return True   # verification disabled

    if not auth_header or not auth_header.startswith("HMAC "):
        logger.warning("[teams] Missing or malformed Authorization header")
        return False

    expected = hmac.new(
        _APP_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    received = auth_header[5:]   # strip "HMAC "
    return hmac.compare_digest(expected, received)


# ── Graph helpers ──────────────────────────────────────────────────────────

async def _run_graph(query: str, thread_id: str,
                     user_id: str, approved: bool = False) -> dict:
    """Run sync LangGraph in thread pool."""
    state = initial_state(
        query     = query,
        thread_id = thread_id,
        user_id   = user_id,
    )
    state["approved"] = approved

    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor,
        lambda: copilot_graph.invoke(
            state,
            config={"configurable": {"thread_id": thread_id}},
        ),
    )
    return result


# ── Activity handlers ──────────────────────────────────────────────────────

async def _handle_message(activity: TeamsActivity) -> dict:
    """
    Process a user text message.
    Returns an Adaptive Card dict ready to send back to Teams.
    """
    query     = (activity.text or "").strip()
    user_id   = activity.from_.id   if activity.from_   else "unknown"
    thread_id = activity.conversation.id if activity.conversation else str(uuid.uuid4())

    if not query:
        return build_error_card("Please enter a question.")

    logger.info("[teams] message from %s: %s", user_id, query[:80])

    try:
        result = await _run_graph(query, thread_id, user_id)
    except Exception as exc:
        logger.error("[teams] graph error: %s", exc)
        return build_error_card(f"Graph execution failed: {exc}")

    # HITL: if pending_action set, show approval card instead
    pending = result.get("pending_action")
    if pending:
        return build_hitl_card(
            pending_action = pending,
            thread_id      = thread_id,
            query          = query,
        )

    return build_response_card(result)


async def _handle_invoke(activity: TeamsActivity) -> dict:
    """
    Process a button click from an Adaptive Card (Action.Submit).
    value = {"action": "approve_tickets"|"reject_tickets", "thread_id": ..., "query": ...}
    """
    value     = activity.value or {}
    action    = value.get("action", "")
    thread_id = value.get("thread_id", str(uuid.uuid4()))
    query     = value.get("query", "")
    user_id   = activity.from_.id if activity.from_ else "unknown"

    logger.info("[teams] invoke action=%s thread=%s user=%s", action, thread_id, user_id)

    if action == "approve_tickets":
        if not query:
            return build_error_card("Cannot resume: original query missing.")
        try:
            result = await _run_graph(query, thread_id, user_id, approved=True)
            return build_response_card(result)
        except Exception as exc:
            return build_error_card(f"Ticket creation failed: {exc}")

    elif action == "reject_tickets":
        return build_error_card("Ticket creation rejected. No Jira tickets were created.")

    else:
        logger.warning("[teams] unknown invoke action: %s", action)
        return build_error_card(f"Unknown action: {action}")


async def _handle_conversation_update(activity: TeamsActivity) -> dict | None:
    """
    Handle bot being added to a channel — send welcome card.
    Returns None if bot was removed (no response needed).
    """
    members_added = activity.membersAdded or []
    bot_id        = activity.from_.id if activity.from_ else ""

    for member in members_added:
        if member.id != bot_id:
            logger.info("[teams] bot added to conversation — sending welcome")
            return build_welcome_card()

    return None   # bot removed — no response


# ── Webhook endpoint ───────────────────────────────────────────────────────

@router.post("/webhook")
@user_limiter.limit("10/minute")
async def teams_webhook(
    request:       Request,
    authorization: str | None = Header(default=None),
):
    """
    Microsoft Teams webhook endpoint.

    Teams POSTs every channel message and bot interaction here.
    We validate the payload, route to the correct handler, and
    return an Adaptive Card as the response.

    Rate limited at 10 requests/minute per X-User-Id (not IP).
    """
    # Read raw body for HMAC verification
    body = await request.body()

    if not _verify_hmac(body, authorization):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    # Parse Activity
    try:
        payload  = await request.json()
        activity = TeamsActivity(**payload)
    except Exception as exc:
        logger.error("[teams] failed to parse activity: %s", exc)
        raise HTTPException(status_code=400, detail=f"Invalid activity payload: {exc}")

    activity_type = activity.type.lower()
    logger.info("[teams] activity type: %s", activity_type)

    # Route to handler
    card: dict | None = None

    if activity_type == "message":
        card = await _handle_message(activity)

    elif activity_type == "invoke":
        card = await _handle_invoke(activity)

    elif activity_type == "conversationupdate":
        card = await _handle_conversation_update(activity)

    else:
        logger.info("[teams] unhandled activity type: %s", activity_type)

    # Teams requires a 200 response — empty body is valid for unhandled types
    if card is None:
        return JSONResponse(content={}, status_code=200)

    return JSONResponse(content=card, status_code=200)


@router.get("/health")
async def teams_health():
    """Teams bot health probe."""
    return {
        "status":    "ok",
        "bot":       "Data Governance Copilot",
        "mock_mode": config.enable_mock,
        "hmac_enabled": bool(_APP_SECRET),
    }