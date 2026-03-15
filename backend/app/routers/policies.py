"""
DEVTrails — Policies & Premium Router

Handles dynamic premium quotes and policy activation.
"""

from fastapi import APIRouter, Depends, HTTPException
from backend.app.dependencies import get_current_user, require_worker
from backend.app.supabase_client import get_supabase_admin
from backend.app.services.pricing import calculate_policy_metrics, calculate_payout

router = APIRouter(prefix="/policies", tags=["Policies"])

@router.get("/quote")
async def get_premium_quote(user: dict = Depends(require_worker)):
    """
    Computes and returns the weekly premium quote and payout cap for the worker.
    """
    sb = get_supabase_admin()
    
    # Load worker context to compute B, E, C
    worker_resp = sb.table("worker_profiles").select("*").eq("profile_id", user["id"]).maybe_single().execute()
    if not worker_resp.data:
        raise HTTPException(status_code=400, detail="Worker profile required for a quote.")
        
    worker_context = worker_resp.data
    
    # We assume average shift length of 9 hours mostly if not provided (though daily stats has it).
    # Since we don't have shift_hours on worker_profile directly, we default it to 9 for the quote.
    worker_context["shift_hours"] = 9.0
    worker_context["trust_score"] = worker_context.get("trust_score", 0.8)
    # Mock gps and acc for quote
    worker_context["gps_consistency_score"] = 0.9
    worker_context["accessibility_score"] = 1.0 
    
    base_metrics = calculate_policy_metrics(worker_context)
    
    # Compute an expected payout/premium using a baseline severe scenario (S=1.0) and p=0.15
    # to show the worker what their coverage looks like.
    quote = calculate_payout(
        covered_income_b=base_metrics["covered_income_b"],
        severity_s=1.0, # quoting worst-case for max payout info
        exposure_e=base_metrics["exposure_e"],
        confidence_base=base_metrics["confidence_base"],
        fraud_penalty=0.0, # zero fraud initially
        claim_probability_p=0.15
    )
    
    return {
        "covered_weekly_income": base_metrics["covered_income_b"],
        "weekly_premium_inr": quote["gross_premium"],
        "max_payout_cap_inr": quote["payout_cap"],
        "exposure_multiplier": base_metrics["exposure_e"],
        "confidence_multiplier": base_metrics["confidence_base"]
    }

@router.post("/activate")
async def activate_policy(user: dict = Depends(require_worker)):
    """
    Mocks activating a weekly policy. 
    In a full DB, this would write to a 'policies' table.
    For this early scaffold, we simply return a success token.
    """
    import datetime
    now = datetime.datetime.utcnow()
    valid_until = now + datetime.timedelta(days=7)
    
    return {
        "status": "active",
        "message": "Weekly coverage activated.",
        "activated_at": now.isoformat() + "Z",
        "valid_until": valid_until.isoformat() + "Z",
        "policy_id": f"POL-{user['id'][:8]}-{now.strftime('%Y%m%d')}"
    }
