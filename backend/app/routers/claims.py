"""
DEVTrails — Claims Router

Handles:
- POST /claims (Submit manual claim)
- GET /claims (List claims — worker sees own, admin sees all)
- GET /claims/{id} (View single claim + trace)
- POST /claims/{id}/review (Admin review action)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from backend.app.dependencies import get_current_user, require_insurer_admin
from backend.app.supabase_client import get_supabase_admin
from backend.app.services.claim_pipeline import run_claim_pipeline
from backend.app.services.evidence import extract_exif_metadata
from backend.app.services.gemini_analysis import generate_claim_narrative
import httpx

router = APIRouter(prefix="/claims", tags=["Claims"])

class ManualClaimRequest(BaseModel):
    claim_reason: str
    stated_lat: float | None = None
    stated_lng: float | None = None
    trigger_event_id: str | None = None
    shift_id: str | None = None
    evidence_url: str | None = None

class AdminReviewRequest(BaseModel):
    decision: str # "approve", "hold", "escalate", "reject"
    decision_reason: str | None = None

@router.post("/")
async def submit_claim(body: ManualClaimRequest, user: dict = Depends(get_current_user)):
    """Submit a manual claim."""
    sb = get_supabase_admin()
    
    # Needs worker_context
    worker_resp = sb.table("worker_profiles").select("*, zones(*)").eq("profile_id", user["id"]).maybe_single().execute()
    if not worker_resp.data:
        raise HTTPException(status_code=400, detail="Worker profile required to submit claim.")
        
    worker_context = worker_resp.data
    
    trigger_context = None
    if body.trigger_event_id:
        tg_resp = sb.table("trigger_events").select("*").eq("id", body.trigger_event_id).maybe_single().execute()
        trigger_context = tg_resp.data
        
    # Process Real Evidence if provided
    evidence_records = []
    if body.evidence_url:
        try:
            # Download image bytes mapped from frontend Storage url
            async with httpx.AsyncClient() as client:
                img_res = await client.get(body.evidence_url, timeout=10)
            img_res.raise_for_status()
            exif_data = extract_exif_metadata(img_res.content)

            evidence_records.append({
                "evidence_type": "photo",
                "storage_path": body.evidence_url,
                "exif_lat": exif_data.get("exif_lat"),
                "exif_lng": exif_data.get("exif_lng"),
                "exif_timestamp": exif_data.get("exif_timestamp"),
            })
        except Exception as e:
            print(f"Failed to fetch or parse evidence image: {e}")
            # Still append record but without EXIF if fetching failed
            evidence_records.append({
                "evidence_type": "photo",
                "storage_path": body.evidence_url
            })
        
    # Run the pipeline just to get initial scoring / traces
    pipeline_result = run_claim_pipeline(
        claim_id="pending",
        worker_context=worker_context,
        trigger_context=trigger_context,
        claim_mode="manual",
        evidence_records=evidence_records,
        claim_record={
            "stated_lat": body.stated_lat,
            "stated_lng": body.stated_lng,
            "claim_reason": body.claim_reason,
        }
    )
    
    # Store claim in DB
    initial_status = "submitted"
    
    claim_insert = {
        "worker_profile_id": user["id"],
        "trigger_event_id": body.trigger_event_id,
        "claim_mode": "manual",
        "claim_reason": body.claim_reason,
        "stated_lat": body.stated_lat,
        "stated_lng": body.stated_lng,
        "shift_id": body.shift_id,
        "claim_status": initial_status
    }
    
    ins_resp = sb.table("manual_claims").insert(claim_insert).execute()
    new_claim = ins_resp.data[0]
    claim_id = new_claim["id"]
    
    # Store claim evidence in DB
    for ev in evidence_records:
        ev["claim_id"] = claim_id
        sb.table("claim_evidence").insert(ev).execute()
    
    # Generate Admin Assistive AI Summary
    ai_summary = await generate_claim_narrative(
        claim_record=claim_insert,
        pipeline_result=pipeline_result,
        worker_context=worker_context
    )
    pipeline_result["ai_summary"] = ai_summary

    # Save the payout recommendation and initial scores
    payout_rec = pipeline_result["payout_recommendation"]
    payout_ins = {
        "claim_id": claim_id,
        "covered_weekly_income_b": payout_rec["covered_weekly_income_b"],
        "claim_probability_p": 0.15,
        "severity_score_s": payout_rec["severity_score_s"],
        "exposure_score_e": payout_rec["exposure_score_e"],
        "confidence_score_c": payout_rec["confidence_score_c"],
        "fraud_holdback_fh": payout_rec["fraud_holdback_fh"],
        "outlier_uplift_u": payout_rec["outlier_uplift_u"],
        "payout_cap": payout_rec["payout_cap"],
        "expected_payout": payout_rec["expected_payout"],
        "gross_premium": payout_rec["gross_premium"],
        "recommended_payout": payout_rec["recommended_payout"],
        "explanation_json": pipeline_result
    }
    sb.table("payout_recommendations").insert(payout_ins).execute()
    
    return {"status": "created", "claim": new_claim, "pipeline": pipeline_result}


@router.get("/")
async def list_claims(user: dict = Depends(get_current_user)):
    """List claims. Workers see their own; Admins see all."""
    sb = get_supabase_admin()
    
    query = sb.table("manual_claims").select("*, worker_profiles(city, platform_name), trigger_events(trigger_family)")
    
    if user["role"] == "worker":
        query = query.eq("worker_profile_id", user["id"])
        
    resp = query.order("claimed_at", desc=True).limit(50).execute()
    return {"claims": resp.data}


@router.get("/{claim_id}")
async def get_claim_detail(claim_id: str, user: dict = Depends(get_current_user)):
    """Get single claim detail, evidence, and payout recommendations."""
    sb = get_supabase_admin()
    
    claim_resp = sb.table("manual_claims").select(
        "*, worker_profiles(*, profiles(*)), trigger_events(*)"
    ).eq("id", claim_id).maybe_single().execute()
    
    if not claim_resp.data:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    claim_data = claim_resp.data
    
    # Check access
    if user["role"] == "worker" and claim_data["worker_profile_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    evidence_resp = sb.table("claim_evidence").select("*").eq("claim_id", claim_id).execute()
    payout_resp = sb.table("payout_recommendations").select("*").eq("claim_id", claim_id).maybe_single().execute()
    review_resp = sb.table("claim_reviews").select("*, insurer_profiles(company_name)").eq("claim_id", claim_id).execute()
    
    return {
        "claim": claim_data,
        "evidence": evidence_resp.data,
        "payout_recommendation": payout_resp.data,
        "reviews": review_resp.data
    }


@router.post("/{claim_id}/review", dependencies=[Depends(require_insurer_admin)])
async def admin_review_claim(claim_id: str, body: AdminReviewRequest, user: dict = Depends(get_current_user)):
    """Submit a manual decision/review for a claim."""
    sb = get_supabase_admin()
    
    ins_resp = sb.table("claim_reviews").insert({
        "claim_id": claim_id,
        "reviewer_profile_id": user["id"],
        "decision": body.decision,
        "decision_reason": body.decision_reason
    }).execute()
    
    # Update claim status
    status_mapping = {
        "approve": "approved",
        "hold": "held",
        "reject": "rejected",
        "escalate": "held" # Escalation implies holding for further review
    }
    
    new_status = status_mapping.get(body.decision, "held")
    sb.table("manual_claims").update({"claim_status": new_status}).eq("id", claim_id).execute()
    
    # Audit log (using new audit_events table)
    sb.table("audit_events").insert({
        "entity_type": "claim",
        "entity_id": claim_id,
        "action_type": f"claim_reviewed_{body.decision}",
        "actor_profile_id": user["id"],
        "event_payload": body.model_dump()
    }).execute()
    
    return {"status": "reviewed", "claim_id": claim_id, "decision": body.decision}
