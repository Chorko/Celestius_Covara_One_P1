"""
Covara One — Triggers Router

Handles:
- GET /triggers/library (Static 15-trigger list)
- GET /triggers/live (Active triggers filtered by city/zone)
- GET /triggers/civic-news (NewsAPI civic disruption feed)
- POST /triggers/simulate (Admin mock injection)
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from backend.app.dependencies import require_insurer_admin
from backend.app.supabase_client import get_supabase_admin
from backend.app.services.trigger_engine import TRIGGER_LIBRARY, get_overlapping_triggers
from backend.app.services.news_ingest import fetch_civic_news

router = APIRouter(prefix="/triggers", tags=["Triggers"])


class SimulateTriggerRequest(BaseModel):
    city: str
    zone_id: str
    trigger_family: str
    trigger_code: str
    observed_value: float
    severity_band: str  # watch, claim, escalation
    started_at: str | None = None


@router.get("/library")
async def get_trigger_library():
    """Returns the static 15-trigger lookup library."""
    return {
        "triggers": list(TRIGGER_LIBRARY.values()),
        "count": len(TRIGGER_LIBRARY),
    }


@router.get("/overlap")
async def get_overlapping(
    zone_id: str,
    shift_start: str,
    shift_end: str,
):
    """
    Find all trigger events that temporally overlap with a worker's
    shift window in the given zone.  Uses the trigger-engine overlap
    logic (event started before shift ends AND event ended after shift
    starts or is still ongoing).
    """
    sb = get_supabase_admin()
    results = get_overlapping_triggers(sb, zone_id, shift_start, shift_end)
    return {"zone_id": zone_id, "overlapping_triggers": results, "count": len(results)}


from fastapi_cache.decorator import cache

@router.get("/live")
@cache(expire=300)
async def get_live_triggers(
    city: Optional[str] = None, zone_id: Optional[str] = None
):
    """
    Get currently active triggers. For demo, it fetches recent triggers without an end_date
    or ended in the future, or just the most recent triggers ordered by start_date.
    """
    sb = get_supabase_admin()

    query = sb.table("trigger_events").select("*, zones(zone_name)")
    if city:
        query = query.eq("city", city)
    if zone_id:
        query = query.eq("zone_id", zone_id)

    # For demo purposes, we fetch the 20 most recent triggers
    resp = query.order("started_at", desc=True).limit(20).execute()
    return {"active_triggers": resp.data}


@router.get("/civic-news")
@cache(expire=300)
async def get_civic_news(
    city: Optional[str] = Query(
        None,
        description="Optional city to scope civic disruption news (e.g. Mumbai)",
    )
):
    """Fetch civic disruption articles from configured news providers."""
    result = await fetch_civic_news(city=city)
    payload = result.get("data") if isinstance(result, dict) else {}

    return {
        "city": city,
        "provider": result.get("provider") if isinstance(result, dict) else None,
        "pool": result.get("pool") if isinstance(result, dict) else "news",
        "cached": bool(result.get("cached", False)) if isinstance(result, dict) else False,
        "total_results": int((payload or {}).get("total_results", 0)),
        "high_relevance_count": int((payload or {}).get("high_relevance_count", 0)),
        "articles": (payload or {}).get("articles", []),
        "warning": result.get("warning") if isinstance(result, dict) else None,
        "error": result.get("error") if isinstance(result, dict) else None,
    }


@router.post("/simulate", dependencies=[Depends(require_insurer_admin)])
async def simulate_trigger(body: SimulateTriggerRequest):
    """Ingest a mock trigger event into the system. Admin only."""
    sb = get_supabase_admin()

    # Lookup proper reference and labels if available
    metadata = TRIGGER_LIBRARY.get(body.trigger_code, {})

    started_at = body.started_at
    if not started_at:
        started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    ins_data = {
        "city": body.city,
        "zone_id": body.zone_id,
        "trigger_family": body.trigger_family,
        "trigger_code": body.trigger_code,
        "source_ref_id": metadata.get("source"),
        "observed_value": body.observed_value,
        "official_threshold_label": "Simulated Threshold",
        "product_threshold_value": metadata.get("threshold", "Simulated"),
        "severity_band": body.severity_band,
        "source_type": "mock",
        "started_at": started_at,
    }

    # We clean None values to prevent Supabase errors if columns don't allow null for certain logic,
    # though our schema is fairly forgiving.
    resp = sb.table("trigger_events").insert(ins_data).execute()

    return {"status": "simulated", "event": resp.data[0]}

