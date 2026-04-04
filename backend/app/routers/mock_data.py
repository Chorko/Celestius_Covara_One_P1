"""
Covara One — Mock Data & Simulation Router

Provides endpoints for generating synthetic data and simulating claim scenarios
end-to-end without committing to the database. Useful for demo environments and EDA.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
import random

from backend.app.dependencies import require_insurer_admin
from backend.app.supabase_client import get_supabase_admin
from backend.app.seed import seed_all
from backend.app.services.claim_pipeline import get_claim_probability
from backend.app.services.fraud_engine import evaluate_fraud_risk
from backend.app.services.pricing import calculate_policy_metrics, calculate_payout

router = APIRouter(prefix="/simulate", tags=["Simulation & Mock Data"])

class ScenarioRequest(BaseModel):
    worker_id: str
    zone_id: str
    trigger_family: str
    raw_value: float


@router.post("/mock-data/generate", dependencies=[Depends(require_insurer_admin)])
async def generate_mock_data():
    """Generates synthetic data into the DB based on the seed scripts."""
    result = seed_all()
    return {"status": "success", "message": "Synthetic data generated.", "details": result}


@router.post("/claim-scenario", dependencies=[Depends(require_insurer_admin)])
async def simulate_claim_scenario(body: ScenarioRequest):
    """
    Simulates a claim through the 8-stage pipeline using real
    functions without committing records. Returns detailed diagnostics.
    """
    sb = get_supabase_admin()
    
    # 1. Fetch Worker Context
    worker_resp = sb.table("worker_profiles").select("*").eq("profile_id", body.worker_id).maybe_single().execute()
    worker_context = worker_resp.data or {
        "profile_id": body.worker_id,
        "trust_score": 0.85,
        "gps_consistency_score": 0.9,
    }
    
    # 2. Setup Trigger Context
    trigger_context = {
        "trigger_family": body.trigger_family,
        "raw_value": body.raw_value,
        "zone_id": body.zone_id,
    }
    
    # 3. Simulate Pipeline Components
    base_metrics = calculate_policy_metrics(worker_context)
    
    ml_prob = get_claim_probability(trigger_context, worker_context)
    
    # Simulate severity function based on threshold heuristics
    # (Since actual calculate_severity involves DB, we approximate here)
    severity_s = min(body.raw_value / 100.0 * 2.0, 1.0)
    
    fraud_res = evaluate_fraud_risk(
        worker_context=worker_context,
        trigger_context=trigger_context,
        zone_claims_last_hour=random.randint(1, 10),
    )
    
    payout_res = calculate_payout(
        covered_income_b=base_metrics["covered_income_b"],
        severity_s=severity_s,
        exposure_e=base_metrics["exposure_e"],
        confidence_base=base_metrics["confidence_base"],
        fraud_penalty=fraud_res["fraud_penalty"],
        claim_probability_p=ml_prob,
    )
    
    return {
        "simulation": "completed",
        "inputs": body.dict(),
        "worker_metrics": base_metrics,
        "ml_probability": ml_prob,
        "fraud_engine": fraud_res,
        "payout_calculation": payout_res,
        "recommended_action": fraud_res["recommended_action"],
    }
