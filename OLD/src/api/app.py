"""FastAPI application — /query, /query/stream, /history, /agents/status, /teams/webhook, /ingest."""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv()

from src.core.logging_utils import get_logger
from src.api.middleware import limiter

logger = get_logger("api.app")

# Module-level import — patchable in tests
from src.graph.graph import get_graph  # noqa: E402

app = FastAPI(title="Data Governance Copilot API", version="1.0.0")
app.state.limiter = limiter

# Include Teams router
from src.teams.bot import router as teams_router
app.include_router(teams_router)


# ── Models ─────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    thread_id: str = "default"
    user_id: str = "api-user"
    time_range: str = "last_30_days"
    data_products: List[str] = []
    approved: bool = False


# ── Internal helpers ────────────────────────────────────────────────────────────

def _run_graph(req: QueryRequest) -> Dict:
    """Invoke the LangGraph and return the result dict."""
    graph = get_graph()
    state = {
        "query": req.query,
        "thread_id": req.thread_id,
        "user_id": req.user_id,
        "time_range": req.time_range,
        "data_products": req.data_products,
        "approved": req.approved,
    }
    return graph.invoke(state, config={"configurable": {"thread_id": req.thread_id}})


def _to_response(result: Dict, req: QueryRequest) -> Dict:
    return {
        "query_id": result.get("query_id", str(uuid.uuid4())[:8]),
        "thread_id": req.thread_id,
        "intent": result.get("intent", "unknown"),
        "summary": result.get("final_summary", ""),
        "confidence": result.get("confidence", 0.0),
        "sources": list(set(result.get("sources", [])))[:10],
        "auto_tickets": result.get("auto_tickets", []),
        "anomalies": result.get("anomalies", []),
        "errors": result.get("errors", []),
        "execution_ms": result.get("execution_ms", 0.0),
        "pending_action": result.get("pending_action"),
    }


# ── Endpoints ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "data-governance-copilot"}


@app.post("/query")
async def query_endpoint(request: Request, req: QueryRequest):
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    try:
        result = _run_graph(req)
    except Exception as exc:
        logger.error(f"Graph invocation failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    # Guardrail blocked
    if result.get("guardrail_passed") is False:
        raise HTTPException(status_code=400, detail=result.get("final_summary", "Query blocked"))

    return _to_response(result, req)


@app.post("/query/stream")
async def query_stream(request: Request, req: QueryRequest):
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    async def event_generator():
        yield f"data: {json.dumps({'type': 'start', 'thread_id': req.thread_id})}\n\n"
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: _run_graph(req))
            payload = _to_response(result, req)
            yield f"data: {json.dumps({'type': 'result', **payload})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/history/{thread_id}")
async def history(request: Request, thread_id: str):
    try:
        graph = get_graph()
        checkpointer = getattr(graph, "checkpointer", None)
        if checkpointer is None:
            return {"thread_id": thread_id, "messages": [], "turns": 0}
        config = {"configurable": {"thread_id": thread_id}}
        state = checkpointer.get(config)
        history_msgs = []
        if state and state.values:
            history_msgs = state.values.get("conversation_history", [])
        return {"thread_id": thread_id, "messages": history_msgs, "turns": len(history_msgs)}
    except Exception:
        return {"thread_id": thread_id, "messages": [], "turns": 0}


@app.get("/agents/status")
async def agents_status(request: Request):
    agent_names = ["information", "knowledge", "metadata", "capacity", "rule"]

    redis_ok = False
    try:
        from src.core.cache import _redis_client
        if _redis_client:
            _redis_client.ping()
            redis_ok = True
    except Exception:
        pass

    token_usage: Dict = {}
    try:
        from src.core.llm_guard import get_daily_usage
        token_usage = get_daily_usage()
    except Exception:
        pass

    mock_mode = os.getenv("ENABLE_MOCK", "true").lower() == "true"

    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "redis_ok": redis_ok,
        "mock_mode": mock_mode,
        "agents": [{"name": a, "status": "ready"} for a in agent_names],
        "daily_tokens": token_usage,
        "token_usage": token_usage,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/ingest")
async def ingest(request: Request):
    """Trigger on-demand document ingestion via Airflow REST API."""
    try:
        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(status_code=400, detail="No file uploaded")

        airflow_url = os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080")
        dag_id = "on_demand_ingest_dag"
        import tempfile

        contents = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        # Try to trigger Airflow; fall back gracefully
        run_id = None
        try:
            import aiohttp
            payload = {"conf": {"filepath": tmp_path}}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{airflow_url}/api/v1/dags/{dag_id}/dagRuns",
                    json=payload,
                    auth=aiohttp.BasicAuth(
                        os.getenv("AIRFLOW_USER", "airflow"),
                        os.getenv("AIRFLOW_PASSWORD", "airflow"),
                    ),
                ) as resp:
                    data = await resp.json()
                    run_id = data.get("dag_run_id")
        except Exception:
            run_id = f"local-{uuid.uuid4().hex[:8]}"

        return {"status": "triggered", "dag_run_id": run_id, "filepath": tmp_path}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Ingest failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
