"""
Covara One — Zones Router

Provides zone listing for city selection during onboarding,
claim zone matching, and trigger zone display.
"""

from fastapi import APIRouter, HTTPException
from backend.app.supabase_client import get_supabase_admin

router = APIRouter(prefix="/zones", tags=["Zones"])


from fastapi_cache.decorator import cache

@router.get("/")
@cache(expire=3600)
async def list_zones(city: str | None = None):
    """List operational zones, optionally filtered by city.

    Returns zone id, name, city, and center coordinates.
    Polygon GeoJSON is excluded from list view for performance.
    """
    sb = get_supabase_admin()
    query = sb.table("zones").select(
        "id, city, zone_name, center_lat, center_lng"
    )

    if city:
        query = query.eq("city", city)

    resp = query.order("city").order("zone_name").execute()
    return {"zones": resp.data, "count": len(resp.data)}


@router.get("/{zone_id}")
async def get_zone_detail(zone_id: str):
    """Get full zone detail including polygon GeoJSON."""
    sb = get_supabase_admin()
    resp = (
        sb.table("zones")
        .select("*")
        .eq("id", zone_id)
        .maybe_single()
        .execute()
    )
    if not resp.data:  # type: ignore
        raise HTTPException(status_code=404, detail="Zone not found")
    return resp.data  # type: ignore


@router.get("/cities/list")
async def list_cities():
    """Return distinct cities that have zones defined."""
    sb = get_supabase_admin()
    resp = sb.table("zones").select("city").execute()
    cities = sorted(set(row["city"] for row in resp.data)) if resp.data else []
    return {"cities": cities}
