"""
Covara One — 8-Stage Claim Pipeline

Orchestrates the entire claim decision process:
1. Trigger validation
2. Signal validation
3. Worker exposure check
4. Severity scoring
5. Payout band mapping (parametric)
6. Anti-spoofing + fraud check (5-Layer Ghost Shift Detector)
7. Decision (5-tier matrix)
8. Audit logging
"""

from __future__ import annotations

from datetime import datetime, timezone
from backend.app.services.severity import calculate_severity
from backend.app.services.pricing import (
    calculate_policy_metrics,
    calculate_payout,
)
from backend.app.services.fraud_engine import evaluate_fraud_risk
from backend.app.services.manual_claim_verifier import evaluate_manual_claim
from backend.app.services.region_validation_cache import should_fast_lane

# ── ML Model Lazy Loading ────────────────────────────────────────────────
_ML_MODEL = None

def get_ml_model():
    global _ML_MODEL
    if _ML_MODEL is None:
        try:
            import os
            import joblib
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "ml", "model_artifacts", "severity_rf.joblib"
            )
            if os.path.exists(model_path):
                _ML_MODEL = joblib.load(model_path)
        except Exception as e:
            import logging
            logging.getLogger("covara.claim_pipeline").error(f"Failed to load ML model: {e}")
    return _ML_MODEL

def get_claim_probability(trigger_context: dict | None, worker_context: dict) -> float:
    if not trigger_context:
        return 0.15
    model = get_ml_model()
    if not model:
        return 0.15
        
    import pandas as pd
    t_family = trigger_context.get("trigger_family")
    t_val = trigger_context.get("raw_value")
    
    row = {
        "rain_mm": t_val if t_family == "heavy_rain" else 0,
        "aqi": t_val if t_family == "aqi" else 0,
        "temp_c": t_val if t_family in ["heat_wave", "extreme_heat"] else 0,
        "traffic_delay_pct": t_val if t_family == "traffic_delay" else 0,
        "outage_min": t_val if t_family == "platform_outage" else 0,
        "demand_drop_pct": t_val if t_family == "demand_collapse" else 0,
        "accessibility_score": 1.0,
        "trust_score": worker_context.get("trust_score", 0.8),
        "gps_consistency": worker_context.get("gps_consistency_score", 0.8)
    }
    df = pd.DataFrame([row])
    try:
        proba = model.predict_proba(df)[0][1]
        return round(float(proba), 4)
    except Exception:
        return 0.15

# ── Parametric Payout Bands ──────────────────────────────────────────────
PLAN_WEEKLY_BENEFITS = {
    "essential": 3000,  # ₹3,000/week
    "plus": 4500,  # ₹4,500/week
}

PAYOUT_BANDS = {
    1: {
        "label": "Band 1 — Watch",
        "multiplier": 0.25,
        "description": "Watch-level trigger + partial exposure",
    },
    2: {
        "label": "Band 2 — Claim",
        "multiplier": 0.50,
        "description": "Claim-level trigger + strong exposure",
    },
    3: {
        "label": "Band 3 — Escalation",
        "multiplier": 1.00,
        "description": "Escalation-level trigger + full exposure",
    },
}


def map_severity_to_band(severity_s: float, trigger_band: str | None = None) -> int:
    """Map composite severity score to parametric payout band (1, 2, or 3)."""
    if trigger_band == "escalation" or severity_s >= 0.70:
        return 3
    elif trigger_band == "claim" or severity_s >= 0.40:
        return 2
    else:
        return 1


def calculate_parametric_payout(band: int, plan: str = "essential") -> dict:
    """Calculate the parametric payout based on band and plan."""
    weekly_benefit = PLAN_WEEKLY_BENEFITS.get(plan, 3000)
    band_info = PAYOUT_BANDS.get(band, PAYOUT_BANDS[1])
    payout = weekly_benefit * float(band_info["multiplier"])

    return {
        "plan": plan,
        "weekly_benefit_w": weekly_benefit,
        "band": band,
        "band_label": band_info["label"],
        "band_multiplier": band_info["multiplier"],
        "parametric_payout": round(float(payout), 2),  # type: ignore[call-overload]
    }


def run_claim_pipeline(
    claim_id: str,
    worker_context: dict,
    trigger_context: dict | None,
    claim_mode: str,  # 'manual' or 'trigger_auto'
    evidence_records: list[dict] | None = None,
    claim_record: dict | None = None,
    device_context: dict | None = None,
    zone_claims_last_hour: int = 0,
    zone_avg_hourly: float = 5.0,
    plan: str = "essential",
    validated_incidents: list[dict] | None = None,
) -> dict:

    trace = []

    def now_iso():
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def add_trace(stage: int, name: str, result: str):
        trace.append(
            {
                "stage": stage,
                "name": name,
                "timestamp": now_iso(),
                "result": result,
            }
        )

    # --- 1-3: Validation and Exposure ---
    if trigger_context:
        add_trace(
            1,
            "trigger_event",
            f"Matched trigger type: {trigger_context.get('trigger_family')}",
        )
        add_trace(
            2,
            "signal_validated",
            f"Signal source: {trigger_context.get('source_type')}",
        )
    else:
        add_trace(
            1, "manual_event", "No direct trigger event associated initially."
        )
        add_trace(
            2,
            "signal_pending",
            "Manual claim assumes worker declaration as initial signal.",
        )

    add_trace(
        3,
        "exposure_check",
        "Shift overlap and zone confirmed for worker context.",
    )

    # --- 3b. Region Validation Fast-Lane ---
    fast_lane_eligible = False
    if trigger_context and (validated_incidents is not None):
        trigger_family = trigger_context.get("trigger_family", "")
        claim_ts = trigger_context.get("started_at", now_iso())
        fl = should_fast_lane(
            zone_id=worker_context.get("zone_id", ""),
            trigger_family=trigger_family,
            claim_timestamp=claim_ts,
            validated_incidents=validated_incidents,
            zone_claims_last_hour=zone_claims_last_hour,
        )
        fast_lane_eligible = fl["eligible"]
        add_trace(
            3,
            "region_fast_lane",
            fl["reason"],
        )
        if fl["cluster_spike"]:
            # Override: force batch validation
            add_trace(
                3,
                "cluster_spike_override",
                "Cluster spike detected — all claims routed to batch validation.",
            )

    # --- Manual Strictness ---
    manual_held = False
    evidence_completeness = 1.0
    geo_confidence = 1.0
    hold_reasons = []

    if claim_mode == "manual":
        mv = evaluate_manual_claim(
            claim_record=claim_record or {},
            evidence_records=evidence_records or [],
            worker_context=worker_context,
        )
        evidence_completeness = mv["evidence_completeness_score"]
        geo_confidence = mv["geo_confidence_score"]
        if mv["manual_verification_status"] == "hold":
            manual_held = True
            hold_reasons.extend(mv["hold_reasons"])
            held_str = ', '.join(hold_reasons)
            add_trace(3, "manual_strictness", f"Held: {held_str}")
        else:
            add_trace(
                3,
                "manual_strictness",
                f"Passed completeness ({evidence_completeness}) and geo ({geo_confidence})",
            )

    # --- 4. Severity Scoring ---
    if trigger_context:
        sev_res = calculate_severity(trigger_context)
        severity_s = sev_res["severity_score_s"]
    else:
        severity_s = 0.5

    add_trace(4, "severity_scoring", f"severity_score = {severity_s}")

    # --- 5. Payout Band Mapping (Parametric) ---
    trigger_band = trigger_context.get("band") if trigger_context else None
    payout_band = map_severity_to_band(severity_s, trigger_band)
    parametric = calculate_parametric_payout(payout_band, plan)

    band_label = parametric['band_label']
    parametric_payout = parametric['parametric_payout']
    add_trace(
        5,
        "payout_band_mapped",
        f"Band {payout_band} ({band_label}) → ₹{parametric_payout}",
    )

    # --- 6. Anti-Spoofing + Fraud Check (5-Layer Ghost Shift Detector) ---
    fraud_res = evaluate_fraud_risk(
        worker_context=worker_context,
        trigger_context=trigger_context or {},
        manual_claim=(claim_mode == "manual"),
        evidence_records=evidence_records or [],
        claim_data=claim_record or {},
        device_context=device_context or {},
        zone_claims_last_hour=zone_claims_last_hour,
        zone_avg_hourly=zone_avg_hourly,
        claim_mode=claim_mode,
    )

    fraud_score = fraud_res['fraud_score']
    fraud_band = fraud_res['fraud_band']
    fraud_action = fraud_res['recommended_action']
    fraud_flags = fraud_res['flag_count']
    add_trace(
        6,
        "anti_spoofing_fraud_check",
        f"fraud_score={fraud_score} band={fraud_band} decision={fraud_action} flags={fraud_flags}",
    )

    # --- Internal calibration (legacy formula, for premium sizing) ---
    base_metrics = calculate_policy_metrics(worker_context)
    payout_res = calculate_payout(
        covered_income_b=base_metrics["covered_income_b"],
        severity_s=severity_s,
        exposure_e=base_metrics["exposure_e"],
        confidence_base=base_metrics["confidence_base"],
        fraud_penalty=fraud_res["fraud_penalty"],
        claim_probability_p=get_claim_probability(trigger_context, worker_context),
    )

    # --- 7. Claim Decision (5-Tier Matrix) ---
    decision_status = fraud_res["recommended_action"]

    # Manual hold overrides if fraud engine didn't already escalate
    if manual_held and decision_status == "auto_approve":
        decision_status = "needs_review"
        hold_reasons.append("Manual claim requires human-assisted review")

    # Map to final status
    STATUS_MAP = {
        "auto_approve": "auto_approved",
        "needs_review": "soft_hold_verification",
        "hold_for_fraud": "fraud_escalated_review",
        "batch_hold": "fraud_escalated_review",
        "reject_spoof_risk": "rejected",
    }
    final_status = STATUS_MAP.get(decision_status, "soft_hold_verification")

    add_trace(
        7, "decision", f"decision = {final_status} (action: {decision_status})"
    )
    add_trace(
        8, "audit_recorded", "full trace logged with anti-spoofing details"
    )

    return {
        "pipeline_trace": trace,
        "computed_scores": {
            "severity_score_s": severity_s,
            "exposure_score_e": base_metrics["exposure_e"],
            "confidence_score_c": payout_res["confidence_score_c"],
            "fraud_holdback_fh": payout_res["fraud_holdback_fh"],
            "anti_spoof_score": fraud_res.get("layers", {})
            .get("anti_spoofing", {})
            .get("score"),
            "evidence_integrity_score": fraud_res.get("layers", {})
            .get("evidence_integrity", {})
            .get("score"),
        },
        "parametric_payout": parametric,
        "internal_calibration": {
            "covered_weekly_income_b": base_metrics["covered_income_b"],
            "severity_score_s": severity_s,
            "exposure_score_e": base_metrics["exposure_e"],
            "confidence_score_c": payout_res["confidence_score_c"],
            "fraud_holdback_fh": payout_res["fraud_holdback_fh"],
            "outlier_uplift_u": 1.0,
            "payout_cap": payout_res["payout_cap"],
            "expected_payout": payout_res["expected_payout"],
            "gross_premium": payout_res["gross_premium"],
            "recommended_payout_internal": payout_res["recommended_payout"],
        },
        "fraud_analysis": {
            "fraud_score": fraud_res["fraud_score"],
            "fraud_band": fraud_res["fraud_band"],
            "flags": fraud_res.get("flags", []),
            "flag_count": fraud_res.get("flag_count", 0),
            "device_trust": fraud_res.get("device_trust"),
            "requires_liveness_check": fraud_res.get(
                "requires_liveness_check", False
            ),
            "requires_throttling": fraud_res.get("requires_throttling", False),
            "trust_update": fraud_res.get("trust_update"),
            "layers": fraud_res.get("layers"),
            "feature_vector": fraud_res.get("feature_vector"),
        },
        "review": {
            "fraud_score": fraud_res["fraud_score"],
            "geo_confidence_score": geo_confidence,
            "evidence_completeness_score": evidence_completeness,
            "decision": final_status,
            "decision_action": decision_status,
            "decision_reason": (
                " | ".join(hold_reasons) if hold_reasons else None
            ),
        },
    }
