"""
Covara One — Pricing & Payout Engine

IRDAI-Aligned Micro-Insurance Premium Model:
  - Essential plan: ₹28/week  (₹4/day)  → covers ₹3,000/week max payout
  - Plus plan:      ₹42/week  (₹6/day)  → covers ₹4,500/week max payout

  Annual premium range: ₹1,456 – ₹2,184
  IRDAI micro-insurance limit: ₹10,000/year → we are well within bounds.

Actuarial formulas:
  B = 0.70 × hourly_income × shift_hours × active_days   (covered weekly income)
  E = clip(0.45 + 0.30×(shift_hours/12) + 0.25×(1−acc), 0.35, 1.00)  (exposure)
  C = clip(0.50 + 0.30×trust + 0.10×gps + 0.10×bank, 0.45, 1.00)    (confidence)
  Payout = min(Cap, B × S × E × C × (1 - FH))
  Premium = [E[Payout] / (1 - expense_load)] × U
"""


def clip(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(val, max_val))


# ── Plan Definitions ──────────────────────────────────────────────────

PLAN_DEFINITIONS = {
    "essential": {
        "weekly_premium_inr": 28,
        "daily_premium_inr": 4,
        "weekly_benefit_cap_inr": 3000,
        "annual_premium_inr": 1456,       # 28 × 52
        "annual_benefit_cap_inr": 156000,  # 3000 × 52 (theoretical max)
        "description": "Basic income protection for gig workers",
    },
    "plus": {
        "weekly_premium_inr": 42,
        "daily_premium_inr": 6,
        "weekly_benefit_cap_inr": 4500,
        "annual_premium_inr": 2184,       # 42 × 52
        "annual_benefit_cap_inr": 234000,  # 4500 × 52 (theoretical max)
        "description": "Enhanced coverage with higher payout ceiling",
    },
}

# ── Regulatory Constants ──────────────────────────────────────────────
IRDAI_MICRO_INSURANCE_ANNUAL_LIMIT = 10000  # ₹10,000/year max premium
EXPENSE_LOAD = 0.22     # 12% admin + 10% margin (IRDAI allowed)
CLAIM_PROBABILITY = 0.15  # Actuarial baseline claim probability


def calculate_policy_metrics(worker_context: dict) -> dict:
    """
    Computes base policy metrics: B (covered income), E (exposure), C (confidence).

    Requires:
      avg_hourly_income_inr (or hourly_income), shift_hours, active_days,
      trust_score, gps_consistency_score, bank_verified, accessibility_score
    """
    income = (
        worker_context.get("avg_hourly_income_inr")
        or worker_context.get("hourly_income")
        or 0.0
    )
    shift_hours = worker_context.get("shift_hours", 9.0)
    active_days = worker_context.get("active_days", 6)

    # B = 0.70 × hourly_income × shift_hours × active_days
    covered_income_b = 0.70 * income * shift_hours * active_days

    # E = clip(0.45 + 0.30×(shift_hours/12) + 0.25×(1 − accessibility_score),
    #          0.35, 1.00)
    acc = worker_context.get("accessibility_score", 1.0)
    exposure_e = clip(
        0.45 + 0.30 * (shift_hours / 12.0) + 0.25 * (1.0 - acc), 0.35, 1.00
    )

    # Confidence base (before fraud penalty)
    trust = worker_context.get("trust_score", 0.75)
    gps = worker_context.get("gps_consistency_score", 0.80)
    bank = 1.0 if worker_context.get("bank_verified", False) else 0.0

    confidence_base = clip(
        0.50 + 0.30 * trust + 0.10 * gps + 0.10 * bank, 0.45, 1.00
    )

    return {
        "covered_income_b": round(covered_income_b, 2),
        "exposure_e": round(exposure_e, 4),
        "confidence_base": round(confidence_base, 4),
    }


def calculate_payout(
    covered_income_b: float,
    severity_s: float,
    exposure_e: float,
    confidence_base: float,
    fraud_penalty: float,
    claim_probability_p: float = CLAIM_PROBABILITY,
    outlier_uplift_u: float = 1.0,
    plan: str = "essential",
) -> dict:
    """
    Computes final premium and payout values.

    Premium is clamped to the plan's fixed weekly rate.
    Payout is capped by the plan's weekly benefit ceiling.
    """
    plan_def = PLAN_DEFINITIONS.get(plan, PLAN_DEFINITIONS["essential"])

    # C = confidence_base × (1 - 0.70 × fraud_penalty)
    confidence_c = confidence_base * (1.0 - 0.70 * fraud_penalty)

    # FH = fraud_penalty × 0.5 (holdback ratio)
    fraud_holdback_fh = fraud_penalty * 0.5

    # Payout cap = plan weekly benefit ceiling
    payout_cap = plan_def["weekly_benefit_cap_inr"]

    # Expected payout = p × B × S × E × C × (1 - FH)
    expected_payout = (
        claim_probability_p
        * covered_income_b
        * severity_s
        * exposure_e
        * confidence_c
        * (1.0 - fraud_holdback_fh)
    )

    # Gross premium = [Expected Payout / (1 - expense_load)] × U
    actuarial_premium = (expected_payout / (1.0 - EXPENSE_LOAD)) * outlier_uplift_u

    # Final premium = fixed plan rate (actuarial premium is for internal calibration only)
    gross_premium = plan_def["weekly_premium_inr"]

    # Raw payout = B × S × E × C × (1 - FH)
    raw_payout = (
        covered_income_b
        * severity_s
        * exposure_e
        * confidence_c
        * (1.0 - fraud_holdback_fh)
    )

    # Final payout = min(Cap, Raw_Payout)
    final_payout = min(payout_cap, raw_payout)

    return {
        "confidence_score_c": round(confidence_c, 4),
        "fraud_holdback_fh": round(fraud_holdback_fh, 4),
        "payout_cap": round(payout_cap, 2),
        "expected_payout": round(expected_payout, 2),
        "actuarial_premium": round(actuarial_premium, 2),
        "gross_premium": round(gross_premium, 2),
        "raw_payout": round(raw_payout, 2),
        "recommended_payout": round(final_payout, 2),
        "plan": plan,
        "plan_details": plan_def,
    }


def get_premium_quote(plan: str = "essential") -> dict:
    """
    Simple premium quote for a plan — no worker context needed.
    Used by the frontend pricing page.
    """
    plan_def = PLAN_DEFINITIONS.get(plan, PLAN_DEFINITIONS["essential"])
    return {
        "plan": plan,
        "weekly_premium_inr": plan_def["weekly_premium_inr"],
        "daily_premium_inr": plan_def["daily_premium_inr"],
        "annual_premium_inr": plan_def["annual_premium_inr"],
        "weekly_benefit_cap_inr": plan_def["weekly_benefit_cap_inr"],
        "irdai_compliant": plan_def["annual_premium_inr"] <= IRDAI_MICRO_INSURANCE_ANNUAL_LIMIT,
        "description": plan_def["description"],
    }

