"""
Covara One — Policies & Premium Router

Handles dynamic premium quotes and policy activation.
Supports exactly two plans: Essential and Plus.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from backend.app.dependencies import require_worker
from backend.app.supabase_client import get_supabase_admin
from backend.app.services.policy_service import (
    VALID_PLANS,
    quote_policy_for_worker,
    upsert_weekly_policy,
)

router = APIRouter(prefix="/policies", tags=["Policies"])


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
    try:
        return quote_policy_for_worker(sb, user["id"], plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    try:
        return upsert_weekly_policy(sb, user["id"], body.plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Policy storage unavailable. Apply database migrations and retry."
            ),
        ) from exc

