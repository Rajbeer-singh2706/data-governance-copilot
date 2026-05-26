# MCP client factory — Collibra + Jira tool loading with graceful fallback

"""
src/core/mcp_client.py  — NEW file (Day 18)
MCP client factory with graceful fallback.
"""
import logging, os
from typing import List
logger = logging.getLogger(__name__)

_USE_MCP = os.getenv("USE_MCP","false").lower()=="true"
_SERVER_ENV = {"collibra":"COLLIBRA_MCP_SERVER","jira":"JIRA_MCP_SERVER"}


def get_mcp_tools(server_name: str) -> List:
    """
    Load LangChain tools from an MCP server.
    Returns [] when disabled, not configured, or packages missing.

    Agents call this and check the return value:
      tools = get_mcp_tools("collibra")
      if tools:
          # real Collibra API via MCP
      else:
          # fall back to existing mock / REST implementation
    """
    if not _USE_MCP:
        return []

    env_key    = _SERVER_ENV.get(server_name)
    server_cmd = os.getenv(env_key,"") if env_key else ""
    if not server_cmd:
        logger.warning("[mcp] No server configured for: %s", server_name)
        return []

    try:
        return _load_tools(server_cmd, server_name)
    except ImportError:
        logger.warning("[mcp] missing langchain-mcp-adapters / mcp packages")
        return []
    except Exception as exc:
        logger.warning("[mcp] %s connection failed: %s", server_name, exc)
        return []


def is_mcp_enabled() -> bool:
    return _USE_MCP

def list_configured_servers() -> List[str]:
    return [n for n,k in _SERVER_ENV.items() if os.getenv(k,"")]


def _load_tools(server_cmd: str, server_name: str) -> List:
    """Start MCP server subprocess and load its tools as LangChain BaseTool objects."""
    import asyncio
    from langchain_mcp_adapters.tools import load_mcp_tools
    from mcp                          import ClientSession, StdioServerParameters
    from mcp.client.stdio             import stdio_client

    parts  = server_cmd.split()
    params = StdioServerParameters(command=parts[0], args=parts[1:], env=None)

    async def _async_load():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await load_mcp_tools(session)
                logger.info("[mcp] %s: loaded %d tool(s): %s",
                            server_name, len(tools), [t.name for t in tools])
                return tools

    return asyncio.run(_async_load())