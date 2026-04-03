"""
Covara One — AQI Data Ingestion Service

Polls air quality data from N providers (round-robin + LRU cached).
Providers are AUTO-DISCOVERED from .env vars matching AQI_API_KEY_*.

How to add a new AQI provider:
  1. Add AQI_API_KEY_4=your_key (or any number/name) to .env
  2. Write a fetch function below (must return the same dict shape)
  3. Register it in the PROVIDER_REGISTRY dict
  That's it — no config.py changes needed.

Built-in providers:
  AQI_API_KEY_1  → CPCB / data.gov.in
  AQI_API_KEY_2  → OpenWeather Air Pollution (or reuses OPENWEATHER_API_KEY)
"""

import logging
import os
import httpx
from ..config import settings
from .api_pool import ApiProviderPool, ApiProvider

logger = logging.getLogger("covara.aqi_ingest")


# ── Provider fetch functions ─────────────────────────────────────────────


async def _fetch_cpcb(lat: float, lon: float, key: str = "", city: str = "", **_) -> dict:
    """Fetch AQI from CPCB via data.gov.in Open Government Data API.
    
    Supports city-level filtering via filters[city] and pollutant
    filtering via filters[pollutant_id] for PM2.5 readings.
    """
    url = (
        f"https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
        f"?api-key={key}&format=json&offset=0&limit=10"
    )
    # Add city filter if available for zone-level precision
    if city:
        url += f"&filters[city]={city}"
    # Prefer PM2.5 readings for AQI calculation
    url += "&filters[pollutant_id]=PM2.5"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    records = data.get("records", [])
    if not records:
        # Retry without pollutant filter to get any available reading
        fallback_url = (
            f"https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
            f"?api-key={key}&format=json&offset=0&limit=10"
        )
        if city:
            fallback_url += f"&filters[city]={city}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(fallback_url)
            resp.raise_for_status()
            data = resp.json()
        records = data.get("records", [])

    if not records:
        return {"provider": "cpcb", "aqi": None, "pm25": None, "pm10": None, "raw": data}
    rec = records[0]
    return {
        "provider": "cpcb",
        "aqi": _safe_float(rec.get("pollutant_avg")),
        "pm25": _safe_float(rec.get("pollutant_avg")) if rec.get("pollutant_id") == "PM2.5" else None,
        "pm10": _safe_float(rec.get("pollutant_avg")) if rec.get("pollutant_id") == "PM10" else None,
        "station": rec.get("station"),
        "city": rec.get("city"),
        "last_update": rec.get("last_update"),
        "raw": data,
    }


async def _fetch_openweather_aqi(lat: float, lon: float, key: str = "", **_) -> dict:
    """Fetch AQI from OpenWeather Air Pollution API."""
    url = (
        f"https://api.openweathermap.org/data/2.5/air_pollution"
        f"?lat={lat}&lon={lon}&appid={key}"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    components = data.get("list", [{}])[0].get("components", {})
    aqi_index = data.get("list", [{}])[0].get("main", {}).get("aqi", 0)
    # OpenWeather AQI: 1=Good, 5=Very Poor. Map to Indian AQI scale roughly.
    ow_to_indian = {1: 50, 2: 100, 3: 200, 4: 300, 5: 400}
    return {
        "provider": "openweather_aqi",
        "aqi": ow_to_indian.get(aqi_index, 0),
        "pm25": components.get("pm2_5"),
        "pm10": components.get("pm10"),
        "no2": components.get("no2"),
        "raw": data,
    }


def _safe_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


# ── Provider Registry ────────────────────────────────────────────────────
# Map .env slot names to (fetch_fn, needs_key, display_name).

PROVIDER_REGISTRY: dict[str, tuple] = {
    "1": (_fetch_cpcb, True, "cpcb"),
    "2": (_fetch_openweather_aqi, True, "openweather_aqi"),
    # Add more:
    # "3": (_fetch_aqicn, True, "aqicn"),
}


# ── Build the AQI pool (auto-discovery from .env) ────────────────────────

aqi_pool = ApiProviderPool("aqi", cache_ttl_seconds=300, cache_maxsize=256)

# Auto-discover all AQI_API_KEY_* from .env
discovered_keys = settings.get_api_keys("AQI")
# Also check legacy OPENWEATHER_API_KEY for slot 2
if settings.openweather_api_key and "2" not in discovered_keys:
    discovered_keys["2"] = settings.openweather_api_key

for slot, api_key in sorted(discovered_keys.items()):
    if slot in PROVIDER_REGISTRY:
        fetch_fn, needs_key, name = PROVIDER_REGISTRY[slot]
        if needs_key:
            _fn = fetch_fn
            _key = api_key
            async def _bound_fn(lat, lon, _f=_fn, _k=_key, **kw):
                return await _f(lat=lat, lon=lon, key=_k, **kw)
            aqi_pool.add_provider(
                ApiProvider(name=name, fetch_fn=_bound_fn, priority=int(slot) if slot.isdigit() else 50)
            )
        else:
            aqi_pool.add_provider(
                ApiProvider(name=name, fetch_fn=fetch_fn, priority=int(slot) if slot.isdigit() else 50)
            )
    else:
        logger.info(f"AQI slot '{slot}' has a key but no registered fetch function. "
                     f"Add it to PROVIDER_REGISTRY in aqi_ingest.py to activate.")

logger.info(f"AQI pool initialized with {aqi_pool.provider_count} provider(s)")


# ── Public API ───────────────────────────────────────────────────────────


async def fetch_aqi(lat: float, lon: float) -> dict:
    """Fetch current AQI using the resilient provider pool."""
    result = await aqi_pool.call(lat=lat, lon=lon)
    if result.get("error"):
        logger.error(f"AQI fetch failed: {result}")
    return result


def get_aqi_pool_health() -> dict:
    """Returns health status of all AQI providers."""
    return aqi_pool.get_health_report()
