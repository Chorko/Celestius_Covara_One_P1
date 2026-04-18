"""
Covara One — Rewards & Coins Engine

Gamification layer for worker retention and engagement.
Awards coins for positive behaviors, enables redemption for
premium discounts and free coverage weeks.

Coin Schedule:
    weekly_login         — 10 coins (once per week)
    consecutive_weeks    — 50 coins (4 active weeks in a row)
    clean_claim          — 25 coins (approved claim with fraud_score < 0.15)
    disruption_active    — 15 coins (worker was active during a trigger event)
    referral             — 100 coins (referred worker completes onboarding)
    profile_complete     — 20 coins (all KYC steps done)

Redemption:
    100 coins = ₹5 premium discount
    500 coins = 1 free week of coverage
"""

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("covara.rewards")

# ── Coin Award Amounts ───────────────────────────────────────────────────
COIN_AMOUNTS = {
    "weekly_login": 10,
    "consecutive_weeks_4": 50,
    "clean_claim": 25,
    "disruption_active": 15,
    "referral": 100,
    "profile_complete": 20,
}

DISCOUNT_COINS_REQUIRED = 100
DISCOUNT_RATE_INR = 5
FREE_WEEK_COINS_REQUIRED = 500


async def get_balance(sb, profile_id: str) -> int:
    """Get current coin balance for a worker."""
    try:
        resp = (
            sb.table("driver_coin_balance")
            .select("balance")
            .eq("profile_id", profile_id)
            .maybe_single()
            .execute()
        )
        if resp.data:
            return int(resp.data.get("balance", 0))
    except Exception as e:
        logger.warning(f"Could not fetch coin balance for {profile_id}: {e}")
    return 0


async def get_history(sb, profile_id: str, limit: int = 20) -> list:
    """Get recent coin transaction history."""
    try:
        resp = (
            sb.table("coins_ledger")
            .select("id, activity, coins, description, created_at")
            .eq("profile_id", profile_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        logger.warning(f"Could not fetch coin history for {profile_id}: {e}")
        return []


async def award_coins(
    sb,
    profile_id: str,
    activity: str,
    coins: int,
    description: str = "",
    reference_id: str | None = None,
) -> dict:
    """
    Award coins to a worker. Returns the new balance.
    All coin awards are idempotent per (profile_id, activity, reference_id).
    """
    try:
        if reference_id:
            existing = (
                sb.table("coins_ledger")
                .select("id")
                .eq("profile_id", profile_id)
                .eq("activity", activity)
                .eq("reference_id", reference_id)
                .limit(1)
                .execute()
            )
            if existing.data:
                current_balance = await get_balance(sb, profile_id)
                return {
                    "success": True,
                    "coins_awarded": 0,
                    "new_balance": current_balance,
                    "idempotent": True,
                    "reference_id": reference_id,
                }

        row = {
            "profile_id": profile_id,
            "activity": activity,
            "coins": coins,
            "description": description,
        }
        if reference_id:
            row["reference_id"] = reference_id

        sb.table("coins_ledger").insert(row).execute()

        new_balance = await get_balance(sb, profile_id)
        logger.info(
            f"Awarded {coins} coins to {profile_id} for {activity}. "
            f"New balance: {new_balance}"
        )
        return {"success": True, "coins_awarded": coins, "new_balance": new_balance}
    except Exception as e:
        # If a concurrent insert already wrote this reference, treat as idempotent success.
        msg = str(e).lower()
        if reference_id and ("duplicate" in msg or "unique" in msg):
            current_balance = await get_balance(sb, profile_id)
            return {
                "success": True,
                "coins_awarded": 0,
                "new_balance": current_balance,
                "idempotent": True,
                "reference_id": reference_id,
            }

        logger.error(f"Failed to award coins to {profile_id}: {e}")
        return {"success": False, "error": str(e)}


async def check_weekly_login_bonus(sb, profile_id: str) -> dict:
    """
    Award 10 coins if worker hasn't received a weekly login bonus
    in the current calendar week.
    """
    try:
        week_start = datetime.now(timezone.utc) - timedelta(days=7)
        resp = (
            sb.table("coins_ledger")
            .select("id")
            .eq("profile_id", profile_id)
            .eq("activity", "weekly_login")
            .gte("created_at", week_start.isoformat())
            .limit(1)
            .execute()
        )
        if resp.data:
            return {"awarded": False, "reason": "already_awarded_this_week"}

        return await award_coins(
            sb, profile_id,
            activity="weekly_login",
            coins=COIN_AMOUNTS["weekly_login"],
            description="Weekly login bonus",
        )
    except Exception as e:
        return {"awarded": False, "error": str(e)}


async def award_clean_claim(sb, profile_id: str, claim_id: str, fraud_score: float) -> dict:
    """
    Award 25 coins for an approved claim with fraud_score < 0.15.
    Called from auto_claim_engine after successful claim processing.
    """
    if fraud_score >= 0.15:
        return {"awarded": False, "reason": f"fraud_score {fraud_score} >= 0.15"}

    return await award_coins(
        sb, profile_id,
        activity="clean_claim",
        coins=COIN_AMOUNTS["clean_claim"],
        description=f"Clean claim approved (fraud_score={fraud_score:.3f})",
        reference_id=claim_id,
    )


async def award_referral(sb, referrer_id: str, referee_id: str) -> dict:
    """Award 100 coins to the referrer when a referred worker completes onboarding."""
    return await award_coins(
        sb, referrer_id,
        activity="referral",
        coins=COIN_AMOUNTS["referral"],
        description=f"Referral bonus: referred worker {referee_id[:8]}",
        reference_id=referee_id,
    )


async def redeem_discount(sb, profile_id: str) -> dict:
    """
    Redeem 100 coins for a ₹5 premium discount.
    Returns discount amount if successful.
    """
    balance = await get_balance(sb, profile_id)

    if balance < DISCOUNT_COINS_REQUIRED:
        return {
            "success": False,
            "remaining_balance": balance,
            "error": f"Need {DISCOUNT_COINS_REQUIRED} coins, have {balance}",
        }

    result = await award_coins(
        sb, profile_id,
        activity="redeemed_discount",
        coins=-DISCOUNT_COINS_REQUIRED,
        description=f"Redeemed {DISCOUNT_COINS_REQUIRED} coins for ₹{DISCOUNT_RATE_INR} discount",
    )

    if result.get("success"):
        result["discount_inr"] = DISCOUNT_RATE_INR

    return result


async def redeem_free_week(sb, profile_id: str) -> dict:
    """
    Redeem 500 coins for a free week of coverage.
    Returns success status and new balance.
    """
    balance = await get_balance(sb, profile_id)

    if balance < FREE_WEEK_COINS_REQUIRED:
        return {
            "success": False,
            "remaining_balance": balance,
            "error": f"Need {FREE_WEEK_COINS_REQUIRED} coins, have {balance}",
        }

    result = await award_coins(
        sb, profile_id,
        activity="redeemed_free_week",
        coins=-FREE_WEEK_COINS_REQUIRED,
        description=f"Redeemed {FREE_WEEK_COINS_REQUIRED} coins for free week",
    )

    if result.get("success"):
        result["free_week"] = True

    return result
