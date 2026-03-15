"""
DEVTrails — Workers Router

CRUD for worker profiles. Used by:
- Worker app (view/update own profile)
- Insurer app (view worker records, read-only)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from backend.app.dependencies import get_current_user, require_worker, require_insurer_admin
from backend.app.supabase_client import get_supabase_admin

router = APIRouter(prefix="/workers", tags=["Workers"])


class WorkerProfileUpdate(BaseModel):
    """Fields a worker can update on their own profile."""
    platform_name: str | None = None
    city: str | None = None
    preferred_zone_id: str | None = None
    vehicle_type: str | None = None
    avg_hourly_income_inr: float | None = None
    gps_consent: bool | None = None


# ── Worker-facing endpoints ────────────────────────────────────────

@router.get("/me")
async def get_my_worker_profile(user: dict = Depends(require_worker)):
    """Return the authenticated worker's full profile (profiles + worker_profiles)."""
    sb = get_supabase_admin()
    resp = (
        sb.table("worker_profiles")
        .select("*, profiles(*)")
        .eq("profile_id", user["id"])
        .maybe_single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Worker profile not found.")
    return resp.data


@router.put("/me")
async def update_my_worker_profile(
    body: WorkerProfileUpdate,
    user: dict = Depends(require_worker),
):
    """Update the authenticated worker's profile."""
    sb = get_supabase_admin()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    resp = (
        sb.table("worker_profiles")
        .update(updates)
        .eq("profile_id", user["id"])
        .execute()
    )
    return {"status": "updated", "fields": list(updates.keys())}


@router.get("/me/stats")
async def get_my_worker_stats(user: dict = Depends(require_worker)):
    """Return historical logic. If new user, dynamically synthesize 14 days of realistic platform stats."""
    sb = get_supabase_admin()
    
    # 1. Fetch real stats if they exist
    resp = sb.table("platform_worker_daily_stats").select("*").eq("worker_profile_id", user["id"]).order("stat_date", desc=False).execute()
    
    if resp.data and len(resp.data) > 0:
        return {"stats": resp.data}
        
    # 2. If new user, dynamically generate 14 days of history to power the UI
    import datetime
    import random
    
    worker_resp = sb.table("worker_profiles").select("avg_hourly_income_inr").eq("profile_id", user["id"]).maybe_single().execute()
    hourly_rate = float(worker_resp.data.get("avg_hourly_income_inr", 85.0)) if worker_resp.data else 85.0
    
    synthetic_stats = []
    today = datetime.date.today()
    
    for i in range(14, 0, -1):
        stat_date = today - datetime.timedelta(days=i)
        
        # Simulate gig-worker variance (some days slow, some busy, some off)
        is_day_off = random.random() < 0.15
        
        if is_day_off:
            active_h = 0.0
            gross = 0.0
        else:
            active_h = float(f"{random.uniform(5.5, 11.0):.1f}")
            # Add up to 20% variance on hourly rate dynamically
            daily_rate = hourly_rate * random.uniform(0.8, 1.25)
            gross = float(f"{active_h * daily_rate:.2f}")
            
        synthetic_stats.append({
            "worker_profile_id": user["id"],
            "stat_date": stat_date.isoformat(),
            "active_hours": active_h,
            "completed_orders": int(active_h * 1.8),
            "accepted_orders": int(active_h * 2),
            "cancelled_orders": 0 if is_day_off else random.randint(0, 2),
            "gross_earnings_inr": gross,
            "platform_login_minutes": int(active_h * 60) + random.randint(10, 45)
        })
        
    # We choose not to write these to DB so we don't spam the DB during demo resets,
    # but the frontend Recharts component will render them beautifully.
    return {"stats": synthetic_stats}


# ── Insurer-facing endpoints (read-only) ───────────────────────────

@router.get("/", dependencies=[Depends(require_insurer_admin)])
async def list_workers(city: str | None = None, limit: int = 50, offset: int = 0):
    """List worker profiles. Insurer/admin only."""
    sb = get_supabase_admin()
    query = sb.table("worker_profiles").select("*, profiles(full_name, email)")

    if city:
        query = query.eq("city", city)

    resp = query.range(offset, offset + limit - 1).execute()
    return {"workers": resp.data, "count": len(resp.data)}


@router.get("/{worker_id}", dependencies=[Depends(require_insurer_admin)])
async def get_worker_detail(worker_id: str):
    """Get a single worker's full profile. Insurer/admin only."""
    sb = get_supabase_admin()
    resp = (
        sb.table("worker_profiles")
        .select("*, profiles(full_name, email, phone, created_at)")
        .eq("profile_id", worker_id)
        .maybe_single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Worker not found.")
    return resp.data
