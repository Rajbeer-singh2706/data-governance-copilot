"""
src/teams/bot.py  — NEW file (Day 17)
Teams webhook handler — FastAPI router mounted at /teams
"""
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
import asyncio, hashlib, hmac, logging, os, sys, uuid
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from teams.cards  import (build_error_card, build_hitl_card,
                           build_response_card, build_welcome_card)
from teams.models import TeamsActivity
from api.middleware import user_limiter
from config.settings import config
from graph.graph import copilot_graph
from graph.state import initial_state

logger    = logging.getLogger(__name__)
router    = APIRouter(prefix="/teams", tags=["Teams"])
_executor = ThreadPoolExecutor(max_workers=2)
_SECRET   = os.getenv("TEAMS_APP_SECRET", "")


def _verify_hmac(body: bytes, auth: str | None) -> bool:
    if not _SECRET: return True           # verification disabled
    if not auth or not auth.startswith("HMAC "): return False
    expected = hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, auth[5:])


async def _run_graph(query, thread_id, user_id, approved=False) -> dict:
    state = initial_state(query=query, thread_id=thread_id, user_id=user_id)
    state["approved"] = approved
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: copilot_graph.invoke(
            state, config={"configurable":{"thread_id":thread_id}}
        )
    )


async def _handle_message(activity: TeamsActivity) -> dict:
    query     = (activity.text or "").strip()
    user_id   = activity.from_.id   if activity.from_   else "unknown"
    thread_id = activity.conversation.id if activity.conversation else str(uuid.uuid4())
    if not query:
        return build_error_card("Please enter a question.")
    try:
        result  = await _run_graph(query, thread_id, user_id)
    except Exception as exc:
        return build_error_card(str(exc))
    pending = result.get("pending_action")
    if pending:
        return build_hitl_card(pending, thread_id, query)
    return build_response_card(result)


async def _handle_invoke(activity: TeamsActivity) -> dict:
    value     = activity.value or {}
    action    = value.get("action", "")
    thread_id = value.get("thread_id", str(uuid.uuid4()))
    query     = value.get("query", "")
    user_id   = activity.from_.id if activity.from_ else "unknown"
    if action == "approve_tickets":
        if not query: return build_error_card("Missing original query.")
        try:
            result = await _run_graph(query, thread_id, user_id, approved=True)
            return build_response_card(result)
        except Exception as exc:
            return build_error_card(str(exc))
    elif action == "reject_tickets":
        return build_error_card("Ticket creation rejected.")
    return build_error_card(f"Unknown action: {action}")


async def _handle_conversation_update(activity: TeamsActivity) -> dict | None:
    bot_id = activity.from_.id if activity.from_ else ""
    for m in (activity.membersAdded or []):
        if m.id != bot_id: return build_welcome_card()
    return None


@router.post("/webhook")
@user_limiter.limit("10/minute")
async def teams_webhook(request: Request,
                        authorization: str | None = Header(default=None)):
    body = await request.body()
    if not _verify_hmac(body, authorization):
        raise HTTPException(401, "Invalid HMAC signature")
    try:
        activity = TeamsActivity(**(await request.json()))
    except Exception as exc:
        raise HTTPException(400, f"Invalid payload: {exc}")

    t = activity.type.lower()
    if t == "message":           card = await _handle_message(activity)
    elif t == "invoke":          card = await _handle_invoke(activity)
    elif t == "conversationupdate": card = await _handle_conversation_update(activity)
    else:                        card = None

    return JSONResponse(content=card or {}, status_code=200)


@router.get("/health")
async def teams_health():
    return {"status":"ok","bot":"Data Governance Copilot",
            "mock_mode":config.enable_mock,"hmac_enabled":bool(_SECRET)}