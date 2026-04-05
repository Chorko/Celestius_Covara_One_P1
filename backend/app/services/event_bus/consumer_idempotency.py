"""
Covara One - Consumer Idempotency Helpers

Provides a lightweight ledger-based API for idempotent event consumers.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from backend.app.config import settings
from backend.app.services.event_bus.contracts import DomainEvent

logger = logging.getLogger("covara.event_consumer")


@dataclass(frozen=True)
class ConsumeLease:
    should_process: bool
    ledger_id: str | None
    attempt_count: int
    reason: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_duplicate_ledger_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "duplicate key" in msg
        and "event_consumer_ledger_consumer_event_uniq" in msg
    )


def _payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def begin_consume(sb, consumer_name: str, event: DomainEvent) -> ConsumeLease:
    """
    Acquire idempotency lease for a consumer+event pair.

    Returns should_process=False when event has already been handled
    successfully or is currently being processed by another worker.
    """
    row = {
        "consumer_name": consumer_name,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "event_key": event.key,
        "status": "processing",
        "attempt_count": 1,
        "first_seen_at": _utc_now_iso(),
        "last_attempt_at": _utc_now_iso(),
        "result_payload": {
            "payload_hash": _payload_hash(event.payload),
        },
    }

    try:
        insert_resp = sb.table("event_consumer_ledger").insert(row).execute()
        inserted = (insert_resp.data or [{}])[0]
        return ConsumeLease(
            should_process=True,
            ledger_id=inserted.get("id"),
            attempt_count=1,
            reason="acquired",
        )
    except Exception as exc:
        if not _is_duplicate_ledger_error(exc):
            raise

    existing_resp = (
        sb.table("event_consumer_ledger")
        .select("id,status,attempt_count")
        .eq("consumer_name", consumer_name)
        .eq("event_id", event.event_id)
        .maybe_single()
        .execute()
    )
    existing = existing_resp.data or {}

    status = existing.get("status")
    attempt_count = int(existing.get("attempt_count") or 1)
    ledger_id = existing.get("id")

    if status == "succeeded":
        return ConsumeLease(
            should_process=False,
            ledger_id=ledger_id,
            attempt_count=attempt_count,
            reason="already_succeeded",
        )

    if status == "processing":
        return ConsumeLease(
            should_process=False,
            ledger_id=ledger_id,
            attempt_count=attempt_count,
            reason="already_processing",
        )

    if status == "dead_letter":
        return ConsumeLease(
            should_process=False,
            ledger_id=ledger_id,
            attempt_count=attempt_count,
            reason="dead_lettered",
        )

    retry_attempt = attempt_count + 1
    (
        sb.table("event_consumer_ledger")
        .update(
            {
                "status": "processing",
                "attempt_count": retry_attempt,
                "last_attempt_at": _utc_now_iso(),
                "last_error": None,
            }
        )
        .eq("id", ledger_id)
        .execute()
    )

    return ConsumeLease(
        should_process=True,
        ledger_id=ledger_id,
        attempt_count=retry_attempt,
        reason="retry_acquired",
    )


def mark_consume_succeeded(
    sb,
    ledger_id: str,
    result_payload: dict[str, Any] | None = None,
) -> None:
    payload = {
        "status": "succeeded",
        "processed_at": _utc_now_iso(),
        "last_error": None,
    }
    if result_payload is not None:
        payload["result_payload"] = result_payload

    sb.table("event_consumer_ledger").update(payload).eq("id", ledger_id).execute()


def mark_consume_failed(
    sb,
    ledger_id: str,
    error: str,
    dead_letter: bool = False,
) -> None:
    payload = {
        "status": "dead_letter" if dead_letter else "failed",
        "last_error": error,
        "last_attempt_at": _utc_now_iso(),
    }
    if dead_letter:
        payload["dead_lettered_at"] = _utc_now_iso()

    sb.table("event_consumer_ledger").update(payload).eq("id", ledger_id).execute()


def _consumer_max_attempts() -> int:
    try:
        return max(1, int(settings.event_consumer_max_attempts))
    except Exception:
        return 5


def get_consumer_ledger_status_counts(sb) -> dict[str, int]:
    """Return aggregate consumer-ledger status counts."""
    resp = sb.table("event_consumer_ledger").select("status").execute()
    rows = resp.data or []

    counts = {
        "processing": 0,
        "succeeded": 0,
        "failed": 0,
        "dead_letter": 0,
    }
    for row in rows:
        status = row.get("status")
        if status in counts:
            counts[status] += 1

    counts["total"] = len(rows)
    return counts


def list_dead_letter_consumer_entries(
    sb,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List dead-lettered consumer-ledger rows for triage."""
    resp = (
        sb.table("event_consumer_ledger")
        .select(
            "id,consumer_name,event_id,event_type,event_key,status,"
            "attempt_count,last_error,first_seen_at,last_attempt_at,dead_lettered_at"
        )
        .eq("status", "dead_letter")
        .order("dead_lettered_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def requeue_dead_letter_consumer_entries(
    sb,
    limit: int = 100,
) -> dict[str, int]:
    """
    Requeue dead-lettered consumer entries by:
    1) resetting ledger state to failed (eligible for retry acquisition),
    2) re-opening corresponding outbox events to pending for replay.
    """
    rows_resp = (
        sb.table("event_consumer_ledger")
        .select("id,event_id")
        .eq("status", "dead_letter")
        .order("dead_lettered_at", desc=False)
        .limit(limit)
        .execute()
    )
    rows = rows_resp.data or []

    if not rows:
        return {
            "selected": 0,
            "ledger_requeued": 0,
            "outbox_requeued": 0,
        }

    ledger_requeued = 0
    outbox_requeued = 0

    for row in rows:
        ledger_id = row.get("id")
        event_id = row.get("event_id")
        if not ledger_id or not event_id:
            continue

        (
            sb.table("event_consumer_ledger")
            .update(
                {
                    "status": "failed",
                    "last_error": None,
                    "dead_lettered_at": None,
                    "last_attempt_at": _utc_now_iso(),
                }
            )
            .eq("id", ledger_id)
            .execute()
        )
        ledger_requeued += 1

        (
            sb.table("event_outbox")
            .update(
                {
                    "status": "pending",
                    "retry_count": 0,
                    "last_error": None,
                    "dead_lettered_at": None,
                    "available_at": _utc_now_iso(),
                }
            )
            .eq("event_id", str(event_id))
            .execute()
        )
        outbox_requeued += 1

    return {
        "selected": len(rows),
        "ledger_requeued": ledger_requeued,
        "outbox_requeued": outbox_requeued,
    }


async def consume_idempotently(
    sb,
    consumer_name: str,
    event: DomainEvent,
    handler: Callable[[DomainEvent], Awaitable[dict[str, Any] | None]],
) -> dict[str, Any]:
    """
    Execute a consumer handler with idempotency ledger protection.
    """
    lease = begin_consume(sb=sb, consumer_name=consumer_name, event=event)
    if not lease.should_process:
        return {
            "processed": False,
            "reason": lease.reason,
            "attempt_count": lease.attempt_count,
            "ledger_id": lease.ledger_id,
        }

    if not lease.ledger_id:
        raise RuntimeError("Missing ledger id for acquired consume lease")

    try:
        result_payload = await handler(event)
        mark_consume_succeeded(
            sb=sb,
            ledger_id=lease.ledger_id,
            result_payload=result_payload,
        )
        return {
            "processed": True,
            "reason": "succeeded",
            "attempt_count": lease.attempt_count,
            "ledger_id": lease.ledger_id,
            "result": result_payload,
        }
    except Exception as exc:
        dead_letter = lease.attempt_count >= _consumer_max_attempts()
        mark_consume_failed(
            sb=sb,
            ledger_id=lease.ledger_id,
            error=str(exc),
            dead_letter=dead_letter,
        )
        logger.warning(
            "Consumer %s failed for event_id=%s: %s",
            consumer_name,
            event.event_id,
            exc,
        )
        if dead_letter:
            return {
                "processed": False,
                "reason": "dead_lettered",
                "attempt_count": lease.attempt_count,
                "ledger_id": lease.ledger_id,
                "error": str(exc),
            }
        raise
