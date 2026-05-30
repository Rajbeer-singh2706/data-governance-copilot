"""FastAPI application — REST + SSE + Teams bot."""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from src.api.middleware import limiter, user_limiter
from src.graph.graph import get_graph
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app = FastAPI(title="Data Governance Copilot API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str
    thread_id: str = "default"
    user_id: str = "anonymous"
    time_range: str = "last_30_days"
    data_products: list = []


def _run_graph(query_req: QueryRequest) -> dict:
    graph = get_graph()
    state = {
        "query": query_req.query,
        "thread_id": query_req.thread_id,
        "user_id": query_req.user_id,
        "time_range": query_req.time_range,
        "data_products": query_req.data_products,
        "approved": False,
    }
    config = {"configurable": {"thread_id": query_req.thread_id}}
    result = graph.invoke(state, config=config)
    return result


@app.get("/health")
async def health():
    return {"status": "ok", "service": "data-governance-copilot"}


@app.post("/query")
@limiter.limit("20/minute")
async def query(request: Request, body: QueryRequest):
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _run_graph, body)
        return {
            "query_id": result.get("query_id", str(uuid.uuid4())[:8]),
            "summary": result.get("final_summary", ""),
            "confidence": result.get("confidence", 0.0),
            "anomalies": result.get("anomalies", []),
            "sources": result.get("sources", []),
            "execution_ms": result.get("execution_ms", 0),
            "pending_action": result.get("pending_action"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/query/stream")
@limiter.limit("20/minute")
async def query_stream(request: Request, body: QueryRequest):
    async def event_generator() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'event': 'start', 'query': body.query})}\n\n"
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, _run_graph, body)
            yield f"data: {json.dumps({'event': 'result', 'data': {'summary': result.get('final_summary', ''), 'anomalies': result.get('anomalies', []), 'confidence': result.get('confidence', 0)}})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'event': 'error', 'message': str(exc)})}\n\n"
        yield f"data: {json.dumps({'event': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/history/{thread_id}")
@limiter.limit("60/minute")
async def get_history(request: Request, thread_id: str):
    return {"thread_id": thread_id, "messages": [], "note": "History requires checkpointer with persistent storage"}


@app.get("/agents/status")
@limiter.limit("120/minute")
async def agents_status(request: Request):
    from src.core.cache import get_client
    from src.core.llm_guard import get_daily_usage
    from src.config.settings import get_config

    client = get_client(get_config())
    token_usage = get_daily_usage(client)
    return {
        "redis": "connected" if client else "unavailable",
        "agents": ["information", "knowledge", "metadata", "capacity", "rule"],
        "mock_mode": os.getenv("ENABLE_MOCK", "true"),
        "token_usage": token_usage,
    }


@app.post("/ingest")
@limiter.limit("10/minute")
async def ingest(request: Request, file: UploadFile = File(...)):
    """Upload a document and trigger Airflow on_demand_ingest_dag."""
    import tempfile, shutil, httpx

    suffix = os.path.splitext(file.filename or "doc.pdf")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    airflow_host = os.getenv("AIRFLOW_HOST", "localhost:8080")
    airflow_user = os.getenv("AIRFLOW_ADMIN_USER", "admin")
    airflow_pass = os.getenv("AIRFLOW_ADMIN_PASSWORD", "admin")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://{airflow_host}/api/v1/dags/on_demand_ingest_dag/dagRuns",
                json={"conf": {"filepath": tmp_path}},
                auth=(airflow_user, airflow_pass),
                timeout=10,
            )
        return {"status": "triggered", "filepath": tmp_path, "dag_run": resp.json()}
    except Exception as exc:
        return {"status": "queued_locally", "filepath": tmp_path, "note": str(exc)}


# Include Teams bot router
from src.teams.bot import router as teams_router
app.include_router(teams_router)
