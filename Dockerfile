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
    uv pip install --no-cache-dir -r requirements.txt

    
# Start the Streamlit application
CMD ["streamlit", "run", "src/ui/app.py", 
     "--server.port=8501", 
     "--server.address=0.0.0.0"]