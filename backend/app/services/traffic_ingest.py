"""
Covara One — Traffic Data Ingestion Service

Polls traffic data from N providers (round-robin + LRU cached).
Providers are AUTO-DISCOVERED from .env vars matching TRAFFIC_API_KEY_*.

How to add a new traffic provider:
  1. Add TRAFFIC_API_KEY_2=your_key (or any number/name) to .env
  2. Write a fetch function below (must return the same dict shape)
  3. Register it in the PROVIDER_REGISTRY dict
  That's it — no config.py changes needed.

Built-in providers:
  TRAFFIC_API_KEY_1  → TomTom
"""

import logging
import os
import httpx
from ..config import settings
from .api_pool import ApiProviderPool, ApiProvider

logger = logging.getLogger("covara.traffic_ingest")


# ── Provider fetch functions ─────────────────────────────────────────────


async def _fetch_tomtom(lat: float, lon: float, key: str = "", **_) -> dict:
    """Fetch traffic flow from TomTom API."""
    url = (
        f"https://api.tomtom.com/traffic/services/4/flowSegmentData"
        f"/absolute/10/json?point={lat},{lon}&key={key}"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    flow = data.get("flowSegmentData", {})
    current = flow.get("currentSpeed", 0)
    freeflow = flow.get("freeFlowSpeed", 1)
    delay_pct = max(0, round((1 - current / freeflow) * 100, 1)) if freeflow > 0 else 0
    return {
        "provider": "tomtom",
        "current_speed_kmh": current,
        "freeflow_speed_kmh": freeflow,
        "delay_percent": delay_pct,
        "confidence": flow.get("confidence"),
        "road_closure": flow.get("roadClosure", False),
        "raw": data,
    }


# ── Provider Registry ────────────────────────────────────────────────────
# Map .env slot names to (fetch_fn, needs_key, display_name).

PROVIDER_REGISTRY: dict[str, tuple] = {
    "1": (_fetch_tomtom, True, "tomtom"),
    # Add more:
    # "2": (_fetch_here_maps, True, "here_maps"),
    # "3": (_fetch_mapbox, True, "mapbox"),
}


# ── Build the traffic pool (auto-discovery from .env) ─────────────────────

traffic_pool = ApiProviderPool("traffic", cache_ttl_seconds=180, cache_maxsize=256)

# Auto-discover all TRAFFIC_API_KEY_* from .env
discovered_keys = settings.get_api_keys("TRAFFIC")
# Also check legacy TOMTOM_API_KEY for slot 1
if settings.tomtom_api_key and "1" not in discovered_keys:
    discovered_keys["1"] = settings.tomtom_api_key

for slot, api_key in sorted(discovered_keys.items()):
    if slot in PROVIDER_REGISTRY:
        fetch_fn, needs_key, name = PROVIDER_REGISTRY[slot]
        if needs_key:
            _fn = fetch_fn
            _key = api_key
            async def _bound_fn(lat, lon, _f=_fn, _k=_key, **kw):
                return await _f(lat=lat, lon=lon, key=_k, **kw)
            traffic_pool.add_provider(
                ApiProvider(name=name, fetch_fn=_bound_fn, priority=int(slot) if slot.isdigit() else 50)
            )
        else:
            traffic_pool.add_provider(
                ApiProvider(name=name, fetch_fn=fetch_fn, priority=int(slot) if slot.isdigit() else 50)
            )
    else:
        logger.info(f"Traffic slot '{slot}' has a key but no registered fetch function. "
                     f"Add it to PROVIDER_REGISTRY in traffic_ingest.py to activate.")

logger.info(f"Traffic pool initialized with {traffic_pool.provider_count} provider(s)")


# ── Route Plausibility Check ────────────────────────────────────────────


async def check_route_plausibility(
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
) -> dict:
    """
    Verify a worker's claimed route is physically possible via TomTom Routing.
    Returns route plausibility score (0.0 to 1.0).
    """
    key = settings.get_api_key("TRAFFIC", "1") or settings.tomtom_api_key
    if not key:
        return {"plausible": None, "score": None, "reason": "no_api_key"}

    url = (
        f"https://api.tomtom.com/routing/1/calculateRoute"
        f"/{start_lat},{start_lon}:{end_lat},{end_lon}/json?key={key}"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        routes = data.get("routes", [])
        if not routes:
            return {"plausible": False, "score": 0.1, "reason": "no_route_found"}
        summary = routes[0].get("summary", {})
        distance_m = summary.get("lengthInMeters", 0)
        travel_time_s = summary.get("travelTimeInSeconds", 0)
        if distance_m < 200_000 and travel_time_s > 60:
            return {"plausible": True, "score": 0.85, "distance_km": distance_m / 1000, "travel_min": travel_time_s / 60}
        else:
            return {"plausible": False, "score": 0.3, "reason": "route_implausible", "distance_km": distance_m / 1000}
    except Exception as e:
        logger.warning(f"Route plausibility check failed: {e}")
        return {"plausible": None, "score": None, "reason": f"api_error: {e}"}


# ── Public API ───────────────────────────────────────────────────────────


async def fetch_traffic(lat: float, lon: float) -> dict:
    """Fetch current traffic using the resilient provider pool."""
    result = await traffic_pool.call(lat=lat, lon=lon)
    if result.get("error"):
        logger.error(f"Traffic fetch failed: {result}")
    return result


def get_traffic_pool_health() -> dict:
    """Returns health status of all traffic providers."""
    return traffic_pool.get_health_report()
