# ═══════════════════════════════════════════════════════════════════════════
# Data Governance Copilot — Dockerfile
#
# Python 3.12-slim  (3.13 skipped: hiredis + psycopg2-binary C-ext friction)
#
# uv installation: COPY --from=ghcr.io/astral-sh/uv (official pattern)
#   WHY NOT pip install uv:
#     • pip install in slim images places the binary in /usr/local/bin but
#       RUN layers in non-interactive shells sometimes don't see it (exit 127)
#     • COPY --from copies a pre-built static binary — no PATH issues, no pip,
#       no network call, faster build
#
# Two-stage build:
#   builder  — installs deps into /app/.venv (has gcc for C extensions)
#   runtime  — copies only .venv + src (no build tools, smaller image)
#
# Layer-cache order:
#   requirements.txt copied BEFORE src/ → code changes don't re-run pip
# ═══════════════════════════════════════════════════════════════════════════

# ── uv binary (official image — static binary, no PATH issues) ─────────────
FROM ghcr.io/astral-sh/uv:0.9.9 AS uv-bin


# ── Stage 1: Builder ────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Pull uv binary from the official uv image — avoids 'pip install uv' + exit 127
COPY --from=uv-bin /uv /usr/local/bin/uv

# System build deps:
#   gcc        — needed by hiredis (C extension)
#   libpq-dev  — needed by psycopg2-binary (Day 18 pgvector)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Dependency layer (cached unless requirements.txt changes) ─────────────
COPY requirements.txt pyproject.toml ./

RUN uv venv .venv \
    && uv pip install --no-cache -r requirements.txt


# ── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Only the runtime .so needed by hiredis/psycopg2 at run-time (not the -dev headers)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built venv — no compiler, no uv, no pip in the final image
COPY --from=builder /app/.venv ./.venv

# Copy application source
COPY src/ ./src/
COPY pyproject.toml ./

# Create writable directories that compose volumes will mount into
RUN mkdir -p /app/data /app/logs

# Non-root user — good security practice
RUN useradd -m -u 1000 copilot \
    && chown -R copilot:copilot /app
USER copilot

# ── Environment ──────────────────────────────────────────────────────────────
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Streamlit
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

# ── Health check ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# ── Default: Streamlit UI ─────────────────────────────────────────────────────
# Override in compose.yml for FastAPI:
#   command: uvicorn src.api.app:app --host 0.0.0.0 --port 8000
CMD ["streamlit", "run", "src/ui/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]