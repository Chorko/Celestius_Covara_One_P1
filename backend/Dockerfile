# ── Backend (FastAPI + Python 3.12) ───────────────────────────────────
# Multi-stage build: slim image, no dev dependencies in production.

FROM python:3.12-slim AS base

# Prevents Python from writing .pyc files and enables unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5 \
    PIP_REQUIRE_HASHES=0

WORKDIR /app

# ── Stage 1: Install dependencies ────────────────────────────────────
FROM base AS deps

# System dependencies for psycopg2 and Pillow
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc libpq-dev libjpeg62-turbo-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.runtime.txt .
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir --prefer-binary -r requirements.runtime.txt

# ── Stage 2: Production image ────────────────────────────────────────
# Start from deps to avoid a second apt update/install pass during build.
FROM deps AS production

# Copy application code
COPY backend/ ./backend/
COPY .env.example ./.env.example

# Health check — hits the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"

EXPOSE 8000

# Run with uvicorn — 4 workers for production
CMD ["uvicorn", "backend.app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--log-level", "info"]
