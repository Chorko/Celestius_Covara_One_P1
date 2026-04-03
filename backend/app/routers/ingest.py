"""
Covara One — Data Ingestion Router

Endpoints for triggering weather/AQI/traffic data ingestion,
viewing pool health diagnostics, AND evaluating thresholds to
create trigger_events automatically.

Phase 1 upgrade: Each ingest endpoint now also evaluates the data
against the trigger threshold table and writes trigger_events.
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional

from ..dependencies import require_insurer_admin
from ..supabase_client import get_supabase_admin
from ..services.weather_ingest import fetch_weather, get_weather_pool_health
from ..services.aqi_ingest import fetch_aqi, get_aqi_pool_health
from ..services.traffic_ingest import fetch_traffic, get_traffic_pool_health
from ..services.trigger_evaluator import (
    evaluate_weather_data,
    evaluate_aqi_data,
    evaluate_traffic_data,
    scan_all_zones_async,
)

router = APIRouter(prefix="/ingest", tags=["Data Ingestion"])


@router.get("/weather")
async def ingest_weather(
    lat: float = 19.08,
    lon: float = 72.88,
    zone_id: Optional[str] = Query(None, description="Zone ID to evaluate triggers for"),
    city: Optional[str] = Query(None, description="City name for trigger metadata"),
):
    """
    Fetch current weather data via the resilient provider pool.
    If zone_id is provided, also evaluates against trigger thresholds
    and creates trigger_events for any crossed thresholds.
    """
    result = await fetch_weather(lat=lat, lon=lon)

    triggers_created = []
    if zone_id and city and not result.get("error"):
        sb = get_supabase_admin()
        triggers_created = evaluate_weather_data(sb, result, zone_id, city)

    return {
        "data": result,
        "triggers_created": triggers_created,
        "triggers_count": len(triggers_created),
    }


@router.get("/aqi")
async def ingest_aqi(
    lat: float = 19.08,
    lon: float = 72.88,
    zone_id: Optional[str] = Query(None, description="Zone ID to evaluate triggers for"),
    city: Optional[str] = Query(None, description="City name for trigger metadata"),
):
    """
    Fetch current AQI data via the resilient provider pool.
    If zone_id is provided, also evaluates against trigger thresholds
    and creates trigger_events for any crossed thresholds.
    """
    result = await fetch_aqi(lat=lat, lon=lon)

    triggers_created = []
    if zone_id and city and not result.get("error"):
        sb = get_supabase_admin()
        triggers_created = evaluate_aqi_data(sb, result, zone_id, city)

    return {
        "data": result,
        "triggers_created": triggers_created,
        "triggers_count": len(triggers_created),
    }


@router.get("/traffic")
async def ingest_traffic(
    lat: float = 19.08,
    lon: float = 72.88,
    zone_id: Optional[str] = Query(None, description="Zone ID to evaluate triggers for"),
    city: Optional[str] = Query(None, description="City name for trigger metadata"),
):
    """
    Fetch current traffic data via the resilient provider pool.
    If zone_id is provided, also evaluates against trigger thresholds
    and creates trigger_events for any crossed thresholds.
    """
    result = await fetch_traffic(lat=lat, lon=lon)

    triggers_created = []
    if zone_id and city and not result.get("error"):
        sb = get_supabase_admin()
        triggers_created = evaluate_traffic_data(sb, result, zone_id, city)

    return {
        "data": result,
        "triggers_created": triggers_created,
        "triggers_count": len(triggers_created),
    }


@router.get("/health")
async def pool_health():
    """
    Returns health diagnostics for all API provider pools.
    Shows: provider status, call counts, error rates, cache sizes.
    """
    return {
        "weather": get_weather_pool_health(),
        "aqi": get_aqi_pool_health(),
        "traffic": get_traffic_pool_health(),
    }


@router.post(
    "/scan-all-zones",
    dependencies=[Depends(require_insurer_admin)],
)
async def scan_all_zones():
    """
    Batch scan: Fetches weather, AQI, and traffic data for ALL configured
    zones and evaluates every reading against the trigger threshold table.

    Creates trigger_events for any crossed thresholds.
    Respects the 6-hour cooldown to prevent duplicate triggers.

    This is the main endpoint for scheduled/cron-based trigger ingestion.
    Admin only.
    """
    sb = get_supabase_admin()
    result = await scan_all_zones_async(sb)
    return result
