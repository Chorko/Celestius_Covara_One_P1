"""
DEVTrails — Analytics Router

Powers the dashboard charts and metrics for the insurer/admin persona.
"""

from fastapi import APIRouter, Depends
from backend.app.dependencies import require_insurer_admin
from backend.app.supabase_client import get_supabase_admin

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", dependencies=[Depends(require_insurer_admin)])
async def get_dashboard_summary():
    """
    Returns aggregate metrics for the admin dashboard.
    """
    sb = get_supabase_admin()
    
    # In a real app we'd use SQL aggregation via RPC. For this scaffold,
    # we fetch needed rows and compute in memory.
    
    # 1. Claims Overview
    claims_resp = sb.table("manual_claims").select("id, claim_status").execute()
    total_claims = len(claims_resp.data)
    pending_claims = sum(1 for c in claims_resp.data if c["claim_status"] in ["submitted", "held"])
    approved_claims = sum(1 for c in claims_resp.data if c["claim_status"] == "approved")
    
    # 2. Financials (Payouts)
    payout_resp = sb.table("payout_recommendations").select("expected_payout, recommended_payout").execute()
    total_expected = sum(p["expected_payout"] or 0 for p in payout_resp.data)
    total_payouts = sum(p["recommended_payout"] or 0 for p in payout_resp.data)
    
    # 3. Triggers Mix
    trigger_resp = sb.table("trigger_events").select("trigger_family").execute()
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
            "active_workers": active_workers
        },
        "charts": {
            "trigger_mix": trigger_counts
        }
    }
