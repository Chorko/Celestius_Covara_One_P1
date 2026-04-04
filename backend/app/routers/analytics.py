"""
Covara One — Analytics Router

Powers the dashboard charts and metrics for the insurer/admin persona.
"""

from fastapi import APIRouter, Depends
from backend.app.dependencies import require_insurer_admin
from backend.app.supabase_client import get_supabase_admin

router = APIRouter(prefix="/analytics", tags=["Analytics"])


from fastapi_cache.decorator import cache

@router.get("/summary", dependencies=[Depends(require_insurer_admin)])
@cache(expire=120)
async def get_dashboard_summary():
    """
    Returns aggregate metrics for the admin dashboard.
    """
    sb = get_supabase_admin()

    # In a real app we'd use SQL aggregation via RPC. For this scaffold,
    # we fetch needed rows and compute in memory.

    # 1. Claims Overview
    claims_resp = (
        sb.table("manual_claims").select("id, claim_status").execute()
    )
    total_claims = len(claims_resp.data)
    # 8-state model: pending = not yet decided; approved = all successful outcomes
    PENDING_STATES = {"submitted", "soft_hold_verification", "fraud_escalated_review"}
    APPROVED_STATES = {"approved", "auto_approved", "paid"}
    pending_claims = sum(
        1 for c in claims_resp.data if c["claim_status"] in PENDING_STATES
    )
    approved_claims = sum(
        1 for c in claims_resp.data if c["claim_status"] in APPROVED_STATES
    )

    # 2. Financials (Payouts & Actuarial Metrics)
    payout_resp = (
        sb.table("payout_recommendations")
        .select("expected_payout, recommended_payout, gross_premium")
        .execute()
    )
    total_expected = sum(p.get("expected_payout") or 0 for p in payout_resp.data)
    total_payouts = sum(p.get("recommended_payout") or 0 for p in payout_resp.data)
    total_premium = sum(p.get("gross_premium") or 0 for p in payout_resp.data)
    
    # Actuarial Calculations
    # Target BCR implies how much of premium goes to expected claims (0.55 - 0.70)
    burning_cost_rate = (total_expected / total_premium) if total_premium > 0 else 0.0
    # Loss ratio is actual payouts vs premium
    loss_ratio = (total_payouts / total_premium) if total_premium > 0 else 0.0


    # 3. Triggers Mix
    trigger_resp = (
        sb.table("trigger_events").select("trigger_family").execute()
    )
    trigger_counts = {}
    for t in trigger_resp.data:
        fam = t["trigger_family"]
        trigger_counts[fam] = trigger_counts.get(fam, 0) + 1

    # 4. Active Policies (Workers)
    worker_resp = sb.table("worker_profiles").select("profile_id").execute()
    active_workers = len(worker_resp.data)

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
    }
