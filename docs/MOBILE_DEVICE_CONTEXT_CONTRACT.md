# Mobile Device Context Contract (v2)

This document defines the signed mobile telemetry contract between native clients and backend claim ingestion.

## Goal

Provide tamper-resistant device telemetry for Layer 3 anti-spoofing while preserving backward compatibility for legacy web claim flows.

## Request headers

Send these headers with POST /claims whenever mobile device context is present:

- X-Device-Context: raw JSON string payload.
- X-Device-Context-Signature: lowercase hex HMAC-SHA256 signature.
- X-Device-Context-Timestamp: unix epoch seconds or ISO8601 UTC timestamp.
- X-Device-Context-Key-Id: optional key identifier for active secret.
- X-Request-ID: optional correlation ID (recommended).

Policy:
- If X-Device-Context exists, signature verification is mandatory.
- If X-Device-Context is absent, request follows legacy web behavior.

## Signature algorithm

Canonical message:

```text
{timestamp}.{raw_json_payload}
```

Signature:

```text
hex(HMAC_SHA256(secret_for_key_id, canonical_message))
```

Critical rules:
- Sign the exact raw JSON string that is sent in X-Device-Context.
- Do not reorder or reformat keys after signing.
- Timestamp freshness window is 5 minutes.

## Replay protection

Payload MUST include nonce (or request_id) for replay defense.

Required behavior:
- Server rejects repeated nonce values within replay window.
- Server rejects stale timestamps beyond max skew.

## Required payload fields (v2)

```json
{
  "schema_version": "2.0",
  "nonce": "8f0f0d36-6c2f-4b55-98ea-9655f4c12139",
  "os_platform": "android",
  "device_model": "Pixel 8",
  "hardware_id": "a8c9e5b7...",
  "is_rooted": false,
  "is_emulator": false,
  "debugger_attached": false,
  "developer_mode_active": false,
  "mock_location_detected": false,
  "mock_location_source": "none",
  "malicious_packages_found": [],
  "vpn_active": false,
  "has_accelerometer": true,
  "has_gyroscope": true,
  "integrity_verdict": "moderate",
  "signal_confidence": "medium",
  "collection_method": "heuristic",
  "collection_warnings": [],
  "unsupported_checks": [],
  "attestation_provider": "none",
  "attestation_verdict": "not_configured",
  "attestation_token_present": false
}
```

Recommended optional fields:
- app_version
- app_build_number
- location_permission_scope
- precise_location_enabled

Attestation fields are intentionally attestation-ready:
- provider can be none while integration is pending.
- verdict can be not_configured or not_available without hard-failing claims.
- backend consumes these as trust-weighting inputs, not standalone deny signals.

## Backend behavior

- No context header:
  - Request accepted (legacy mode).
  - Trust summary downgraded to low confidence (not hard-failed).
- Context header present + valid signature + valid freshness + non-replayed nonce:
  - Request accepted.
  - Verified context passed into anti-spoofing and persisted in claim explanation output.
  - Backend derives device_trust_score and device_trust_tier for claim/review surfaces.
- Context header present + any invalid security condition:
  - Request rejected with HTTP 400.

## Alias normalization

Backend normalizes these aliases:
- mock_location_detected -> mock_location_enabled
- developer_mode_active -> developer_mode
- is_jailbroken -> is_rooted
- debugger_detected -> debugger_attached

## Key management

Minimum required env:
- DEVICE_CONTEXT_HMAC_SECRET for default key.

Optional per-key rotation pattern:
- DEVICE_CONTEXT_HMAC_SECRET_<KEY_ID>

Operational guidance:
- Rotate by issuing new key-id to app version cohort.
- Maintain overlap period where old and new key IDs validate.
- Revoke compromised key-id by removing corresponding secret.

## Compatibility

Supported clients:
- Legacy web clients (no context).
- Mobile v1 clients (context without nonce accepted only if server policy allows; planned deprecation).
- Mobile v2 clients (required target behavior).

## Security notes

- HMAC signature prevents payload tampering in transit but does not replace TLS.
- Embedded app secrets can be extracted over time; rely on layered controls (attestation, behavior scoring, and key rotation).
