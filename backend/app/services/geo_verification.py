"""
Covara One — Geo-Verification Service

Verifies if provided geographic coordinates fall within or near
the designated operational zones.
"""

import math


def calculate_distance_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees).
    """
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r


def verify_zone_match(
    evidence_lat: float,
    evidence_lng: float,
    zone_center_lat: float,
    zone_center_lng: float,
) -> dict:
    """
    Checks if evidence location is near the zone center.
    In a full production scenario this would do polygon intersection (PostGIS logic),
    but for this early scaffold we use a haversine distance radius check.
    """
    distance = calculate_distance_km(
        evidence_lat, evidence_lng, zone_center_lat, zone_center_lng
    )

    # Assuming an average zone radius of 5km for urban India
    # If the distance is > 10km, it's a severe mismatch and flagged as high
    # confidence of mismatched location.

    if distance <= 5.0:
        match_level = "inside_zone"
        geo_confidence = 1.0
    elif distance <= 10.0:
        match_level = "near_zone_boundary"
        geo_confidence = 0.7
    else:
        match_level = "outside_zone"
        geo_confidence = 0.0

    return {
        "distance_km": round(distance, 2),
        "match_level": match_level,
        "geo_confidence": geo_confidence,
    }
