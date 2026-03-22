"""
DEVTrails — FastAPI Application Entry Point

This is the main backend API for the DEVTrails parametric insurance platform.
It is an early scaffold — not a production backend.

Run:
    uvicorn backend.app.main:app --reload --port 8000

Docs:
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.dependencies import require_insurer_admin
from backend.app.routers import (
    auth,
    workers,
    zones,
    claims,
    triggers,
    policies,
    analytics,
)
from backend.app.seed import seed_all

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
    yield


# ── App Setup ─────────────────────────────────────────────────────

app = FastAPI(
    title="DEVTrails API",
    description=(
        "Backend API for the DEVTrails parametric income-protection platform. "
        "Early scaffold — not a production backend."
    ),
    version="0.2.0-scaffold",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Register Routers ──────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(workers.router)
app.include_router(zones.router)
app.include_router(claims.router)
app.include_router(triggers.router)
app.include_router(policies.router)
app.include_router(analytics.router)


# ── Root & Health ─────────────────────────────────────────────────


@app.get("/", tags=["System"])
def root():
    """API root — returns basic info."""
    return {
        "service": "devtrails-api",
        "version": "0.2.0-scaffold",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health", tags=["System"])
def health_check():
    """Health check with config status."""
    missing = settings.validate()
    return {
        "status": "ok" if not missing else "degraded",
        "service": "devtrails-api",
        "version": "0.2.0-scaffold",
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
