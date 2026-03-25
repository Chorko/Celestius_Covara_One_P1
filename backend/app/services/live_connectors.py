"""
Covara One — Live API Connectors

Unified module for external API integrations.  Each connector
follows the same pattern:
  1.  Try the live API if a key is configured.
  2.  Fall back to mock data if not.

Connectors:
  • IMD (India Meteorological Department) — rainfall, temperature
  • CPCB (Central Pollution Control Board) — AQI
  • OpenWeather — weather fallback
  • TomTom — traffic flow, snap-to-roads, geofencing

All connectors return normalised dicts that the trigger engine
and fraud engine can consume without caring whether the data
was real or mock.
"""

import os
import httpx
from typing import Optional

# ── API Keys (from env) ──────────────────────────────────────────────────
OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY", "")
TOMTOM_KEY = os.getenv("TOMTOM_API_KEY", "")
CPCB_KEY = os.getenv("CPCB_API_KEY", "")

# ── IMD Station IDs ──────────────────────────────────────────────────────
IMD_STATIONS = {
    "mumbai": {"name": "Santacruz", "id": "43057"},
    "delhi": {"name": "Safdarjung", "id": "42182"},
    "bangalore": {"name": "HAL Airport", "id": "43296"},
    "hyderabad": {"name": "Begumpet", "id": "43128"},
}


# ═══════════════════════════════════════════════════════════════════════════
#  IMD — Rainfall & Temperature
# ═══════════════════════════════════════════════════════════════════════════

async def fetch_imd_rainfall(city: str) -> dict:
    """
    Fetch rainfall data from IMD district-wise rainfall API.
    Falls back to mock data if IMD IP whitelisting is not active.
    """
    station = IMD_STATIONS.get(city.lower())
    if not station:
        return _mock_rainfall(city)

    url = f"https://mausam.imd.gov.in/api/districtwise_rainfall_api.php?id={station['id']}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "source": "imd_live",
                    "city": city,
                    "station": station["name"],
                    "rain_mm_24h": float(data.get("Daily Actual", 0)),
                    "category": data.get("Daily Category", "unknown"),
                    "raw": data,
                }
    except Exception:
        pass

    return _mock_rainfall(city)


async def fetch_imd_temperature(city: str) -> dict:
    """
    Fetch current temperature from IMD current weather API.
    Falls back to mock data if unavailable.
    """
    station = IMD_STATIONS.get(city.lower())
    if not station:
        return _mock_temperature(city)

    url = f"https://mausam.imd.gov.in/api/current_wx_api.php?id={station['id']}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "source": "imd_live",
                    "city": city,
                    "station": station["name"],
                    "temp_c": float(data.get("Temperature", 0)),
                    "weather_code": data.get("Weather Code", ""),
                    "raw": data,
                }
    except Exception:
        pass

    return _mock_temperature(city)


# ═══════════════════════════════════════════════════════════════════════════
#  CPCB — Air Quality Index
# ═══════════════════════════════════════════════════════════════════════════

async def fetch_cpcb_aqi(city: str) -> dict:
    """
    Fetch real-time AQI from CPCB via data.gov.in OGD API.
    Falls back to mock data if API key is not configured.
    """
    if CPCB_KEY:
        url = (
            "https://api.data.gov.in/resource/"
            "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
            f"?api-key={CPCB_KEY}&format=json"
            f"&filters[city]={city}"
            "&limit=1"
        )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    records = data.get("records", [])
                    if records:
                        rec = records[0]
                        return {
                            "source": "cpcb_live",
                            "city": city,
                            "aqi": int(rec.get("pollutant_avg", 0)),
                            "pollutant": rec.get("pollutant_id", "PM2.5"),
                            "station": rec.get("station", "unknown"),
                            "raw": rec,
                        }
        except Exception:
            pass

    return _mock_aqi(city)


# ═══════════════════════════════════════════════════════════════════════════
#  OpenWeather — Fallback Weather Feed
# ═══════════════════════════════════════════════════════════════════════════

async def fetch_openweather(city: str) -> dict:
    """
    Fetch current weather from OpenWeather API (fallback for IMD).
    """
    if OPENWEATHER_KEY:
        url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?q={city},IN&appid={OPENWEATHER_KEY}&units=metric"
        )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    rain_1h = data.get("rain", {}).get("1h", 0)
                    return {
                        "source": "openweather_live",
                        "city": city,
                        "temp_c": data["main"]["temp"],
                        "rain_mm_1h": rain_1h,
                        "humidity": data["main"]["humidity"],
                        "description": data["weather"][0]["description"],
                        "raw": data,
                    }
        except Exception:
            pass

    return _mock_weather(city)


# ═══════════════════════════════════════════════════════════════════════════
#  TomTom — Traffic Flow & Anti-Spoofing
# ═══════════════════════════════════════════════════════════════════════════

async def fetch_tomtom_traffic(lat: float, lng: float) -> dict:
    """
    Fetch traffic flow data from TomTom Traffic API.
    """
    if TOMTOM_KEY:
        url = (
            f"https://api.tomtom.com/traffic/services/4/flowSegmentData/"
            f"absolute/10/json?point={lat},{lng}&key={TOMTOM_KEY}"
        )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    flow = data.get("flowSegmentData", {})
                    free_flow = flow.get("freeFlowSpeed", 60)
                    current = flow.get("currentSpeed", 60)
                    delay_pct = max(0, round((1 - current / free_flow) * 100, 1)) if free_flow > 0 else 0
                    return {
                        "source": "tomtom_live",
                        "current_speed_kmh": current,
                        "free_flow_speed_kmh": free_flow,
                        "traffic_delay_pct": delay_pct,
                        "confidence": flow.get("confidence", 0),
                        "raw": flow,
                    }
        except Exception:
            pass

    return _mock_traffic(lat, lng)


async def fetch_tomtom_snap_to_roads(
    lat: float, lng: float
) -> dict:
    """
    Snap GPS coordinates to nearest road via TomTom.
    Used for anti-spoofing route plausibility checks.
    """
    if TOMTOM_KEY:
        url = (
            f"https://api.tomtom.com/snap/1/versionNumber/snap"
            f"?points={lat},{lng}&key={TOMTOM_KEY}"
        )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    snapped = data.get("snappedPoints", [])
                    if snapped:
                        return {
                            "source": "tomtom_live",
                            "snapped": True,
                            "confidence": snapped[0].get("confidence", 0),
                            "road_name": snapped[0].get("road", {}).get("name", ""),
                            "raw": snapped[0],
                        }
        except Exception:
            pass

    return {
        "source": "mock",
        "snapped": True,
        "confidence": 0.85,
        "road_name": "Mock Road",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Mock Fallbacks
# ═══════════════════════════════════════════════════════════════════════════

def _mock_rainfall(city: str) -> dict:
    import random
    return {
        "source": "mock",
        "city": city,
        "station": "simulated",
        "rain_mm_24h": round(random.uniform(0, 80), 1),
        "category": "moderate",
    }


def _mock_temperature(city: str) -> dict:
    import random
    return {
        "source": "mock",
        "city": city,
        "station": "simulated",
        "temp_c": round(random.uniform(28, 42), 1),
        "weather_code": "",
    }


def _mock_aqi(city: str) -> dict:
    import random
    return {
        "source": "mock",
        "city": city,
        "aqi": random.randint(80, 350),
        "pollutant": "PM2.5",
        "station": "simulated",
    }


def _mock_weather(city: str) -> dict:
    import random
    return {
        "source": "mock",
        "city": city,
        "temp_c": round(random.uniform(25, 40), 1),
        "rain_mm_1h": round(random.uniform(0, 15), 1),
        "humidity": random.randint(40, 90),
        "description": "simulated conditions",
    }


def _mock_traffic(lat: float, lng: float) -> dict:
    import random
    delay = round(random.uniform(5, 55), 1)
    return {
        "source": "mock",
        "current_speed_kmh": round(60 * (1 - delay / 100), 1),
        "free_flow_speed_kmh": 60,
        "traffic_delay_pct": delay,
        "confidence": 0.7,
    }
