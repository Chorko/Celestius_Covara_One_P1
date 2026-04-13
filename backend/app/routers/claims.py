"""
Covara One — Claims Router

Handles:
- POST /claims (Submit manual claim)
- GET /claims (List claims — worker sees own, admin sees all)
- GET /claims/{id} (View single claim + trace)
- POST /claims/{id}/review (Admin review action)
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from backend.app.config import settings
from backend.app.dependencies import get_current_user, require_insurer_admin
from backend.app.supabase_client import get_supabase_admin
from backend.app.services.claim_pipeline import run_claim_pipeline
from backend.app.services.device_context_security import (
    summarize_device_context_trust,
    verify_signed_device_context,
)
from backend.app.services.event_bus.outbox import enqueue_domain_event, persist_claim_with_outbox
from backend.app.services.evidence import extract_exif_metadata
from backend.app.services.gemini_analysis import generate_claim_narrative
from backend.app.services.observability import increment_counter, structured_log
from backend.app.services.payout_workflow import (
    get_payout_trace_for_claim,
    initiate_payout_for_claim,
)
from backend.app.services.review_workflow import (
    TERMINAL_CLAIM_STATUSES,
    build_review_meta,
    compute_review_due_at,
)
from backend.app.rate_limit import limiter
import httpx

router = APIRouter(prefix="/claims", tags=["Claims"])
logger = logging.getLogger("covara.claims")


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


class AssignClaimRequest(BaseModel):
    reviewer_profile_id: str | None = None
    due_in_hours: int | None = None
    assignment_note: str | None = None


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _request_id(request: Request | None) -> str | None:
    if request is None:
        return None

    state_id = getattr(getattr(request, "state", None), "request_id", None)
    if state_id:
        return str(state_id)

    header_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
    if header_id:
        return header_id

    return None


def _load_reviewer_name_map(sb, reviewer_ids: list[str]) -> dict[str, str]:
    if not reviewer_ids:
        return {}

    rows = (
        sb.table("profiles")
        .select("id, full_name")
        .in_("id", reviewer_ids)
        .execute()
        .data
        or []
    )
    return {
        row["id"]: row.get("full_name") or row["id"]
        for row in rows
        if row.get("id")
    }


def _prepare_review_meta(claim: dict, reviewer_name_map: dict[str, str], user: dict) -> dict:
    reviewer_user_id = user.get("id") if user.get("role") == "insurer_admin" else None
    return build_review_meta(
        claim=claim,
        reviewer_names_by_id=reviewer_name_map,
        current_user_id=reviewer_user_id,
        due_soon_hours=settings.review_sla_due_soon_hours,
    )


def _extract_device_trust_from_payout_row(payout_row: dict | None) -> dict | None:
    if not isinstance(payout_row, dict):
        return None

    explanation = payout_row.get("explanation_json")
    if not isinstance(explanation, dict):
        return None

    direct_summary = explanation.get("device_trust")
    if isinstance(direct_summary, dict):
        return direct_summary

    fraud_layers = (
        explanation.get("fraud_analysis", {})
        .get("layers", {})
        .get("anti_spoofing", {})
    )
    if not isinstance(fraud_layers, dict):
        return None

    device_flags = fraud_layers.get("flags_fired")
    return {
        "device_trust_tier": fraud_layers.get("device_trust_tier"),
        "device_trust_score": fraud_layers.get("device_trust_score"),
        "signal_confidence": fraud_layers.get("signal_confidence"),
        "attestation_verdict": fraud_layers.get("attestation_verdict"),
        "risk_signals": device_flags if isinstance(device_flags, list) else [],
    }


@router.post("")
@router.post("/")
@limiter.limit("5/minute")
async def submit_claim(
    request: Request, body: ManualClaimRequest, user: dict = Depends(get_current_user)
):
    """Submit a manual claim."""
    sb = get_supabase_admin()
    request_id = _request_id(request)

    structured_log(
        logger,
        logging.INFO,
        "claim.submit.started",
        request_id=request_id,
        worker_profile_id=user.get("id"),
        trigger_event_id=body.trigger_event_id,
    )

    # Optional mobile device context payload (cryptographically signed).
    raw_device_context = request.headers.get("X-Device-Context")
    device_context_signature = request.headers.get("X-Device-Context-Signature")
    device_context_timestamp = request.headers.get("X-Device-Context-Timestamp")
    device_context_key_id = request.headers.get("X-Device-Context-Key-Id")

    context_verification = verify_signed_device_context(
        raw_context=raw_device_context,
        signature=device_context_signature,
        timestamp=device_context_timestamp,
        secret=settings.device_context_hmac_secret,
        key_id=device_context_key_id,
    )

    # Backward compatible: web clients without context continue to work.
    # But if a context blob is sent, it must be validly signed.
    if raw_device_context and not context_verification.verified:
        increment_counter(
            "claim_submission_total",
            labels={"outcome": "invalid_device_context"},
        )
        structured_log(
            logger,
            logging.WARNING,
            "claim.submit.rejected.invalid_device_context",
            request_id=request_id,
            worker_profile_id=user.get("id"),
            verification_reason=context_verification.reason,
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid signed device context: {context_verification.reason}",
        )

    context_present = bool(raw_device_context)
    signature_verified = bool(context_present and context_verification.verified)

    device_context = dict(context_verification.context)
    trust_summary = summarize_device_context_trust(
        context=device_context,
        context_present=context_present,
        signature_verified=signature_verified,
    )
    device_context["context_present"] = context_present
    device_context["signature_verified"] = signature_verified
    device_context["signature_reason"] = context_verification.reason
    device_context["schema_version"] = context_verification.schema_version
    device_context["nonce"] = context_verification.nonce
    device_context["device_trust_score"] = trust_summary["device_trust_score"]
    device_context["device_trust_tier"] = trust_summary["device_trust_tier"]
    device_context["device_risk_signals"] = trust_summary["risk_signals"]
    if context_verification.key_id:
        device_context["key_id"] = context_verification.key_id

    if trust_summary.get("device_trust_tier") in {"low", "high_risk"}:
        increment_counter(
            "claim_device_trust_degraded_total",
            labels={
                "tier": str(trust_summary.get("device_trust_tier") or "unknown"),
                "signature_verified": str(signature_verified).lower(),
            },
        )

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
            structured_log(
                logger,
                logging.WARNING,
                "claim.submit.evidence_parse_failed",
                request_id=request_id,
                worker_profile_id=user.get("id"),
                error=str(e),
            )
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
        device_context=device_context,
        claim_record={
            "stated_lat": body.stated_lat,
            "stated_lng": body.stated_lng,
            "claim_reason": body.claim_reason,
            "device_id": device_context.get("hardware_id"),
            "client_ip": request.client.host if request.client else None,
        },
        plan=body.plan,
    )

    pipeline_result["device_context_security"] = {
        "context_present": context_present,
        "signature_verified": signature_verified,
        "verification_reason": context_verification.reason,
        "timestamp": context_verification.timestamp,
        "key_id": context_verification.key_id,
        "schema_version": context_verification.schema_version,
        "nonce": context_verification.nonce,
        "trust_summary": trust_summary,
    }
    pipeline_result["device_trust"] = trust_summary

    # Build persistence rows
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
        "assignment_state": "unassigned",
        "review_due_at": compute_review_due_at(None, settings.review_sla_hours),
    }

    # Generate Admin Assistive AI Summary
    ai_summary = await generate_claim_narrative(
        claim_record=claim_insert,
        pipeline_result=pipeline_result,
        worker_context=worker_context,  # type: ignore
    )
    pipeline_result["ai_summary"] = ai_summary

    # Build payout recommendation row
    cal = pipeline_result["internal_calibration"]
    payout_ins = {
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
        "recommended_payout": cal.get(
            "recommended_payout_internal",
            pipeline_result.get("parametric_payout", {}).get("parametric_payout", 0),
        ),
        "explanation_json": pipeline_result,
    }

    submitted_event_payload = {
        "worker_profile_id": user["id"],
        "claim_mode": "manual",
        "trigger_event_id": body.trigger_event_id,
        "claim_status": initial_status,
        "plan": body.plan,
        "device_context_present": bool(raw_device_context),
        "signature_verified": context_verification.verified,
        "request_id": request_id,
    }

    persist_result = await persist_claim_with_outbox(
        sb=sb,
        claim_row=claim_insert,
        payout_row=payout_ins,
        event_type="claim.submitted",
        event_key=str(user["id"]),
        event_source="claims.submit_claim",
        event_payload=submitted_event_payload,
    )

    if persist_result.get("duplicate_skipped"):
        increment_counter(
            "claim_submission_total",
            labels={"outcome": "duplicate_skipped"},
        )
        structured_log(
            logger,
            logging.WARNING,
            "claim.submit.duplicate_skipped",
            request_id=request_id,
            worker_profile_id=user.get("id"),
            trigger_event_id=body.trigger_event_id,
        )
        raise HTTPException(
            status_code=409,
            detail="Duplicate worker-event claim detected.",
        )

    claim_id = persist_result.get("claim_id")
    if not claim_id:
        raise HTTPException(status_code=500, detail="Failed to persist claim transaction")

    # Store claim evidence in DB (outside transaction; can be retried independently).
    for ev in evidence_records:
        ev["claim_id"] = claim_id
        sb.table("claim_evidence").insert(ev).execute()

    claim_resp = (
        sb.table("manual_claims")
        .select("*")
        .eq("id", claim_id)
        .maybe_single()
        .execute()
    )
    new_claim = claim_resp.data or {**claim_insert, "id": claim_id}

    increment_counter(
        "claim_submission_total",
        labels={"outcome": "created"},
    )
    structured_log(
        logger,
        logging.INFO,
        "claim.submit.completed",
        request_id=request_id,
        worker_profile_id=user.get("id"),
        claim_id=claim_id,
        trust_tier=trust_summary.get("device_trust_tier"),
    )

    return {
        "status": "created",
        "claim": new_claim,
        "pipeline": pipeline_result,
    }


@router.get("")
@router.get("/")
async def list_claims(
    queue: str = Query("all", description="all | mine | unassigned | overdue"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page (max 100)"),
    user: dict = Depends(get_current_user),
):
    """List claims with pagination. Workers see their own; Admins see all."""
    sb = get_supabase_admin()
    queue_key = (queue or "all").strip().lower()
    offset = (page - 1) * page_size

    query = sb.table("manual_claims").select(
        "*, worker_profiles(city, platform_name), trigger_events(trigger_family)",
        count="exact",
    )

    if user["role"] == "worker":
        query = query.eq("worker_profile_id", user["id"])

    resp = query.order("claimed_at", desc=True).range(offset, offset + page_size - 1).execute()
    claims = resp.data or []
    total_count = resp.count or len(claims)

    if user["role"] == "worker":
        return {"claims": claims}

    reviewer_ids = sorted(
        {
            c.get("assigned_reviewer_profile_id")
            for c in claims
            if c.get("assigned_reviewer_profile_id")
        }
    )
    reviewer_name_map = _load_reviewer_name_map(sb, reviewer_ids)

    for claim in claims:
        meta = _prepare_review_meta(claim, reviewer_name_map, user)
        claim["review_meta"] = meta
        if meta.get("assigned_reviewer_profile_id"):
            claim["assigned_reviewer"] = {
                "id": meta.get("assigned_reviewer_profile_id"),
                "full_name": meta.get("assigned_reviewer_name"),
            }

    if queue_key == "mine":
        claims = [
            c
            for c in claims
            if c.get("review_meta", {}).get("assigned_reviewer_profile_id")
            == user["id"]
        ]
    elif queue_key == "unassigned":
        claims = [
            c
            for c in claims
            if c.get("review_meta", {}).get("assignment_state") == "unassigned"
        ]
    elif queue_key == "overdue":
        claims = [
            c
            for c in claims
            if c.get("review_meta", {}).get("sla_status") == "overdue"
        ]

    def _sort_claim(item: dict):
        meta = item.get("review_meta", {})
        status_rank = {
            "overdue": 0,
            "due_soon": 1,
            "on_track": 2,
            "not_set": 3,
            "escalated": 4,
            "resolved": 5,
        }
        sla_rank = status_rank.get(meta.get("sla_status"), 9)
        hours_to_due = meta.get("hours_to_due")
        due_rank = hours_to_due if isinstance(hours_to_due, (float, int)) else 10_000
        return (sla_rank, due_rank)

    claims.sort(key=_sort_claim)
    return {
        "claims": claims,
        "queue": queue_key,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total_count,
            "total_pages": max(1, (total_count + page_size - 1) // page_size),
        },
    }


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
    payout_trace = get_payout_trace_for_claim(sb, claim_id)
    device_trust = _extract_device_trust_from_payout_row(payout_resp.data)  # type: ignore[arg-type]

    reviewer_name_map: dict[str, str] = {}
    assigned_reviewer_id = claim_data.get("assigned_reviewer_profile_id")
    if assigned_reviewer_id:
        reviewer_name_map = _load_reviewer_name_map(sb, [assigned_reviewer_id])

    claim_data["review_meta"] = _prepare_review_meta(
        claim_data,
        reviewer_name_map,
        user,
    )
    if assigned_reviewer_id:
        claim_data["assigned_reviewer"] = {
            "id": assigned_reviewer_id,
            "full_name": reviewer_name_map.get(assigned_reviewer_id),
        }

    return {
        "claim": claim_data,
        "evidence": evidence_resp.data,
        "payout_recommendation": payout_resp.data,  # type: ignore
        "payout_trace": payout_trace,
        "device_trust": device_trust,
        "reviews": review_resp.data,
    }


@router.post(
    "/{claim_id}/assign", dependencies=[Depends(require_insurer_admin)]
)
async def assign_claim(
    claim_id: str,
    body: AssignClaimRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Assign claim ownership and SLA due timestamp for review operations."""
    sb = get_supabase_admin()
    request_id = _request_id(request)
    claim_resp = (
        sb.table("manual_claims")
        .select(
            "id, claimed_at, claim_status, assigned_reviewer_profile_id, assignment_state, review_due_at"
        )
        .eq("id", claim_id)
        .maybe_single()
        .execute()
    )
    claim_row = claim_resp.data
    if not claim_row:
        raise HTTPException(status_code=404, detail="Claim not found")

    if claim_row.get("claim_status") in TERMINAL_CLAIM_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Cannot reassign a claim in terminal status.",
        )

    reviewer_id = body.reviewer_profile_id or user["id"]
    reviewer_exists = (
        sb.table("insurer_profiles")
        .select("profile_id")
        .eq("profile_id", reviewer_id)
        .maybe_single()
        .execute()
        .data
    )
    if not reviewer_exists:
        raise HTTPException(
            status_code=400,
            detail="Assigned reviewer must be a valid insurer admin profile.",
        )

    due_hours = body.due_in_hours or settings.review_sla_hours
    if due_hours < 1 or due_hours > 240:
        raise HTTPException(
            status_code=400,
            detail="due_in_hours must be between 1 and 240.",
        )

    now_iso = _now_iso()
    update_payload = {
        "assigned_reviewer_profile_id": reviewer_id,
        "assignment_state": "assigned",
        "assigned_at": now_iso,
        "review_due_at": compute_review_due_at(claim_row.get("claimed_at"), due_hours),
    }

    sb.table("manual_claims").update(update_payload).eq("id", claim_id).execute()

    sb.table("audit_events").insert(
        {
            "entity_type": "claim",
            "entity_id": claim_id,
            "action_type": "claim_assigned",
            "actor_profile_id": user["id"],
            "event_payload": {
                "reviewer_profile_id": reviewer_id,
                "due_in_hours": due_hours,
                "assignment_note": body.assignment_note,
                "request_id": request_id,
            },
        }
    ).execute()

    try:
        await enqueue_domain_event(
            sb=sb,
            event_type="claim.assigned",
            key=claim_id,
            source="claims.assign_claim",
            payload={
                "claim_id": claim_id,
                "assigned_reviewer_profile_id": reviewer_id,
                "assigned_by": user["id"],
                "review_due_at": update_payload["review_due_at"],
                "request_id": request_id,
            },
        )
    except Exception as e:
        structured_log(
            logger,
            logging.WARNING,
            "claim.assign.event_publish_failed",
            request_id=request_id,
            claim_id=claim_id,
            error=str(e),
        )

    updated_claim = {
        **claim_row,
        **update_payload,
    }
    reviewer_name_map = _load_reviewer_name_map(sb, [reviewer_id])
    meta = _prepare_review_meta(updated_claim, reviewer_name_map, user)

    increment_counter(
        "claim_assignment_total",
        labels={"outcome": "assigned"},
    )
    structured_log(
        logger,
        logging.INFO,
        "claim.assign.completed",
        request_id=request_id,
        claim_id=claim_id,
        assigned_reviewer_profile_id=reviewer_id,
        due_in_hours=due_hours,
    )

    return {
        "status": "assigned",
        "claim_id": claim_id,
        "assigned_reviewer_profile_id": reviewer_id,
        "review_meta": meta,
    }


@router.post(
    "/{claim_id}/review", dependencies=[Depends(require_insurer_admin)]
)
async def admin_review_claim(
    claim_id: str,
    body: AdminReviewRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Submit a manual decision/review for a claim."""
    sb = get_supabase_admin()
    request_id = _request_id(request)

    claim_resp = (
        sb.table("manual_claims")
        .select(
            "id, claimed_at, claim_status, assigned_reviewer_profile_id, assignment_state, assigned_at, first_reviewed_at, review_due_at"
        )
        .eq("id", claim_id)
        .maybe_single()
        .execute()
    )
    claim_row = claim_resp.data
    if not claim_row:
        raise HTTPException(status_code=404, detail="Claim not found")

    owner_id = claim_row.get("assigned_reviewer_profile_id")
    if owner_id and owner_id != user["id"]:
        raise HTTPException(
            status_code=409,
            detail="Claim is assigned to another reviewer.",
        )

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
    now_iso = _now_iso()
    claim_update = {
        "claim_status": new_status,
        "last_reviewed_at": now_iso,
        "assigned_reviewer_profile_id": owner_id or user["id"],
        "assigned_at": claim_row.get("assigned_at") or now_iso,
        "review_due_at": claim_row.get("review_due_at")
        or compute_review_due_at(claim_row.get("claimed_at"), settings.review_sla_hours),
    }

    if not claim_row.get("first_reviewed_at"):
        claim_update["first_reviewed_at"] = now_iso

    if body.decision == "escalate":
        claim_update["assignment_state"] = "escalated"
        claim_update["escalated_at"] = now_iso
        claim_update["escalation_reason"] = body.decision_reason
    elif body.decision in {"approve", "reject", "flag_post_approval"}:
        claim_update["assignment_state"] = "resolved"
    else:
        claim_update["assignment_state"] = "in_review"

    sb.table("manual_claims").update(claim_update).eq("id", claim_id).execute()

    # Audit log (using new audit_events table)
    sb.table("audit_events").insert(
        {
            "entity_type": "claim",
            "entity_id": claim_id,
            "action_type": f"claim_reviewed_{body.decision}",
            "actor_profile_id": user["id"],
            "event_payload": {
                **body.model_dump(),
                "assignment_state": claim_update.get("assignment_state"),
                "review_due_at": claim_update.get("review_due_at"),
                "request_id": request_id,
            },
        }
    ).execute()

    try:
        await enqueue_domain_event(
            sb=sb,
            event_type="claim.reviewed",
            key=claim_id,
            source="claims.admin_review_claim",
            payload={
                "claim_id": claim_id,
                "reviewer_profile_id": user["id"],
                "decision": body.decision,
                "decision_reason": body.decision_reason,
                "resulting_status": new_status,
                "assignment_state": claim_update.get("assignment_state"),
                "request_id": request_id,
            },
        )
    except Exception as e:
        structured_log(
            logger,
            logging.WARNING,
            "claim.review.event_publish_failed",
            request_id=request_id,
            claim_id=claim_id,
            decision=body.decision,
            error=str(e),
        )

    payout_result = None
    if body.decision == "approve":
        try:
            payout_result = await initiate_payout_for_claim(
                sb,
                claim_id=claim_id,
                initiated_by_profile_id=user["id"],
                trigger_source="claims.admin_review_claim",
                request_id=request_id,
                force_retry=False,
                initiation_note="auto_initiated_from_review_approval",
            )
        except ValueError as e:
            payout_result = {
                "status": "not_initiated",
                "reason": str(e),
            }
        except Exception as e:
            payout_result = {
                "status": "initiation_error",
                "reason": str(e),
            }

    increment_counter(
        "claim_review_actions_total",
        labels={
            "decision": body.decision,
            "resulting_status": new_status,
        },
    )
    structured_log(
        logger,
        logging.INFO,
        "claim.review.completed",
        request_id=request_id,
        claim_id=claim_id,
        reviewer_profile_id=user.get("id"),
        decision=body.decision,
        resulting_status=new_status,
    )

    return {
        "status": "reviewed",
        "claim_id": claim_id,
        "decision": body.decision,
        "assignment_state": claim_update.get("assignment_state"),
        "payout": payout_result,
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
    request: Request,
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
    request_id = _request_id(request)

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

    owner_id = claim_data.get("assigned_reviewer_profile_id")
    if owner_id and owner_id != user["id"]:
        raise HTTPException(
            status_code=409,
            detail="Claim is assigned to another reviewer.",
        )

    # Apply trust score penalty
    worker_profile = claim_data.get("worker_profiles", {})
    current_trust = float(worker_profile.get("trust_score", 0.8) or 0.8)
    penalty_result = apply_post_approval_penalty(
        worker_trust_score=current_trust,
        fraud_severity=body.fraud_severity,
    )

    now_iso = _now_iso()
    # Update claim status to post_approval_flagged and close assignment loop.
    sb.table("manual_claims").update(
        {
            "claim_status": "post_approval_flagged",
            "assignment_state": "resolved",
            "assigned_reviewer_profile_id": owner_id or user["id"],
            "assigned_at": claim_data.get("assigned_at") or now_iso,
            "first_reviewed_at": claim_data.get("first_reviewed_at") or now_iso,
            "last_reviewed_at": now_iso,
        }
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
                "request_id": request_id,
            },
        }
    ).execute()

    increment_counter(
        "claim_post_approval_flags_total",
        labels={"severity": body.fraud_severity},
    )
    structured_log(
        logger,
        logging.WARNING,
        "claim.flagged_post_approval",
        request_id=request_id,
        claim_id=claim_id,
        reviewer_profile_id=user.get("id"),
        severity=body.fraud_severity,
    )

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
async def auto_process_claims(request: Request, lookback_hours: int = 6):
    """
    Run the zero-touch auto-claim engine.

    Finds all trigger_events in the last `lookback_hours` with severity
    'claim' or 'escalation', identifies eligible workers, runs the full
    claim pipeline for each, and persists results + payout recommendations.
    """
    from backend.app.services.auto_claim_engine import run_auto_claim_engine
    sb = get_supabase_admin()
    request_id = _request_id(request)

    structured_log(
        logger,
        logging.INFO,
        "claims.auto_process.started",
        request_id=request_id,
        lookback_hours=lookback_hours,
    )

    result = await run_auto_claim_engine(sb, lookback_hours=lookback_hours)

    try:
        await enqueue_domain_event(
            sb=sb,
            event_type="claims.auto_process.completed",
            key="auto_process",
            source="claims.auto_process_claims",
            payload={
                "lookback_hours": lookback_hours,
                "triggers_scanned": result.get("triggers_scanned", 0),
                "workers_eligible": result.get("workers_eligible", 0),
                "claims_auto_approved": result.get("claims_auto_approved", 0),
                "claims_needs_review": result.get("claims_needs_review", 0),
                "claims_held": result.get("claims_held", 0),
                "claims_rejected": result.get("claims_rejected", 0),
                "duplicates_skipped": result.get("duplicates_skipped", 0),
                "request_id": request_id,
            },
        )
    except Exception as e:
        structured_log(
            logger,
            logging.WARNING,
            "claims.auto_process.event_publish_failed",
            request_id=request_id,
            error=str(e),
        )

    increment_counter(
        "claims_auto_process_runs_total",
        labels={"outcome": "completed"},
    )
    increment_counter(
        "claims_auto_process_claims_total",
        amount=int(result.get("claims_auto_approved", 0)),
        labels={"outcome": "auto_approved"},
    )
    increment_counter(
        "claims_auto_process_claims_total",
        amount=int(result.get("claims_needs_review", 0)),
        labels={"outcome": "needs_review"},
    )
    increment_counter(
        "claims_auto_process_claims_total",
        amount=int(result.get("claims_held", 0)),
        labels={"outcome": "held"},
    )
    increment_counter(
        "claims_auto_process_claims_total",
        amount=int(result.get("claims_rejected", 0)),
        labels={"outcome": "rejected"},
    )
    structured_log(
        logger,
        logging.INFO,
        "claims.auto_process.completed",
        request_id=request_id,
        triggers_scanned=result.get("triggers_scanned", 0),
        workers_eligible=result.get("workers_eligible", 0),
        claims_auto_approved=result.get("claims_auto_approved", 0),
        claims_needs_review=result.get("claims_needs_review", 0),
        claims_held=result.get("claims_held", 0),
        claims_rejected=result.get("claims_rejected", 0),
    )

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
@limiter.limit("3/minute")
async def sync_offline_claims(
    request: Request, body: OfflineSyncRequest, user: dict = Depends(get_current_user)
):
    """Sync batched offline claims."""
    sb = get_supabase_admin()
    request_id = _request_id(request)

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
            "assignment_state": "unassigned",
            "review_due_at": compute_review_due_at(None, settings.review_sla_hours),
        }
        ins_resp = sb.table("manual_claims").insert(claim_insert).execute()
        synced_claim_ids.append(ins_resp.data[0]["id"])

        # Also write an audit event for regional correlation tracing
        sb.table("audit_events").insert({
            "entity_type": "claim",
            "entity_id": ins_resp.data[0]["id"],
            "action_type": "dark_zone_offline_sync",
            "actor_profile_id": user["id"],
            "event_payload": {
                **payload.model_dump(),
                "request_id": request_id,
            },
        }).execute()

    try:
        await enqueue_domain_event(
            sb=sb,
            event_type="claim.offline_synced",
            key=str(user["id"]),
            source="claims.sync_offline_claims",
            payload={
                "worker_profile_id": user["id"],
                "synced_count": len(synced_claim_ids),
                "claim_ids": synced_claim_ids,
                "request_id": request_id,
            },
        )
    except Exception as e:
        structured_log(
            logger,
            logging.WARNING,
            "claim.offline_sync.event_publish_failed",
            request_id=request_id,
            worker_profile_id=user.get("id"),
            error=str(e),
        )

    increment_counter(
        "claim_offline_sync_total",
        amount=len(synced_claim_ids),
        labels={"outcome": "synced"},
    )
    structured_log(
        logger,
        logging.INFO,
        "claim.offline_sync.completed",
        request_id=request_id,
        worker_profile_id=user.get("id"),
        synced_count=len(synced_claim_ids),
    )

    return {
        "status": "synced",
        "synced_count": len(synced_claim_ids),
        "claim_ids": synced_claim_ids,
        "message": "Offline claims synced and held for regional anomaly correlation.",
    }


