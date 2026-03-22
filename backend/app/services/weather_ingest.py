"""
Covara One — Weather Data Ingestion Service

Polls weather data from N weather providers (round-robin + LRU cached).
Providers are AUTO-DISCOVERED from .env vars matching WEATHER_API_KEY_*.

How to add a new weather provider:
  1. Add WEATHER_API_KEY_4=your_key (or any number/name) to .env
  2. Write a fetch function below (must return the same dict shape)
  3. Register it in the PROVIDER_REGISTRY dict
  That's it — no config.py changes needed.

Built-in providers:
  WEATHER_API_KEY_1  → OpenWeatherMap
  (OpenMeteo needs no key — always registered)
"""

import logging
import os
import httpx
from ..config import settings
from .api_pool import ApiProviderPool, ApiProvider

logger = logging.getLogger("covara.weather_ingest")

# ── Provider fetch functions ─────────────────────────────────────────────
# Each function takes (lat, lon, **kwargs) and returns a normalized dict.
# The **key** kwarg contains the API key from .env.


async def _fetch_openweather(lat: float, lon: float, key: str = "", **_) -> dict:
    """Fetch weather from OpenWeatherMap."""
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={lat}&lon={lon}&appid={key}&units=metric"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    return {
        "provider": "openweather",
        "temp_c": data.get("main", {}).get("temp"),
        "humidity": data.get("main", {}).get("humidity"),
        "rain_1h_mm": data.get("rain", {}).get("1h", 0),
        "rain_3h_mm": data.get("rain", {}).get("3h", 0),
        "wind_speed": data.get("wind", {}).get("speed"),
        "description": data.get("weather", [{}])[0].get("description", ""),
        "raw": data,
    }


async def _fetch_openmeteo(lat: float, lon: float, **_) -> dict:
    """Fetch weather from Open-Meteo (no API key needed — always available)."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
        f"&timezone=Asia/Kolkata"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    current = data.get("current", {})
    return {
        "provider": "openmeteo",
        "temp_c": current.get("temperature_2m"),
        "humidity": current.get("relative_humidity_2m"),
        "rain_1h_mm": current.get("precipitation", 0),
        "rain_3h_mm": None,
        "wind_speed": current.get("wind_speed_10m"),
        "description": "",
        "raw": data,
    }


# ── Provider Registry ────────────────────────────────────────────────────
# Map .env slot names to (fetch_fn, needs_key). Add new providers here.
# "1" matches WEATHER_API_KEY_1, "2" matches WEATHER_API_KEY_2, etc.

PROVIDER_REGISTRY: dict[str, tuple] = {
    "1": (_fetch_openweather, True,  "openweather"),
    # Add more keyed providers:
    # "3": (_fetch_imd, True, "imd"),
    # "4": (_fetch_accuweather, True, "accuweather"),
}


# ── Build the weather pool (auto-discovery from .env) ────────────────────

weather_pool = ApiProviderPool("weather", cache_ttl_seconds=300, cache_maxsize=256)

# 1️⃣ Always register Open-Meteo (no key needed — guaranteed fallback)
weather_pool.add_provider(
    ApiProvider(name="openmeteo", fetch_fn=_fetch_openmeteo, priority=100)
)

# 2️⃣ Auto-discover all WEATHER_API_KEY_* from .env
discovered_keys = settings.get_api_keys("WEATHER")
# Also check legacy OPENWEATHER_API_KEY
if settings.openweather_api_key and "1" not in discovered_keys:
    discovered_keys["1"] = settings.openweather_api_key

for slot, api_key in sorted(discovered_keys.items()):
    if slot in PROVIDER_REGISTRY:
        fetch_fn, needs_key, name = PROVIDER_REGISTRY[slot]
        # Bind the key into the fetch function via a closure
        if needs_key:
            _fn = fetch_fn
            _key = api_key
            async def _bound_fn(lat, lon, _f=_fn, _k=_key, **kw):
                return await _f(lat=lat, lon=lon, key=_k, **kw)
            weather_pool.add_provider(
                ApiProvider(name=name, fetch_fn=_bound_fn, priority=int(slot) if slot.isdigit() else 50)
            )
        else:
            weather_pool.add_provider(
                ApiProvider(name=name, fetch_fn=fetch_fn, priority=int(slot) if slot.isdigit() else 50)
            )
    else:
        # Unknown slot — register a generic keyed provider
        logger.info(f"Weather slot '{slot}' has a key but no registered fetch function. "
                     f"Add it to PROVIDER_REGISTRY in weather_ingest.py to activate.")

logger.info(f"Weather pool initialized with {weather_pool.provider_count} provider(s)")


# ── Public API ───────────────────────────────────────────────────────────


async def fetch_weather(lat: float, lon: float) -> dict:
    """Fetch current weather using the resilient provider pool."""
    result = await weather_pool.call(lat=lat, lon=lon)
    if result.get("error"):
        logger.error(f"Weather fetch failed: {result}")
    return result


def get_weather_pool_health() -> dict:
    """Returns health status of all weather providers."""
    return weather_pool.get_health_report()
