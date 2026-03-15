"""
DEVTrails — Fraud Scoring Engine
Ghost Shift Detector Implementation

Produces `fraud_penalty`, `fraud_score`, and decision bands.
"""

def evaluate_fraud_risk(worker_context: dict, trigger_context: dict, manual_claim: bool = False) -> dict:
    """
    Evaluates fraud across 3 mock layers.
    Returns fraud_score, fraud_penalty, and decision band.
    """
    # Layer 1: Event Truth
    # How reliable is the signal source?
    reliability = trigger_context.get("source_reliability", 0.8)
    event_risk = 1.0 - reliability
    
    # Layer 2: Worker Truth (Shift Overlap & Activity)
    active_days = worker_context.get("active_days", 6)
    if active_days == 0:
        worker_risk = 0.9 # High risk if claim without normal activity
    else:
        worker_risk = 0.1
        
    # Layer 3: Behavioral Anomaly
    prior_claim_rate = worker_context.get("prior_claim_rate", 0.0)
    gps_consistency = worker_context.get("gps_consistency_score", 0.8)
    anomoly_risk = prior_claim_rate + (1.0 - gps_consistency)
    
    # Composite Fraud Score
    raw_fraud_score = (0.2 * event_risk) + (0.3 * worker_risk) + (0.5 * anomoly_risk)
    
    # Stricter bounds for manual claims
    if manual_claim:
        raw_fraud_score *= 1.25 
        
    fraud_score = min(max(raw_fraud_score, 0.0), 1.0)
    
    # Band determination
    if fraud_score < 0.25:
        band = "low"
        decision = "approve"
        fraud_penalty = fraud_score * 0.2
    elif fraud_score < 0.60:
        band = "medium"
        decision = "hold"
        fraud_penalty = fraud_score * 0.5
    else:
        band = "high"
        decision = "escalate"
        fraud_penalty = fraud_score * 0.8
        
    return {
        "fraud_score": round(fraud_score, 4),
        "fraud_penalty": round(fraud_penalty, 4),
        "fraud_band": band,
        "recommended_action": decision
    }
