"""
DEVTrails — Seed Data Loader

Populates the Supabase database with synthetic demo data:
- Zones (Mumbai, Delhi, Bangalore, Hyderabad — 2 zones each)
- Trigger events (diverse events across cities/zones)
- Platform worker daily stats (synthetic)
- Platform order events (synthetic)

This uses the service-role client to bypass RLS.

Run via CLI:
    python -m backend.app.seed

Or via FastAPI admin endpoint:
    POST /admin/seed (insurer_admin only)
"""

import uuid
from datetime import datetime, timedelta, date
import random
from backend.app.supabase_client import get_supabase_admin


# ── Zone Definitions ──────────────────────────────────────────────
# Approximate center coordinates for demo zones in 4 Indian cities.

ZONES = [
    {"city": "Mumbai",    "zone_name": "Andheri-W",       "center_lat": 19.1364, "center_lng": 72.8296},
    {"city": "Mumbai",    "zone_name": "Bandra-Kurla",    "center_lat": 19.0596, "center_lng": 72.8656},
    {"city": "Delhi",     "zone_name": "Connaught-Place", "center_lat": 28.6315, "center_lng": 77.2167},
    {"city": "Delhi",     "zone_name": "Saket-South",     "center_lat": 28.5244, "center_lng": 77.2066},
    {"city": "Bangalore", "zone_name": "Koramangala",     "center_lat": 12.9352, "center_lng": 77.6245},
    {"city": "Bangalore", "zone_name": "Indiranagar",     "center_lat": 12.9784, "center_lng": 77.6408},
    {"city": "Hyderabad", "zone_name": "Madhapur",        "center_lat": 17.4486, "center_lng": 78.3908},
    {"city": "Hyderabad", "zone_name": "Gachibowli",      "center_lat": 17.4401, "center_lng": 78.3489},
]


# ── Trigger Event Templates ──────────────────────────────────────
# Diverse trigger scenarios across cities, using documented thresholds.

def _make_trigger_events(zone_lookup: dict[str, str]) -> list[dict]:
    """Generate seed trigger events.
    zone_lookup maps 'City-ZoneName' to zone UUID.
    """
    base_date = datetime(2026, 3, 10, 6, 0, 0)
    events = [
        # Rain claim — Mumbai Andheri
        {
            "city": "Mumbai", "zone_id": zone_lookup["Mumbai-Andheri-W"],
            "trigger_family": "rain", "trigger_code": "RAIN_HEAVY",
            "source_ref_id": "R3", "observed_value": 72.0,
            "official_threshold_label": "IMD heavy rainfall (64.5 mm/24h)",
            "product_threshold_value": "64.5 mm",
            "severity_band": "claim", "source_type": "public_source",
            "started_at": base_date.isoformat(),
            "ended_at": (base_date + timedelta(hours=8)).isoformat(),
        },
        # Rain escalation — Mumbai Bandra
        {
            "city": "Mumbai", "zone_id": zone_lookup["Mumbai-Bandra-Kurla"],
            "trigger_family": "rain", "trigger_code": "RAIN_EXTREME",
            "source_ref_id": "R3", "observed_value": 130.0,
            "official_threshold_label": "IMD very heavy rainfall (115.6 mm/24h)",
            "product_threshold_value": "115.6 mm",
            "severity_band": "escalation", "source_type": "public_source",
            "started_at": base_date.isoformat(),
            "ended_at": (base_date + timedelta(hours=10)).isoformat(),
        },
        # AQI claim — Delhi Connaught
        {
            "city": "Delhi", "zone_id": zone_lookup["Delhi-Connaught-Place"],
            "trigger_family": "aqi", "trigger_code": "AQI_SEVERE",
            "source_ref_id": "R1", "observed_value": 340.0,
            "official_threshold_label": "CPCB Very Poor AQI (301-400)",
            "product_threshold_value": "301+",
            "severity_band": "claim", "source_type": "public_source",
            "started_at": (base_date + timedelta(days=1)).isoformat(),
            "ended_at": (base_date + timedelta(days=1, hours=12)).isoformat(),
        },
        # Heat claim — Delhi Saket
        {
            "city": "Delhi", "zone_id": zone_lookup["Delhi-Saket-South"],
            "trigger_family": "heat", "trigger_code": "HEAT_WAVE",
            "source_ref_id": "R4", "observed_value": 46.0,
            "official_threshold_label": "IMD heat-wave (≥45°C plains)",
            "product_threshold_value": "45°C",
            "severity_band": "claim", "source_type": "public_source",
            "started_at": (base_date + timedelta(days=2)).isoformat(),
            "ended_at": (base_date + timedelta(days=2, hours=10)).isoformat(),
        },
        # Traffic delay — Bangalore Koramangala (internal operational)
        {
            "city": "Bangalore", "zone_id": zone_lookup["Bangalore-Koramangala"],
            "trigger_family": "traffic", "trigger_code": "TRAFFIC_SEVERE",
            "source_ref_id": None, "observed_value": 55.0,
            "official_threshold_label": None,
            "product_threshold_value": "40%+ delay",
            "severity_band": "watch", "source_type": "internal_operational",
            "started_at": (base_date + timedelta(days=3)).isoformat(),
            "ended_at": (base_date + timedelta(days=3, hours=6)).isoformat(),
        },
        # Platform outage — Bangalore Indiranagar (internal operational)
        {
            "city": "Bangalore", "zone_id": zone_lookup["Bangalore-Indiranagar"],
            "trigger_family": "outage", "trigger_code": "PLATFORM_OUTAGE",
            "source_ref_id": None, "observed_value": 45.0,
            "official_threshold_label": None,
            "product_threshold_value": "30+ min outage",
            "severity_band": "claim", "source_type": "internal_operational",
            "started_at": (base_date + timedelta(days=4)).isoformat(),
            "ended_at": (base_date + timedelta(days=4, hours=2)).isoformat(),
        },
        # Demand collapse — Hyderabad Madhapur (internal operational)
        {
            "city": "Hyderabad", "zone_id": zone_lookup["Hyderabad-Madhapur"],
            "trigger_family": "demand", "trigger_code": "DEMAND_COLLAPSE",
            "source_ref_id": None, "observed_value": 42.0,
            "official_threshold_label": None,
            "product_threshold_value": "35%+ order drop",
            "severity_band": "watch", "source_type": "internal_operational",
            "started_at": (base_date + timedelta(days=5)).isoformat(),
            "ended_at": (base_date + timedelta(days=5, hours=8)).isoformat(),
        },
        # AQI escalation — Hyderabad Gachibowli
        {
            "city": "Hyderabad", "zone_id": zone_lookup["Hyderabad-Gachibowli"],
            "trigger_family": "aqi", "trigger_code": "AQI_EXTREME",
            "source_ref_id": "R1", "observed_value": 420.0,
            "official_threshold_label": "CPCB Severe AQI (401+)",
            "product_threshold_value": "401+",
            "severity_band": "escalation", "source_type": "public_source",
            "started_at": (base_date + timedelta(days=6)).isoformat(),
            "ended_at": (base_date + timedelta(days=6, hours=14)).isoformat(),
        },
    ]
    return events


def _make_daily_stats(worker_id: str, days: int = 14) -> list[dict]:
    """Generate synthetic daily stats for a worker over the last N days."""
    stats = []
    for i in range(days):
        d = date.today() - timedelta(days=i)
        active_h = round(random.uniform(6.0, 11.0), 1)
        completed = random.randint(8, 25)
        accepted = completed + random.randint(0, 5)
        cancelled = random.randint(0, 3)
        gross = round(completed * random.uniform(55.0, 95.0), 2)
        stats.append({
            "worker_profile_id": worker_id,
            "stat_date": d.isoformat(),
            "active_hours": active_h,
            "completed_orders": completed,
            "accepted_orders": accepted,
            "cancelled_orders": cancelled,
            "gross_earnings_inr": gross,
            "platform_login_minutes": int(active_h * 60 + random.randint(-30, 30)),
            "gps_consistency_score": round(random.uniform(0.70, 0.98), 2),
        })
    return stats


def seed_zones(sb) -> dict[str, str]:
    """Insert seed zones. Returns mapping of 'City-ZoneName' → zone UUID."""
    zone_lookup = {}
    for z in ZONES:
        zone_id = str(uuid.uuid4())
        sb.table("zones").upsert({
            "id": zone_id,
            **z,
        }).execute()
        key = f"{z['city']}-{z['zone_name']}"
        zone_lookup[key] = zone_id
    return zone_lookup


def seed_triggers(sb, zone_lookup: dict[str, str]):
    """Insert seed trigger events using documented thresholds."""
    events = _make_trigger_events(zone_lookup)
    for ev in events:
        sb.table("trigger_events").insert(ev).execute()
    return len(events)


def seed_demo_users(sb) -> dict:
    """Creates demo users in Supabase Auth and corresponding profiles."""
    users_created = {}
    
    # Check if they exist to avoid errors on re-run
    try:
        w_exist = sb.table("profiles").select("id").eq("email", "worker@demo.com").execute()
        if w_exist.data:
            print("   ℹ️ Demo worker already exists, skipping auth creation.")
            users_created["worker_id"] = w_exist.data[0]["id"]
        else:
            w_res = sb.auth.admin.create_user({
                "email": "worker@demo.com",
                "password": "demopassword",
                "email_confirm": True
            })
            w_id = w_res.user.id
            users_created["worker_id"] = w_id
            sb.table("profiles").insert({
                "id": w_id, "role": "worker", "email": "worker@demo.com", "full_name": "Ravi Kumar"
            }).execute()
            sb.table("worker_profiles").insert({
                "profile_id": w_id, "platform_name": "Swiggy", "city": "Bangalore", 
                "vehicle_type": "Bike", "avg_hourly_income_inr": 85.0, 
                "bank_verified": True, "trust_score": 0.85, "gps_consent": True
            }).execute()
            
        a_exist = sb.table("profiles").select("id").eq("email", "admin@demo.com").execute()
        if a_exist.data:
            print("   ℹ️ Demo admin already exists, skipping auth creation.")
            users_created["admin_id"] = a_exist.data[0]["id"]
        else:
            a_res = sb.auth.admin.create_user({
                "email": "admin@demo.com",
                "password": "demopassword",
                "email_confirm": True
            })
            a_id = a_res.user.id
            users_created["admin_id"] = a_id
            sb.table("profiles").insert({
                "id": a_id, "role": "insurer_admin", "email": "admin@demo.com", "full_name": "Neha Sharma"
            }).execute()
            sb.table("insurer_profiles").insert({
                "profile_id": a_id, "company_name": "DEVTrails Insurance", "job_title": "Claims Adjuster"
            }).execute()
            
    except Exception as e:
        print(f"   ⚠️ Auth/Profile seeding error: {e}")
        
    return users_created


def seed_worker_stats(sb, worker_id: str):
    """Seed synthetic daily stats and order events for a worker."""
    if not worker_id:
        return
        
    # Check if already seeded
    existing = sb.table("platform_worker_daily_stats").select("id").eq("worker_profile_id", worker_id).limit(1).execute()
    if existing.data:
        print("   ℹ️ Synthetic stats already exist, skipping.")
        return
        
    stats = _make_daily_stats(worker_id)
    for row in stats:
        sb.table("platform_worker_daily_stats").insert(row).execute()
        
    print(f"   ✅ {len(stats)} daily platform stats created")

def seed_all():
    """Run the full seed process."""
    sb = get_supabase_admin()

    print("🌱 Seeding zones...")
    zone_lookup = seed_zones(sb)
    print(f"   ✅ {len(zone_lookup)} zones created")

    print("🌱 Seeding trigger events...")
    count = seed_triggers(sb, zone_lookup)
    print(f"   ✅ {count} trigger events created")

    print("🌱 Seeding Demo Users...")
    users = seed_demo_users(sb)
    
    if "worker_id" in users:
        print("🌱 Seeding synthetic stats for worker...")
        seed_worker_stats(sb, users["worker_id"])

    print("✅ Seed complete.")
    return {
        "zones": len(zone_lookup),
        "trigger_events": count,
        "worker_seeded": "worker_id" in users,
        "admin_seeded": "admin_id" in users
    }


if __name__ == "__main__":
    seed_all()
