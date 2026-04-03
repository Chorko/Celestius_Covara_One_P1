"""
Tests for the IRDAI-aligned pricing engine.

Validates:
  - Premium outputs fall within ₹20–50/week range
  - Payout caps match plan definitions
  - Actuarial formulas produce correct B, E, C values
  - IRDAI micro-insurance annual limit compliance
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.services.pricing import (
    calculate_policy_metrics,
    calculate_payout,
    get_premium_quote,
    PLAN_DEFINITIONS,
    IRDAI_MICRO_INSURANCE_ANNUAL_LIMIT,
)


class TestPlanDefinitions:
    """Verify plan structures are IRDAI-compliant."""

    def test_essential_premium_in_range(self):
        plan = PLAN_DEFINITIONS["essential"]
        assert 20 <= plan["weekly_premium_inr"] <= 50, \
            f"Essential weekly premium {plan['weekly_premium_inr']} outside ₹20-50 range"

    def test_plus_premium_in_range(self):
        plan = PLAN_DEFINITIONS["plus"]
        assert 20 <= plan["weekly_premium_inr"] <= 50, \
            f"Plus weekly premium {plan['weekly_premium_inr']} outside ₹20-50 range"

    def test_annual_premium_under_irdai_limit(self):
        for plan_name, plan in PLAN_DEFINITIONS.items():
            assert plan["annual_premium_inr"] <= IRDAI_MICRO_INSURANCE_ANNUAL_LIMIT, \
                f"{plan_name} annual premium ₹{plan['annual_premium_inr']} exceeds IRDAI limit ₹{IRDAI_MICRO_INSURANCE_ANNUAL_LIMIT}"

    def test_essential_cheaper_than_plus(self):
        assert PLAN_DEFINITIONS["essential"]["weekly_premium_inr"] < PLAN_DEFINITIONS["plus"]["weekly_premium_inr"]

    def test_plus_benefit_higher_than_essential(self):
        assert PLAN_DEFINITIONS["plus"]["weekly_benefit_cap_inr"] > PLAN_DEFINITIONS["essential"]["weekly_benefit_cap_inr"]


class TestPolicyMetrics:
    """Verify B, E, C calculations."""

    def test_covered_income_formula(self):
        ctx = {"avg_hourly_income_inr": 100, "shift_hours": 9, "active_days": 6}
        m = calculate_policy_metrics(ctx)
        # B = 0.70 * 100 * 9 * 6 = 3780
        assert m["covered_income_b"] == 3780.0

    def test_zero_income_returns_zero_b(self):
        ctx = {"avg_hourly_income_inr": 0, "shift_hours": 9, "active_days": 6}
        m = calculate_policy_metrics(ctx)
        assert m["covered_income_b"] == 0.0

    def test_exposure_clipped_to_range(self):
        ctx = {"avg_hourly_income_inr": 100, "shift_hours": 0, "active_days": 6, "accessibility_score": 1.0}
        m = calculate_policy_metrics(ctx)
        assert 0.35 <= m["exposure_e"] <= 1.0

    def test_confidence_clipped_to_range(self):
        ctx = {"avg_hourly_income_inr": 100, "trust_score": 0.0, "gps_consistency_score": 0.0}
        m = calculate_policy_metrics(ctx)
        assert 0.45 <= m["confidence_base"] <= 1.0


class TestPayoutCalculation:
    """Verify payout engine with plan caps."""

    def test_payout_capped_by_plan(self):
        result = calculate_payout(
            covered_income_b=50000,  # Very high income
            severity_s=1.0,
            exposure_e=1.0,
            confidence_base=1.0,
            fraud_penalty=0.0,
            plan="essential",
        )
        # Payout must not exceed Essential cap (₹3000)
        assert result["recommended_payout"] <= PLAN_DEFINITIONS["essential"]["weekly_benefit_cap_inr"]

    def test_premium_matches_plan_rate(self):
        result = calculate_payout(
            covered_income_b=3780,
            severity_s=0.5,
            exposure_e=0.67,
            confidence_base=0.85,
            fraud_penalty=0.0,
            plan="essential",
        )
        assert result["gross_premium"] == PLAN_DEFINITIONS["essential"]["weekly_premium_inr"]

    def test_fraud_penalty_reduces_payout(self):
        clean = calculate_payout(
            covered_income_b=3780, severity_s=1.0, exposure_e=0.8,
            confidence_base=0.9, fraud_penalty=0.0, plan="essential",
        )
        fraud = calculate_payout(
            covered_income_b=3780, severity_s=1.0, exposure_e=0.8,
            confidence_base=0.9, fraud_penalty=0.8, plan="essential",
        )
        assert fraud["recommended_payout"] < clean["recommended_payout"]

    def test_plus_plan_higher_cap(self):
        result = calculate_payout(
            covered_income_b=50000, severity_s=1.0, exposure_e=1.0,
            confidence_base=1.0, fraud_penalty=0.0, plan="plus",
        )
        assert result["payout_cap"] == PLAN_DEFINITIONS["plus"]["weekly_benefit_cap_inr"]


class TestPremiumQuote:
    """Verify the simple quote endpoint."""

    def test_essential_quote(self):
        q = get_premium_quote("essential")
        assert q["weekly_premium_inr"] == 28
        assert q["daily_premium_inr"] == 4
        assert q["irdai_compliant"] is True

    def test_plus_quote(self):
        q = get_premium_quote("plus")
        assert q["weekly_premium_inr"] == 42
        assert q["daily_premium_inr"] == 6
        assert q["irdai_compliant"] is True

    def test_invalid_plan_falls_back(self):
        q = get_premium_quote("nonexistent")
        assert q["plan"] == "nonexistent"
        # Falls back to essential defaults
        assert q["weekly_premium_inr"] == 28
