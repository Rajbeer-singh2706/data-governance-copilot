"""
src/api/app.py  — NEW file (Day 16)
FastAPI REST server with rate limiting and SSE streaming.
"""

from __future__ import annotations
import asyncio, json, os, sys, uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.middleware  import limiter
from config.settings import config
from core.cache      import get_client
from core.llm_guard  import check_and_record_tokens, estimate_tokens, get_daily_usage
from graph.graph     import copilot_graph
from graph.state     import initial_state


app = FastAPI(title="Data Governance Copilot API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS","*").split(","),
    allow_methods=["GET","POST"], allow_headers=["*"])

_executor = ThreadPoolExecutor(max_workers=int(os.getenv("MAX_WORKERS","4")))

class QueryRequest(BaseModel):
    query:         str
    thread_id:     Optional[str]       = None
    user_id:       Optional[str]       = "api-user"
    time_range:    Optional[str]       = "last_month"
    data_products: Optional[List[str]] = []
    approved:      Optional[bool]      = False   # Day 15 HITL flag

class QueryResponse(BaseModel):
    query_id: str; 
    thread_id: str; 
    intent: str; 
    summary: str
    confidence: float; 
    sources: List[str]; 
    auto_tickets: List[str]
    anomalies: List[str]; 
    errors: List[dict]; 
    execution_ms: float
    pending_action: Optional[dict] = None


async def _run_graph(body: QueryRequest) -> dict:
    """Run sync LangGraph in thread pool — never blocks the async event loop."""
    thread_id = body.thread_id or str(uuid.uuid4())
    state = initial_state(query=body.query, thread_id=thread_id,
                          user_id=body.user_id or "api-user",
                          time_range=body.time_range or "last_month")
    state["approved"] = body.approved or False
    if body.data_products:
        state["data_products"] = body.data_products
    cfg    = {"configurable": {"thread_id": thread_id}}
    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor,
                                        lambda: copilot_graph.invoke(state, config=cfg))
    result["_thread_id"] = thread_id
    return result

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()+"Z"}


@app.post("/query", response_model=QueryResponse)
@limiter.limit("20/minute")
async def query_endpoint(request: Request, body: QueryRequest):
    if not body.query.strip():
        raise HTTPException(400, "query cannot be empty")
    try:
        result = await _run_graph(body)
    except Exception as exc:
        raise HTTPException(500, str(exc))
    redis = get_client(config.redis)
    if redis:
        tokens = estimate_tokens(result.get("final_summary",""))
        if not check_and_record_tokens(redis, tokens):
            raise HTTPException(429, "Daily token budget exceeded. Resets at midnight UTC.")
    return QueryResponse(
        query_id=result.get("query_id","?"), thread_id=result["_thread_id"],
        intent=result.get("intent","unknown"), summary=result.get("final_summary",""),
        confidence=result.get("confidence",0.0), sources=result.get("sources",[]),
        auto_tickets=result.get("auto_tickets",[]), anomalies=result.get("anomalies",[]),
        errors=result.get("errors",[]), execution_ms=result.get("execution_ms",0.0),
        pending_action=result.get("pending_action"),
    )

@app.post("/query/stream")
@limiter.limit("20/minute")
async def query_stream(request: Request, body: QueryRequest):
    """SSE streaming: start → result → done events."""
    if not body.query.strip():
        raise HTTPException(400, "query cannot be empty")

    async def event_stream():
        qid = str(uuid.uuid4())[:8]
        yield f"data: {json.dumps({'type':'start','query_id':qid})}"
        try:
            result = await _run_graph(body)
            payload = {"type":"result",
                "query_id": result.get("query_id","?"),
                "thread_id": result["_thread_id"],
                "intent": result.get("intent","unknown"),
                "summary": result.get("final_summary",""),
                "confidence": result.get("confidence",0.0),
                "execution_ms": result.get("execution_ms",0.0)}
            yield f"data: {json.dumps(payload)}"
            yield f"data: {json.dumps({'type':'done','execution_ms':result.get('execution_ms',0)})}"
        except Exception as exc:
            yield f"data: {json.dumps({'type':'error','message':str(exc)})}"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Connection":"keep-alive"})


@app.get("/history/{thread_id}")
@limiter.limit("60/minute")
async def history_endpoint(request: Request, thread_id: str):
    try:
        snap = copilot_graph.get_state({"configurable":{"thread_id":thread_id}})
        if not snap or not snap.values:
            return {"thread_id":thread_id,"turns":0,"history":[]}
        history = snap.values.get("conversation_history",[])
        return {"thread_id":thread_id,"turns":len(history),"history":history}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get("/agents/status")
@limiter.limit("120/minute")
async def agents_status(request: Request):
    redis = get_client(config.redis)
    redis_ok = False
    if redis:
        try: redis.ping(); redis_ok=True
        except: pass
    agents = [{"name":n,"status":"ready","mock":config.enable_mock}
              for n in ["information","knowledge","metadata","capacity","rule"]]
    return {"status":"ok","version":"1.0.0","environment":config.environment,
            "mock_mode":config.enable_mock,"redis_ok":redis_ok,
            "agents":agents,"daily_tokens":get_daily_usage(redis),
            "timestamp":datetime.utcnow().isoformat()+"Z"}