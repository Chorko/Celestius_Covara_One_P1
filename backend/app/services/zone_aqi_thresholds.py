"""
Covara One — Zone-Aware AQI Threshold Engine

India's cities have dramatically different baseline AQI levels:
  - Mumbai: 60-80 (coastal winds, sea breeze ventilation)
  - Delhi: 150-250 (landlocked, high vehicular + industrial + crop burning load)
  - Bangalore: 40-60 (elevated city, good natural ventilation)
  - Hyderabad: 80-120 (semi-arid, high dust baseline)

Additionally, within a city, zone type matters for impact:
  - Urban commercial zones (Connaught Place, BKC): better drainage, covered
    high-rises, workers have option to shelter. Thresholds are slightly higher.
  - Mixed residential-commercial zones (Andheri-W, Koramangala): moderate.
  - Peri-urban / semi-rural zones: exposed roads, no shelter, worse water
    drainage → triggers should fire at LOWER absolute AQI values.

This module is used by trigger_evaluator.py to apply contextually appropriate
AQI thresholds instead of a single fixed national threshold.

References:
  - CPCB AQI categories: Good(0-50), Satisfactory(51-100), Moderate(101-200),
    Poor(201-300), Very Poor(301-400), Severe(401+)
  - Mumbai baseline: CPCB MPCB stations (Andheri, Bandra, BKC avg 60-80)
  - Delhi baseline: CPCB Delhi stations consistent at 150-250 winter, 100-150 summer
  - Bangalore baseline: CPCB Karnataka 40-60
  - Hyderabad baseline: CPCB Telangana 80-120
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone

logger = logging.getLogger("covara.zone_aqi_thresholds")


# ── City Baseline AQI (annual average PM2.5-based) ────────────────────────────

CITY_BASELINES: dict[str, dict] = {
    "mumbai": {
        "avg_aqi": 70,
        "zone_type": "coastal_urban",
        "drainage_quality": "good",  # BMC drainage infrastructure
        "aqi_watch": 150,     # Moderate → CPCB band 3 start
        "aqi_claim": 250,     # Poor → CPCB band 4
        "aqi_extreme": 350,   # Very Poor start
        "description": "Coastal city with sea-breeze ventilation. Good BMC drainage. Higher thresholds vs inland cities."
    },
    "delhi": {
        "avg_aqi": 185,
        "zone_type": "landlocked_urban",
        "drainage_quality": "moderate",
        "aqi_watch": 251,     # Very Poor threshold (since Poor=200 is the Delhi 'normal')
        "aqi_claim": 351,     # Severe start — Delhi regular baseline is~200
        "aqi_extreme": 401,   # True extreme
        "description": "Chronically high AQI baseline. Triggers calibrated above 'normal bad' Delhi levels."
    },
    "bangalore": {
        "avg_aqi": 55,
        "zone_type": "elevated_urban",
        "drainage_quality": "moderate",
        "aqi_watch": 101,     # Moderate start — Bangalore is clean city
        "aqi_claim": 201,     # Poor threshold
        "aqi_extreme": 301,   # Very Poor
        "description": "Elevated city with good natural ventilation. Low baseline → triggers fire at lower AQI."
    },
    "hyderabad": {
        "avg_aqi": 100,
        "zone_type": "semi_arid_urban",
        "drainage_quality": "moderate",
        "aqi_watch": 151,     # Poor threshold start
        "aqi_claim": 251,     # Very Poor start
        "aqi_extreme": 351,   # Severe start
        "description": "High dust baseline due to semi-arid terrain. Moderate thresholds."
    },
    "chennai": {
        "avg_aqi": 65,
        "zone_type": "coastal_urban",
        "drainage_quality": "moderate",
        "aqi_watch": 151,
        "aqi_claim": 251,
        "aqi_extreme": 351,
        "description": "Coastal city similar to Mumbai profile."
    },
    "pune": {
        "avg_aqi": 80,
        "zone_type": "urban",
        "drainage_quality": "moderate",
        "aqi_watch": 151,
        "aqi_claim": 251,
        "aqi_extreme": 351,
        "description": "Hill-ringed city, moderate ventilation."
    },
}

# ── Zone Type Adjustments ─────────────────────────────────────────────────────
# Applied on top of city baseline thresholds.
# Urban core: +25 (workers have shelter options, better buildings, covered OA)
# Mixed suburban: +0 (baseline)
# Peri-urban / exposed: -25 (no shelter, poor roads, vulnerable)

ZONE_TYPE_ADJUSTMENTS: dict[str, int] = {
    "urban_core": +25,       # Connaught Place, Bandra-Kurla, Koramangala tech park
    "mixed": 0,              # Andheri-W, Madhapur, Indiranagar residential
    "peri_urban": -25,       # Outer areas, transit corridors
}

# Zone name → zone type mapping for known seeded zones
KNOWN_ZONE_TYPES: dict[str, str] = {
    "Andheri-W": "mixed",
    "Bandra-Kurla": "urban_core",
    "Connaught-Place": "urban_core",
    "Saket-South": "mixed",
    "Koramangala": "mixed",
    "Indiranagar": "mixed",
    "Madhapur": "urban_core",
    "Gachibowli": "urban_core",
}


def get_aqi_thresholds_for_zone(sb, zone_id: str, city: str, zone_name: str = "") -> dict:
    """
    Returns calibrated AQI trigger thresholds (watch/claim/extreme) for a
    specific zone.
    
    Order of precedence:
      1. Dynamic DB thresholds from `zone_monthly_thresholds` (current month)
      2. Static city+zone fallback (from CITY_BASELINES and ZONE_TYPE_ADJUSTMENTS)
      3. CPCB National Standard (pure fallback)
    """
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    
    # ── Try DB first ──
    if sb and zone_id:
        try:
            resp = sb.table("zone_monthly_thresholds") \
                .select("*") \
                .eq("zone_id", zone_id) \
                .eq("year_month", current_month) \
                .eq("metric", "aqi") \
                .maybe_single() \
                .execute()
                
            data = resp.data
            if data:
                return {
                    "watch": data["watch_threshold"],
                    "claim": data["claim_threshold"],
                    "extreme": data["extreme_threshold"],
                    "city_baseline_aqi": data.get("observed_p50"),  # roughly median
                    "zone_type": "dynamic",
                    "zone_type_adjustment": 0,
                    "city_description": f"Dynamic monthly bounds based on real observations (n={data.get('sample_count',0)})",
                    "source": "dynamic_db",
                }
        except Exception as e:
            logger.warning(f"Failed to fetch dynamic threshold for {zone_id}: {e}. Falling back to static.")

    # ── Static Fallback ──
    city_key = city.lower().strip()
    city_config = CITY_BASELINES.get(city_key)

    if not city_config:
        # Fallback to CPCB national standard thresholds
        logger.debug(f"No city-specific AQI config for '{city}' — using national CPCB standard")
        return {
            "watch": 201,      # CPCB: Poor band starts at 201
            "claim": 301,      # CPCB: Very Poor band
            "extreme": 401,    # CPCB: Severe band
            "city_baseline_aqi": None,
            "zone_type": "standard",
            "source": "national_cpcb_standard",
        }

    # Resolve zone type
    zone_type = KNOWN_ZONE_TYPES.get(zone_name, "mixed")
    adjustment = ZONE_TYPE_ADJUSTMENTS.get(zone_type, 0)

    watch_threshold = city_config["aqi_watch"] + adjustment
    claim_threshold = city_config["aqi_claim"] + adjustment
    extreme_threshold = city_config["aqi_extreme"] + adjustment

    # Never let thresholds go below CPCB absolute minimums
    watch_threshold = max(watch_threshold, 101)    # At minimum "Moderate"
    claim_threshold = max(claim_threshold, 201)    # At minimum "Poor"
    extreme_threshold = max(extreme_threshold, 301)  # At minimum "Very Poor"

    return {
        "watch": watch_threshold,
        "claim": claim_threshold,
        "extreme": extreme_threshold,
        "city_baseline_aqi": city_config["avg_aqi"],
        "zone_type": zone_type,
        "zone_type_adjustment": adjustment,
        "city_description": city_config["description"],
        "source": "zone_calibrated_static",
    }


def evaluate_aqi_for_zone(sb, aqi_value: float, zone_id: str, city: str, zone_name: str = "") -> tuple[str, str, str] | None:
    """
    Evaluate AQI against zone-calibrated thresholds.
    """
    thresholds = get_aqi_thresholds_for_zone(sb, zone_id, city, zone_name)

    if aqi_value >= thresholds["extreme"]:
        return (
            "AQI_EXTREME",
            "escalation",
            f"Extreme AQI: {aqi_value:.0f} ≥ {thresholds['extreme']} "
            f"[{city} extreme threshold, zone: {zone_name or 'unknown'}]"
        )
    elif aqi_value >= thresholds["claim"]:
        return (
            "AQI_SEVERE",
            "claim",
            f"Severe AQI: {aqi_value:.0f} ≥ {thresholds['claim']} "
            f"[{city} claim threshold, baseline AQI {thresholds['city_baseline_aqi']}]"
        )
    elif aqi_value >= thresholds["watch"]:
        return (
            "AQI_CAUTION",
            "watch",
            f"AQI caution: {aqi_value:.0f} ≥ {thresholds['watch']} "
            f"[{city} watch threshold, zone type: {thresholds['zone_type']}]"
        )
    return None


# ── Rain Drainage Thresholds (zone-aware) ────────────────────────────────────
# Urban zones with good drainage systems (Mumbai BMC, Delhi NMS) can handle
# more rain before triggering. Rural/peri-urban areas have lower thresholds.

RAIN_DRAINAGE_ADJUSTMENTS: dict[str, dict] = {
    "mumbai": {
        "urban_core": {
            "watch": 64.5,      # IMD: Heavy rainfall starts
            "claim": 115.6,     # IMD: Very Heavy rainfall
            "extreme": 204.4,   # IMD: Extremely Heavy
        },
        "mixed": {
            "watch": 48.0,      # Lower — mixed drainage quality
            "claim": 90.0,
            "extreme": 170.0,
        },
        "peri_urban": {
            "watch": 35.0,      # Poor drainage, low tolerance
            "claim": 64.5,
            "extreme": 115.6,
        },
    },
    "delhi": {
        "urban_core": {"watch": 64.5, "claim": 115.6, "extreme": 204.4},
        "mixed": {"watch": 48.0, "claim": 90.0, "extreme": 170.0},
        "peri_urban": {"watch": 25.0, "claim": 48.0, "extreme": 90.0},
    },
    # Default for other cities
    "_default": {
        "urban_core": {"watch": 64.5, "claim": 115.6, "extreme": 204.4},
        "mixed": {"watch": 48.0, "claim": 90.0, "extreme": 170.0},
        "peri_urban": {"watch": 35.0, "claim": 64.5, "extreme": 115.6},
    },
}


def get_rain_thresholds_for_zone(city: str, zone_name: str = "") -> dict:
    """
    Returns rain trigger thresholds calibrated for city + zone drainage capacity.
    """
    city_key = city.lower().strip()
    zone_type = KNOWN_ZONE_TYPES.get(zone_name, "mixed")

    city_config = RAIN_DRAINAGE_ADJUSTMENTS.get(city_key, RAIN_DRAINAGE_ADJUSTMENTS["_default"])
    zone_config = city_config.get(zone_type, city_config["mixed"])

    return {
        "watch": zone_config["watch"],
        "claim": zone_config["claim"],
        "extreme": zone_config["extreme"],
        "zone_type": zone_type,
        "city": city,
        "source": "zone_drainage_calibrated",
    }
