"""
Covara One — Dynamic Threshold Engine
Computes and stores dynamic, monthly, zone-aware environmental thresholds.

In a real production environment, this engine runs on the 1st of every month via cron.
It queries 30 days of historical data from external APIs (IMD, CPCB) for every
configured zone, calculates distribution percentiles, and writes thresholds to
the `zone_monthly_thresholds` table.

For this Covara One build, we simulate the historical data ingestion using
realistic statistical distributions per city to calculate the p50/p75/p90 percentiles.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
import numpy as np

# Use the established city baselines to generate realistic historical distributions
from .zone_aqi_thresholds import CITY_BASELINES, KNOWN_ZONE_TYPES, ZONE_TYPE_ADJUSTMENTS

logger = logging.getLogger("covara.dynamic_thresholds")

def compute_and_upsert_monthly_thresholds(sb) -> dict:
    """
    Computes monthly dynamic thresholds for all zones and upserts them
    into the zone_monthly_thresholds table.
    """
    # 1. Fetch all zones
    resp = sb.table("zones").select("id, city, zone_name, zone_type").execute()
    zones = resp.data
    if not zones:
        return {"status": "error", "message": "No zones found in database."}

    current_time = datetime.now(timezone.utc)
    current_month = current_time.strftime("%Y-%m")
    expires_time = current_time + timedelta(days=60)
    expires_at_iso = expires_time.isoformat()
    
    upsert_data = []

    for zone in zones:
        city_key = zone["city"].lower().strip()
        # Fallback to pure synthetic data if city is unknown
        city_config = CITY_BASELINES.get(city_key, {"avg_aqi": 100})
        
        avg_aqi = city_config["avg_aqi"]
        zone_type = zone.get("zone_type") or KNOWN_ZONE_TYPES.get(zone["zone_name"], "mixed")
        adjustment = ZONE_TYPE_ADJUSTMENTS.get(zone_type, 0)
        
        # ── 1. Simulate 30 days of historical AQI data ──
        # Use log-normal distribution around the average to simulate realistic AQI spikes
        # Scale determines the spread
        scale = 0.3 if city_key == 'delhi' else 0.2 
        # mu is adjusted so the mean closely matches the baseline
        mu = np.log(avg_aqi) - (scale**2 / 2)
        history = np.random.lognormal(mean=mu, sigma=scale, size=30)
        
        # Calculate percentiles
        p25 = np.percentile(history, 25)
        p50 = np.percentile(history, 50)  # Median
        p75 = np.percentile(history, 75)
        p90 = np.percentile(history, 90)
        p99 = np.percentile(history, 99)
        mean_val = np.mean(history)
        std_val = np.std(history)

        # ── 2. Derive triggering thresholds ──
        # Business Logic:
        # Watch = 40% above median
        # Claim = 30% above 75th percentile
        # Extreme = 20% above 90th percentile
        calc_watch = p50 * 1.40
        calc_claim = p75 * 1.30
        calc_extreme = p90 * 1.20
        
        # Apply zone-type structural adjustments (+25 for urban_core, etc)
        calc_watch += adjustment
        calc_claim += adjustment
        calc_extreme += adjustment

        # Clamp to CPCB absolute minimums (We never trigger 'Severe' if AQI is <301)
        # Even if Bangalore has clean air, a 'claim' payout still requires meaningful real-world disruption
        watch_final = max(calc_watch, 101)    # CPCB Moderate
        claim_final = max(calc_claim, 201)    # CPCB Poor
        extreme_final = max(calc_extreme, 301) # CPCB Very Poor

        upsert_data.append({
            "zone_id": zone["id"],
            "year_month": current_month,
            "metric": "aqi",
            "observed_mean": round(float(mean_val), 2),
            "observed_stddev": round(float(std_val), 2),
            "observed_p25": round(float(p25), 2),
            "observed_p50": round(float(p50), 2),
            "observed_p75": round(float(p75), 2),
            "observed_p90": round(float(p90), 2),
            "observed_p99": round(float(p99), 2),
            "sample_count": 30,
            "watch_threshold": round(float(watch_final), 2),
            "claim_threshold": round(float(claim_final), 2),
            "extreme_threshold": round(float(extreme_final), 2),
            "data_source": "dynamic_simulation",
            "computed_at": current_time.isoformat(),
            "expires_at": expires_at_iso
        })

    # Upsert to Supabase
    try:
        # Using returning='minimal' to avoid fetching the large payload back
        res = sb.table("zone_monthly_thresholds").upsert(
            upsert_data, 
            on_conflict="zone_id,year_month,metric"
        ).execute()
        
        logger.info(f"Successfully computed and upserted dynamic thresholds for {len(upsert_data)} zones.")
        return {
            "status": "success", 
            "message": f"Computed {len(upsert_data)} dynamic thresholds.",
            "month": current_month
        }
    except Exception as e:
        logger.error(f"Failed to upsert dynamic thresholds: {str(e)}")
        return {"status": "error", "message": str(e)}

