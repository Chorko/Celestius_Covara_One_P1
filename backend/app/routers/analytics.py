"""
Covara One — Analytics Router

Powers the dashboard charts and metrics for the insurer/admin persona.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from backend.app.dependencies import require_insurer_admin
from backend.app.supabase_client import get_supabase_admin

router = APIRouter(prefix="/analytics", tags=["Analytics"])


from fastapi_cache.decorator import cache


CITY_TIERS: dict[str, set[str]] = {
    "tier_1": {
        "Mumbai",
        "Delhi",
        "Bangalore",
        "Bengaluru",
        "Chennai",
        "Hyderabad",
        "Kolkata",
        "Pune",
        "Ahmedabad",
    },
    "tier_2": {
        "Jaipur",
        "Lucknow",
        "Chandigarh",
        "Indore",
        "Bhopal",
        "Kochi",
        "Coimbatore",
        "Surat",
        "Nagpur",
    },
    "tier_3": {
        "Trivandrum",
        "Guwahati",
        "Vadodara",
        "Patna",
        "Kanpur",
        "Vizag",
        "Visakhapatnam",
        "Nashik",
    },
}


def _days_to_from_iso(days: int | None) -> str | None:
    if not days:
        return None
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _normalize_city_values(
    city: str | None,
    city_tier: Literal["tier_1", "tier_2", "tier_3"] | None,
) -> list[str] | None:
    if city:
        return [city.strip()]
    if city_tier:
        values = CITY_TIERS.get(city_tier, set())
        return sorted(values)
    return None


def _count_exact(query, select_field: str = "id") -> int:
    resp = query.select(select_field, count="exact", head=True).execute()
    return int(resp.count or 0)

@router.get("/summary", dependencies=[Depends(require_insurer_admin)])
@cache(expire=120)
async def get_dashboard_summary(
    days: int | None = Query(default=None, ge=1, le=365),
    city: str | None = Query(default=None),
    city_tier: Literal["tier_1", "tier_2", "tier_3"] | None = Query(default=None),
):
    """
    Returns aggregate metrics for the admin dashboard.

    Optional filters:
    - days: trailing time window (1-365)
    - city: exact city
    - city_tier: tier-based city grouping (ignored when city is provided)
    """
    sb = get_supabase_admin()
    from_iso = _days_to_from_iso(days)
    city_values = _normalize_city_values(city=city, city_tier=city_tier)

    # Resolve workers first for optional city/tier scoped claim filtering.
    worker_ids: list[str] | None = None
    if city_values is not None:
        worker_resp = (
            sb.table("worker_profiles")
            .select("profile_id")
            .in_("city", city_values)
            .execute()
        )
        worker_ids = [str(row["profile_id"]) for row in (worker_resp.data or [])]

    def claims_query():
        query = sb.table("manual_claims")
        if from_iso:
            query = query.gte("claimed_at", from_iso)
        if worker_ids is not None:
            if worker_ids:
                query = query.in_("worker_profile_id", worker_ids)
            else:
                # Force empty result when no workers match city/tier filter.
                query = query.in_("worker_profile_id", ["00000000-0000-0000-0000-000000000000"])
        return query

    # 1. Claims Overview (exact counts via PostgREST count)
    total_claims = _count_exact(claims_query())

    # 8-state model: pending = not yet decided; approved = successful outcomes
    PENDING_STATES = {"submitted", "soft_hold_verification", "fraud_escalated_review"}
    APPROVED_STATES = {"approved", "auto_approved", "paid"}
    pending_claims = _count_exact(
        claims_query().in_("claim_status", list(PENDING_STATES))
    )
    approved_claims = _count_exact(
        claims_query().in_("claim_status", list(APPROVED_STATES))
    )

    # 2. Financials (scoped rows only)
    payout_rows: list[dict] = []
    payout_query = sb.table("payout_recommendations").select(
        "claim_id, expected_payout, recommended_payout, gross_premium"
    )
    if from_iso:
        payout_query = payout_query.gte("created_at", from_iso)

    if city_values is not None:
        claim_rows = claims_query().select("id").execute().data or []
        claim_ids = [str(row["id"]) for row in claim_rows]
        if claim_ids:
            payout_rows = payout_query.in_("claim_id", claim_ids).execute().data or []
    else:
        payout_rows = payout_query.execute().data or []

    total_expected = sum(p.get("expected_payout") or 0 for p in payout_rows)
    total_payouts = sum(p.get("recommended_payout") or 0 for p in payout_rows)
    total_premium = sum(p.get("gross_premium") or 0 for p in payout_rows)
    
    # Actuarial Calculations
    # Target BCR implies how much of premium goes to expected claims (0.55 - 0.70)
    burning_cost_rate = (total_expected / total_premium) if total_premium > 0 else 0.0
    # Loss ratio is actual payouts vs premium
    loss_ratio = (total_payouts / total_premium) if total_premium > 0 else 0.0

    # 3. Triggers Mix
    trigger_query = sb.table("trigger_events").select("trigger_family, city")
    if from_iso:
        trigger_query = trigger_query.gte("started_at", from_iso)
    if city_values:
        trigger_query = trigger_query.in_("city", city_values)
    trigger_resp = trigger_query.execute()

    trigger_counts = {}
    for t in (trigger_resp.data or []):
        fam = t["trigger_family"]
        trigger_counts[fam] = trigger_counts.get(fam, 0) + 1

    # 4. Active Policies (Workers)
    if worker_ids is None:
        active_workers = _count_exact(sb.table("worker_profiles"), "profile_id")
    else:
        active_workers = len(worker_ids)

    return {
        "metrics": {
            "total_claims": total_claims,
            "pending_claims": pending_claims,
            "approved_claims": approved_claims,
            "total_expected_payout_inr": round(total_expected, 2),
            "total_recommended_payout_inr": round(total_payouts, 2),
            "loss_ratio": round(loss_ratio, 3),
            "burning_cost_rate": round(burning_cost_rate, 3),
            "active_workers": active_workers,
        },
        "charts": {"trigger_mix": trigger_counts},
        "filters": {
            "days": days,
            "city": city,
            "city_tier": city_tier,
            "from_iso": from_iso,
        },
    }
