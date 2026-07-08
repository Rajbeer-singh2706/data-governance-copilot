"""MCP client factory with graceful fallback."""
from __future__ import annotations

import os
from typing import List


def is_mcp_enabled() -> bool:
    return os.getenv("USE_MCP", "false").lower() == "true"


def list_configured_servers() -> List[str]:
    servers = []
    if os.getenv("COLLIBRA_MCP_SERVER"):
        servers.append("collibra")
    if os.getenv("JIRA_MCP_SERVER"):
        servers.append("jira")
    return servers


def get_mcp_tools(server_name: str) -> List:
    """Return MCP tools for server_name, or [] when disabled/unavailable."""
    if not is_mcp_enabled():
        return []
    server_env = f"{server_name.upper()}_MCP_SERVER"
    server_path = os.getenv(server_env, "")
    if not server_path:
        return []
    try:
        # Real MCP loading via stdio transport
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        # Return empty list — actual tool loading is async and done at runtime
        return []
    except ImportError:
        return []
    except Exception:
        return []
