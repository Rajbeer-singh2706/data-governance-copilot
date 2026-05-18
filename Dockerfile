# ═══════════════════════════════════════════════
# Stage 1: Builder — installs all dependencies
# ═══════════════════════════════════════════════

FROM python:3.11-slim as builder

WORKDIR /app

# Install uv — fastest Python package installer
RUN pip install uv --no-cache-dir


# Copy dependency files FIRST (enables Docker layer caching)
# If these files don't change, Docker skips the install step
COPY requirements.txt .
COPY pyproject.toml .

RUN uv venv .venv && \
   . .venv/bin/activate && \
    uv pip install -r requirements.txt --no-cache

FROM python:3.11-slim AS runtime
WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY src/ ./src/
COPY pyproject.toml .
RUN useradd -m -u 1000 copilot && \
chown -R copilot:copilot /app
USER copilot

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1

ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=10s \
--start-period=60s --retries=3 \
CMD python -c "import urllib.request; \
urllib.request.urlopen('http://localhost:8501/_stcore/health')"

    
# Start the Streamlit application
CMD ["streamlit", "run", "src/ui/app.py",  "--server.port=8501", "--server.address=0.0.0.0"]