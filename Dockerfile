# ═══════════════════════════════════════════════════════════════════════════
# Data Governance Copilot — Dockerfile
#
# Python 3.12-slim  (3.13 dropped: hiredis + some LangChain C-extensions
#                    have known build friction on 3.13 as of May 2026)
#
# Two-stage build:
#   builder  — installs uv + all deps into an isolated venv
#   runtime  — copies only the venv + source; no build tools in final image
#
# Layer-cache strategy:
#   requirements.txt / pyproject.toml copied BEFORE src/ so a code-only
#   change does NOT re-run the expensive pip install step.
# ═══════════════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# System build deps needed by hiredis (C ext) and psycopg2-binary (Day 18)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv — significantly faster than pip for large dependency trees
RUN pip install --no-cache-dir uv==0.7.8

# ── Dependency layer (cached unless requirements change) ──────────────────
COPY requirements.txt pyproject.toml ./
RUN uv venv .venv \
    && .venv/bin/pip install --no-cache-dir --upgrade pip \
    && uv pip install --no-cache -r requirements.txt


# ── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Only the runtime system lib needed by hiredis / redis at run time
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built venv from builder — no compiler needed here
COPY --from=builder /app/.venv ./.venv

# Copy application source
COPY src/ ./src/
COPY pyproject.toml ./

# Create writable runtime directories (volumes will mount over these)
RUN mkdir -p /app/data /app/logs

# Non-root user for security
RUN useradd -m -u 1000 copilot \
    && chown -R copilot:copilot /app
USER copilot

# ── Environment ──────────────────────────────────────────────────────────────
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
# Disable stdout buffering so logs appear immediately in docker logs
ENV PYTHONUNBUFFERED=1
# Keeps Python from writing .pyc files into the image layer
ENV PYTHONDONTWRITEBYTECODE=1

# Streamlit — headless, no telemetry
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

# ── Health check ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# ── Default command: Streamlit UI ────────────────────────────────────────────
# Override in compose.yml to run FastAPI instead:
#   command: uvicorn src.api.app:app --host 0.0.0.0 --port 8000
CMD ["streamlit", "run", "src/ui/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]