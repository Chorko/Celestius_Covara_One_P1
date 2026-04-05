"""
Covara One - Event Outbox Service

Durable event publishing helpers backed by the event_outbox table.
This provides retryable delivery semantics independent of broker state.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.config import settings
from backend.app.services.event_bus.contracts import DomainEvent
from backend.app.services.event_bus.factory import publish_domain_event

logger = logging.getLogger("covara.event_outbox")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _build_backoff_seconds(retry_count: int) -> int:
    # 2^n capped at 5 minutes.
    return min(300, 2 ** max(1, retry_count))


def _is_duplicate_worker_event_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "duplicate key" in msg and "idx_unique_worker_event" in msg


def _first_data_row(data: Any) -> dict[str, Any] | None:
    if isinstance(data, list):
        if not data:
            return None
        first = data[0]
        return first if isinstance(first, dict) else None

    if isinstance(data, dict):
        return data

    return None


def _outbox_max_retries() -> int:
    value = getattr(settings, "event_outbox_max_retries", 10)
    try:
        return max(1, int(value))
    except Exception:
        return 10


def _should_run_inline_consumers() -> bool:
    if not settings.event_bus_inline_consumer_enabled:
        return False

    backend = (settings.event_bus_backend or "inmemory").strip().lower()
    return backend == "inmemory"


def _mark_outbox_failure(
    sb,
    event_id: str,
    previous_retry_count: int,
    error_text: str,
) -> tuple[str, int]:
    retry_count = previous_retry_count + 1
    max_retries = _outbox_max_retries()

    update_payload = {
        "retry_count": retry_count,
        "last_error": error_text,
        "available_at": (_utc_now() + timedelta(seconds=_build_backoff_seconds(retry_count))).isoformat(),
    }

    if retry_count >= max_retries:
        update_payload["status"] = "dead_letter"
        update_payload["dead_lettered_at"] = _utc_now_iso()
    else:
        update_payload["status"] = "failed"

    sb.table("event_outbox").update(update_payload).eq("event_id", event_id).execute()
    return str(update_payload["status"]), retry_count


async def _publish_and_mark_outbox_event(
    sb,
    event: DomainEvent,
    previous_retry_count: int = 0,
) -> dict[str, Any]:
    try:
        await publish_domain_event(event)

        if _should_run_inline_consumers():
            from backend.app.services.event_bus.consumer_dispatch import (
                dispatch_event_to_consumers,
            )

            await dispatch_event_to_consumers(sb=sb, event=event)

        sb.table("event_outbox").update(
            {
                "status": "processed",
                "processed_at": _utc_now_iso(),
                "last_error": None,
                "dead_lettered_at": None,
            }
        ).eq("event_id", event.event_id).execute()
        return {
            "event_id": event.event_id,
            "status": "processed",
            "published": True,
            "retry_count": previous_retry_count,
        }
    except Exception as exc:
        status, retry_count = _mark_outbox_failure(
            sb=sb,
            event_id=event.event_id,
            previous_retry_count=previous_retry_count,
            error_text=str(exc),
        )
        return {
            "event_id": event.event_id,
            "status": status,
            "published": False,
            "retry_count": retry_count,
            "error": str(exc),
        }


async def enqueue_domain_event(
    sb,
    event_type: str,
    payload: dict[str, Any],
    key: str | None = None,
    source: str = "backend",
    publish_immediately: bool | None = None,
) -> dict[str, Any]:
    """
    Persist an event to outbox and optionally attempt immediate publish.

    Returns a status dict with event_id and delivery result.
    """
    event = DomainEvent(
        event_type=event_type,
        payload=payload,
        key=key,
        source=source,
    )

    row = {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "event_key": event.key,
        "event_source": event.source,
        "event_payload": event.payload,
        "status": "pending",
        "retry_count": 0,
        "created_at": event.occurred_at,
        "available_at": event.occurred_at,
    }

    sb.table("event_outbox").insert(row).execute()

    should_publish_now = (
        settings.event_bus_publish_on_write
        if publish_immediately is None
        else publish_immediately
    )

    if not should_publish_now:
        return {
            "event_id": event.event_id,
            "status": "pending",
            "published": False,
        }

    result = await _publish_and_mark_outbox_event(
        sb=sb,
        event=event,
        previous_retry_count=0,
    )
    if result.get("status") != "processed":
        logger.warning("Immediate outbox publish failed for event_id=%s", event.event_id)
    return result


async def persist_claim_with_outbox(
    sb,
    claim_row: dict[str, Any],
    payout_row: dict[str, Any],
    event_type: str,
    event_payload: dict[str, Any],
    event_key: str | None = None,
    event_source: str = "backend",
    publish_immediately: bool | None = None,
) -> dict[str, Any]:
    """
    Persist claim + payout + outbox event with best-effort transaction semantics.

    Preferred path calls the SQL RPC `persist_claim_with_outbox` for atomic writes.
    If RPC is unavailable, falls back to sequential writes and standard outbox enqueue.
    """
    should_publish_now = (
        settings.event_bus_publish_on_write
        if publish_immediately is None
        else publish_immediately
    )

    rpc_supported = hasattr(sb, "rpc")
    if rpc_supported:
        try:
            rpc_response = sb.rpc(
                "persist_claim_with_outbox",
                {
                    "p_claim": claim_row,
                    "p_payout": payout_row,
                    "p_event_type": event_type,
                    "p_event_key": event_key,
                    "p_event_source": event_source,
                    "p_event_payload": event_payload,
                },
            ).execute()

            rpc_row = _first_data_row(getattr(rpc_response, "data", None))
            if not rpc_row:
                raise RuntimeError("persist_claim_with_outbox RPC returned no data")

            duplicate_skipped = bool(rpc_row.get("duplicate_skipped"))
            claim_id = rpc_row.get("claim_id")
            event_id = rpc_row.get("event_id")

            if duplicate_skipped:
                return {
                    "claim_id": None,
                    "event_id": None,
                    "duplicate_skipped": True,
                    "published": False,
                    "status": "duplicate_skipped",
                }

            if not claim_id or not event_id:
                raise RuntimeError("persist_claim_with_outbox RPC missing ids")

            event_payload_with_claim = dict(event_payload)
            event_payload_with_claim.setdefault("claim_id", str(claim_id))

            event = DomainEvent(
                event_id=str(event_id),
                event_type=event_type,
                payload=event_payload_with_claim,
                key=event_key,
                source=event_source,
                occurred_at=str(claim_row.get("claimed_at") or _utc_now_iso()),
            )

            if not should_publish_now:
                return {
                    "claim_id": str(claim_id),
                    "event_id": str(event_id),
                    "duplicate_skipped": False,
                    "published": False,
                    "status": "pending",
                }

            publish_result = await _publish_and_mark_outbox_event(
                sb=sb,
                event=event,
                previous_retry_count=0,
            )
            publish_result.update(
                {
                    "claim_id": str(claim_id),
                    "duplicate_skipped": False,
                }
            )
            return publish_result
        except Exception as exc:
            logger.warning("Transactional RPC persist failed, using fallback path: %s", exc)

    try:
        claim_response = sb.table("manual_claims").insert(claim_row).execute()
        claim_data = _first_data_row(getattr(claim_response, "data", None)) or {}
        claim_id = claim_data.get("id")
        if not claim_id:
            raise RuntimeError("manual_claims insert did not return claim id")
    except Exception as exc:
        if _is_duplicate_worker_event_error(exc):
            return {
                "claim_id": None,
                "event_id": None,
                "duplicate_skipped": True,
                "published": False,
                "status": "duplicate_skipped",
            }
        raise

    payout_insert = dict(payout_row)
    payout_insert["claim_id"] = claim_id
    sb.table("payout_recommendations").insert(payout_insert).execute()

    event_payload_with_claim = dict(event_payload)
    event_payload_with_claim.setdefault("claim_id", str(claim_id))

    event_result = await enqueue_domain_event(
        sb=sb,
        event_type=event_type,
        key=event_key,
        source=event_source,
        payload=event_payload_with_claim,
        publish_immediately=should_publish_now,
    )
    event_result.update(
        {
            "claim_id": str(claim_id),
            "duplicate_skipped": False,
        }
    )
    return event_result


async def relay_pending_outbox_events(sb, batch_size: int = 100) -> dict[str, int]:
    """
    Publish pending/failed outbox events and update delivery status.
    """
    now_iso = _utc_now_iso()

    response = (
        sb.table("event_outbox")
        .select(
            "id,event_id,event_type,event_key,event_source,event_payload,created_at,retry_count,status"
        )
        .in_("status", ["pending", "failed"])
        .lte("available_at", now_iso)
        .order("created_at", desc=False)
        .limit(batch_size)
        .execute()
    )

    rows = response.data or []
    if not rows:
        return {
            "fetched": 0,
            "processed": 0,
            "failed": 0,
            "dead_lettered": 0,
        }

    processed = 0
    failed = 0
    dead_lettered = 0

    for row in rows:
        event = DomainEvent(
            event_id=row["event_id"],
            event_type=row["event_type"],
            key=row.get("event_key"),
            source=row.get("event_source") or "backend",
            payload=row.get("event_payload") or {},
            occurred_at=row.get("created_at") or now_iso,
        )

        result = await _publish_and_mark_outbox_event(
            sb=sb,
            event=event,
            previous_retry_count=int(row.get("retry_count") or 0),
        )
        status = result.get("status")
        if status == "processed":
            processed += 1
        elif status == "dead_letter":
            dead_lettered += 1
        else:
            failed += 1

    return {
        "fetched": len(rows),
        "processed": processed,
        "failed": failed,
        "dead_lettered": dead_lettered,
    }


async def get_outbox_status_counts(sb) -> dict[str, int]:
    """Return simple status counts for event_outbox."""
    response = (
        sb.table("event_outbox")
        .select("status")
        .execute()
    )
    rows = response.data or []

    counts = {
        "pending": 0,
        "failed": 0,
        "processed": 0,
        "dead_letter": 0,
    }
    for row in rows:
        status = row.get("status")
        if status in counts:
            counts[status] += 1

    counts["total"] = len(rows)
    return counts


async def list_dead_letter_outbox_events(
    sb,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List recent dead-lettered outbox events for operations triage."""
    response = (
        sb.table("event_outbox")
        .select(
            "event_id,event_type,event_key,event_source,event_payload,"
            "retry_count,last_error,created_at,dead_lettered_at"
        )
        .eq("status", "dead_letter")
        .order("dead_lettered_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


async def requeue_dead_letter_outbox_events(
    sb,
    limit: int = 100,
) -> dict[str, int]:
    """Move dead-lettered events back to pending for controlled replay."""
    response = (
        sb.table("event_outbox")
        .select("event_id")
        .eq("status", "dead_letter")
        .order("dead_lettered_at", desc=False)
        .limit(limit)
        .execute()
    )

    rows = response.data or []
    if not rows:
        return {
            "selected": 0,
            "requeued": 0,
        }

    requeued = 0
    for row in rows:
        event_id = row.get("event_id")
        if not event_id:
            continue

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
            .eq("event_id", event_id)
            .execute()
        )
        requeued += 1

    return {
        "selected": len(rows),
        "requeued": requeued,
    }
