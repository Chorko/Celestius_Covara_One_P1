"""Payout workflow orchestration.

Handles payout initiation, provider webhook settlement ingestion, state transitions,
and retry scheduling while keeping provider-specific logic outside this module.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from backend.app.services.event_bus.outbox import enqueue_domain_event
from backend.app.services.observability import increment_counter, structured_log
from backend.app.services.payout_provider import (
    PAYOUT_STATUS_VALUES,
    get_payout_provider,
    normalize_payout_status,
    PayoutInitiationCommand,
)


logger = logging.getLogger("covara.payout_workflow")


PAYOUT_TERMINAL_STATUSES = {"settled", "cancelled", "reversed"}
PAYOUT_RETRYABLE_STATUSES = {"failed", "manual_review", "cancelled", "reversed"}


ALLOWED_PAYOUT_TRANSITIONS: dict[str, set[str]] = {
    "initiated": {"pending", "processing", "settled", "failed", "cancelled", "manual_review"},
    "pending": {"processing", "settled", "failed", "cancelled", "manual_review"},
    "processing": {"settled", "failed", "reversed", "manual_review"},
    "settled": {"reversed"},
    "failed": {"initiated", "cancelled", "manual_review"},
    "manual_review": {"initiated", "processing", "settled", "cancelled", "failed"},
    "cancelled": {"initiated"},
    "reversed": {"manual_review"},
}


def _extract_device_trust_from_explanation(explanation: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(explanation, dict):
        return {}

    direct = explanation.get("device_trust")
    if isinstance(direct, dict):
        return direct

    fraud_analysis = explanation.get("fraud_analysis")
    if isinstance(fraud_analysis, dict):
        nested = fraud_analysis.get("device_trust")
        if isinstance(nested, dict):
            return nested
        anti_spoof = (fraud_analysis.get("layers") or {}).get("anti_spoofing")
        if isinstance(anti_spoof, dict):
            return {
                "device_trust_tier": anti_spoof.get("device_trust_tier"),
                "signal_confidence": anti_spoof.get("signal_confidence"),
                "attestation_verdict": anti_spoof.get("attestation_verdict"),
                "risk_signals": anti_spoof.get("flags_fired")
                if isinstance(anti_spoof.get("flags_fired"), list)
                else [],
            }

    return {}


def _resolve_version_snapshot(sb, table_name: str, version_id: Any) -> dict[str, Any] | None:
    resolved_id = str(version_id or "").strip()
    if not resolved_id:
        return None

    try:
        row = (
            sb.table(table_name)
            .select("id, version_key")
            .eq("id", resolved_id)
            .maybe_single()
            .execute()
            .data
        )
    except Exception:
        row = None

    if isinstance(row, dict):
        return {
            "id": row.get("id") or resolved_id,
            "key": row.get("version_key"),
        }

    return {
        "id": resolved_id,
        "key": None,
    }


def build_trust_stamp_for_claim(sb, claim_id: str) -> dict[str, Any]:
    claim_row: dict[str, Any] = {}
    try:
        claim_row = (
            sb.table("manual_claims")
            .select("id, rule_version_id, model_version_id")
            .eq("id", claim_id)
            .maybe_single()
            .execute()
            .data
            or {}
        )
    except Exception:
        claim_row = {}

    explanation_json: dict[str, Any] = {}
    try:
        payout_rec = (
            sb.table("payout_recommendations")
            .select("explanation_json")
            .eq("claim_id", claim_id)
            .maybe_single()
            .execute()
            .data
            or {}
        )
        if isinstance(payout_rec.get("explanation_json"), dict):
            explanation_json = payout_rec["explanation_json"]
    except Exception:
        explanation_json = {}

    fraud_analysis = explanation_json.get("fraud_analysis")
    if not isinstance(fraud_analysis, dict):
        fraud_analysis = {}

    device_trust = _extract_device_trust_from_explanation(explanation_json)

    trust_stamp: dict[str, Any] = {
        "device_trust_tier": device_trust.get("device_trust_tier"),
        "signal_confidence": device_trust.get("signal_confidence"),
        "attestation_verdict": device_trust.get("attestation_verdict"),
        "fraud_score_band": fraud_analysis.get("fraud_band"),
        "version_governance": {
            "rule_version": _resolve_version_snapshot(
                sb,
                "rule_versions",
                claim_row.get("rule_version_id"),
            ),
            "model_version": _resolve_version_snapshot(
                sb,
                "model_versions",
                claim_row.get("model_version_id"),
            ),
        },
    }

    risk_signals = device_trust.get("risk_signals")
    if isinstance(risk_signals, list):
        trust_stamp["risk_signals"] = risk_signals

    return trust_stamp


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _hash_payload(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _retry_next_at(retry_count: int) -> str:
    delay_minutes = min(12 * 60, 5 * (2 ** max(0, retry_count - 1)))
    return (
        _utc_now() + timedelta(minutes=delay_minutes)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _extract_missing_column_name(exc: Exception) -> str | None:
    message = str(exc)
    patterns = [
        r"could not find the '([^']+)' column",
        r'column\s+[\w\."]+\.([a-zA-Z_][\w]*)\s+does not exist',
        r"column\s+\"?([a-zA-Z_][\w]*)\"?\s+does not exist",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return str(match.group(1))
    return None


def _is_not_null_constraint_on_column(exc: Exception, column: str) -> bool:
    message = str(exc).lower()
    needle = f'null value in column "{column.lower()}"'
    return needle in message and "violates not-null constraint" in message


def _legacy_payout_status_fallback(status: str) -> str | None:
    normalized = normalize_payout_status(status)
    mapping = {
        "pending": "submitted",
        "settled": "paid",
        "cancelled": "failed",
        "reversed": "failed",
    }
    return mapping.get(normalized)


def _insert_settlement_event_row(sb, row: dict[str, Any]) -> list[dict[str, Any]]:
    """Insert settlement row while tolerating missing columns in older DB schemas."""
    payload = dict(row)
    last_exc: Exception | None = None

    for _ in range(8):
        try:
            return sb.table("payout_settlement_events").insert(payload).execute().data or []
        except Exception as exc:
            last_exc = exc
            missing_col = _extract_missing_column_name(exc)
            if not missing_col or missing_col not in payload:
                raise
            payload.pop(missing_col, None)

    if last_exc:
        raise last_exc
    return []


def _update_settlement_event_row(
    sb,
    settlement_event_id: str,
    update_payload: dict[str, Any],
) -> None:
    """Update settlement row while tolerating missing columns in older DB schemas."""
    payload = dict(update_payload)
    last_exc: Exception | None = None

    for _ in range(8):
        if not payload:
            return
        try:
            sb.table("payout_settlement_events").update(payload).eq("id", settlement_event_id).execute()
            return
        except Exception as exc:
            last_exc = exc
            missing_col = _extract_missing_column_name(exc)
            if not missing_col or missing_col not in payload:
                raise
            payload.pop(missing_col, None)

    if last_exc:
        raise last_exc


def _update_payout_request_row(
    sb,
    payout_request_id: str,
    update_payload: dict[str, Any],
) -> dict[str, Any]:
    """Update payout request row while tolerating missing columns in older DB schemas."""
    payload = dict(update_payload)
    last_exc: Exception | None = None

    for _ in range(8):
        if not payload:
            return {}
        try:
            sb.table("payout_requests").update(payload).eq("id", payout_request_id).execute()
            return payload
        except Exception as exc:
            last_exc = exc

            message = str(exc).lower()
            if "payout_requests_status_check" in message and "status" in payload:
                fallback_status = _legacy_payout_status_fallback(str(payload.get("status") or ""))
                if fallback_status and fallback_status != payload.get("status"):
                    payload["status"] = fallback_status
                    continue

            missing_col = _extract_missing_column_name(exc)
            if not missing_col or missing_col not in payload:
                raise
            payload.pop(missing_col, None)

    if last_exc:
        raise last_exc
    return {}


def _extract_webhook_fields(payload: dict[str, Any]) -> dict[str, str]:
    provider_event_id = str(
        payload.get("provider_event_id")
        or payload.get("event_id")
        or payload.get("id")
        or payload.get("eventId")
        or ""
    )
    provider_reference_id = str(
        payload.get("provider_reference_id")
        or payload.get("reference_id")
        or payload.get("transaction_id")
        or payload.get("payout_id")
        or ""
    )
    correlation_id = str(
        payload.get("correlation_id")
        or payload.get("reference")
        or payload.get("request_id")
        or ""
    )
    event_type = str(
        payload.get("event_type")
        or payload.get("type")
        or payload.get("event")
        or "payout.settlement"
    )
    raw_status = str(payload.get("status") or payload.get("state") or "")
    status = normalize_payout_status(raw_status)

    return {
        "provider_event_id": provider_event_id,
        "provider_reference_id": provider_reference_id,
        "correlation_id": correlation_id,
        "event_type": event_type,
        "raw_status": raw_status,
        "status": status,
    }


def _insert_transition(
    sb,
    *,
    payout_request_id: str,
    previous_status: str | None,
    new_status: str,
    reason: str,
    actor_type: str,
    actor_profile_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    row = {
        # Modern schema columns.
        "payout_request_id": payout_request_id,
        "previous_status": previous_status,
        "new_status": new_status,
        "transition_reason": reason,
        "actor_type": actor_type,
        "actor_profile_id": actor_profile_id,
        "transition_metadata": metadata or {},
        "created_at": _utc_now_iso(),
        # Legacy schema aliases.
        "from_status": previous_status,
        "to_status": new_status,
        "reason": reason,
        "metadata": metadata or {},
    }

    payload = dict(row)
    last_exc: Exception | None = None
    for _ in range(10):
        try:
            sb.table("payout_status_transitions").insert(payload).execute()
            return
        except Exception as exc:
            last_exc = exc
            missing_col = _extract_missing_column_name(exc)
            if missing_col and missing_col in payload:
                payload.pop(missing_col, None)
                continue
            raise

    if last_exc:
        raise last_exc


def _apply_transition(
    sb,
    *,
    payout_row: dict[str, Any],
    new_status: str,
    reason: str,
    actor_type: str,
    actor_profile_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_status = normalize_payout_status(str(payout_row.get("status") or "") or "initiated")
    target = normalize_payout_status(new_status)

    allowed = ALLOWED_PAYOUT_TRANSITIONS.get(current_status, set())
    if target != current_status and target not in allowed:
        raise ValueError(
            f"Invalid payout transition from '{current_status}' to '{target}'"
        )

    update_payload: dict[str, Any] = {
        "status": target,
        "updated_at": _utc_now_iso(),
    }
    if target == "settled":
        update_payload["settled_at"] = _utc_now_iso()
        update_payload["next_retry_at"] = None
    if target in {"failed", "manual_review"}:
        retries = int(payout_row.get("retry_count") or 0)
        update_payload["retry_count"] = retries + 1
        update_payload["next_retry_at"] = _retry_next_at(retries + 1)

    applied_payload = _update_payout_request_row(
        sb,
        str(payout_row["id"]),
        update_payload,
    )
    payout_row.update(applied_payload)

    _insert_transition(
        sb,
        payout_request_id=str(payout_row["id"]),
        previous_status=current_status,
        new_status=target,
        reason=reason,
        actor_type=actor_type,
        actor_profile_id=actor_profile_id,
        metadata=metadata,
    )

    return payout_row


def _find_payout_by_references(
    sb,
    *,
    provider_reference_id: str,
    correlation_id: str,
    claim_id: str,
) -> dict[str, Any] | None:
    if provider_reference_id:
        try:
            row = (
                sb.table("payout_requests")
                .select("*")
                .eq("provider_reference_id", provider_reference_id)
                .maybe_single()
                .execute()
                .data
            )
        except Exception as exc:
            if _extract_missing_column_name(exc) != "provider_reference_id":
                raise
            row = None
        if row:
            return row

    if correlation_id:
        try:
            row = (
                sb.table("payout_requests")
                .select("*")
                .eq("correlation_id", correlation_id)
                .maybe_single()
                .execute()
                .data
            )
        except Exception as exc:
            if _extract_missing_column_name(exc) != "correlation_id":
                raise
            row = None
        if row:
            return row

    if claim_id:
        row = (
            sb.table("payout_requests")
            .select("*")
            .eq("claim_id", claim_id)
            .maybe_single()
            .execute()
            .data
        )
        if row:
            return row

    return None


def _upsert_audit_event(
    sb,
    *,
    claim_id: str,
    actor_profile_id: str | None,
    action_type: str,
    payload: dict[str, Any],
) -> None:
    sb.table("audit_events").insert(
        {
            "entity_type": "payout",
            "entity_id": claim_id,
            "action_type": action_type,
            "actor_profile_id": actor_profile_id,
            "event_payload": payload,
        }
    ).execute()


async def initiate_payout_for_claim(
    sb,
    *,
    claim_id: str,
    initiated_by_profile_id: str | None,
    trigger_source: str,
    request_id: str | None = None,
    force_retry: bool = False,
    requested_provider: str | None = None,
    initiation_note: str | None = None,
) -> dict[str, Any]:
    increment_counter(
        "payout_initiation_attempt_total",
        labels={"retry": str(force_retry).lower()},
    )
    structured_log(
        logger,
        logging.INFO,
        "payout.initiation.started",
        request_id=request_id,
        claim_id=claim_id,
        initiated_by_profile_id=initiated_by_profile_id,
        force_retry=force_retry,
    )

    claim = (
        sb.table("manual_claims")
        .select("id, worker_profile_id, claim_status")
        .eq("id", claim_id)
        .maybe_single()
        .execute()
        .data
    )
    if not claim:
        increment_counter("payout_initiation_rejected_total", labels={"reason": "claim_not_found"})
        raise ValueError("Claim not found")

    if claim.get("claim_status") not in {"approved", "auto_approved", "paid"}:
        increment_counter("payout_initiation_rejected_total", labels={"reason": "claim_not_approved"})
        raise ValueError("Claim must be approved before payout initiation")

    payout_rec = (
        sb.table("payout_recommendations")
        .select("id, recommended_payout")
        .eq("claim_id", claim_id)
        .maybe_single()
        .execute()
        .data
    )
    amount = _safe_float((payout_rec or {}).get("recommended_payout"), default=0.0)
    if amount <= 0:
        increment_counter("payout_initiation_rejected_total", labels={"reason": "no_payable_amount"})
        raise ValueError("No payable amount found for claim")

    trust_stamp = build_trust_stamp_for_claim(sb, claim_id)

    existing = (
        sb.table("payout_requests")
        .select("*")
        .eq("claim_id", claim_id)
        .maybe_single()
        .execute()
        .data
    )

    if existing and not force_retry:
        increment_counter("payout_initiation_outcome_total", labels={"status": "already_exists"})
        return {
            "status": "already_exists",
            "idempotent": True,
            "payout": existing,
            "trust_stamp": trust_stamp,
        }

    if existing and force_retry and str(existing.get("status")) not in PAYOUT_RETRYABLE_STATUSES:
        increment_counter(
            "payout_initiation_rejected_total",
            labels={"reason": "retry_not_allowed"},
        )
        raise ValueError(
            "Payout retry is only allowed for failed/manual_review/cancelled/reversed statuses"
        )

    worker = (
        sb.table("worker_profiles")
        .select("profile_id, bank_verified, phone_number")
        .eq("profile_id", claim["worker_profile_id"])
        .maybe_single()
        .execute()
        .data
    ) or {}

    correlation_id = f"claim-{claim_id}-{uuid4().hex[:10]}"
    retry_count = int((existing or {}).get("retry_count") or 0)
    idempotency_key = (
        f"claim:{claim_id}:retry:{retry_count + 1}" if existing else f"claim:{claim_id}:initial"
    )

    now_iso = _utc_now_iso()

    if not bool(worker.get("bank_verified", False)):
        payload = {
            "provider_key": "manual_gate",
            "provider_reference_id": None,
            "correlation_id": correlation_id,
            "idempotency_key": idempotency_key,
            "status": "manual_review",
            "failure_code": "bank_not_verified",
            "failure_reason": "Worker bank account is not verified for payout.",
            "updated_at": now_iso,
            "next_retry_at": _retry_next_at(retry_count + 1),
            "retry_count": retry_count + 1,
            "metadata": {
                "initiation_note": initiation_note,
                "trigger_source": trigger_source,
                "reason": "bank_not_verified",
                "request_id": request_id,
            },
        }

        if existing:
            sb.table("payout_requests").update(payload).eq("id", existing["id"]).execute()
            payout_row = {**existing, **payload}
            _insert_transition(
                sb,
                payout_request_id=str(existing["id"]),
                previous_status=str(existing.get("status") or ""),
                new_status="manual_review",
                reason="bank_not_verified",
                actor_type="system",
                actor_profile_id=initiated_by_profile_id,
                metadata=payload["metadata"],
            )
        else:
            insert_payload = {
                "claim_id": claim_id,
                "worker_profile_id": claim["worker_profile_id"],
                "payout_recommendation_id": (payout_rec or {}).get("id"),
                "amount": amount,
                "currency": "INR",
                "initiated_at": now_iso,
                "initiated_by_profile_id": initiated_by_profile_id,
                "initiation_source": trigger_source,
                **payload,
            }
            created = sb.table("payout_requests").insert(insert_payload).execute().data or []
            payout_row = created[0] if created else {**insert_payload, "id": None}
            if payout_row.get("id"):
                _insert_transition(
                    sb,
                    payout_request_id=str(payout_row["id"]),
                    previous_status=None,
                    new_status="manual_review",
                    reason="bank_not_verified",
                    actor_type="system",
                    actor_profile_id=initiated_by_profile_id,
                    metadata=payload["metadata"],
                )

        _upsert_audit_event(
            sb,
            claim_id=claim_id,
            actor_profile_id=initiated_by_profile_id,
            action_type="payout_manual_review_required",
            payload={
                "claim_id": claim_id,
                "reason": "bank_not_verified",
                "retry_count": payload["retry_count"],
                "request_id": request_id,
                "trust_stamp": trust_stamp,
            },
        )
        increment_counter("payout_initiation_outcome_total", labels={"status": "manual_review"})
        increment_counter("payout_failure_total", labels={"reason": "bank_not_verified"})
        structured_log(
            logger,
            logging.WARNING,
            "payout.initiation.manual_review",
            request_id=request_id,
            claim_id=claim_id,
            reason="bank_not_verified",
        )
        return {
            "status": "manual_review",
            "idempotent": False,
            "payout": payout_row,
            "trust_stamp": trust_stamp,
        }

    provider = get_payout_provider(preferred_key=requested_provider)
    command = PayoutInitiationCommand(
        claim_id=claim_id,
        worker_profile_id=str(claim["worker_profile_id"]),
        amount=amount,
        currency="INR",
        beneficiary_ref=str(worker.get("phone_number") or f"worker:{claim['worker_profile_id']}"),
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )
    provider_result = await provider.initiate_payout(command)

    base_payload = {
        "claim_id": claim_id,
        "worker_profile_id": claim["worker_profile_id"],
        "payout_recommendation_id": (payout_rec or {}).get("id"),
        "amount": amount,
        "currency": "INR",
        "provider_key": provider_result.provider_key,
        "provider_reference_id": provider_result.provider_reference_id,
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key,
        "failure_code": provider_result.failure_code,
        "failure_reason": provider_result.failure_reason,
        "metadata": {
            "initiation_note": initiation_note,
            "trigger_source": trigger_source,
            "request_id": request_id,
            "provider_metadata": provider_result.metadata,
            "raw_status": provider_result.raw_status,
        },
        "updated_at": now_iso,
    }

    if existing:
        sb.table("payout_requests").update(
            {
                **base_payload,
                "status": "initiated",
                "retry_count": retry_count + 1,
                "next_retry_at": None,
            }
        ).eq("id", existing["id"]).execute()
        payout_row = {
            **existing,
            **base_payload,
            "status": "initiated",
            "retry_count": retry_count + 1,
            "next_retry_at": None,
        }
        _insert_transition(
            sb,
            payout_request_id=str(existing["id"]),
            previous_status=str(existing.get("status") or ""),
            new_status="initiated",
            reason="retry_initiated" if force_retry else "initiated",
            actor_type="system",
            actor_profile_id=initiated_by_profile_id,
            metadata={"trigger_source": trigger_source, "force_retry": force_retry},
        )
    else:
        insert_payload = {
            **base_payload,
            "status": "initiated",
            "retry_count": 0,
            "next_retry_at": None,
            "initiated_at": now_iso,
            "initiated_by_profile_id": initiated_by_profile_id,
            "initiation_source": trigger_source,
        }
        created = sb.table("payout_requests").insert(insert_payload).execute().data or []
        payout_row = created[0] if created else {**insert_payload, "id": None}
        if payout_row.get("id"):
            _insert_transition(
                sb,
                payout_request_id=str(payout_row["id"]),
                previous_status=None,
                new_status="initiated",
                reason="initiated",
                actor_type="system",
                actor_profile_id=initiated_by_profile_id,
                metadata={"trigger_source": trigger_source, "force_retry": force_retry},
            )

    final_status = normalize_payout_status(provider_result.status)
    if final_status not in PAYOUT_STATUS_VALUES:
        final_status = "manual_review"

    if final_status != "initiated" and payout_row.get("id"):
        payout_row = _apply_transition(
            sb,
            payout_row=payout_row,
            new_status=final_status,
            reason="provider_initiation_response",
            actor_type="provider",
            actor_profile_id=None,
            metadata={
                "provider_key": provider_result.provider_key,
                "provider_reference_id": provider_result.provider_reference_id,
            },
        )

    if final_status == "settled":
        sb.table("manual_claims").update({"claim_status": "paid"}).eq("id", claim_id).execute()

    _upsert_audit_event(
        sb,
        claim_id=claim_id,
        actor_profile_id=initiated_by_profile_id,
        action_type="payout_initiated" if not force_retry else "payout_retried",
        payload={
            "claim_id": claim_id,
            "provider_key": provider_result.provider_key,
            "provider_reference_id": provider_result.provider_reference_id,
            "status": final_status,
            "retry": force_retry,
            "failure_code": provider_result.failure_code,
            "request_id": request_id,
            "trust_stamp": trust_stamp,
        },
    )

    try:
        await enqueue_domain_event(
            sb=sb,
            event_type="payout.initiated" if not force_retry else "payout.retry_initiated",
            key=claim_id,
            source=trigger_source,
            payload={
                "claim_id": claim_id,
                "payout_request_id": payout_row.get("id"),
                "status": payout_row.get("status"),
                "provider_key": payout_row.get("provider_key"),
                "provider_reference_id": payout_row.get("provider_reference_id"),
                "retry_count": payout_row.get("retry_count", 0),
                "request_id": request_id,
                "trust_stamp": trust_stamp,
            },
        )
    except Exception:
        # outbox write failures are non-blocking for initiation response
        pass

    increment_counter(
        "payout_initiation_outcome_total",
        labels={"status": str(payout_row.get("status") or final_status)},
    )
    if str(payout_row.get("status") or final_status) in {"failed", "manual_review", "cancelled", "reversed"}:
        increment_counter(
            "payout_failure_total",
            labels={"reason": str(payout_row.get("status") or final_status)},
        )

    structured_log(
        logger,
        logging.INFO,
        "payout.initiation.completed",
        request_id=request_id,
        claim_id=claim_id,
        payout_status=payout_row.get("status") or final_status,
        provider_key=payout_row.get("provider_key"),
        provider_reference_id=payout_row.get("provider_reference_id"),
    )

    return {
        "status": str(payout_row.get("status") or final_status),
        "idempotent": False,
        "payout": payout_row,
        "trust_stamp": trust_stamp,
    }


async def ingest_settlement_webhook(
    sb,
    *,
    provider_key: str,
    payload_bytes: bytes,
    signature_header: str | None,
    source_ip: str | None,
    request_id: str | None = None,
) -> dict[str, Any]:
    increment_counter("payout_webhook_total", labels={"outcome": "received"})
    provider = get_payout_provider(preferred_key=provider_key)
    signature_valid = provider.verify_webhook_signature(payload_bytes, signature_header)

    payload_hash = _hash_payload(payload_bytes)
    try:
        payload = json.loads(payload_bytes.decode("utf-8") if payload_bytes else "{}")
        if not isinstance(payload, dict):
            raise ValueError("Webhook payload must be a JSON object")
    except Exception as exc:
        payload = {}
        provider_event_id = f"decode_error_{payload_hash[:24]}"
        row = {
            "provider": provider.provider_key,
            "provider_key": provider.provider_key,
            "provider_event_id": provider_event_id,
            "provider_reference_id": None,
            "event_type": "decode_error",
            "signature_valid": signature_valid,
            "processing_status": "failed",
            "error_message": f"invalid_json: {exc}",
            "payload": {"raw": payload_bytes.decode("utf-8", errors="replace")},
            "payload_hash": payload_hash,
            "source_ip": source_ip,
            "received_at": _utc_now_iso(),
            "processed_at": _utc_now_iso(),
        }
        try:
            _insert_settlement_event_row(sb, row)
        except Exception:
            pass
        increment_counter("payout_webhook_total", labels={"outcome": "invalid_payload"})
        return {
            "status": "invalid_payload",
            "signature_valid": signature_valid,
            "processed": False,
            "reason": str(exc),
        }

    fields = _extract_webhook_fields(payload)
    provider_event_id = fields["provider_event_id"] or f"event_{payload_hash[:24]}"
    status = fields["status"]

    payout_row = _find_payout_by_references(
        sb,
        provider_reference_id=fields["provider_reference_id"],
        correlation_id=fields["correlation_id"],
        claim_id=str(payload.get("claim_id") or ""),
    )

    event_insert = {
        "payout_request_id": payout_row.get("id") if payout_row else None,
        "provider": provider.provider_key,
        "provider_key": provider.provider_key,
        "provider_event_id": provider_event_id,
        "provider_reference_id": fields["provider_reference_id"] or None,
        "event_type": fields["event_type"],
        "signature_valid": signature_valid,
        "processing_status": "received",
        "payload": payload,
        "payload_hash": payload_hash,
        "source_ip": source_ip,
        "received_at": _utc_now_iso(),
    }

    try:
        settlement_row = _insert_settlement_event_row(sb, event_insert)
        settlement_event = settlement_row[0] if settlement_row else None
    except Exception as exc:
        if "duplicate" in str(exc).lower() and "provider_event_id" in str(exc).lower():
            increment_counter("payout_webhook_total", labels={"outcome": "duplicate"})
            return {
                "status": "duplicate",
                "signature_valid": signature_valid,
                "processed": False,
                "provider_event_id": provider_event_id,
            }
        if _is_not_null_constraint_on_column(exc, "payout_request_id"):
            settlement_event = None
        else:
            raise

    if not signature_valid:
        increment_counter("payout_webhook_signature_failures_total")
        increment_counter("payout_webhook_total", labels={"outcome": "rejected_signature"})
        increment_counter("payout_failure_total", labels={"reason": "webhook_signature_failed"})
        structured_log(
            logger,
            logging.WARNING,
            "payout.webhook.signature_failed",
            request_id=request_id,
            provider_key=provider.provider_key,
            provider_event_id=provider_event_id,
        )
        if settlement_event and settlement_event.get("id"):
            _update_settlement_event_row(
                sb,
                str(settlement_event["id"]),
                {
                    "processing_status": "rejected",
                    "error_message": "invalid_signature",
                    "processed_at": _utc_now_iso(),
                },
            )
        return {
            "status": "rejected",
            "signature_valid": False,
            "processed": False,
            "reason": "invalid_signature",
        }

    if not payout_row:
        increment_counter("payout_webhook_total", labels={"outcome": "payout_not_found"})
        if settlement_event and settlement_event.get("id"):
            _update_settlement_event_row(
                sb,
                str(settlement_event["id"]),
                {
                    "processing_status": "failed",
                    "error_message": "payout_request_not_found",
                    "processed_at": _utc_now_iso(),
                },
            )
        return {
            "status": "failed",
            "signature_valid": True,
            "processed": False,
            "reason": "payout_request_not_found",
        }

    trust_stamp = build_trust_stamp_for_claim(sb, str(payout_row.get("claim_id") or ""))

    target_status = normalize_payout_status(status)
    if target_status == "initiated":
        target_status = "pending"

    try:
        payout_row = _apply_transition(
            sb,
            payout_row=payout_row,
            new_status=target_status,
            reason=f"webhook:{fields['event_type']}",
            actor_type="provider_webhook",
            actor_profile_id=None,
            metadata={
                "provider_event_id": provider_event_id,
                "provider_key": provider.provider_key,
                "raw_status": fields["raw_status"],
            },
        )
    except Exception as exc:
        increment_counter("payout_webhook_total", labels={"outcome": "transition_failed"})
        increment_counter("payout_failure_total", labels={"reason": "webhook_transition_failed"})
        if settlement_event and settlement_event.get("id"):
            _update_settlement_event_row(
                sb,
                str(settlement_event["id"]),
                {
                    "processing_status": "failed",
                    "error_message": f"transition_error: {exc}",
                    "processed_at": _utc_now_iso(),
                },
            )

        if str(payout_row.get("status") or "") != "manual_review":
            try:
                payout_row = _apply_transition(
                    sb,
                    payout_row=payout_row,
                    new_status="manual_review",
                    reason="invalid_transition_manual_review_fallback",
                    actor_type="system",
                    actor_profile_id=None,
                    metadata={"original_error": str(exc), "provider_event_id": provider_event_id},
                )
            except Exception:
                pass

        return {
            "status": "failed",
            "signature_valid": True,
            "processed": False,
            "reason": str(exc),
            "trust_stamp": trust_stamp,
        }

    if target_status == "settled":
        sb.table("manual_claims").update({"claim_status": "paid"}).eq(
            "id", payout_row["claim_id"]
        ).execute()

    if settlement_event and settlement_event.get("id"):
        _update_settlement_event_row(
            sb,
            str(settlement_event["id"]),
            {
                "payout_request_id": payout_row["id"],
                "processing_status": "processed",
                "processed_at": _utc_now_iso(),
                "error_message": None,
            },
        )

    _upsert_audit_event(
        sb,
        claim_id=str(payout_row["claim_id"]),
        actor_profile_id=None,
        action_type="payout_settlement_event_processed",
        payload={
            "provider_key": provider.provider_key,
            "provider_event_id": provider_event_id,
            "payout_request_id": payout_row["id"],
            "new_status": payout_row.get("status"),
            "request_id": request_id,
            "trust_stamp": trust_stamp,
        },
    )

    try:
        await enqueue_domain_event(
            sb=sb,
            event_type="payout.settlement.updated",
            key=str(payout_row["claim_id"]),
            source="payouts.webhook",
            payload={
                "claim_id": payout_row["claim_id"],
                "payout_request_id": payout_row["id"],
                "provider_key": provider.provider_key,
                "provider_event_id": provider_event_id,
                "status": payout_row.get("status"),
                "request_id": request_id,
                "trust_stamp": trust_stamp,
            },
        )
    except Exception:
        pass

    increment_counter("payout_webhook_total", labels={"outcome": "processed"})
    increment_counter(
        "payout_settlement_status_total",
        labels={"status": str(payout_row.get("status") or "unknown")},
    )
    if str(payout_row.get("status") or "") in {"failed", "manual_review", "reversed", "cancelled"}:
        increment_counter(
            "payout_failure_total",
            labels={"reason": str(payout_row.get("status") or "unknown")},
        )

    structured_log(
        logger,
        logging.INFO,
        "payout.webhook.processed",
        request_id=request_id,
        provider_key=provider.provider_key,
        provider_event_id=provider_event_id,
        payout_request_id=payout_row.get("id"),
        payout_status=payout_row.get("status"),
    )

    return {
        "status": "processed",
        "signature_valid": True,
        "processed": True,
        "payout_status": payout_row.get("status"),
        "payout_request_id": payout_row.get("id"),
        "provider_event_id": provider_event_id,
        "trust_stamp": trust_stamp,
    }


def get_payout_trace_for_claim(sb, claim_id: str) -> dict[str, Any]:
    payout: dict[str, Any] | None = None
    try:
        payout_resp = (
            sb.table("payout_requests")
            .select("*")
            .eq("claim_id", claim_id)
            .maybe_single()
            .execute()
        )
        payout = (
            payout_resp.data
            if payout_resp and isinstance(getattr(payout_resp, "data", None), dict)
            else None
        )
    except Exception:
        payout = None

    if not payout:
        return {
            "claim_id": claim_id,
            "payout": None,
            "settlement_events": [],
            "transitions": [],
            "trust_stamp": build_trust_stamp_for_claim(sb, claim_id),
        }

    settlement_events: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []

    try:
        settlement_resp = (
            sb.table("payout_settlement_events")
            .select("*")
            .eq("payout_request_id", payout["id"])
            .execute()
        )
        settlement_events = (
            settlement_resp.data
            if settlement_resp and isinstance(getattr(settlement_resp, "data", None), list)
            else []
        )
    except Exception:
        settlement_events = []

    try:
        transition_resp = (
            sb.table("payout_status_transitions")
            .select("*")
            .eq("payout_request_id", payout["id"])
            .execute()
        )
        transitions = (
            transition_resp.data
            if transition_resp and isinstance(getattr(transition_resp, "data", None), list)
            else []
        )
    except Exception:
        transitions = []

    return {
        "claim_id": claim_id,
        "payout": payout,
        "settlement_events": settlement_events,
        "transitions": transitions,
        "trust_stamp": build_trust_stamp_for_claim(sb, claim_id),
    }
