"""
Covara One — Trigger Evaluator Service

The BRIDGE between raw API data and the trigger_events table.

This module takes normalized weather/AQI/traffic data from the ingestion
pools and evaluates it against the 16-trigger threshold table. When a
threshold is crossed, it creates a trigger_event row in Supabase.

Deduplication: Will not re-create a trigger for the same
              zone + trigger_family within COOLDOWN_HOURS.

This is the module that was MISSING — the ingest pools fetched data
perfectly but never evaluated thresholds or wrote trigger_events.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("covara.trigger_evaluator")

# ── Cooldown: suppress duplicate triggers for same zone+family ───────
COOLDOWN_HOURS = 6

# ── Threshold Definitions (from trigger_engine.py T1-T16) ───────────
# Each returns: (trigger_code, severity_band, description) or None

def _evaluate_rain(rain_mm: float) -> tuple[str, str, str] | None:
    """Evaluate rainfall against T1/T2/T3 thresholds."""
    if rain_mm >= 115.6:
        return ("RAIN_EXTREME", "escalation", f"Extreme rainfall: {rain_mm:.1f}mm ≥ 115.6mm")
    elif rain_mm >= 64.5:
        return ("RAIN_HEAVY", "claim", f"Heavy rainfall: {rain_mm:.1f}mm ≥ 64.5mm")
    elif rain_mm >= 48.0:
        return ("RAIN_WATCH", "watch", f"Rain watch: {rain_mm:.1f}mm ≥ 48mm")
    return None


def _evaluate_temperature(temp_c: float) -> tuple[str, str, str] | None:
    """Evaluate temperature against T7/T8 thresholds."""
    if temp_c >= 47.0:
        return ("HEAT_SEVERE", "escalation", f"Severe heat: {temp_c:.1f}°C ≥ 47°C")
    elif temp_c >= 45.0:
        return ("HEAT_WAVE", "claim", f"Heat wave: {temp_c:.1f}°C ≥ 45°C")
    return None


def _evaluate_aqi(aqi_value: float) -> tuple[str, str, str] | None:
    """Evaluate AQI against T5/T6/T16 thresholds."""
    if aqi_value >= 401:
        return ("AQI_EXTREME", "escalation", f"Extreme AQI: {aqi_value:.0f} ≥ 401")
    elif aqi_value >= 301:
        return ("AQI_SEVERE", "claim", f"Severe AQI: {aqi_value:.0f} ≥ 301")
    elif aqi_value >= 201:
        return ("AQI_CAUTION", "watch", f"AQI caution: {aqi_value:.0f} ≥ 201")
    return None


def _evaluate_traffic_delay(delay_pct: float) -> tuple[str, str, str] | None:
    """Evaluate traffic delay against T12 threshold."""
    if delay_pct >= 40.0:
        return ("TRAFFIC_SEVERE", "watch", f"Severe traffic: {delay_pct:.1f}% delay ≥ 40%")
    return None


# ── Trigger Source Mapping ──────────────────────────────────────────
TRIGGER_SOURCES = {
    "RAIN_WATCH": "R3",
    "RAIN_HEAVY": "R3",
    "RAIN_EXTREME": "R3",
    "HEAT_WAVE": "R4",
    "HEAT_SEVERE": "R4",
    "AQI_CAUTION": "R1",
    "AQI_SEVERE": "R1",
    "AQI_EXTREME": "R1",
    "TRAFFIC_SEVERE": "internal",
}

TRIGGER_FAMILIES = {
    "RAIN_WATCH": "rain",
    "RAIN_HEAVY": "rain",
    "RAIN_EXTREME": "rain",
    "HEAT_WAVE": "heat",
    "HEAT_SEVERE": "heat",
    "AQI_CAUTION": "aqi",
    "AQI_SEVERE": "aqi",
    "AQI_EXTREME": "aqi",
    "TRAFFIC_SEVERE": "traffic",
}

TRIGGER_THRESHOLDS = {
    "RAIN_WATCH": "≥ 48 mm",
    "RAIN_HEAVY": "≥ 64.5 mm",
    "RAIN_EXTREME": "≥ 115.6 mm",
    "HEAT_WAVE": "≥ 45°C",
    "HEAT_SEVERE": "≥ 47°C",
    "AQI_CAUTION": "201-300",
    "AQI_SEVERE": "301+",
    "AQI_EXTREME": "401+",
    "TRAFFIC_SEVERE": "≥ 40% delay",
}


# ── Core Evaluator Functions ────────────────────────────────────────


def _is_on_cooldown(sb, zone_id: str, trigger_family: str) -> bool:
    """Check if a trigger of this family already fired for this zone recently."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=COOLDOWN_HOURS)).isoformat()
    try:
        resp = (
            sb.table("trigger_events")
            .select("id")
            .eq("zone_id", zone_id)
            .eq("trigger_family", trigger_family)
            .gte("started_at", cutoff)
            .limit(1)
            .execute()
        )
        return bool(resp.data)
    except Exception as e:
        logger.warning(f"Cooldown check failed for {zone_id}/{trigger_family}: {e}")
        return False  # If we can't check, allow the trigger


def _create_trigger_event(
    sb,
    trigger_code: str,
    zone_id: str,
    city: str,
    observed_value: float,
    severity_band: str,
    description: str,
    source_provider: str,
) -> dict | None:
    """Insert a trigger_event into Supabase if not on cooldown."""
    family = TRIGGER_FAMILIES.get(trigger_code, "unknown")

    if _is_on_cooldown(sb, zone_id, family):
        logger.info(
            f"Trigger {trigger_code} for zone {zone_id} is on cooldown — skipping"
        )
        return None

    now_iso = datetime.now(timezone.utc).isoformat()

    row = {
        "city": city,
        "zone_id": zone_id,
        "trigger_family": family,
        "trigger_code": trigger_code,
        "source_ref_id": TRIGGER_SOURCES.get(trigger_code, "internal"),
        "observed_value": observed_value,
        "official_threshold_label": description,
        "product_threshold_value": TRIGGER_THRESHOLDS.get(trigger_code, ""),
        "severity_band": severity_band,
        "source_type": source_provider,
        "started_at": now_iso,
    }

    try:
        resp = sb.table("trigger_events").insert(row).execute()
        created = resp.data[0] if resp.data else row
        logger.info(
            f"🔔 TRIGGER CREATED: {trigger_code} ({severity_band}) "
            f"in {city}/{zone_id} — {description}"
        )
        return created
    except Exception as e:
        logger.error(f"Failed to create trigger {trigger_code}: {e}")
        return None


# ── Public Evaluation Functions (called by ingest router) ───────────


def evaluate_weather_data(
    sb, weather_response: dict, zone_id: str, city: str
) -> list[dict]:
    """
    Evaluate weather data against rain and temperature thresholds.
    Creates trigger_events for any thresholds crossed.

    Returns list of created trigger events.
    """
    created = []
    provider = weather_response.get("provider", "unknown")
    weather_data = weather_response.get("data") or {}

    # ── Rain evaluation ──
    # Try rain_1h_mm first (OpenWeather), then rain_mm_24h (IMD/legacy)
    rain_mm = weather_data.get("rain_1h_mm") or weather_data.get("rain_3h_mm") or 0
    # For 1h rain, extrapolate to approximate 24h equivalent for threshold comparison
    # This is a rough heuristic — in production, use cumulative 24h data
    rain_24h_approx = weather_data.get("rain_mm_24h")
    if rain_24h_approx is None and rain_mm:
        # If we only have 1h data, note this in the description
        rain_result = _evaluate_rain(float(rain_mm))
        if rain_result:
            code, band, desc = rain_result
            desc += f" (1h reading, provider: {provider})"
            event = _create_trigger_event(
                sb, code, zone_id, city, float(rain_mm), band, desc, provider
            )
            if event:
                created.append(event)
    elif rain_24h_approx:
        rain_result = _evaluate_rain(float(rain_24h_approx))
        if rain_result:
            code, band, desc = rain_result
            event = _create_trigger_event(
                sb, code, zone_id, city, float(rain_24h_approx), band, desc, provider
            )
            if event:
                created.append(event)

    # ── Temperature evaluation ──
    temp_c = weather_data.get("temp_c")
    if temp_c is not None:
        temp_result = _evaluate_temperature(float(temp_c))
        if temp_result:
            code, band, desc = temp_result
            event = _create_trigger_event(
                sb, code, zone_id, city, float(temp_c), band, desc, provider
            )
            if event:
                created.append(event)

    return created


def evaluate_aqi_data(
    sb, aqi_response: dict, zone_id: str, city: str
) -> list[dict]:
    """
    Evaluate AQI data against air quality thresholds.
    Creates trigger_events for any thresholds crossed.
    """
    created = []
    provider = aqi_response.get("provider", "unknown")
    aqi_data = aqi_response.get("data") or {}
    aqi_value = aqi_data.get("aqi")

    if aqi_value is not None:
        aqi_result = _evaluate_aqi(float(aqi_value))
        if aqi_result:
            code, band, desc = aqi_result
            desc += f" (provider: {provider})"
            event = _create_trigger_event(
                sb, code, zone_id, city, float(aqi_value), band, desc, provider
            )
            if event:
                created.append(event)

    return created


def evaluate_traffic_data(
    sb, traffic_response: dict, zone_id: str, city: str
) -> list[dict]:
    """
    Evaluate traffic data against delay thresholds.
    Creates trigger_events for any thresholds crossed.
    """
    created = []
    provider = traffic_response.get("provider", "unknown")
    traffic_data = traffic_response.get("data") or {}
    delay_pct = traffic_data.get("delay_percent") or traffic_data.get("traffic_delay_pct")

    if delay_pct is not None:
        traffic_result = _evaluate_traffic_delay(float(delay_pct))
        if traffic_result:
            code, band, desc = traffic_result
            desc += f" (provider: {provider})"
            event = _create_trigger_event(
                sb, code, zone_id, city, float(delay_pct), band, desc, provider
            )
            if event:
                created.append(event)

    return created


def scan_all_zones(sb) -> dict:
    """
    Batch scan: fetch data for all configured zones and evaluate triggers.
    This is the main entry point for scheduled/cron trigger ingestion.

    Returns summary of scan results.
    """
    from backend.app.services.zone_coordinates import get_all_zone_coordinates
    from backend.app.services.weather_ingest import fetch_weather
    from backend.app.services.aqi_ingest import fetch_aqi
    from backend.app.services.traffic_ingest import fetch_traffic

    zones = get_all_zone_coordinates(sb)
    logger.info(f"Starting trigger scan for {len(zones)} zones...")

    summary = {
        "zones_scanned": len(zones),
        "triggers_created": 0,
        "triggers": [],
        "errors": [],
    }

    import asyncio

    async def _scan_zone(zone: dict) -> list[dict]:
        zone_triggers = []
        zone_id = zone["zone_id"]
        city = zone["city"]
        lat = zone["lat"]
        lng = zone["lng"]

        try:
            # 1. Weather
            weather = await fetch_weather(lat=lat, lon=lng)
            if not weather.get("error"):
                triggers = evaluate_weather_data(sb, weather, zone_id, city)
                zone_triggers.extend(triggers)
        except Exception as e:
            summary["errors"].append(f"Weather scan failed for {city}: {e}")

        try:
            # 2. AQI
            aqi = await fetch_aqi(lat=lat, lon=lng)
            if not aqi.get("error"):
                triggers = evaluate_aqi_data(sb, aqi, zone_id, city)
                zone_triggers.extend(triggers)
        except Exception as e:
            summary["errors"].append(f"AQI scan failed for {city}: {e}")

        try:
            # 3. Traffic
            traffic = await fetch_traffic(lat=lat, lon=lng)
            if not traffic.get("error"):
                triggers = evaluate_traffic_data(sb, traffic, zone_id, city)
                zone_triggers.extend(triggers)
        except Exception as e:
            summary["errors"].append(f"Traffic scan failed for {city}: {e}")

        return zone_triggers

    # Run all zone scans
    loop = asyncio.get_event_loop()
    for zone in zones:
        try:
            zone_triggers = loop.run_until_complete(_scan_zone(zone))
            summary["triggers"].extend(zone_triggers)
        except RuntimeError:
            # Already in an async context — use await directly
            zone_triggers = asyncio.run(_scan_zone(zone))
            summary["triggers"].extend(zone_triggers)

    summary["triggers_created"] = len(summary["triggers"])
    logger.info(
        f"Trigger scan complete: {summary['triggers_created']} triggers created "
        f"across {summary['zones_scanned']} zones"
    )
    return summary


async def scan_all_zones_async(sb) -> dict:
    """
    Async version of scan_all_zones for use inside FastAPI endpoints.
    """
    from backend.app.services.zone_coordinates import get_all_zone_coordinates
    from backend.app.services.weather_ingest import fetch_weather
    from backend.app.services.aqi_ingest import fetch_aqi
    from backend.app.services.traffic_ingest import fetch_traffic

    zones = get_all_zone_coordinates(sb)
    logger.info(f"Starting async trigger scan for {len(zones)} zones...")

    summary = {
        "zones_scanned": len(zones),
        "triggers_created": 0,
        "triggers": [],
        "errors": [],
        "zone_results": [],
    }

    for zone in zones:
        zone_id = zone["zone_id"]
        city = zone["city"]
        lat = zone["lat"]
        lng = zone["lng"]
        zone_result = {"zone": zone["zone_name"], "city": city, "triggers": []}

        # 1. Weather
        try:
            weather = await fetch_weather(lat=lat, lon=lng)
            if not weather.get("error") and weather.get("data"):
                payload = weather["data"]
                triggers = evaluate_weather_data(sb, weather, zone_id, city)
                zone_result["triggers"].extend(triggers)
                zone_result["weather"] = {
                    "provider": weather.get("provider"),
                    "temp_c": payload.get("temp_c"),
                    "rain_mm": payload.get("rain_1h_mm") or payload.get("rain_3h_mm"),
                }
        except Exception as e:
            summary["errors"].append(f"Weather/{city}: {e}")

        # 2. AQI
        try:
            aqi = await fetch_aqi(lat=lat, lon=lng)
            if not aqi.get("error") and aqi.get("data"):
                payload = aqi["data"]
                triggers = evaluate_aqi_data(sb, aqi, zone_id, city)
                zone_result["triggers"].extend(triggers)
                zone_result["aqi"] = {
                    "provider": aqi.get("provider"),
                    "aqi": payload.get("aqi"),
                }
        except Exception as e:
            summary["errors"].append(f"AQI/{city}: {e}")

        # 3. Traffic
        try:
            traffic = await fetch_traffic(lat=lat, lon=lng)
            if not traffic.get("error") and traffic.get("data"):
                payload = traffic["data"]
                triggers = evaluate_traffic_data(sb, traffic, zone_id, city)
                zone_result["triggers"].extend(triggers)
                zone_result["traffic"] = {
                    "provider": traffic.get("provider"),
                    "delay_pct": payload.get("delay_percent"),
                }
        except Exception as e:
            summary["errors"].append(f"Traffic/{city}: {e}")

        summary["triggers"].extend(zone_result["triggers"])
        summary["zone_results"].append(zone_result)

    summary["triggers_created"] = len(summary["triggers"])
    logger.info(
        f"Async trigger scan complete: {summary['triggers_created']} triggers "
        f"across {summary['zones_scanned']} zones"
    )
    return summary
