"""
Covara One - Device Context Signature Verification

Validates cryptographically signed mobile device-context payloads.
Payload signing format:
    signature = HMAC_SHA256(secret, "{timestamp}.{raw_json}")

Adds replay protection and key-id aware secret selection.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class DeviceContextVerification:
    verified: bool
    reason: str
    context: dict[str, Any]
    signature_present: bool
    timestamp: str | None = None
    key_id: str | None = None
    schema_version: str | None = None
    nonce: str | None = None


# In-memory nonce cache for replay protection.
# Format: "<key_id_or_default>:<nonce>" -> first_seen_utc
_NONCE_CACHE: dict[str, datetime] = {}


def _normalize_key_id(key_id: str | None) -> str | None:
    if not key_id:
        return None
    normalized = key_id.strip()
    return normalized if normalized else None


def _resolve_secret(default_secret: str | None, key_id: str | None) -> str | None:
    """
    Resolve signing secret.

    If key_id is provided, backend tries DEVICE_CONTEXT_HMAC_SECRET_<KEY_ID>
    (uppercased with '-' replaced by '_'). Falls back to default_secret.
    """
    normalized_key_id = _normalize_key_id(key_id)
    if normalized_key_id:
        env_suffix = normalized_key_id.upper().replace("-", "_")
        keyed_secret = os.getenv(f"DEVICE_CONTEXT_HMAC_SECRET_{env_suffix}", "")
        if keyed_secret:
            return keyed_secret

    return default_secret


def _prune_nonce_cache(now_utc: datetime, max_skew_seconds: int) -> None:
    stale_keys = []
    for cache_key, seen_at in _NONCE_CACHE.items():
        age = (now_utc - seen_at).total_seconds()
        if age > max_skew_seconds:
            stale_keys.append(cache_key)

    for cache_key in stale_keys:
        _NONCE_CACHE.pop(cache_key, None)


def _extract_nonce(context: dict[str, Any]) -> str | None:
    raw_nonce = context.get("nonce") or context.get("request_id")
    if raw_nonce is None:
        return None

    nonce = str(raw_nonce).strip()
    return nonce if nonce else None


def compute_hmac_signature(raw_context: str, timestamp: str, secret: str) -> str:
    """Compute the expected lowercase hex HMAC-SHA256 signature."""
    signed_blob = f"{timestamp}.{raw_context}".encode("utf-8")
    return hmac.new(
        secret.encode("utf-8"),
        signed_blob,
        hashlib.sha256,
    ).hexdigest()


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        # Support unix epoch seconds as string.
        if value.isdigit():
            return datetime.fromtimestamp(int(value), tz=timezone.utc)

        # Support ISO8601 timestamp.
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _normalize_context_aliases(context: dict[str, Any]) -> dict[str, Any]:
    """Map mobile payload aliases to backend anti-spoofing keys."""
    normalized = dict(context)

    alias_pairs = {
        "mock_location_detected": "mock_location_enabled",
        "developer_mode_active": "developer_mode",
        "is_jailbroken": "is_rooted",
        "debugger_detected": "debugger_attached",
    }

    for source_key, target_key in alias_pairs.items():
        if source_key in normalized and target_key not in normalized:
            normalized[target_key] = normalized[source_key]

    return normalized


def summarize_device_context_trust(
    *,
    context: dict[str, Any],
    context_present: bool,
    signature_verified: bool,
) -> dict[str, Any]:
    """Summarize device trust quality for claim/review surfaces.

    This is deliberately heuristic and attestation-ready: missing attestation does
    not hard-fail claims but lowers trust confidence.
    """
    signals: list[str] = []

    if not context_present:
        return {
            "context_present": False,
            "signature_verified": False,
            "device_trust_score": 0.45,
            "device_trust_tier": "low",
            "signal_confidence": "low",
            "attestation_verdict": "missing",
            "risk_signals": ["missing_device_context"],
        }

    score = 0.85 if signature_verified else 0.20

    if bool(context.get("is_rooted")):
        score -= 0.30
        signals.append("rooted_device")
    if bool(context.get("is_emulator")):
        score -= 0.20
        signals.append("emulator_runtime")
    if bool(context.get("debugger_attached")):
        score -= 0.18
        signals.append("debugger_attached")
    if bool(context.get("mock_location_enabled") or context.get("mock_location_detected")):
        score -= 0.20
        signals.append("mock_location_detected")

    malicious = context.get("malicious_packages_found")
    if isinstance(malicious, list) and malicious:
        score -= min(0.25, 0.07 * len(malicious))
        signals.append("malicious_packages_detected")

    attestation = str(context.get("attestation_verdict") or "").strip().lower()
    if attestation in {"failed", "invalid", "device_not_trusted"}:
        score -= 0.25
        signals.append("attestation_failed")
    elif attestation in {"not_configured", "not_available", "error", ""}:
        score -= 0.10
        signals.append("attestation_unavailable")

    confidence = str(context.get("signal_confidence") or "").strip().lower()
    if confidence in {"low", "unknown", ""}:
        score -= 0.10
        signals.append("low_signal_confidence")
    elif confidence == "medium":
        score -= 0.04

    score = max(0.0, min(1.0, round(score, 4)))

    if score >= 0.80:
        tier = "high"
    elif score >= 0.60:
        tier = "moderate"
    elif score >= 0.40:
        tier = "low"
    else:
        tier = "high_risk"

    return {
        "context_present": True,
        "signature_verified": bool(signature_verified),
        "device_trust_score": score,
        "device_trust_tier": tier,
        "signal_confidence": confidence or "unknown",
        "attestation_verdict": attestation or "missing",
        "risk_signals": signals,
    }


def verify_signed_device_context(
    raw_context: str | None,
    signature: str | None,
    timestamp: str | None,
    secret: str | None,
    key_id: str | None = None,
    max_skew_seconds: int = 300,
) -> DeviceContextVerification:
    """
    Verify signed device context payload.

    Returns verified=True when:
    - no context is provided (legacy web clients), or
    - context is present and signature is valid + timestamp fresh.
    """
    if not raw_context:
        if signature:
            return DeviceContextVerification(
                verified=False,
                reason="signature_without_context",
                context={},
                signature_present=True,
                timestamp=timestamp,
                key_id=key_id,
            )

        return DeviceContextVerification(
            verified=True,
            reason="absent",
            context={},
            signature_present=False,
            timestamp=timestamp,
            key_id=key_id,
        )

    try:
        parsed_context = json.loads(raw_context)
        if not isinstance(parsed_context, dict):
            return DeviceContextVerification(
                verified=False,
                reason="invalid_context_type",
                context={},
                signature_present=bool(signature),
                timestamp=timestamp,
                key_id=key_id,
            )
    except json.JSONDecodeError:
        return DeviceContextVerification(
            verified=False,
            reason="invalid_context_json",
            context={},
            signature_present=bool(signature),
            timestamp=timestamp,
            key_id=key_id,
        )

    normalized_context = _normalize_context_aliases(parsed_context)
    schema_version = str(normalized_context.get("schema_version", "1.0"))
    nonce = _extract_nonce(normalized_context)

    # v2 clients are required to send a nonce/request_id for replay defense.
    if schema_version.startswith("2") and not nonce:
        return DeviceContextVerification(
            verified=False,
            reason="missing_nonce",
            context=normalized_context,
            signature_present=bool(signature),
            timestamp=timestamp,
            key_id=key_id,
            schema_version=schema_version,
            nonce=nonce,
        )

    active_secret = _resolve_secret(secret, key_id)

    if not active_secret:
        return DeviceContextVerification(
            verified=False,
            reason="hmac_secret_not_configured",
            context=normalized_context,
            signature_present=bool(signature),
            timestamp=timestamp,
            key_id=key_id,
            schema_version=schema_version,
            nonce=nonce,
        )

    if not signature or not timestamp:
        return DeviceContextVerification(
            verified=False,
            reason="missing_signature_or_timestamp",
            context=normalized_context,
            signature_present=bool(signature),
            timestamp=timestamp,
            key_id=key_id,
            schema_version=schema_version,
            nonce=nonce,
        )

    parsed_ts = _parse_timestamp(timestamp)
    if parsed_ts is None:
        return DeviceContextVerification(
            verified=False,
            reason="invalid_timestamp",
            context=normalized_context,
            signature_present=True,
            timestamp=timestamp,
            key_id=key_id,
            schema_version=schema_version,
            nonce=nonce,
        )

    now_utc = datetime.now(timezone.utc)
    if abs((now_utc - parsed_ts).total_seconds()) > max_skew_seconds:
        return DeviceContextVerification(
            verified=False,
            reason="stale_timestamp",
            context=normalized_context,
            signature_present=True,
            timestamp=timestamp,
            key_id=key_id,
            schema_version=schema_version,
            nonce=nonce,
        )

    expected = compute_hmac_signature(raw_context, timestamp, active_secret)
    if not hmac.compare_digest(expected, signature.strip().lower()):
        return DeviceContextVerification(
            verified=False,
            reason="signature_mismatch",
            context=normalized_context,
            signature_present=True,
            timestamp=timestamp,
            key_id=key_id,
            schema_version=schema_version,
            nonce=nonce,
        )

    # Replay protection check after signature/timestamp validation.
    if nonce:
        _prune_nonce_cache(now_utc, max_skew_seconds)
        replay_key = f"{_normalize_key_id(key_id) or 'default'}:{nonce}"
        if replay_key in _NONCE_CACHE:
            return DeviceContextVerification(
                verified=False,
                reason="replayed_nonce",
                context=normalized_context,
                signature_present=True,
                timestamp=timestamp,
                key_id=key_id,
                schema_version=schema_version,
                nonce=nonce,
            )

        _NONCE_CACHE[replay_key] = now_utc

    return DeviceContextVerification(
        verified=True,
        reason="verified",
        context=normalized_context,
        signature_present=True,
        timestamp=timestamp,
        key_id=key_id,
        schema_version=schema_version,
        nonce=nonce,
    )

