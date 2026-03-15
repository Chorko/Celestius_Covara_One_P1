"""
DEVTrails — Trigger Engine Service

Handles logic related to the 15-trigger library and matching
active disruption events to worker zones/shifts.
"""

from datetime import datetime

# The 15-trigger library (T1-T15) mapped directly from documentation
TRIGGER_LIBRARY = {
    "RAIN_WATCH":       {"id": "T1",  "family": "rain",      "band": "watch",      "threshold": ">= 48 mm", "source": "R3"},
    "RAIN_HEAVY":       {"id": "T2",  "family": "rain",      "band": "claim",      "threshold": ">= 64.5 mm", "source": "R3"},
    "RAIN_EXTREME":     {"id": "T3",  "family": "rain",      "band": "escalation", "threshold": ">= 115.6 mm", "source": "R3"},
    "WATERLOGGING":     {"id": "T4",  "family": "access",    "band": "claim",      "threshold": "<= 0.40 score", "source": "internal"},
    "AQI_CAUTION":      {"id": "T5",  "family": "aqi",       "band": "watch",      "threshold": "201-300", "source": "R1"},
    "AQI_SEVERE":       {"id": "T6",  "family": "aqi",       "band": "claim",      "threshold": "301+", "source": "R1"},
    "HEAT_WAVE":        {"id": "T7",  "family": "heat",      "band": "claim",      "threshold": ">= 45C", "source": "R4"},
    "HEAT_SEVERE":      {"id": "T8",  "family": "heat",      "band": "escalation", "threshold": ">= 47C", "source": "R4"},
    "HEAT_PERSISTENCE": {"id": "T9",  "family": "heat",      "band": "watch",      "threshold": "2 days hot", "source": "R4"},
    "ZONE_CLOSURE":     {"id": "T10", "family": "closure",   "band": "claim",      "threshold": "flag = 1", "source": "internal"},
    "CURFEW":           {"id": "T11", "family": "closure",   "band": "claim",      "threshold": ">= 4h", "source": "internal"},
    "TRAFFIC_SEVERE":   {"id": "T12", "family": "traffic",   "band": "watch",      "threshold": ">= 40% delay", "source": "internal"},
    "PLATFORM_OUTAGE":  {"id": "T13", "family": "outage",    "band": "claim",      "threshold": ">= 30 min", "source": "internal"},
    "DEMAND_COLLAPSE":  {"id": "T14", "family": "demand",    "band": "watch",      "threshold": ">= 35% drop", "source": "internal"},
    "COMPOSITE":        {"id": "T15", "family": "composite", "band": "escalation", "threshold": ">= 0.70 score", "source": "internal"},
    "AQI_EXTREME":      {"id": "T16", "family": "aqi",       "band": "escalation", "threshold": "401+", "source": "R1"}, # Added based on threshold table
}

def get_trigger_metadata(trigger_code: str) -> dict | None:
    return TRIGGER_LIBRARY.get(trigger_code)

def get_overlapping_triggers(sb, zone_id: str, shift_start: str, shift_end: str) -> list[dict]:
    """Find all trigger events for a zone that temporally overlap with a shift.

    Overlap logic: event starts before shift ends AND event ends after shift starts.
    If event has no ended_at, we assume it's ongoing and overlaps if it started before shift ends.
    """
    # Supabase / PostgREST doesn't support complex OR logic easily in a single url string,
    # but we can fetch events that started before shift ends, and filter out those that ended before shift starts.
    
    resp = (
        sb.table("trigger_events")
        .select("*")
        .eq("zone_id", zone_id)
        .lte("started_at", shift_end)
        .execute()
    )
    
    overlapping = []
    for ev in resp.data:
        ended_at = ev.get("ended_at")
        if ended_at is None:
            # Ongoing event
            overlapping.append(ev)
        elif ended_at > shift_start:
            overlapping.append(ev)
            
    return overlapping
