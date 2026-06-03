.PHONY: help install test lint docker-build up down mcp-stdio mcp-sse init-neon clean

help:
	@echo "Data Governance Copilot — make targets"
	@echo ""
	@echo "  install       Install dependencies with uv"
	@echo "  test          Run full test suite"
	@echo "  lint          Run ruff linter"
	@echo "  docker-build  Build all Docker images"
	@echo "  up            Start all services (Neon-backed)"
	@echo "  down          Stop all services"
	@echo "  mcp-stdio     Start MCP server (stdio, for Claude Desktop)"
	@echo "  mcp-sse       Start MCP server (SSE, for remote clients)"
	@echo "  init-neon     Run Neon schema initialisation SQL"

install:
	uv pip install -r requirements.txt

test:
	ENABLE_MOCK=true REDIS_ENABLED=false \
	  uv run pytest tests/ --cov=src --cov-fail-under=80 -v

lint:
	ruff check src/ tests/

docker-build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

## Start MCP in stdio mode
# Or copy the config from claude_desktop_config_example.json
# into ~/Library/Application Support/Claude/claude_desktop_config.json
mcp-stdio:
	PYTHONPATH=src TRANSPORT=stdio \
	  uv run python -m src.mcp_server.server

mcp-sse:
	PYTHONPATH=src TRANSPORT=sse MCP_PORT=8002 \
	  uv run python -m src.mcp_server.server

# 3. Run the init SQL (once)
init-neon:
	uv run python -c "import os,sys,subprocess; url=os.getenv('DATABASE_URL'); (sys.stderr.write('ERROR: DATABASE_URL not set. Export your Neon connection string first.\n') or sys.exit(1)) if not url else subprocess.check_call(['psql', url, '-f', 'scripts/init_neon.sql'])"

ui:
	PYTHONPATH=src uv run streamlit run src/ui/app.py

api:
	PYTHONPATH=src uv run uvicorn src.api.app:app --reload --port 8000

# Cleanup
clean: ## Clean up everything
	docker compose down -v
	docker system prune -f