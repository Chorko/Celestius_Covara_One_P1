"""Policy quote and activation helpers shared by policy/payment routers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib

from backend.app.services.pricing import (
    PLAN_DEFINITIONS,
    calculate_payout,
    calculate_policy_metrics,
)

VALID_PLANS = ("essential", "plus")

# Keep payout band labels consistent with claim pipeline docs.
PAYOUT_BANDS = {
    1: {
        "label": "Band 1 — Watch",
        "multiplier": 0.25,
        "description": "Moderate disruption with partial exposure",
    },
    2: {
        "label": "Band 2 — Claim",
        "multiplier": 0.50,
        "description": "Major disruption with strong exposure",
    },
    3: {
        "label": "Band 3 — Escalation",
        "multiplier": 1.00,
        "description": "Severe disruption with full exposure match",
    },
}


def _normalize_plan(plan: str) -> str:
    plan_key = (plan or "essential").strip().lower()
    if plan_key not in VALID_PLANS:
        raise ValueError(f"Invalid plan '{plan}'. Must be 'essential' or 'plus'.")
    return plan_key


def _plan_uplift_factor(plan: str) -> float:
    base_cap = float(PLAN_DEFINITIONS["essential"]["weekly_benefit_cap_inr"])
    selected_cap = float(PLAN_DEFINITIONS[plan]["weekly_benefit_cap_inr"])
    if base_cap <= 0:
        return 1.0
    return round(selected_cap / base_cap, 2)


def _profile_hash_ratio(worker_profile_id: str, plan: str) -> float:
    seed = f"{worker_profile_id}:{plan}".encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    raw = int.from_bytes(digest[:8], byteorder="big", signed=False)
    max_raw = (1 << 64) - 1
    return raw / max_raw if max_raw else 0.0


def _personalize_weekly_premium(base_premium: float, worker_profile_id: str, plan: str) -> float:
    """Add deterministic profile-level diversification while preserving parametric bounds."""
    plan_def = PLAN_DEFINITIONS[plan]
    min_weekly = float(plan_def.get("min_weekly_premium_inr", plan_def["weekly_premium_inr"]))
    max_weekly = float(plan_def.get("max_weekly_premium_inr", plan_def["weekly_premium_inr"]))

    base = float(base_premium)
    ratio = _profile_hash_ratio(worker_profile_id, plan)
    hashed_target = min_weekly + ((max_weekly - min_weekly) * ratio)

    # Preserve pricing signal from observed risk metrics while adding per-profile spread.
    blended = (0.78 * base) + (0.22 * hashed_target)

    # Avoid floor-collapsing multiple workers onto one value when actuarial base hits minimum.
    if abs(base - min_weekly) < 0.01:
        floor_spread_rupees = min(4.0, max(0.0, max_weekly - min_weekly))
        blended = min_weekly + (ratio * floor_spread_rupees)

    return round(min(max(blended, min_weekly), max_weekly), 2)


def _load_worker_profile(sb, worker_profile_id: str) -> dict:
    worker_resp = (
        sb.table("worker_profiles")
        .select("*")
        .eq("profile_id", worker_profile_id)
        .maybe_single()
        .execute()
    )

    worker_row = worker_resp.data if worker_resp else None
    if not worker_row:
        raise ValueError("Worker profile required for quote/activation.")

    return worker_row


def _build_quote_context(worker_row: dict) -> dict:
    # Quote-level defaults stabilize premiums for workers with sparse history.
    return {
        **worker_row,
        "shift_hours": float(worker_row.get("shift_hours") or 9.0),
        "active_days": int(worker_row.get("active_days") or 6),
        "trust_score": float(worker_row.get("trust_score") or 0.8),
        "gps_consistency_score": float(worker_row.get("gps_consistency_score") or 0.9),
        "accessibility_score": float(worker_row.get("accessibility_score") or 1.0),
    }


def expire_stale_policies_for_worker(sb, worker_profile_id: str) -> None:
    """Expire active policies whose validity window has already elapsed."""
    if not worker_profile_id:
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        (
            sb.table("policies")
            .update(
                {
                    "status": "expired",
                    "updated_at": now_iso,
                }
            )
            .eq("worker_profile_id", worker_profile_id)
            .eq("status", "active")
            .lt("valid_until", now_iso)
            .execute()
        )
    except Exception:
        # Non-blocking safeguard: quote/activation should still work if update fails.
        return


def quote_policy_for_worker(sb, worker_profile_id: str, plan: str = "essential") -> dict:
    plan_key = _normalize_plan(plan)
    expire_stale_policies_for_worker(sb, worker_profile_id)
    worker_row = _load_worker_profile(sb, worker_profile_id)
    worker_context = _build_quote_context(worker_row)

    base_metrics = calculate_policy_metrics(worker_context)
    quote = calculate_payout(
        covered_income_b=base_metrics["covered_income_b"],
        severity_s=1.0,
        exposure_e=base_metrics["exposure_e"],
        confidence_base=base_metrics["confidence_base"],
        fraud_penalty=0.0,
        plan=plan_key,
    )

    base_weekly_premium = float(quote["gross_premium"])
    personalized_weekly_premium = _personalize_weekly_premium(
        base_weekly_premium,
        worker_profile_id,
        plan_key,
    )

    weekly_benefit = float(PLAN_DEFINITIONS[plan_key]["weekly_benefit_cap_inr"])
    payout_bands = []
    for band_num, band_info in sorted(PAYOUT_BANDS.items()):
        payout_bands.append(
            {
                "band": band_num,
                "label": band_info["label"],
                "description": band_info["description"],
                "multiplier": band_info["multiplier"],
                "payout_amount": round(weekly_benefit * float(band_info["multiplier"]), 2),
            }
        )

    return {
        "plan": plan_key,
        "weekly_benefit_w": weekly_benefit,
        "payout_bands": payout_bands,
        "covered_weekly_income": base_metrics["covered_income_b"],
        "weekly_premium_inr": personalized_weekly_premium,
        "max_payout_cap_inr": quote["payout_cap"],
        "exposure_multiplier": base_metrics["exposure_e"],
        "confidence_multiplier": base_metrics["confidence_base"],
        "actuarial_premium_inr": quote["actuarial_premium"],
        "base_weekly_premium_inr": base_weekly_premium,
        "plan_uplift_factor": _plan_uplift_factor(plan_key),
    }


def upsert_weekly_policy(
    sb,
    worker_profile_id: str,
    plan: str,
    weekly_premium_inr: float | None = None,
) -> dict:
    plan_key = _normalize_plan(plan)
    expire_stale_policies_for_worker(sb, worker_profile_id)
    worker_row = _load_worker_profile(sb, worker_profile_id)

    quote = quote_policy_for_worker(sb, worker_profile_id, plan_key)
    weekly_benefit = float(PLAN_DEFINITIONS[plan_key]["weekly_benefit_cap_inr"])
    premium_amount = float(weekly_premium_inr or quote["weekly_premium_inr"])

    now = datetime.now(timezone.utc)
    valid_until = now + timedelta(days=7)

    existing_policy_id = None
    try:
        existing_resp = (
            sb.table("policies")
            .select("policy_id")
            .eq("worker_profile_id", worker_profile_id)
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

    policy_id = existing_policy_id or f"POL-{worker_profile_id[:8]}-{now.strftime('%Y%m%d%H%M%S')}"

    policy_row = {
        "policy_id": policy_id,
        "worker_profile_id": worker_profile_id,
        "zone_id": worker_row.get("preferred_zone_id"),
        "plan_type": plan_key,
        "coverage_amount": weekly_benefit,
        "premium_amount": premium_amount,
        "status": "active",
        "activated_at": now.isoformat(),
        "valid_until": valid_until.isoformat(),
        "updated_at": now.isoformat(),
    }

    resp = sb.table("policies").upsert(policy_row, on_conflict="policy_id").execute()
    persisted = resp.data[0] if resp and resp.data else policy_row

    return {
        "status": "active",
        "message": f"{plan_key.capitalize()} weekly coverage activated.",
        "plan": plan_key,
        "weekly_benefit_w": weekly_benefit,
        "weekly_premium_inr": round(premium_amount, 2),
        "zone_id": persisted.get("zone_id", worker_row.get("preferred_zone_id")),
        "activated_at": persisted.get("activated_at", policy_row["activated_at"]),
        "valid_until": persisted.get("valid_until", policy_row["valid_until"]),
        "policy_id": persisted.get("policy_id", policy_id),
    }
