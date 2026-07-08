"""
Data Governance Copilot — MCP Server
=====================================
Exposes all five agents (information, knowledge, metadata, capacity, rule)
plus governance helpers as MCP tools.  Supports two transports:

  • stdio   (default) — for Claude Desktop / local clients
  • SSE     (TRANSPORT=sse)  — for remote / web clients (HTTP + SSE)

Usage
-----
  # stdio (Claude Desktop)
  python -m src.mcp_server.server

  # SSE (remote, listens on 0.0.0.0:8002)
  TRANSPORT=sse MCP_PORT=8002 python -m src.mcp_server.server
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

# Ensure project root is on sys.path when run as __main__
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
# Also add src/ so "from agents.xxx" works
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import (
    TextContent,
    Tool,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _ok(data: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


def _err(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps({"error": msg}))]


def _run_agent(agent_name: str, query: str, **kwargs) -> dict:
    """Invoke a single agent and return its result dict."""
    from core.base_agent import AgentRequest
    from graph.nodes import _get_agent
    agent = _get_agent(agent_name)
    if agent is None:
        return {"success": False, "error": f"Agent '{agent_name}' not found"}
    req = AgentRequest(
        query=query,
        thread_id=kwargs.get("thread_id", "mcp-default"),
        data_products=kwargs.get("data_products", []),
        time_range=kwargs.get("time_range", "last_30_days"),
    )
    result = agent.execute(req)
    return {
        "success": result.success,
        "data": result.data,
        "sources": result.sources,
        "errors": result.errors,
        "confidence": getattr(result, "confidence", 0.8),
    }


def _full_graph(query: str, thread_id: str = "mcp-default",
                data_products: list | None = None) -> dict:
    """Run the full LangGraph pipeline and return final state."""
    from graph.graph import get_graph
    graph = get_graph()
    state = {
        "query": query,
        "thread_id": thread_id,
        "user_id": "mcp-user",
        "time_range": "last_30_days",
        "data_products": data_products or [],
        "approved": False,
    }
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(state, config=config)
    return {
        "query_id": result.get("query_id"),
        "intent": result.get("intent"),
        "summary": result.get("final_summary"),
        "confidence": result.get("confidence"),
        "anomalies": result.get("anomalies", []),
        "sources": result.get("sources", []),
        "errors": result.get("errors", []),
        "execution_ms": result.get("execution_ms"),
        "pending_action": result.get("pending_action"),
    }


# ── Server definition ────────────────────────────────────────────────────────

server = Server("data-governance-copilot")

# ── Tool catalogue ────────────────────────────────────────────────────────────

TOOLS: list[Tool] = [
    # 1. Full pipeline
    Tool(
        name="governance_query",
        description=(
            "Run a natural-language data governance query through the full "
            "multi-agent pipeline (intent classification → specialist agents → synthesis). "
            "Returns a summary, detected anomalies, sources, and confidence score."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The governance question to answer"},
                "thread_id": {"type": "string", "default": "mcp-default"},
                "data_products": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of data products to scope (retention, bookings, cac, ltv)",
                },
            },
            "required": ["query"],
        },
    ),
    # 2. Data / metrics agent
    Tool(
        name="query_metrics",
        description=(
            "Query structured data metrics via the Information Agent "
            "(Databricks SQL / mock). Returns row-level data, anomalies, and sources."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "data_products": {"type": "array", "items": {"type": "string"}},
                "time_range": {"type": "string", "default": "last_30_days"},
            },
            "required": ["query"],
        },
    ),
    # 3. Knowledge / RAG agent
    Tool(
        name="search_knowledge_base",
        description=(
            "Semantic search over the governance knowledge base (policies, runbooks, standards) "
            "using the Knowledge Agent (pgvector RAG)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "data_products": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query"],
        },
    ),
    # 4. Metadata / Collibra agent
    Tool(
        name="get_metadata",
        description=(
            "Retrieve data asset metadata and data quality scores from Collibra "
            "via the Metadata Agent."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "data_products": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query"],
        },
    ),
    # 5. Capacity / Jira agent
    Tool(
        name="manage_incidents",
        description=(
            "List open incidents, create Jira tickets, or query SLA status "
            "via the Capacity Agent."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "data_products": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query"],
        },
    ),
    # 6. Rule agent
    Tool(
        name="manage_rules",
        description=(
            "Create, list, update, or evaluate data governance rules "
            "via the Rule Agent."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "e.g. 'create rule: retention must be > 80%'"},
                "data_products": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query"],
        },
    ),
    # 7. System health
    Tool(
        name="get_system_status",
        description="Return the status of all agents, Redis, and daily token usage.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    # 8. Cache invalidation
    Tool(
        name="invalidate_cache",
        description=(
            "Invalidate cached node results for a specific agent or all agents. "
            "Useful after data refreshes."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": "Agent name to invalidate (information_agent, knowledge_agent, metadata_agent) or 'all'",
                },
            },
            "required": ["agent"],
        },
    ),
    # 9. Approve pending HITL action
    Tool(
        name="approve_action",
        description=(
            "Approve a pending Human-in-the-Loop action (e.g., Jira ticket creation) "
            "for a given thread."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "query": {"type": "string", "description": "Repeat the original query to re-run with approval"},
            },
            "required": ["thread_id", "query"],
        },
    ),
    # 10. Ingest a document URL
    Tool(
        name="ingest_document_url",
        description=(
            "Download a document from a URL and ingest it into the pgvector knowledge base. "
            "Triggers the ingestion pipeline (chunking + embedding + upsert)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Publicly accessible document URL"},
                "product": {"type": "string", "description": "Data product tag (optional)"},
            },
            "required": ["url"],
        },
    ),
]


@server.list_tools()
async def list_tools():
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        # ── 1. governance_query ──────────────────────────────────────────────
        if name == "governance_query":
            result = _full_graph(
                query=arguments["query"],
                thread_id=arguments.get("thread_id", "mcp-default"),
                data_products=arguments.get("data_products"),
            )
            return _ok(result)

        # ── 2. query_metrics ─────────────────────────────────────────────────
        elif name == "query_metrics":
            result = _run_agent(
                "information",
                arguments["query"],
                data_products=arguments.get("data_products", []),
                time_range=arguments.get("time_range", "last_30_days"),
            )
            return _ok(result)

        # ── 3. search_knowledge_base ─────────────────────────────────────────
        elif name == "search_knowledge_base":
            result = _run_agent(
                "knowledge",
                arguments["query"],
                data_products=arguments.get("data_products", []),
            )
            return _ok(result)

        # ── 4. get_metadata ──────────────────────────────────────────────────
        elif name == "get_metadata":
            result = _run_agent(
                "metadata",
                arguments["query"],
                data_products=arguments.get("data_products", []),
            )
            return _ok(result)

        # ── 5. manage_incidents ──────────────────────────────────────────────
        elif name == "manage_incidents":
            result = _run_agent(
                "capacity",
                arguments["query"],
                data_products=arguments.get("data_products", []),
            )
            return _ok(result)

        # ── 6. manage_rules ──────────────────────────────────────────────────
        elif name == "manage_rules":
            result = _run_agent(
                "rule",
                arguments["query"],
                data_products=arguments.get("data_products", []),
            )
            return _ok(result)

        # ── 7. get_system_status ─────────────────────────────────────────────
        elif name == "get_system_status":
            from core.cache import get_client
            from core.llm_guard import get_daily_usage
            from config.settings import get_config
            cfg = get_config()
            client = get_client(cfg)
            token_usage = get_daily_usage(client)
            agents = ["information", "knowledge", "metadata", "capacity", "rule"]
            return _ok({
                "status": "ok",
                "redis_ok": client is not None,
                "environment": cfg.environment,
                "agents": [{"name": n, "status": "ready"} for n in agents],
                "daily_tokens": token_usage,
            })

        # ── 8. invalidate_cache ──────────────────────────────────────────────
        elif name == "invalidate_cache":
            from core.cache import get_client, invalidate_pattern
            from config.settings import get_config
            agent = arguments.get("agent", "all")
            client = get_client(get_config())
            if agent == "all":
                patterns = ["information_agent:*", "knowledge_agent:*", "metadata_agent:*"]
            else:
                patterns = [f"{agent}:*"]
            total = sum(invalidate_pattern(client, p) for p in patterns)
            return _ok({"invalidated": total, "patterns": patterns})

        # ── 9. approve_action ────────────────────────────────────────────────
        elif name == "approve_action":
            from core.base_agent import AgentRequest
            thread_id = arguments["thread_id"]
            query = arguments["query"]
            result = _full_graph(
                query=query,
                thread_id=thread_id,
            )
            return _ok({**result, "note": "Re-ran with approved=True not yet wired; use /query endpoint with approved:true"})

        # ── 10. ingest_document_url ──────────────────────────────────────────
        elif name == "ingest_document_url":
            import tempfile, httpx, os as _os
            url = arguments["url"]
            product = arguments.get("product", "general")
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as c:
                resp = await c.get(url)
                resp.raise_for_status()
            suffix = _os.path.splitext(url.split("?")[0])[-1] or ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
            try:
                from ingestion.loaders import load_document
                from ingestion.chunker import chunk_documents
                from ingestion.embedder import embed_chunks
                from ingestion.store import upsert_chunks
                docs = load_document(tmp_path)
                for d in docs:
                    d.metadata.setdefault("product", product)
                chunks = chunk_documents(docs)
                embeddings = embed_chunks(chunks)
                count = upsert_chunks(chunks, embeddings)
                return _ok({"status": "ingested", "chunks": count, "source_url": url})
            finally:
                _os.unlink(tmp_path)

        else:
            return _err(f"Unknown tool: {name}")

    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return _err(str(exc))


# ── Transport ─────────────────────────────────────────────────────────────────

async def _run_stdio():
    from mcp.server.stdio import stdio_server
    init_opts = InitializationOptions(
        server_name="data-governance-copilot",
        server_version="1.0.0",
        capabilities=server.get_capabilities(
            notification_options=None,
            experimental_capabilities={},
        ),
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_opts)


async def _run_sse(host: str = "0.0.0.0", port: int = 8002):
    """SSE transport — HTTP server that speaks MCP over Server-Sent Events."""
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    import uvicorn

    sse = SseServerTransport("/messages")

    async def handle_sse(scope, receive, send):
        async with sse.connect_sse(scope, receive, send) as streams:
            init_opts = InitializationOptions(
                server_name="data-governance-copilot",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            )
            await server.run(streams[0], streams[1], init_opts)

    starlette_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages", app=sse.handle_post_message),
        ]
    )
    logger.info("MCP SSE server starting on %s:%s", host, port)
    config = uvicorn.Config(starlette_app, host=host, port=port, log_level="info")
    uvicorn_server = uvicorn.Server(config)
    await uvicorn_server.serve()


if __name__ == "__main__":
    import asyncio

    transport = os.getenv("TRANSPORT", "stdio").lower()
    if transport == "sse":
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "8002"))
        asyncio.run(_run_sse(host=host, port=port))
    else:
        asyncio.run(_run_stdio())
