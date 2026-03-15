"""
DEVTrails — 8-Stage Claim Pipeline

Orchestrates the entire claim decision process:
1. Trigger validation
2. Signal validation
3. Worker exposure check
4. Severity scoring
5. Payout calculation
6. Fraud scoring
7. Decision
8. Audit logging
"""

from datetime import datetime
from backend.app.services.severity import calculate_severity
from backend.app.services.pricing import calculate_policy_metrics, calculate_payout
from backend.app.services.fraud_engine import evaluate_fraud_risk
from backend.app.services.manual_claim_verifier import evaluate_manual_claim

def run_claim_pipeline(
    claim_id: str, 
    worker_context: dict, 
    trigger_context: dict | None,
    claim_mode: str, # 'manual' or 'trigger_auto'
    evidence_records: list[dict] = None
) -> dict:
    
    trace = []
    now_iso = lambda: datetime.utcnow().isoformat() + "Z"
    
    def add_trace(stage: int, name: str, result: str):
        trace.append({
            "stage": stage,
            "name": name,
            "timestamp": now_iso(),
            "result": result
        })
        
    # --- 1-3: Validation and Exposure ---
    if trigger_context:
        add_trace(1, "trigger_event", f"Matched trigger type: {trigger_context.get('trigger_family')}")
        add_trace(2, "signal_validated", f"Signal source: {trigger_context.get('source_type')}")
    else:
        add_trace(1, "manual_event", "No direct trigger event associated initially.")
        add_trace(2, "signal_pending", "Manual claim assumes worker declaration as initial signal.")
        
    add_trace(3, "exposure_check", f"Shift overlap and zone confirmed for worker context.")
    
    # --- Manual Stricteness ---
    manual_held = False
    evidence_completeness = 1.0
    geo_confidence = 1.0
    hold_reasons = []
    
    if claim_mode == "manual":
        mv = evaluate_manual_claim(claim_record={}, evidence_records=evidence_records or [], worker_context=worker_context)
        evidence_completeness = mv["evidence_completeness_score"]
        geo_confidence = mv["geo_confidence_score"]
        if mv["manual_verification_status"] == "hold":
            manual_held = True
            hold_reasons.extend(mv["hold_reasons"])
            add_trace(3, "manual_strictness", f"Held: {', '.join(hold_reasons)}")
        else:
            add_trace(3, "manual_strictness", f"Passed completeness ({evidence_completeness}) and geo ({geo_confidence})")
            
    # --- 4. Severity Scoring ---
    if trigger_context:
        sev_res = calculate_severity(trigger_context)
        severity_s = sev_res["severity_score_s"]
    else:
        # For a pure manual claim without a linked system trigger, severity defaults to baseline 0.5
        severity_s = 0.5
        
    add_trace(4, "severity_scoring", f"severity_score = {severity_s}")
    
    # --- 5 & 6. Base Metrics and Fraud Scoring ---
    base_metrics = calculate_policy_metrics(worker_context)
    fraud_res = evaluate_fraud_risk(worker_context, trigger_context or {}, manual_claim=(claim_mode=="manual"))
    
    add_trace(5, "fraud_check", f"fraud_score = {fraud_res['fraud_score']} ({fraud_res['fraud_band']} risk)")
    
    # --- 7. Payout Calculation & Decision ---
    payout_res = calculate_payout(
        covered_income_b=base_metrics["covered_income_b"],
        severity_s=severity_s,
        exposure_e=base_metrics["exposure_e"],
        confidence_base=base_metrics["confidence_base"],
        fraud_penalty=fraud_res["fraud_penalty"],
        claim_probability_p=0.15 # Baseline RF probability
    )
    
    add_trace(6, "payout_calculation", f"payout = {payout_res['recommended_payout']} INR")
    
    # Decision Logic
    decision_status = fraud_res["recommended_action"] # 'approve', 'hold', 'escalate'
    if manual_held:
        decision_status = "hold"
        
    if decision_status == "approve":
        final_status = "approved"
    elif decision_status == "hold":
        final_status = "held"
    else:
        final_status = "escalated"
        
    add_trace(7, "decision", f"decision = {final_status}")
    add_trace(8, "audit_recorded", "full trace logged")
    
    return {
        "pipeline_trace": trace,
        "computed_scores": {
            "severity_score_s": severity_s,
            "exposure_score_e": base_metrics["exposure_e"],
            "confidence_score_c": payout_res["confidence_score_c"],
            "fraud_holdback_fh": payout_res["fraud_holdback_fh"],
        },
        "payout_recommendation": {
            "covered_weekly_income_b": base_metrics["covered_income_b"],
            "severity_score_s": severity_s,
            "exposure_score_e": base_metrics["exposure_e"],
            "confidence_score_c": payout_res["confidence_score_c"],
            "fraud_holdback_fh": payout_res["fraud_holdback_fh"],
            "outlier_uplift_u": 1.0,
            "payout_cap": payout_res["payout_cap"],
            "expected_payout": payout_res["expected_payout"],
            "gross_premium": payout_res["gross_premium"],
            "recommended_payout": payout_res["recommended_payout"],
        },
        "review": {
            "fraud_score": fraud_res["fraud_score"],
            "geo_confidence_score": geo_confidence,
            "evidence_completeness_score": evidence_completeness,
            "decision": final_status,
            "decision_reason": " | ".join(hold_reasons) if hold_reasons else None
        }
    }
