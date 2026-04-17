"""
Covara One — Policies & Premium Router

Handles dynamic premium quotes and policy activation.
Supports exactly two plans: Essential and Plus.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from backend.app.dependencies import require_worker
from backend.app.supabase_client import get_supabase_admin
from backend.app.services.pricing import (
    calculate_policy_metrics,
    calculate_payout,
    PLAN_DEFINITIONS,
)
from backend.app.services.claim_pipeline import (
    PLAN_WEEKLY_BENEFITS,
    PAYOUT_BANDS,
)

router = APIRouter(prefix="/policies", tags=["Policies"])

# ── Two plans only ────────────────────────────────────────────────────
VALID_PLANS = ("essential", "plus")


def _plan_uplift_factor(plan: str) -> float:
    """Return relative benefit uplift compared to Essential plan."""
    base_cap = float(PLAN_DEFINITIONS["essential"]["weekly_benefit_cap_inr"])
    selected_cap = float(PLAN_DEFINITIONS[plan]["weekly_benefit_cap_inr"])
    if base_cap <= 0:
        return 1.0
    return round(selected_cap / base_cap, 2)


class ActivatePolicyRequest(BaseModel):
    plan: str = "essential"  # "essential" or "plus"


from fastapi_cache.decorator import cache

@router.get("/quote")
@cache(expire=600)
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

    # Compute expected payout/premium using a baseline severe scenario (S=1.0)
    quote = calculate_payout(
        covered_income_b=base_metrics["covered_income_b"],
        severity_s=1.0,  # quoting worst-case for max payout info
        exposure_e=base_metrics["exposure_e"],
        confidence_base=base_metrics["confidence_base"],
        fraud_penalty=0.0,  # zero fraud initially
        plan=plan,
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
        "plan_uplift_factor": _plan_uplift_factor(plan),
    }


@router.post("/activate")
async def activate_policy(
    body: ActivatePolicyRequest,
    user: dict = Depends(require_worker),
):
    """
    Activates a weekly policy for the selected plan.
    Persists the policy record to the 'policies' table in Supabase.
    """
    if body.plan not in VALID_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan '{body.plan}'. Must be 'essential' or 'plus'.",
        )

    sb = get_supabase_admin()
    now = datetime.now(timezone.utc)
    valid_until = now + timedelta(days=7)
    plan_details = PLAN_DEFINITIONS[body.plan]
    weekly_benefit = float(plan_details["weekly_benefit_cap_inr"])
    weekly_premium = float(plan_details["weekly_premium_inr"])

    # Prefer updating an existing active policy for this worker to avoid
    # creating duplicate active rows across re-activations.
    existing_policy_id = None
    try:
        existing_resp = (
            sb.table("policies")
            .select("policy_id")
            .eq("worker_profile_id", user["id"])
            .eq("status", "active")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        existing_rows = existing_resp.data or []
        if existing_rows:
            existing_policy_id = existing_rows[0].get("policy_id")
    except Exception:
        existing_policy_id = None

    policy_id = existing_policy_id or f"POL-{user['id'][:8]}-{now.strftime('%Y%m%d%H%M%S')}"

    worker_resp = (
        sb.table("worker_profiles")
        .select("profile_id, preferred_zone_id")
        .eq("profile_id", user["id"])
        .maybe_single()
        .execute()
    )
    worker_row = worker_resp.data or {}
    zone_id = worker_row.get("preferred_zone_id")

    policy_row = {
        "policy_id": policy_id,
        "worker_profile_id": user["id"],
        "zone_id": zone_id,
        "plan_type": body.plan,
        "coverage_amount": weekly_benefit,
        "premium_amount": weekly_premium,
        "status": "active",
        "activated_at": now.isoformat(),
        "valid_until": valid_until.isoformat(),
        "updated_at": now.isoformat(),
    }

    try:
        resp = sb.table("policies").upsert(
            policy_row, on_conflict="policy_id"
        ).execute()
        persisted = resp.data[0] if resp.data else policy_row
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Policy storage unavailable. Apply database migrations and retry."
            ),
        ) from exc

    return {
        "status": "active",
        "message": f"{body.plan.capitalize()} weekly coverage activated.",
        "plan": body.plan,
        "weekly_benefit_w": int(weekly_benefit),
        "weekly_premium_inr": int(weekly_premium),
        "zone_id": persisted.get("zone_id", zone_id),
        "activated_at": persisted.get("activated_at", policy_row["activated_at"]),
        "valid_until": persisted.get("valid_until", policy_row["valid_until"]),
        "policy_id": persisted.get("policy_id", policy_id),
    }

