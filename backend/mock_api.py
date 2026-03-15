"""
DEVTrails — Minimal Mock API
A thin vertical slice proving the documented architecture is runnable.
This is NOT a production backend — it is a hackathon demo scaffold.

Run:
    uvicorn backend.mock_api:app --reload --port 8000

Or from the backend/ directory:
    uvicorn mock_api:app --reload --port 8000
"""

import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="DEVTrails Mock API",
    description="Minimal runnable slice of the DEVTrails parametric insurance platform.",
    version="0.1.0-scaffold",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Trigger library — matches the 15-trigger table in root README.md
# ---------------------------------------------------------------------------
TRIGGER_LIBRARY = [
    {"id": "T1",  "name": "Rain Watch",             "threshold": "24h rain >= 48 mm",             "tier": "Early Warning",     "anchoring": "public", "source": "IMD"},
    {"id": "T2",  "name": "Heavy Rain Claim",        "threshold": "24h rain >= 64.5 mm",           "tier": "Claim Trigger",     "anchoring": "public", "source": "IMD"},
    {"id": "T3",  "name": "Extreme Rain Escalation",  "threshold": "24h rain >= 115.6 mm",          "tier": "Severe Escalation", "anchoring": "public", "source": "IMD"},
    {"id": "T4",  "name": "Waterlogging Mobility",    "threshold": "accessibility_score <= 0.40",    "tier": "Claim Trigger",     "anchoring": "operational"},
    {"id": "T5",  "name": "AQI Caution",              "threshold": "AQI 201-300",                   "tier": "Early Warning",     "anchoring": "public", "source": "CPCB"},
    {"id": "T6",  "name": "AQI Severe Exposure",      "threshold": "AQI >= 301 + active shift",     "tier": "Claim Trigger",     "anchoring": "public", "source": "CPCB"},
    {"id": "T7",  "name": "Heat Wave",                "threshold": "temp >= 45C or IMD heat-wave",  "tier": "Claim Trigger",     "anchoring": "public", "source": "IMD/NDMA"},
    {"id": "T8",  "name": "Severe Heat",              "threshold": "temp >= 47C",                   "tier": "Severe Escalation", "anchoring": "public", "source": "IMD/NDMA"},
    {"id": "T9",  "name": "Heat Persistence",         "threshold": "2 consecutive hot-risk days",   "tier": "Early Warning",     "anchoring": "public", "source": "IMD/NDMA"},
    {"id": "T10", "name": "Local Zone Closure",        "threshold": "closure_flag = 1",              "tier": "Claim Trigger",     "anchoring": "operational"},
    {"id": "T11", "name": "Curfew / Strike Closure",   "threshold": "restriction >= 4h",             "tier": "Claim Trigger",     "anchoring": "operational"},
    {"id": "T12", "name": "Traffic Collapse",          "threshold": "travel delay >= 40%",           "tier": "Early Warning",     "anchoring": "operational"},
    {"id": "T13", "name": "Platform Outage",           "threshold": "outage >= 30 min",              "tier": "Claim Trigger",     "anchoring": "operational"},
    {"id": "T14", "name": "Demand Collapse",           "threshold": "orders drop >= 35% vs baseline","tier": "Early Warning",     "anchoring": "operational"},
    {"id": "T15", "name": "Composite Disruption",      "threshold": "composite score >= 0.70",       "tier": "Severe Escalation", "anchoring": "operational"},
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
def health_check():
    """Basic health and version check."""
    return {
        "status": "ok",
        "service": "devtrails-mock-api",
        "version": "0.1.0-scaffold",
        "phase": "documentation-first — this is a demo scaffold, not a production backend",
    }


@app.get("/triggers/library", tags=["Triggers"])
def get_trigger_library():
    """Return the full 15-trigger library as documented in the root README."""
    return {
        "count": len(TRIGGER_LIBRARY),
        "triggers": TRIGGER_LIBRARY,
        "note": "Thresholds with anchoring='public' are sourced from IMD/CPCB/NDMA. "
                "Thresholds with anchoring='operational' are internal product decisions.",
    }


@app.get("/claims/sample", tags=["Claims"])
def get_sample_claim():
    """Return the sample claim JSON from claim-engine/examples/."""
    sample_path = Path(__file__).resolve().parent.parent / "claim-engine" / "examples" / "sample_claim.json"
    if sample_path.exists():
        return json.loads(sample_path.read_text(encoding="utf-8"))
    return {
        "error": "sample_claim.json not found",
        "expected_path": str(sample_path),
    }
