# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ ./src/
COPY dags/ ./dags/
COPY scripts/ ./scripts/

# Ensure any legacy top-level imports (e.g. "from api.middleware") are
# rewritten to the current package layout ("from src.api.middleware"). This
# prevents stale/legacy import paths from causing runtime ModuleNotFoundError
# when images are built from caches or older contexts.
RUN find /app/src -type f -name "*.py" -exec sed -i \
    -e 's/^from api\\./from src.api./g' \
    -e 's/^import api\\./import src.api./g' {} + || true

RUN mkdir -p /app/data /app/docs

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONPATH=/app:/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000 8501 8002

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
