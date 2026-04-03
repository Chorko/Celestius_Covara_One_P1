"""
Covara One — Zone Coordinate Service

Maps zone IDs to geographic coordinates for API calls.
Used by the ingestion pipeline to scan all zones for trigger events.
"""

from __future__ import annotations
import logging

logger = logging.getLogger("covara.zone_coordinates")

# ── Hardcoded city coordinates (used when zones table lacks lat/lng) ────
CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.6139, 77.2090),
    "bangalore": (12.9716, 77.5946),
    "hyderabad": (17.3850, 78.4867),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "pune": (18.5204, 73.8567),
    "ahmedabad": (23.0225, 72.5714),
    "jaipur": (26.9124, 75.7873),
    "lucknow": (26.8467, 80.9462),
}


def get_all_zone_coordinates(sb) -> list[dict]:
    """
    Fetch all zones from Supabase with their center coordinates.
    Falls back to city-level coordinates if zone-level coords are missing.

    Returns: [{"zone_id": "...", "zone_name": "...", "city": "...", "lat": 19.07, "lng": 72.87}, ...]
    """
    try:
        resp = sb.table("zones").select("id, zone_name, city, center_lat, center_lng").execute()
        zones = resp.data or []
    except Exception as e:
        logger.error(f"Failed to fetch zones from Supabase: {e}")
        zones = []

    results = []
    for z in zones:
        lat = z.get("center_lat")
        lng = z.get("center_lng")

        # Fall back to city-level coordinates if zone has no center
        if lat is None or lng is None:
            city = (z.get("city") or "").lower().strip()
            city_coords = CITY_COORDINATES.get(city)
            if city_coords:
                lat, lng = city_coords
            else:
                logger.warning(f"Zone {z.get('zone_name')} in {z.get('city')} has no coordinates — skipping")
                continue

        results.append({
            "zone_id": z["id"],
            "zone_name": z.get("zone_name", ""),
            "city": z.get("city", ""),
            "lat": float(lat),
            "lng": float(lng),
        })

    return results


def get_zone_coordinates(sb, zone_id: str) -> dict | None:
    """Fetch a single zone's coordinates."""
    try:
        resp = (
            sb.table("zones")
            .select("id, zone_name, city, center_lat, center_lng")
            .eq("id", zone_id)
            .maybe_single()
            .execute()
        )
        if not resp.data:
            return None
        z = resp.data
        lat = z.get("center_lat")
        lng = z.get("center_lng")
        if lat is None or lng is None:
            city = (z.get("city") or "").lower().strip()
            city_coords = CITY_COORDINATES.get(city)
            if city_coords:
                lat, lng = city_coords
            else:
                return None
        return {
            "zone_id": z["id"],
            "zone_name": z.get("zone_name", ""),
            "city": z.get("city", ""),
            "lat": float(lat),
            "lng": float(lng),
        }
    except Exception as e:
        logger.error(f"Failed to fetch zone {zone_id}: {e}")
        return None
