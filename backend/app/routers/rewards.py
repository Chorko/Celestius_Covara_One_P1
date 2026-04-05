"""
Covara One — Rewards Router

Endpoints for worker coin balance, transaction history, and redemption.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from backend.app.dependencies import get_current_user
from backend.app.supabase_client import get_supabase_admin
from backend.app.services.rewards_engine import (
    get_balance,
    get_history,
    check_weekly_login_bonus,
    redeem_discount,
    redeem_free_week,
    DISCOUNT_COINS_REQUIRED,
    DISCOUNT_RATE_INR,
    FREE_WEEK_COINS_REQUIRED,
)
from backend.app.rate_limit import limiter

router = APIRouter(prefix="/rewards", tags=["Rewards"])


@router.get("/balance")
async def rewards_balance(user: dict = Depends(get_current_user)):
    """Get current coin balance and redemption options."""
    sb = get_supabase_admin()
    balance = await get_balance(sb, user["id"])

    return {
        "balance": balance,
        "redemption_options": {
            "discount": {
                "coins_required": DISCOUNT_COINS_REQUIRED,
                "value_inr": DISCOUNT_RATE_INR,
                "available": balance >= DISCOUNT_COINS_REQUIRED,
            },
            "free_week": {
                "coins_required": FREE_WEEK_COINS_REQUIRED,
                "available": balance >= FREE_WEEK_COINS_REQUIRED,
            },
        },
    }


@router.get("/history")
async def rewards_history(
    limit: int = 20, user: dict = Depends(get_current_user)
):
    """Get recent coin transaction history."""
    sb = get_supabase_admin()
    history = await get_history(sb, user["id"], limit=limit)
    balance = await get_balance(sb, user["id"])

    return {
        "balance": balance,
        "transactions": history,
    }


@router.post("/check-in")
@limiter.limit("2/hour")
async def daily_check_in(request: Request, user: dict = Depends(get_current_user)):
    """Check in to earn weekly login bonus coins."""
    sb = get_supabase_admin()
    result = await check_weekly_login_bonus(sb, user["id"])
    return result


@router.post("/redeem/discount")
@limiter.limit("3/hour")
async def redeem_discount_endpoint(
    request: Request, user: dict = Depends(get_current_user)
):
    """Redeem 100 coins for a ₹5 premium discount."""
    sb = get_supabase_admin()
    result = await redeem_discount(sb, user["id"])

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Redemption failed"))

    return result


@router.post("/redeem/free-week")
@limiter.limit("1/day")
async def redeem_free_week_endpoint(
    request: Request, user: dict = Depends(get_current_user)
):
    """Redeem 500 coins for a free week of coverage."""
    sb = get_supabase_admin()
    result = await redeem_free_week(sb, user["id"])

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Redemption failed"))

    return result
