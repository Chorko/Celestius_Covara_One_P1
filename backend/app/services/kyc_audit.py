from __future__ import annotations

import hashlib
import logging
from typing import Any

from backend.app.services.observability import structured_log

logger = logging.getLogger("covara.kyc.audit")


def _stable_hash(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def subject_ref(subject_kind: str, subject_raw: str | None) -> str | None:
    digest = _stable_hash(subject_raw)
    if not digest:
        return None
    return f"{subject_kind}:{digest}"


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 4:
        return "***"
    return f"***{digits[-4:]}"


def mask_aadhaar(aadhaar: str | None) -> str | None:
    if not aadhaar:
        return None
    digits = "".join(ch for ch in aadhaar if ch.isdigit())
    if len(digits) < 4:
        return "XXXX-XXXX-XXXX"
    return f"XXXX-XXXX-{digits[-4:]}"


def mask_pan(pan: str | None) -> str | None:
    if not pan:
        return None
    token = pan.strip().upper()
    if len(token) < 6:
        return "***"
    return f"{token[:3]}XXXX{token[-3:]}"


def mask_account_number(account_number: str | None) -> str | None:
    if not account_number:
        return None
    digits = "".join(ch for ch in account_number if ch.isdigit())
    if len(digits) < 4:
        return "***"
    return f"***{digits[-4:]}"


def mask_ifsc(ifsc: str | None) -> str | None:
    if not ifsc:
        return None
    token = ifsc.strip().upper()
    if len(token) <= 4:
        return token
    return f"{token[:4]}XXXXXXX"


def persist_kyc_audit_event(
    sb,
    *,
    verification_type: str,
    success: bool,
    verified: bool | None = None,
    provider: str = "sandbox",
    provider_reference_id: str | None = None,
    provider_status_code: int | None = None,
    subject_kind: str = "unknown",
    subject_raw: str | None = None,
    actor_profile_id: str | None = None,
    request_meta: dict[str, Any] | None = None,
    risk_flags: dict[str, Any] | None = None,
) -> None:
    event_payload = {
        "provider": provider,
        "verification_type": verification_type,
        "success": bool(success),
        "verified": verified,
        "provider_reference_id": provider_reference_id,
        "provider_status_code": provider_status_code,
        "subject_ref": subject_ref(subject_kind, subject_raw),
        "request_meta": request_meta or {},
        "risk_flags": risk_flags or {},
    }

    try:
        sb.table("kyc_verification_events").insert(
            {
                "provider": provider,
                "verification_type": verification_type,
                "actor_profile_id": actor_profile_id,
                "subject_ref": event_payload["subject_ref"],
                "reference_id": provider_reference_id,
                "provider_status_code": provider_status_code,
                "success": bool(success),
                "verified": verified,
                "request_meta": event_payload["request_meta"],
                "risk_flags": event_payload["risk_flags"],
            }
        ).execute()
    except Exception as exc:
        structured_log(
            logger,
            logging.WARNING,
            "kyc.audit.kyc_table_insert_failed",
            verification_type=verification_type,
            error=str(exc),
        )

    try:
        sb.table("audit_events").insert(
            {
                "entity_type": "kyc",
                "entity_id": provider_reference_id or event_payload["subject_ref"],
                "action_type": f"kyc_{verification_type}",
                "actor_profile_id": actor_profile_id,
                "event_payload": event_payload,
            }
        ).execute()
    except Exception as exc:
        structured_log(
            logger,
            logging.WARNING,
            "kyc.audit.audit_events_insert_failed",
            verification_type=verification_type,
            error=str(exc),
        )
