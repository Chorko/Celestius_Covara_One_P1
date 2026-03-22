"""
DEVTrails — Severity Scoring Engine

Computes the Disruption DNA severity score (S) from normalized components.
This score drives the payout scale based on how severe the combined events are.
"""


def normalize_value(val: float, min_val: float, max_val: float) -> float:
    """Normalize a value linearly between 0 and 1 using min/max bounds."""
    if val <= min_val:
        return 0.0
    if val >= max_val:
        return 1.0
    return (val - min_val) / (max_val - min_val)


def calculate_severity(trigger_context: dict) -> dict:
    """
    Computes normalized components and the final S score.
    trigger_context contains values like rain_mm, aqi, temp_c, etc.
    """
    # 1. Normalize individual components based on documented bounds

    # Rain (0mm -> 115.6mm IMD very heavy)
    rain = trigger_context.get("rain_mm", 0.0)
    rain_sev = normalize_value(rain, 0, 115.6)

    # AQI (<=50 -> 401+ CPCB severe)
    aqi = trigger_context.get("aqi", 50.0)
    aqi_sev = normalize_value(aqi, 50, 401)

    # Heat (<=35C -> 47C severe heat)
    heat = trigger_context.get("temp_c", 35.0)
    heat_sev = normalize_value(heat, 35, 47)

    # Traffic (0% -> 80% delay)
    traffic = trigger_context.get("traffic_delay_pct", 0.0)
    # the pct might be 0.45 or 45 based on mock data. Let's assume 0.0 to 1.0 or percentage.
    # The xlsx seed has delay like 0.35, 0.55. So max is 0.80
    traffic_sev = normalize_value(traffic, 0, 0.80)

    # Outage (0 min -> 120 min)
    outage = trigger_context.get("outage_min", 0.0)
    outage_sev = normalize_value(outage, 0, 120)

    # Closure (binary 0 or 1)
    closure = float(trigger_context.get("closure_flag", 0))
    closure_sev = 1.0 if closure >= 1.0 else 0.0

    # Demand drop (0% -> 70% drop)
    demand = trigger_context.get("demand_drop_pct", 0.0)
    demand_sev = normalize_value(demand, 0, 0.70)

    # Accessibility (1.0 -> 0.0 where 0.0 is completely inaccessible)
    # Note: higher severity means lower accessibility
    acc = trigger_context.get("accessibility_score", 1.0)
    acc_sev = 1.0 - normalize_value(acc, 0, 1)

    # 2. Compute composite severity (S)
    # S = 0.23*rain + 0.14*aqi + 0.14*heat + 0.10*traffic + 0.12*outage + 0.10*closure + 0.07*demand + 0.10*access
    s_score = (
        (0.23 * rain_sev)
        + (0.14 * aqi_sev)
        + (0.14 * heat_sev)
        + (0.10 * traffic_sev)
        + (0.12 * outage_sev)
        + (0.10 * closure_sev)
        + (0.07 * demand_sev)
        + (0.10 * acc_sev)
    )

    return {
        "severity_score_s": round(s_score, 4),
        "components": {
            "rain_sev": round(rain_sev, 4),
            "aqi_sev": round(aqi_sev, 4),
            "heat_sev": round(heat_sev, 4),
            "traffic_sev": round(traffic_sev, 4),
            "outage_sev": round(outage_sev, 4),
            "closure_sev": round(closure_sev, 4),
            "demand_sev": round(demand_sev, 4),
            "access_sev": round(acc_sev, 4),
        },
    }
