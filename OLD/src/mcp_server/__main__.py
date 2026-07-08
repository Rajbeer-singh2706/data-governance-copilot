"""Allow `python -m src.mcp_server` to start the server."""
from src.mcp_server.server import _run_stdio, _run_sse
import asyncio, os

transport = os.getenv("TRANSPORT", "stdio").lower()
if transport == "sse":
    asyncio.run(_run_sse(os.getenv("MCP_HOST", "0.0.0.0"), int(os.getenv("MCP_PORT", "8002"))))
else:
    asyncio.run(_run_stdio())
