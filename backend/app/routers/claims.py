"""
Covara One — Claims Router

Handles:
- POST /claims (Submit manual claim)
- GET /claims (List claims — worker sees own, admin sees all)
- GET /claims/{id} (View single claim + trace)
- POST /claims/{id}/review (Admin review action)
"""

from fastapi import APIRouter, Depends, HTTPException
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
    plan: str = "essential"  # "essential" or "plus"


class AdminReviewRequest(BaseModel):
    decision: str  # "approve", "hold", "escalate", "reject"
    decision_reason: str | None = None


@router.post("/")
async def submit_claim(
    body: ManualClaimRequest, user: dict = Depends(get_current_user)
):
    """Submit a manual claim."""
    sb = get_supabase_admin()

    # Validate plan
    if body.plan not in ("essential", "plus"):
        raise HTTPException(
            status_code=400,
            detail="Plan must be 'essential' or 'plus'.",
        )

    # Needs worker_context
    worker_resp = (
        sb.table("worker_profiles")
        .select("*, zones(*)")
        .eq("profile_id", user["id"])
        .maybe_single()
        .execute()
    )
    if not worker_resp.data:  # type: ignore
        raise HTTPException(
            status_code=400, detail="Worker profile required to submit claim."
        )

    worker_context = worker_resp.data  # type: ignore

    trigger_context = None
    if body.trigger_event_id:
        tg_resp = (
            sb.table("trigger_events")
            .select("*")
            .eq("id", body.trigger_event_id)
            .maybe_single()
            .execute()
        )
        trigger_context = tg_resp.data  # type: ignore

    # Process Real Evidence if provided
    evidence_records = []
    if body.evidence_url:
        try:
            # Download image bytes mapped from frontend Storage url
            async with httpx.AsyncClient() as client:
                img_res = await client.get(body.evidence_url, timeout=10)
            img_res.raise_for_status()
            exif_data = extract_exif_metadata(img_res.content)

            evidence_records.append(
                {
                    "evidence_type": "photo",
                    "storage_path": body.evidence_url,
                    "exif_lat": exif_data.get("exif_lat"),
                    "exif_lng": exif_data.get("exif_lng"),
                    "exif_timestamp": exif_data.get("exif_timestamp"),
                }
            )
        except Exception as e:
            print(f"Failed to fetch or parse evidence image: {e}")
            # Still append record but without EXIF if fetching failed
            evidence_records.append(
                {"evidence_type": "photo", "storage_path": body.evidence_url}
            )

    # Run the pipeline just to get initial scoring / traces
    pipeline_result = run_claim_pipeline(
        claim_id="pending",
        worker_context=worker_context,  # type: ignore
        trigger_context=trigger_context,  # type: ignore
        claim_mode="manual",
        evidence_records=evidence_records,
        claim_record={
            "stated_lat": body.stated_lat,
            "stated_lng": body.stated_lng,
            "claim_reason": body.claim_reason,
        },
        plan=body.plan,
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
        "claim_status": initial_status,
    }

    ins_resp = sb.table("manual_claims").insert(claim_insert).execute()
    new_claim = ins_resp.data[0]
    claim_id = new_claim["id"]  # type: ignore

    # Store claim evidence in DB
    for ev in evidence_records:
        ev["claim_id"] = claim_id
        sb.table("claim_evidence").insert(ev).execute()

    # Generate Admin Assistive AI Summary
    ai_summary = await generate_claim_narrative(
        claim_record=claim_insert,
        pipeline_result=pipeline_result,
        worker_context=worker_context,  # type: ignore
    )
    pipeline_result["ai_summary"] = ai_summary

    # Save the payout recommendation and initial scores
    cal = pipeline_result["internal_calibration"]
    payout_ins = {
        "claim_id": claim_id,
        "covered_weekly_income_b": cal["covered_weekly_income_b"],
        "claim_probability_p": 0.15,
        "severity_score_s": cal["severity_score_s"],
        "exposure_score_e": cal["exposure_score_e"],
        "confidence_score_c": cal["confidence_score_c"],
        "fraud_holdback_fh": cal["fraud_holdback_fh"],
        "outlier_uplift_u": cal["outlier_uplift_u"],
        "payout_cap": cal["payout_cap"],
        "expected_payout": cal["expected_payout"],
        "gross_premium": cal["gross_premium"],
        "recommended_payout": cal["recommended_payout"],
        "explanation_json": pipeline_result,
    }
    sb.table("payout_recommendations").insert(payout_ins).execute()

    return {
        "status": "created",
        "claim": new_claim,
        "pipeline": pipeline_result,
    }


@router.get("/")
async def list_claims(user: dict = Depends(get_current_user)):
    """List claims. Workers see their own; Admins see all."""
    sb = get_supabase_admin()

    query = sb.table("manual_claims").select(
        "*, worker_profiles(city, platform_name), trigger_events(trigger_family)"
    )

    if user["role"] == "worker":
        query = query.eq("worker_profile_id", user["id"])

    resp = query.order("claimed_at", desc=True).limit(50).execute()
    return {"claims": resp.data}


@router.get("/{claim_id}")
async def get_claim_detail(
    claim_id: str, user: dict = Depends(get_current_user)
):
    """Get single claim detail, evidence, and payout recommendations."""
    sb = get_supabase_admin()

    claim_resp = (
        sb.table("manual_claims")
        .select("*, worker_profiles(*, profiles(*)), trigger_events(*)")
        .eq("id", claim_id)
        .maybe_single()
        .execute()
    )

    if not claim_resp.data:  # type: ignore
        raise HTTPException(status_code=404, detail="Claim not found")

    claim_data = claim_resp.data  # type: ignore

    # Check access
    if (
        user["role"] == "worker"
        and claim_data["worker_profile_id"] != user["id"]  # type: ignore
    ):
        raise HTTPException(status_code=403, detail="Forbidden")

    evidence_resp = (
        sb.table("claim_evidence")
        .select("*")
        .eq("claim_id", claim_id)
        .execute()
    )
    payout_resp = (
        sb.table("payout_recommendations")
        .select("*")
        .eq("claim_id", claim_id)
        .maybe_single()
        .execute()
    )
    review_resp = (
        sb.table("claim_reviews")
        .select("*, insurer_profiles(company_name)")
        .eq("claim_id", claim_id)
        .execute()
    )

    return {
        "claim": claim_data,
        "evidence": evidence_resp.data,
        "payout_recommendation": payout_resp.data,  # type: ignore
        "reviews": review_resp.data,
    }


@router.post(
    "/{claim_id}/review", dependencies=[Depends(require_insurer_admin)]
)
async def admin_review_claim(
    claim_id: str,
    body: AdminReviewRequest,
    user: dict = Depends(get_current_user),
):
    """Submit a manual decision/review for a claim."""
    sb = get_supabase_admin()

    sb.table("claim_reviews").insert(
        {
            "claim_id": claim_id,
            "reviewer_profile_id": user["id"],
            "decision": body.decision,
            "decision_reason": body.decision_reason,
        }
    ).execute()

    # Update claim status — uses expanded state machine
    status_mapping = {
        "approve": "approved",
        "hold": "soft_hold_verification",
        "reject": "rejected",
        "escalate": "fraud_escalated_review",
        "flag_post_approval": "post_approval_flagged",
    }

    new_status = status_mapping.get(body.decision, "soft_hold_verification")
    sb.table("manual_claims").update({"claim_status": new_status}).eq(
        "id", claim_id
    ).execute()

    # Audit log (using new audit_events table)
    sb.table("audit_events").insert(
        {
            "entity_type": "claim",
            "entity_id": claim_id,
            "action_type": f"claim_reviewed_{body.decision}",
            "actor_profile_id": user["id"],
            "event_payload": body.model_dump(),
        }
    ).execute()

    return {
        "status": "reviewed",
        "claim_id": claim_id,
        "decision": body.decision,
    }


# ── Post-Approval Fraud Flagging (Gap §4.4) ──────────────────────────


class PostApprovalFlagRequest(BaseModel):
    fraud_severity: str = "moderate"  # minor / moderate / severe / critical
    reason: str | None = None


@router.post(
    "/{claim_id}/flag", dependencies=[Depends(require_insurer_admin)]
)
async def flag_post_approval(
    claim_id: str,
    body: PostApprovalFlagRequest,
    user: dict = Depends(get_current_user),
):
    """
    Flag a previously approved/paid claim for post-approval fraud.
    Applies trust score penalty to the worker and logs for audit.
    """
    from backend.app.services.region_validation_cache import (
        apply_post_approval_penalty,
    )

    sb = get_supabase_admin()

    # Validate the claim exists and is in an approved/paid state
    claim_resp = (
        sb.table("manual_claims")
        .select("*, worker_profiles(profile_id, trust_score)")
        .eq("id", claim_id)
        .maybe_single()
        .execute()
    )

    if not claim_resp.data:  # type: ignore
        raise HTTPException(status_code=404, detail="Claim not found")

    claim_data = claim_resp.data  # type: ignore
    if claim_data["claim_status"] not in ("approved", "paid", "auto_approved"):
        raise HTTPException(
            status_code=400,
            detail=f"Claim must be approved/paid to flag. Current: {claim_data['claim_status']}",
        )

    # Apply trust score penalty
    worker_profile = claim_data.get("worker_profiles", {})
    current_trust = float(worker_profile.get("trust_score", 0.8) or 0.8)
    penalty_result = apply_post_approval_penalty(
        worker_trust_score=current_trust,
        fraud_severity=body.fraud_severity,
    )

    # Update claim status to post_approval_flagged
    sb.table("manual_claims").update(
        {"claim_status": "post_approval_flagged"}
    ).eq("id", claim_id).execute()

    # Downgrade worker trust score
    worker_id = claim_data.get("worker_profile_id")
    if worker_id:
        sb.table("worker_profiles").update(
            {"trust_score": penalty_result["new_trust_score"]}
        ).eq("profile_id", worker_id).execute()

    # Record the review
    sb.table("claim_reviews").insert(
        {
            "claim_id": claim_id,
            "reviewer_profile_id": user["id"],
            "decision": "flag_post_approval",
            "decision_reason": (
                f"Post-approval fraud flag ({body.fraud_severity}): "
                f"{body.reason or 'No reason provided'}"
            ),
        }
    ).execute()

    # Audit log
    sb.table("audit_events").insert(
        {
            "entity_type": "claim",
            "entity_id": claim_id,
            "action_type": "post_approval_fraud_flag",
            "actor_profile_id": user["id"],
            "event_payload": {
                "fraud_severity": body.fraud_severity,
                "reason": body.reason,
                "penalty_result": penalty_result,
            },
        }
    ).execute()

    return {
        "status": "flagged",
        "claim_id": claim_id,
        "fraud_severity": body.fraud_severity,
        "trust_score_penalty": penalty_result,
    }


# ── Zero-Touch Auto-Claim Engine ──────────────────────────────────────


@router.post(
    "/auto-process",
    dependencies=[Depends(require_insurer_admin)],
    summary="Zero-Touch Auto-Claim Engine",
    description=(
        "Scans recent trigger events and automatically creates claims for "
        "every eligible worker — no manual filing required. "
        "This is the parametric insurance core: workers get paid without lifting a finger. "
        "Admin only. Safe to run repeatedly — duplicate claims are prevented by DB constraints."
    ),
)
async def auto_process_claims(lookback_hours: int = 6):
    """
    Run the zero-touch auto-claim engine.

    Finds all trigger_events in the last `lookback_hours` with severity
    'claim' or 'escalation', identifies eligible workers, runs the full
    claim pipeline for each, and persists results + payout recommendations.
    """
    from backend.app.services.auto_claim_engine import run_auto_claim_engine
    sb = get_supabase_admin()
    result = await run_auto_claim_engine(sb, lookback_hours=lookback_hours)
    return {
        "status": "complete",
        "lookback_hours": lookback_hours,
        **result,
    }


# ── Offline Sync (Dark Zone Correlation) ──────────────────────────────


class OfflineSyncPayload(BaseModel):
    stated_lat: float
    stated_lng: float
    offline_timestamp: str
    claim_reason: str = "Dark Zone Offline Sync"


class OfflineSyncRequest(BaseModel):
    sync_payloads: list[OfflineSyncPayload]
    plan: str = "essential"


@router.post(
    "/offline-sync",
    summary="Offline Claim Sync ('Dark Zone')",
    description=(
        "Called when a worker regains internet connectivity after being in a 'Dark Zone' "
        "(e.g., cell towers knocked out during a storm). Batches offline GPS timestamps. "
        "Claims are marked 'soft_hold_verification' to allow DBSCAN and regional correlation "
        "to verify if the zone actually experienced a network outage."
    ),
)
async def sync_offline_claims(
    body: OfflineSyncRequest, user: dict = Depends(get_current_user)
):
    """Sync batched offline claims."""
    sb = get_supabase_admin()

    # Validate worker
    worker_resp = (
        sb.table("worker_profiles").select("profile_id").eq("profile_id", user["id"]).maybe_single().execute()
    )
    if not worker_resp.data:
        raise HTTPException(status_code=400, detail="Worker profile required.")

    synced_claim_ids = []

    for payload in body.sync_payloads:
        claim_insert = {
            "worker_profile_id": user["id"],
            "claim_mode": "manual", # Technically auto/offline, but requires manual fraud verification
            "claim_reason": f"[OFFLINE SYNC @ {payload.offline_timestamp}] {payload.claim_reason}",
            "stated_lat": payload.stated_lat,
            "stated_lng": payload.stated_lng,
            "claim_status": "soft_hold_verification", # Force hold for regional anomaly check
        }
        ins_resp = sb.table("manual_claims").insert(claim_insert).execute()
        synced_claim_ids.append(ins_resp.data[0]["id"])

        # Also write an audit event for regional correlation tracing
        sb.table("audit_events").insert({
            "entity_type": "claim",
            "entity_id": ins_resp.data[0]["id"],
            "action_type": "dark_zone_offline_sync",
            "actor_profile_id": user["id"],
            "event_payload": payload.model_dump(),
        }).execute()

    return {
        "status": "synced",
        "synced_count": len(synced_claim_ids),
        "claim_ids": synced_claim_ids,
        "message": "Offline claims synced and held for regional anomaly correlation.",
    }
