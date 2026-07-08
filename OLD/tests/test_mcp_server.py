"""Tests for MCP server tool handlers (no actual MCP transport needed)."""
from __future__ import annotations

import json
import os
import sys
import pytest

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("ENABLE_MOCK", "true")
os.environ.setdefault("REDIS_ENABLED", "false")


def _text(result) -> str:
    return result[0].text if result else ""


# ── get_system_status ─────────────────────────────────────────────────────────
def test_get_system_status():
    from mcp_server.server import call_tool
    import asyncio
    result = asyncio.run(call_tool("get_system_status", {}))
    data = json.loads(_text(result))
    assert data["status"] == "ok"
    assert "agents" in data
    assert len(data["agents"]) == 5


# ── invalidate_cache ──────────────────────────────────────────────────────────
def test_invalidate_cache_all():
    from mcp_server.server import call_tool
    import asyncio
    result = asyncio.run(call_tool("invalidate_cache", {"agent": "all"}))
    data = json.loads(_text(result))
    assert "invalidated" in data
    assert len(data["patterns"]) == 3


def test_invalidate_cache_specific():
    from mcp_server.server import call_tool
    import asyncio
    result = asyncio.run(call_tool("invalidate_cache", {"agent": "knowledge_agent"}))
    data = json.loads(_text(result))
    assert data["patterns"] == ["knowledge_agent:*"]


# ── query_metrics ─────────────────────────────────────────────────────────────
def test_query_metrics():
    from mcp_server.server import call_tool
    import asyncio
    result = asyncio.run(call_tool("query_metrics", {"query": "What is the retention rate?"}))
    data = json.loads(_text(result))
    assert "success" in data


# ── manage_rules ─────────────────────────────────────────────────────────────
def test_manage_rules():
    from mcp_server.server import call_tool
    import asyncio
    result = asyncio.run(call_tool("manage_rules", {"query": "list all rules"}))
    data = json.loads(_text(result))
    assert "success" in data


# ── unknown tool ──────────────────────────────────────────────────────────────
def test_unknown_tool():
    from mcp_server.server import call_tool
    import asyncio
    result = asyncio.run(call_tool("does_not_exist", {}))
    data = json.loads(_text(result))
    assert "error" in data


# ── tool list ─────────────────────────────────────────────────────────────────
def test_list_tools_count():
    from mcp_server.server import TOOLS
    assert len(TOOLS) == 10
    names = {t.name for t in TOOLS}
    assert "governance_query" in names
    assert "get_system_status" in names
    assert "ingest_document_url" in names
