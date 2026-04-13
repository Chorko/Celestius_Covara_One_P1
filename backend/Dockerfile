# ── Backend (FastAPI + Python 3.12) ───────────────────────────────────
# 3-stage build: build tools only in deps stage, production image is clean.

FROM python:3.12-slim AS base

# Prevents Python from writing .pyc files and enables unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5 \
    PIP_REQUIRE_HASHES=0

WORKDIR /app

# ── Stage 1: Install dependencies (with build tools) ─────────────────
FROM base AS deps

# System dependencies for building psycopg2 and Pillow from source
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc libpq-dev libjpeg62-turbo-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.runtime.txt .
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir --prefer-binary -r requirements.runtime.txt

# ── Stage 2: Production image (clean — no gcc, no build tools) ───────
# Starts from base (slim), copies only the installed Python packages
# and minimal runtime libraries. This cuts ~200MB from the final image.
FROM base AS production

# Runtime-only system libraries (no compilers, no -dev headers)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 libjpeg62-turbo zlib1g && \
    rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from the deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application code
COPY backend/ ./backend/
COPY .env.example ./.env.example

# Run container as non-root user.
RUN addgroup --system --gid 1001 covara && \
    adduser --system --uid 1001 --ingroup covara covara && \
    chown -R covara:covara /app

USER covara

# Health check — hits the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/ready', timeout=3)"

EXPOSE ${PORT:-8000}

# Run with uvicorn — use PORT env var (required by Render) and WEB_CONCURRENCY for workers
CMD uvicorn backend.app.main:app \
     --host 0.0.0.0 \
     --port ${PORT:-8000} \
     --workers ${WEB_CONCURRENCY:-1} \
     --log-level info
