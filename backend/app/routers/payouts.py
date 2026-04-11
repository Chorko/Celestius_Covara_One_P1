"""Covara One - Payouts Router.

Operational payout lifecycle endpoints:
- initiate and retry payout requests for approved claims
- inspect payout traceability for operations
- ingest provider settlement webhooks with signature verification
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.app.dependencies import get_current_user, require_insurer_admin
from backend.app.services.observability import increment_counter, structured_log
from backend.app.supabase_client import get_supabase_admin
from backend.app.services.payout_workflow import (
    get_payout_trace_for_claim,
    ingest_settlement_webhook,
    initiate_payout_for_claim,
)

router = APIRouter(prefix="/payouts", tags=["Payouts"])
logger = logging.getLogger("covara.payouts.router")


def _request_id(request: Request) -> str | None:
    state_id = getattr(getattr(request, "state", None), "request_id", None)
    if state_id:
        return str(state_id)

    header_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
    return header_id if header_id else None


class PayoutInitiateRequest(BaseModel):
    provider_key: str | None = None
    initiation_note: str | None = None


class PayoutRetryRequest(BaseModel):
    provider_key: str | None = None
    retry_note: str | None = None


@router.post(
    "/claims/{claim_id}/initiate",
    dependencies=[Depends(require_insurer_admin)],
    summary="Initiate payout for an approved claim",
)
async def initiate_claim_payout(
    request: Request,
    claim_id: str,
    body: PayoutInitiateRequest,
    user: dict = Depends(get_current_user),
):
    sb = get_supabase_admin()
    request_id = _request_id(request)

    try:
        result = await initiate_payout_for_claim(
            sb,
            claim_id=claim_id,
            initiated_by_profile_id=user["id"],
            trigger_source="payouts.initiate_claim_payout",
            request_id=request_id,
            force_retry=False,
            requested_provider=body.provider_key,
            initiation_note=body.initiation_note,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        increment_counter(
            "payout_initiation_http_total",
            labels={"outcome": "rejected"},
        )
        structured_log(
            logger,
            logging.WARNING,
            "payout.initiate.rejected",
            request_id=request_id,
            claim_id=claim_id,
            error=detail,
        )
        raise HTTPException(status_code=status_code, detail=detail)

    increment_counter(
        "payout_initiation_http_total",
        labels={"outcome": str(result.get("status") or "unknown")},
    )
    structured_log(
        logger,
        logging.INFO,
        "payout.initiate.completed",
        request_id=request_id,
        claim_id=claim_id,
        status=result.get("status"),
    )

    return {
        "status": result.get("status"),
        "idempotent": bool(result.get("idempotent", False)),
        "payout": result.get("payout"),
    }


@router.post(
    "/claims/{claim_id}/retry",
    dependencies=[Depends(require_insurer_admin)],
    summary="Retry a failed/manual-review payout",
)
async def retry_claim_payout(
    request: Request,
    claim_id: str,
    body: PayoutRetryRequest,
    user: dict = Depends(get_current_user),
):
    sb = get_supabase_admin()
    request_id = _request_id(request)

    try:
        result = await initiate_payout_for_claim(
            sb,
            claim_id=claim_id,
            initiated_by_profile_id=user["id"],
            trigger_source="payouts.retry_claim_payout",
            request_id=request_id,
            force_retry=True,
            requested_provider=body.provider_key,
            initiation_note=body.retry_note,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        increment_counter(
            "payout_retry_http_total",
            labels={"outcome": "rejected"},
        )
        structured_log(
            logger,
            logging.WARNING,
            "payout.retry.rejected",
            request_id=request_id,
            claim_id=claim_id,
            error=detail,
        )
        raise HTTPException(status_code=status_code, detail=detail)

    increment_counter(
        "payout_retry_http_total",
        labels={"outcome": str(result.get("status") or "unknown")},
    )
    structured_log(
        logger,
        logging.INFO,
        "payout.retry.completed",
        request_id=request_id,
        claim_id=claim_id,
        status=result.get("status"),
    )

    return {
        "status": result.get("status"),
        "idempotent": bool(result.get("idempotent", False)),
        "payout": result.get("payout"),
    }


@router.get(
    "/claims/{claim_id}",
    dependencies=[Depends(require_insurer_admin)],
    summary="Get payout request and settlement trace for a claim",
)
async def get_claim_payout_trace(claim_id: str):
    sb = get_supabase_admin()
    trace = get_payout_trace_for_claim(sb, claim_id)
    return trace


@router.post(
    "/webhooks/{provider_key}",
    summary="Provider settlement webhook",
    description=(
        "Receives provider settlement callbacks. Signature is verified via "
        "X-Payout-Signature, then events are processed idempotently by provider event id."
    ),
)
async def payout_webhook(provider_key: str, request: Request):
    sb = get_supabase_admin()
    request_id = _request_id(request)
    payload_bytes = await request.body()
    signature = request.headers.get("X-Payout-Signature")

    result = await ingest_settlement_webhook(
        sb,
        provider_key=provider_key,
        payload_bytes=payload_bytes,
        signature_header=signature,
        source_ip=request.client.host if request.client else None,
        request_id=request_id,
    )

    if result.get("status") in {"invalid_payload", "failed", "rejected"}:
        increment_counter(
            "payout_webhook_http_total",
            labels={"outcome": "rejected"},
        )
        structured_log(
            logger,
            logging.WARNING,
            "payout.webhook.rejected",
            request_id=request_id,
            provider_key=provider_key,
            status=result.get("status"),
        )
        raise HTTPException(status_code=400, detail=result)

    increment_counter(
        "payout_webhook_http_total",
        labels={"outcome": str(result.get("status") or "unknown")},
    )

    return result
