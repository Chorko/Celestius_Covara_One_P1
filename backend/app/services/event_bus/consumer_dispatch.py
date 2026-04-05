"""
Covara One - Event Consumer Dispatch

Dispatches domain events to in-process consumers using idempotency guards.
This is primarily for in-memory event bus mode in local/dev environments.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from backend.app.services.event_bus.consumer_idempotency import consume_idempotently
from backend.app.services.event_bus.contracts import DomainEvent

logger = logging.getLogger("covara.event_consumers")


async def _get_worker_phone(sb, worker_id: str) -> str | None:
    try:
        resp = (
            sb.table("profiles")
            .select("phone")
            .eq("id", worker_id)
            .maybe_single()
            .execute()
        )
        return resp.data.get("phone") if resp.data else None
    except Exception:
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


async def _handle_auto_claim_notification(sb, event: DomainEvent) -> dict[str, Any]:
    payload = event.payload or {}
    worker_id = str(payload.get("worker_id") or "")
    claim_id = str(payload.get("claim_id") or "")

    if not worker_id or not claim_id:
        return {"sent": False, "reason": "missing_worker_or_claim"}

    phone = await _get_worker_phone(sb, worker_id)
    if not phone:
        return {"sent": False, "reason": "missing_phone"}

    claim_status = str(payload.get("claim_status") or "soft_hold_verification")
    template_key = {
        "auto_approved": "claim_auto_approved",
        "soft_hold_verification": "claim_needs_review",
        "fraud_escalated_review": "claim_needs_review",
        "rejected": "claim_rejected",
    }.get(claim_status, "claim_needs_review")

    trigger_code = str(payload.get("trigger_code") or "disruption")
    payout_amount = int(_safe_float(payload.get("payout_amount"), 0.0))

    from backend.app.services.twilio_service import send_whatsapp_template

    result = send_whatsapp_template(
        phone,
        template_key,
        trigger_type=trigger_code.replace("_", " ").title(),
        amount=str(payout_amount),
        claim_id=claim_id[:8].upper(),
        reason="Fraud risk detected" if claim_status == "rejected" else "",
    )

    if not result.get("success"):
        raise RuntimeError(
            f"Notification consumer failed for claim_id={claim_id}: {result.get('error')}"
        )

    return {
        "sent": True,
        "template": template_key,
        "mock": bool(result.get("mock", False)),
    }


async def _handle_auto_claim_rewards(sb, event: DomainEvent) -> dict[str, Any]:
    payload = event.payload or {}
    decision = str(payload.get("decision") or "")
    fraud_score = _safe_float(payload.get("fraud_score"), default=1.0)

    if decision != "auto_approve" or fraud_score >= 0.15:
        return {"awarded": False, "reason": "criteria_not_met"}

    worker_id = str(payload.get("worker_id") or "")
    claim_id = str(payload.get("claim_id") or "")
    if not worker_id or not claim_id:
        return {"awarded": False, "reason": "missing_worker_or_claim"}

    from backend.app.services.rewards_engine import award_clean_claim

    result = await award_clean_claim(
        sb=sb,
        profile_id=worker_id,
        claim_id=claim_id,
        fraud_score=fraud_score,
    )

    if not result.get("success"):
        raise RuntimeError(
            f"Rewards consumer failed for claim_id={claim_id}: {result.get('error')}"
        )

    return {
        "awarded": True,
        "coins_awarded": int(result.get("coins_awarded", 0)),
        "new_balance": result.get("new_balance"),
    }


_CONSUMER_HANDLERS: dict[
    str,
    list[tuple[str, Callable[[Any, DomainEvent], Awaitable[dict[str, Any] | None]]]],
] = {
    "claim.auto_processed": [
        ("auto_claim_notification_consumer", _handle_auto_claim_notification),
        ("auto_claim_rewards_consumer", _handle_auto_claim_rewards),
    ],
}


async def dispatch_event_to_consumers(sb, event: DomainEvent) -> dict[str, Any]:
    """Dispatch an event to all registered idempotent consumers."""
    handlers = _CONSUMER_HANDLERS.get(event.event_type, [])
    if not handlers:
        return {
            "event_type": event.event_type,
            "consumers": 0,
            "processed": 0,
            "skipped": 0,
            "results": [],
        }

    results: list[dict[str, Any]] = []
    processed = 0
    skipped = 0

    for consumer_name, handler in handlers:
        async def _wrapped(evt: DomainEvent, _handler=handler):
            return await _handler(sb, evt)

        outcome = await consume_idempotently(
            sb=sb,
            consumer_name=consumer_name,
            event=event,
            handler=_wrapped,
        )

        result_row = {"consumer": consumer_name, **outcome}
        results.append(result_row)

        if outcome.get("processed"):
            processed += 1
        else:
            skipped += 1

    logger.info(
        "Consumer dispatch complete: event_type=%s processed=%s skipped=%s",
        event.event_type,
        processed,
        skipped,
    )

    return {
        "event_type": event.event_type,
        "consumers": len(handlers),
        "processed": processed,
        "skipped": skipped,
        "results": results,
    }
