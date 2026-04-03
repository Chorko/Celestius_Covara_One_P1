# ── Backend (FastAPI + Python 3.12) ───────────────────────────────────
# Multi-stage build: slim image, no dev dependencies in production.

FROM python:3.12-slim AS base

# Prevents Python from writing .pyc files and enables unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── Stage 1: Install dependencies ────────────────────────────────────
FROM base AS deps

# System dependencies for psycopg2 and Pillow
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc libpq-dev libjpeg62-turbo-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Production image ────────────────────────────────────────
FROM base AS production

# Runtime-only system libs (no compiler)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 libjpeg62-turbo zlib1g curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application code
COPY backend/ ./backend/
COPY .env.example ./.env.example

# Health check — hits the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Run with uvicorn — 4 workers for production
CMD ["uvicorn", "backend.app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--log-level", "info"]
