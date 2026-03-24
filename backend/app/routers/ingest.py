"""
Covara One — Data Ingestion Router

Endpoints for triggering weather/AQI/traffic data ingestion and
viewing pool health diagnostics.
"""

from fastapi import APIRouter

from ..services.weather_ingest import fetch_weather, get_weather_pool_health
from ..services.aqi_ingest import fetch_aqi, get_aqi_pool_health
from ..services.traffic_ingest import fetch_traffic, get_traffic_pool_health

router = APIRouter(prefix="/ingest", tags=["Data Ingestion"])


@router.get("/weather")
async def ingest_weather(lat: float = 19.08, lon: float = 72.88):
    """
    Fetch current weather data via the resilient provider pool.
    Uses round-robin across 3 providers with LRU caching.
    """
    return await fetch_weather(lat=lat, lon=lon)


@router.get("/aqi")
async def ingest_aqi(lat: float = 19.08, lon: float = 72.88):
    """
    Fetch current AQI data via the resilient provider pool.
    Uses round-robin across 3 providers with LRU caching.
    """
    return await fetch_aqi(lat=lat, lon=lon)


@router.get("/traffic")
async def ingest_traffic(lat: float = 19.08, lon: float = 72.88):
    """
    Fetch current traffic data via the resilient provider pool.
    Uses round-robin across 3 providers with LRU caching.
    """
    return await fetch_traffic(lat=lat, lon=lon)


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
