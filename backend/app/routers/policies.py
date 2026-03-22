"""
Covara One — Policies & Premium Router

Handles dynamic premium quotes and policy activation.
Supports exactly two plans: Essential and Plus.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from backend.app.dependencies import require_worker
from backend.app.supabase_client import get_supabase_admin
from backend.app.services.pricing import (
    calculate_policy_metrics,
    calculate_payout,
)
from backend.app.services.claim_pipeline import (
    PLAN_WEEKLY_BENEFITS,
    PAYOUT_BANDS,
)

router = APIRouter(prefix="/policies", tags=["Policies"])

# ── Two plans only ────────────────────────────────────────────────────────
VALID_PLANS = ("essential", "plus")

# Plan uplift factor: scales the premium (and payout cap) proportionally to
# the plan's weekly benefit relative to the Essential baseline.
# Plus = ₹4,500 / ₹3,000 = 1.5 × Essential.
_ESSENTIAL_BENEFIT = PLAN_WEEKLY_BENEFITS["essential"]
PLAN_UPLIFT: dict[str, float] = {
    plan: round(benefit / _ESSENTIAL_BENEFIT, 6)
    for plan, benefit in PLAN_WEEKLY_BENEFITS.items()
}


class ActivatePolicyRequest(BaseModel):
    plan: str = "essential"  # "essential" or "plus"


@router.get("/quote")
async def get_premium_quote(
    plan: str = Query("essential", description="Plan: 'essential' or 'plus'"),
    user: dict = Depends(require_worker),
):
    """
    Computes and returns the weekly premium quote with parametric
    payout bands for the selected plan.
    """
    if plan not in VALID_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan '{plan}'. Must be 'essential' or 'plus'.",
        )

    sb = get_supabase_admin()

    # Load worker context to compute B, E, C
    worker_resp = (
        sb.table("worker_profiles")
        .select("*")
        .eq("profile_id", user["id"])
        .maybe_single()
        .execute()
    )
    if not worker_resp.data:  # type: ignore
        raise HTTPException(
            status_code=400, detail="Worker profile required for a quote."
        )

    worker_context = worker_resp.data  # type: ignore

    # Default shift_hours and signal scores for quote
    worker_context["shift_hours"] = 9.0  # type: ignore
    worker_context["trust_score"] = worker_context.get("trust_score", 0.8)  # type: ignore
    worker_context["gps_consistency_score"] = 0.9  # type: ignore
    worker_context["accessibility_score"] = 1.0  # type: ignore

    base_metrics = calculate_policy_metrics(worker_context)  # type: ignore

    # Compute an expected payout/premium using a baseline severe scenario
    # (S=1.0) and p=0.15 to show the worker what their coverage looks like.
    # The plan uplift factor scales the premium (and cap) proportionally to
    # the selected plan's weekly benefit, so Plus costs more than Essential.
    plan_uplift = PLAN_UPLIFT[plan]
    quote = calculate_payout(
        covered_income_b=base_metrics["covered_income_b"],
        severity_s=1.0,  # quoting worst-case for max payout info
        exposure_e=base_metrics["exposure_e"],
        confidence_base=base_metrics["confidence_base"],
        fraud_penalty=0.0,  # zero fraud initially
        claim_probability_p=0.15,
        outlier_uplift_u=plan_uplift,
    )

    # ── Parametric payout ladder for selected plan ─────────────────────
    weekly_benefit = PLAN_WEEKLY_BENEFITS[plan]
    payout_bands = []
    for band_num, band_info in sorted(PAYOUT_BANDS.items()):
        payout_bands.append(
            {
                "band": band_num,
                "label": band_info["label"],
                "description": band_info["description"],
                "multiplier": band_info["multiplier"],
                "payout_amount": round(
                    weekly_benefit * band_info["multiplier"], 2  # type: ignore
                ),
            }
        )

    return {
        "plan": plan,
        "weekly_benefit_w": weekly_benefit,
        "payout_bands": payout_bands,
        "covered_weekly_income": base_metrics["covered_income_b"],
        "weekly_premium_inr": quote["gross_premium"],
        "max_payout_cap_inr": quote["payout_cap"],
        "exposure_multiplier": base_metrics["exposure_e"],
        "confidence_multiplier": base_metrics["confidence_base"],
        "plan_uplift_factor": plan_uplift,
    }


@router.post("/activate")
async def activate_policy(
    body: ActivatePolicyRequest,
    user: dict = Depends(require_worker),
):
    """
    Activates a weekly policy for the selected plan.
    In a full DB, this would write to a 'policies' table.
    For this scaffold, we return a success token with plan details.
    """
    if body.plan not in VALID_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan '{body.plan}'. Must be 'essential' or 'plus'.",
        )

    import datetime

    now = datetime.datetime.utcnow()
    valid_until = now + datetime.timedelta(days=7)
    weekly_benefit = PLAN_WEEKLY_BENEFITS[body.plan]

    return {
        "status": "active",
        "message": f"{body.plan.capitalize()} weekly coverage activated.",
        "plan": body.plan,
        "weekly_benefit_w": weekly_benefit,
        "activated_at": now.isoformat() + "Z",
        "valid_until": valid_until.isoformat() + "Z",
        "policy_id": f"POL-{user['id'][:8]}-{now.strftime('%Y%m%d')}",
    }
