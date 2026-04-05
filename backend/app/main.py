"""
Covara One — FastAPI Application Entry Point

This is the main backend API for the Covara One parametric insurance platform.
It is an early scaffold — not a production backend.

Run:
    uvicorn backend.app.main:app --reload --port 8000

Docs:
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""

import asyncio
from contextlib import asynccontextmanager
from contextlib import suppress
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.app.config import settings
from backend.app.dependencies import require_insurer_admin
from backend.app.rate_limit import limiter
from backend.app.routers import (
    auth,
    workers,
    zones,
    claims,
    events,
    triggers,
    policies,
    analytics,
    ingest,
    kyc,
    mock_data,
    rewards,
)
from backend.app.seed import seed_all


async def _outbox_relay_loop() -> None:
    """Continuously relay pending outbox events in small batches."""
    from backend.app.services.event_bus.outbox import relay_pending_outbox_events
    from backend.app.supabase_client import get_supabase_admin

    interval_seconds = max(1, settings.event_outbox_relay_interval_seconds)
    batch_size = max(1, settings.event_outbox_relay_batch_size)

    while True:
        try:
            sb = get_supabase_admin()
            result = await relay_pending_outbox_events(sb, batch_size=batch_size)
            if (
                result.get("processed", 0)
                or result.get("failed", 0)
                or result.get("dead_lettered", 0)
            ):
                print(
                    "INFO: outbox relay batch"
                    f" processed={result.get('processed', 0)}"
                    f" failed={result.get('failed', 0)}"
                    f" dead_lettered={result.get('dead_lettered', 0)}"
                )
        except Exception as e:
            print(f"WARN: outbox relay loop error: {e}")

        await asyncio.sleep(interval_seconds)

# ── Lifespan (startup validation) ─────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate config on startup."""
    missing = settings.validate()
    if missing:
        print(f"WARN:  Missing config: {', '.join(missing)}")
        print("   The API will start but Supabase calls will fail.")
        print("   Create a .env file — see .env.example")
    else:
        print(f"OK: Config loaded. Supabase: {settings.supabase_url}")
        print(f"   Environment: {settings.app_env}")
        
    try:
        from fastapi_cache import FastAPICache
        from fastapi_cache.backends.redis import RedisBackend
        from redis import asyncio as aioredis
        import os
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        redis = aioredis.from_url(redis_url, encoding="utf8", decode_responses=False)
        FastAPICache.init(RedisBackend(redis), prefix="covara-cache")
        print("OK: Redis cache initialized")
    except Exception as e:
        print(f"WARN: Redis cache initialization failed: {e}")

    relay_task = None
    kafka_consumer_task = None
    if settings.event_outbox_relay_enabled:
        relay_task = asyncio.create_task(
            _outbox_relay_loop(),
            name="covara-outbox-relay",
        )
        print(
            "OK: Outbox relay worker started "
            f"(interval={settings.event_outbox_relay_interval_seconds}s, "
            f"batch={settings.event_outbox_relay_batch_size})"
        )
    else:
        print("INFO: Outbox relay worker disabled by config")

    if (
        (settings.event_bus_backend or "").strip().lower() == "kafka"
        and settings.event_consumer_enabled
    ):
        from backend.app.services.event_bus.kafka_consumer import (
            run_kafka_consumer_loop,
        )

        kafka_consumer_task = asyncio.create_task(
            run_kafka_consumer_loop(),
            name="covara-kafka-consumer",
        )
        print(
            "OK: Kafka consumer worker started "
            f"(group={settings.event_consumer_group_id}, "
            f"max_records={settings.event_consumer_max_records})"
        )
    elif (settings.event_bus_backend or "").strip().lower() == "kafka":
        print("INFO: Kafka consumer worker disabled by config")

    try:
        yield
    finally:
        if kafka_consumer_task:
            kafka_consumer_task.cancel()
            with suppress(asyncio.CancelledError):
                await kafka_consumer_task

        if relay_task:
            relay_task.cancel()
            with suppress(asyncio.CancelledError):
                await relay_task


# ── Rate Limiter ──────────────────────────────────────────────────
# ── App Setup ─────────────────────────────────────────────────────

app = FastAPI(
    title="Covara One API",
    description=(
        "Backend API for the Covara One parametric income-protection platform. "
        "Includes zero-touch auto-claims, live trigger ingestion (OpenWeather/TomTom/CPCB), "
        "5-layer fraud detection, IRDAI-compliant KYC (Sandbox.co.in), "
        "and Twilio OTP + WhatsApp notifications."
    ),
    version="0.5.0",
    lifespan=lifespan,
)

# Attach rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS (Explicit methods and headers — no wildcards) ────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Device-Context",
        "X-Device-Context-Signature",
        "X-Device-Context-Timestamp",
        "X-Device-Context-Key-Id",
        "X-Request-ID",
    ],
)


# ── OWASP Security Headers Middleware ─────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Inject OWASP-recommended security headers on every response."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self), camera=(self)"
    if settings.app_env == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
    return response


# ── Register Routers ──────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(workers.router)
app.include_router(zones.router)
app.include_router(claims.router)
app.include_router(events.router)
app.include_router(triggers.router)
app.include_router(policies.router)
app.include_router(analytics.router)
app.include_router(ingest.router)
app.include_router(kyc.router)
app.include_router(mock_data.router)
app.include_router(rewards.router)


# ── Root & Health ─────────────────────────────────────────────────


@app.get("/", tags=["System"])
def root():
    """API root — returns basic info."""
    return {
        "service": "covara-one-api",
        "version": "0.5.0",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health", tags=["System"])
def health_check():
    """Health check with config status."""
    missing = settings.validate()
    return {
        "status": "ok" if not missing else "degraded",
        "service": "covara-one-api",
        "version": "0.5.0",
        "config_ok": not missing,
        "missing_config": missing if missing else None,
    }


# ── Admin Seed Endpoint ──────────────────────────────────────────


@app.post(
    "/admin/seed",
    tags=["Admin"],
    dependencies=[Depends(require_insurer_admin)],
)
async def run_seed():
    """Run the seed data loader. Insurer/admin only.

    Seeds zones and trigger events into the database.
    Safe to run multiple times — uses upsert for zones.
    """
    result = seed_all()
    return {"status": "seeded", **result}


