"""
DEVTrails — Pricing & Payout Engine

Computes Covered Income (B), Exposure (E), Confidence (C),
and the final expected payouts and premiums based on the actuarial formulas.
"""

def clip(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(val, max_val))

def calculate_policy_metrics(worker_context: dict) -> dict:
    """
    Computes base policy metrics: B, E, C.
    Requires: hourly_income, shift_hours, active_days, trust_score, gps_consistency, bank_verified, accessibility_score
    """
    income = worker_context.get("hourly_income", 0.0)
    shift_hours = worker_context.get("shift_hours", 0.0)
    active_days = worker_context.get("active_days", 6)
    
    # B = 0.70 × hourly_income × shift_hours × active_days
    # The documentation references 6 days statically, but we'll use active_days for dynamic accuracy
    covered_income_b = 0.70 * income * shift_hours * active_days
    
    # E = clip(0.45 + 0.30×(shift_hours/12) + 0.25×(1−accessibility_score), 0.35, 1.00)
    acc = worker_context.get("accessibility_score", 1.0)
    exposure_e = clip(0.45 + 0.30 * (shift_hours / 12.0) + 0.25 * (1.0 - acc), 0.35, 1.00)
    
    # Confidence base (before fraud penalty)
    trust = worker_context.get("trust_score", 0.75)
    gps = worker_context.get("gps_consistency_score", 0.80)
    bank = 1.0 if worker_context.get("bank_verified", False) else 0.0
    
    confidence_base = clip(0.50 + 0.30 * trust + 0.10 * gps + 0.10 * bank, 0.45, 1.00)
    
    return {
        "covered_income_b": round(covered_income_b, 2),
        "exposure_e": round(exposure_e, 4),
        "confidence_base": round(confidence_base, 4)
    }

def calculate_payout(
    covered_income_b: float,
    severity_s: float,
    exposure_e: float,
    confidence_base: float,
    fraud_penalty: float,
    claim_probability_p: float = 0.15, # Mock Random Forest baseline
    outlier_uplift_u: float = 1.0
) -> dict:
    """
    Computes final premium and payout values.
    """
    # C = confidence_base * (1 - 0.70 * fraud_penalty)
    confidence_c = confidence_base * (1.0 - 0.70 * fraud_penalty)
    
    # FH is derived from fraud_penalty, e.g. FH = fraud_penalty * 0.5 for holdback
    fraud_holdback_fh = fraud_penalty * 0.5 
    
    # Cap = 0.75 * B * U
    payout_cap = 0.75 * covered_income_b * outlier_uplift_u
    
    # Expected payout = p * B * S * E * C * (1 - FH)
    expected_payout = claim_probability_p * covered_income_b * severity_s * exposure_e * confidence_c * (1.0 - fraud_holdback_fh)
    
    # Gross Premium = [Expected Payout / (1 - 0.12 - 0.10)] * U
    gross_premium = (expected_payout / (1.0 - 0.12 - 0.10)) * outlier_uplift_u
    
    # Raw payout = B * S * E * C * (1 - FH)
    raw_payout = covered_income_b * severity_s * exposure_e * confidence_c * (1.0 - fraud_holdback_fh)
    
    # Final Payout = min(Cap, Raw_Payout)
    final_payout = min(payout_cap, raw_payout)
    
    return {
        "confidence_score_c": round(confidence_c, 4),
        "fraud_holdback_fh": round(fraud_holdback_fh, 4),
        "payout_cap": round(payout_cap, 2),
        "expected_payout": round(expected_payout, 2),
        "gross_premium": round(gross_premium, 2),
        "raw_payout": round(raw_payout, 2),
        "recommended_payout": round(final_payout, 2),
    }
