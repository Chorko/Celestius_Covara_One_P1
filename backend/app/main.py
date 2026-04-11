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
import logging
import time
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
    analytics,
    auth,
    claims,
    events,
    ingest,
    kyc,
    mock_data,
    ops,
    payouts,
    policies,
    rewards,
    triggers,
    workers,
    zones,
)
from backend.app.seed import seed_all
from backend.app.services.observability import (
    bind_request_id,
    increment_counter,
    observe_timing_ms,
    resolve_request_id,
    set_gauge,
    structured_log,
    unbind_request_id,
)


def _configure_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


_configure_logging()
logger = logging.getLogger("covara.app")


async def _outbox_relay_loop(app: FastAPI) -> None:
    """Continuously relay pending outbox events in small batches."""
    from backend.app.services.event_bus.outbox import relay_pending_outbox_events
    from backend.app.supabase_client import get_supabase_admin

    interval_seconds = max(1, settings.event_outbox_relay_interval_seconds)
    batch_size = max(1, settings.event_outbox_relay_batch_size)

    while True:
        try:
            sb = get_supabase_admin()
            result = await relay_pending_outbox_events(sb, batch_size=batch_size)
            app.state.outbox_last_batch = result
            app.state.outbox_last_batch_at = time.time()
            set_gauge("event_outbox_pending", result.get("fetched", 0))
            set_gauge("event_outbox_failed", result.get("failed", 0))
            set_gauge("event_outbox_dead_letter_batch", result.get("dead_lettered", 0))
            if (
                result.get("processed", 0)
                or result.get("failed", 0)
                or result.get("dead_lettered", 0)
            ):
                structured_log(
                    logger,
                    logging.INFO,
                    "outbox.relay.batch",
                    fetched=result.get("fetched", 0),
                    processed=result.get("processed", 0),
                    failed=result.get("failed", 0),
                    dead_lettered=result.get("dead_lettered", 0),
                )
        except Exception as e:
            increment_counter("event_outbox_relay_errors_total")
            structured_log(
                logger,
                logging.WARNING,
                "outbox.relay.error",
                error=str(e),
            )

        await asyncio.sleep(interval_seconds)

# ── Lifespan (startup validation) ─────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate config on startup."""
    app.state.redis_cache_ready = False
    app.state.outbox_worker_running = False
    app.state.kafka_consumer_running = False
    app.state.outbox_last_batch = None
    app.state.outbox_last_batch_at = None

    missing = settings.validate()
    if missing:
        strict_mode = settings.is_strict_env_validation_enabled()
        level = logging.ERROR if strict_mode else logging.WARNING
        structured_log(
            logger,
            level,
            "startup.config.missing",
            strict_env_validation=strict_mode,
            missing_config=missing,
        )
        if strict_mode:
            raise RuntimeError(
                "Missing required configuration in strict env validation mode: "
                + ", ".join(missing)
            )
    else:
        structured_log(
            logger,
            logging.INFO,
            "startup.config.loaded",
            supabase_url=settings.supabase_url,
            app_env=settings.app_env,
        )
        
    try:
        from fastapi_cache import FastAPICache
        from fastapi_cache.backends.redis import RedisBackend
        from redis import asyncio as aioredis
        import os
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        redis = aioredis.from_url(redis_url, encoding="utf8", decode_responses=False)
        FastAPICache.init(RedisBackend(redis), prefix="covara-cache")
        app.state.redis_cache_ready = True
        structured_log(
            logger,
            logging.INFO,
            "startup.redis.ready",
            redis_url=redis_url,
        )
    except Exception as e:
        app.state.redis_cache_ready = False
        increment_counter("startup_redis_init_failures_total")
        structured_log(
            logger,
            logging.WARNING,
            "startup.redis.failed",
            error=str(e),
        )

    relay_task = None
    kafka_consumer_task = None
    if settings.event_outbox_relay_enabled:
        relay_task = asyncio.create_task(
            _outbox_relay_loop(app),
            name="covara-outbox-relay",
        )
        app.state.outbox_worker_running = True
        structured_log(
            logger,
            logging.INFO,
            "startup.outbox_worker.started",
            interval_seconds=settings.event_outbox_relay_interval_seconds,
            batch_size=settings.event_outbox_relay_batch_size,
        )
    else:
        app.state.outbox_worker_running = False
        structured_log(
            logger,
            logging.INFO,
            "startup.outbox_worker.disabled",
        )

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
        app.state.kafka_consumer_running = True
        structured_log(
            logger,
            logging.INFO,
            "startup.kafka_consumer.started",
            group_id=settings.event_consumer_group_id,
            max_records=settings.event_consumer_max_records,
        )
    elif (settings.event_bus_backend or "").strip().lower() == "kafka":
        app.state.kafka_consumer_running = False
        structured_log(
            logger,
            logging.INFO,
            "startup.kafka_consumer.disabled",
        )

    try:
        yield
    finally:
        if kafka_consumer_task:
            kafka_consumer_task.cancel()
            with suppress(asyncio.CancelledError):
                await kafka_consumer_task
            app.state.kafka_consumer_running = False

        if relay_task:
            relay_task.cancel()
            with suppress(asyncio.CancelledError):
                await relay_task
            app.state.outbox_worker_running = False


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
        "X-Correlation-ID",
    ],
)


@app.middleware("http")
async def add_request_id_and_metrics(request: Request, call_next):
    request_id = resolve_request_id(
        request.headers.get("X-Request-ID"),
        request.headers.get("X-Correlation-ID"),
    )

    request.state.request_id = request_id
    request.state.correlation_id = request_id
    token = bind_request_id(request_id)

    method = request.method
    path = request.url.path
    status_code = 500
    started_at = time.perf_counter()

    increment_counter(
        "http_requests_total",
        labels={"method": method, "path": path},
    )

    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = request_id

        if status_code >= 500:
            increment_counter(
                "http_request_failures_total",
                labels={
                    "method": method,
                    "path": path,
                    "status_family": "5xx",
                },
            )

        return response
    except Exception as e:
        increment_counter(
            "http_request_failures_total",
            labels={
                "method": method,
                "path": path,
                "status_family": "5xx",
            },
        )
        structured_log(
            logger,
            logging.ERROR,
            "http.request.unhandled_exception",
            request_id=request_id,
            method=method,
            path=path,
            error_type=type(e).__name__,
            error=str(e),
        )
        raise
    finally:
        duration_ms = (time.perf_counter() - started_at) * 1000
        observe_timing_ms(
            "http_request_latency_ms",
            duration_ms,
            labels={
                "method": method,
                "path": path,
                "status_family": f"{max(1, status_code // 100)}xx",
            },
        )
        unbind_request_id(token)


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
app.include_router(ops.router)
app.include_router(payouts.router)
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
    strict_mode = settings.is_strict_env_validation_enabled()
    return {
        "status": "ok" if not missing else "degraded",
        "service": "covara-one-api",
        "version": "0.5.0",
        "strict_env_validation": strict_mode,
        "config_ok": not missing,
        "missing_config": missing if missing else None,
    }


@app.get("/ready", tags=["System"])
def readiness_check(request: Request):
    """Readiness signal with key runtime component states."""
    missing = settings.validate()
    strict_mode = settings.is_strict_env_validation_enabled()
    kafka_required = (
        (settings.event_bus_backend or "").strip().lower() == "kafka"
        and settings.event_consumer_enabled
    )

    checks = {
        "config_ok": not missing,
        "redis_cache_ready": bool(getattr(request.app.state, "redis_cache_ready", False)),
        "outbox_worker_running": bool(getattr(request.app.state, "outbox_worker_running", False))
        if settings.event_outbox_relay_enabled
        else True,
        "kafka_consumer_running": bool(getattr(request.app.state, "kafka_consumer_running", False))
        if kafka_required
        else True,
    }

    ready = all(checks.values())
    if not ready:
        increment_counter("readiness_degraded_total")

    return {
        "status": "ready" if ready else "degraded",
        "strict_env_validation": strict_mode,
        "checks": checks,
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


