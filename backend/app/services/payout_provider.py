"""Payout provider adapter abstractions and implementations.

This module isolates provider-specific payout initiation and webhook signature logic
behind a consistent interface so the workflow layer is provider-agnostic.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from backend.app.config import settings

logger = logging.getLogger("covara.payout_provider")


PAYOUT_STATUS_VALUES = {
    "initiated",
    "pending",
    "processing",
    "settled",
    "failed",
    "reversed",
    "cancelled",
    "manual_review",
}


def normalize_payout_status(raw_status: str | None) -> str:
    value = (raw_status or "").strip().lower()
    if value in PAYOUT_STATUS_VALUES:
        return value

    aliases = {
        "queued": "pending",
        "created": "initiated",
        "accepted": "initiated",
        "in_progress": "processing",
        "processing_payment": "processing",
        "paid": "settled",
        "success": "settled",
        "completed": "settled",
        "error": "failed",
        "declined": "failed",
        "canceled": "cancelled",
        "chargeback": "reversed",
        "needs_review": "manual_review",
    }
    return aliases.get(value, "manual_review")


@dataclass(frozen=True)
class PayoutInitiationCommand:
    claim_id: str
    worker_profile_id: str
    amount: float
    currency: str
    beneficiary_ref: str
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True)
class PayoutProviderResponse:
    provider_key: str
    provider_reference_id: str
    status: str
    accepted: bool
    raw_status: str | None = None
    failure_code: str | None = None
    failure_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PayoutProviderAdapter(Protocol):
    provider_key: str

    async def initiate_payout(
        self,
        command: PayoutInitiationCommand,
    ) -> PayoutProviderResponse:
        ...

    def verify_webhook_signature(self, payload: bytes, signature_header: str | None) -> bool:
        ...


def _normalized_signature(signature_header: str | None) -> str:
    if not signature_header:
        return ""
    value = signature_header.strip()
    if "=" in value:
        # Supports formats like sha256=<hex>
        _, value = value.split("=", 1)
    return value.strip().lower()


def _verify_hmac_signature(secret: str, payload: bytes, signature_header: str | None) -> bool:
    signature = _normalized_signature(signature_header)
    if not secret or not signature:
        return False

    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _mock_upi_payout(profile_id: str, amount: float, upi_id: str) -> dict[str, Any]:
    """Deterministic fallback mock for legacy payout simulation paths."""
    logger.info(
        "Initiating fallback mock payout of Rs %.2f to %s for %s",
        amount,
        upi_id,
        profile_id,
    )

    await asyncio.sleep(0.5)

    status = "failed" if "fail" in upi_id.lower() else "processed"
    return {
        "status": status,
        "transaction_id": f"pay_{uuid.uuid4().hex[:14]}",
        "amount": amount,
        "currency": "INR",
        "beneficiary": upi_id,
        "processed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "gateway": "mock_razorpay",
    }


class HttpPayoutProviderAdapter:
    """HTTP adapter intended for a real payout provider endpoint.

    The adapter sends an initiation command to an external provider API and maps
    the provider response onto the internal payout status vocabulary.
    """

    provider_key = "http_gateway"

    def __init__(self, *, base_url: str, api_key: str, webhook_secret: str, timeout_seconds: int):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.timeout_seconds = timeout_seconds

    async def initiate_payout(self, command: PayoutInitiationCommand) -> PayoutProviderResponse:
        url = f"{self.base_url}/payouts"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": command.idempotency_key,
            "X-Correlation-Id": command.correlation_id,
        }
        body = {
            "claim_id": command.claim_id,
            "beneficiary_ref": command.beneficiary_ref,
            "amount": command.amount,
            "currency": command.currency,
            "idempotency_key": command.idempotency_key,
            "correlation_id": command.correlation_id,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=body)

            data: dict[str, Any] = {}
            try:
                data = response.json() if response.content else {}
            except Exception:
                data = {}

            provider_reference_id = str(
                data.get("provider_reference_id")
                or data.get("reference_id")
                or data.get("id")
                or f"http_{uuid.uuid4().hex[:16]}"
            )
            raw_status = str(data.get("status") or "")
            status = normalize_payout_status(raw_status or "pending")

            if response.status_code >= 400:
                return PayoutProviderResponse(
                    provider_key=self.provider_key,
                    provider_reference_id=provider_reference_id,
                    status="failed",
                    accepted=False,
                    raw_status=raw_status,
                    failure_code=f"http_{response.status_code}",
                    failure_reason=data.get("message") if isinstance(data, dict) else response.text,
                    metadata={"provider_response": data},
                )

            return PayoutProviderResponse(
                provider_key=self.provider_key,
                provider_reference_id=provider_reference_id,
                status=status,
                accepted=True,
                raw_status=raw_status,
                metadata={"provider_response": data},
            )
        except Exception as exc:
            logger.exception("HTTP payout provider error")
            return PayoutProviderResponse(
                provider_key=self.provider_key,
                provider_reference_id=f"http_{uuid.uuid4().hex[:16]}",
                status="failed",
                accepted=False,
                failure_code="provider_request_error",
                failure_reason=str(exc),
                metadata={},
            )

    def verify_webhook_signature(self, payload: bytes, signature_header: str | None) -> bool:
        return _verify_hmac_signature(self.webhook_secret, payload, signature_header)


class SimulatedGatewayProviderAdapter:
    """Deterministic local adapter that mimics async provider behavior.

    This is the default path when real provider credentials are not configured.
    It is not a hardcoded success mock: it models pending/processing/failure
    outcomes and still enforces webhook signature verification.
    """

    provider_key = "simulated_gateway"

    def __init__(self, *, webhook_secret: str):
        self.webhook_secret = webhook_secret

    async def initiate_payout(self, command: PayoutInitiationCommand) -> PayoutProviderResponse:
        ref = f"sim_{uuid.uuid4().hex[:16]}"
        beneficiary = command.beneficiary_ref.lower()

        if "manual" in beneficiary:
            status = "manual_review"
            accepted = False
            failure_code = "manual_review_required"
            failure_reason = "Beneficiary requires manual provider review."
        elif "fail" in beneficiary:
            status = "failed"
            accepted = False
            failure_code = "beneficiary_rejected"
            failure_reason = "Beneficiary validation failed at provider."
        elif command.amount >= 5000:
            status = "processing"
            accepted = True
            failure_code = None
            failure_reason = None
        else:
            status = "pending"
            accepted = True
            failure_code = None
            failure_reason = None

        return PayoutProviderResponse(
            provider_key=self.provider_key,
            provider_reference_id=ref,
            status=status,
            accepted=accepted,
            raw_status=status,
            failure_code=failure_code,
            failure_reason=failure_reason,
            metadata={
                "simulated": True,
                "beneficiary_ref": command.beneficiary_ref,
                "correlation_id": command.correlation_id,
            },
        )

    def verify_webhook_signature(self, payload: bytes, signature_header: str | None) -> bool:
        return _verify_hmac_signature(self.webhook_secret, payload, signature_header)


class MockFallbackPayoutProviderAdapter:
    """Legacy mock provider retained as explicit fallback only."""

    provider_key = "mock_fallback"

    def __init__(self, *, webhook_secret: str):
        self.webhook_secret = webhook_secret

    async def initiate_payout(self, command: PayoutInitiationCommand) -> PayoutProviderResponse:
        # Keep compatibility with previous mock helper while using the new contract.
        result = await _mock_upi_payout(
            profile_id=command.worker_profile_id,
            amount=command.amount,
            upi_id=command.beneficiary_ref,
        )
        raw_status = str(result.get("status") or "")
        status = normalize_payout_status(raw_status)
        if status == "processing":
            status = "settled"

        return PayoutProviderResponse(
            provider_key=self.provider_key,
            provider_reference_id=str(result.get("transaction_id") or f"mock_{uuid.uuid4().hex[:16]}"),
            status=status,
            accepted=status != "failed",
            raw_status=raw_status,
            failure_code="mock_failed" if status == "failed" else None,
            failure_reason="Mock provider returned failed status." if status == "failed" else None,
            metadata={"mock_result": result},
        )

    def verify_webhook_signature(self, payload: bytes, signature_header: str | None) -> bool:
        return _verify_hmac_signature(self.webhook_secret, payload, signature_header)


def get_payout_provider(preferred_key: str | None = None) -> PayoutProviderAdapter:
    configured = (preferred_key or settings.payout_provider_key or "simulated_gateway").strip().lower()
    webhook_secret = settings.payout_provider_webhook_secret

    if configured in {"http_gateway", "razorpayx", "cashfree", "provider_http"}:
        if settings.payout_provider_api_base_url and settings.payout_provider_api_key:
            return HttpPayoutProviderAdapter(
                base_url=settings.payout_provider_api_base_url,
                api_key=settings.payout_provider_api_key,
                webhook_secret=webhook_secret,
                timeout_seconds=max(1, settings.payout_provider_timeout_seconds),
            )
        message = (
            "Payout provider '%s' selected but PAYOUT_PROVIDER_API_BASE_URL/API_KEY are missing."
            % configured
        )
        if settings.is_strict_env_validation_enabled():
            raise RuntimeError(message)
        logger.warning(
            "%s Falling back to simulated provider.",
            message,
        )
        return SimulatedGatewayProviderAdapter(webhook_secret=webhook_secret)

    if configured in {"simulated", "simulated_gateway", "sandbox_gateway"}:
        return SimulatedGatewayProviderAdapter(webhook_secret=webhook_secret)

    if configured in {"mock", "mock_fallback", "legacy_mock"}:
        return MockFallbackPayoutProviderAdapter(webhook_secret=webhook_secret)

    logger.warning("Unknown payout provider key '%s'; defaulting to simulated provider.", configured)
    return SimulatedGatewayProviderAdapter(webhook_secret=webhook_secret)


def sign_webhook_payload_for_testing(payload: bytes, secret: str) -> str:
    """Helper for deterministic tests of signature verification."""
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
