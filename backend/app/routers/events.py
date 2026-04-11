"""
Covara One - Events Router

Operational endpoints for event bus outbox relay control.
"""

import logging

from fastapi import APIRouter, Depends, Query, Request

from backend.app.config import settings
from backend.app.dependencies import require_insurer_admin
from backend.app.services.observability import increment_counter, structured_log
from backend.app.supabase_client import get_supabase_admin
from backend.app.services.event_bus.outbox import (
    get_outbox_status_counts,
    list_dead_letter_outbox_events,
    relay_pending_outbox_events,
    requeue_dead_letter_outbox_events,
)
from backend.app.services.event_bus.consumer_idempotency import (
    get_consumer_ledger_status_counts,
    list_dead_letter_consumer_entries,
    requeue_dead_letter_consumer_entries,
)

router = APIRouter(prefix="/events", tags=["Events"])
logger = logging.getLogger("covara.events.router")


def _request_id(request: Request | None) -> str | None:
    if request is None:
        return None
    state_id = getattr(getattr(request, "state", None), "request_id", None)
    if state_id:
        return str(state_id)
    return request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")


@router.post(
    "/outbox/relay",
    dependencies=[Depends(require_insurer_admin)],
    summary="Relay pending outbox events",
    description=(
        "Publishes pending/failed outbox events through the configured event bus "
        "and updates delivery status with retry backoff on failure."
    ),
)
async def relay_outbox_events(
    request: Request,
    limit: int = Query(default=settings.event_outbox_relay_batch_size, ge=1, le=500),
):
    sb = get_supabase_admin()
    request_id = _request_id(request)
    result = await relay_pending_outbox_events(sb, batch_size=limit)
    increment_counter("event_outbox_relay_http_total", labels={"outcome": "ok"})
    structured_log(
        logger,
        logging.INFO,
        "events.outbox.relay",
        request_id=request_id,
        batch_size=limit,
        fetched=result.get("fetched", 0),
        processed=result.get("processed", 0),
        failed=result.get("failed", 0),
        dead_lettered=result.get("dead_lettered", 0),
    )
    return {
        "status": "ok",
        "batch_size": limit,
        **result,
    }


@router.get(
    "/outbox/status",
    dependencies=[Depends(require_insurer_admin)],
    summary="Outbox status counts",
)
async def get_outbox_status():
    sb = get_supabase_admin()
    counts = await get_outbox_status_counts(sb)
    return {
        "status": "ok",
        "counts": counts,
    }


@router.get(
    "/outbox/dead-letter",
    dependencies=[Depends(require_insurer_admin)],
    summary="List dead-letter outbox events",
)
async def list_dead_letters(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
):
    sb = get_supabase_admin()
    request_id = _request_id(request)
    events = await list_dead_letter_outbox_events(sb, limit=limit)
    structured_log(
        logger,
        logging.INFO,
        "events.outbox.dead_letter.list",
        request_id=request_id,
        limit=limit,
        returned=len(events),
    )
    return {
        "status": "ok",
        "count": len(events),
        "events": events,
    }


@router.post(
    "/outbox/dead-letter/requeue",
    dependencies=[Depends(require_insurer_admin)],
    summary="Requeue dead-letter outbox events",
)
async def requeue_dead_letters(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
):
    sb = get_supabase_admin()
    request_id = _request_id(request)
    result = await requeue_dead_letter_outbox_events(sb, limit=limit)
    increment_counter(
        "event_outbox_dead_letter_requeue_total",
        amount=int(result.get("requeued", 0)),
    )
    structured_log(
        logger,
        logging.INFO,
        "events.outbox.dead_letter.requeue",
        request_id=request_id,
        selected=result.get("selected", 0),
        requeued=result.get("requeued", 0),
    )
    return {
        "status": "ok",
        **result,
    }


@router.get(
    "/consumers/status",
    dependencies=[Depends(require_insurer_admin)],
    summary="Consumer ledger status counts",
)
async def get_consumer_status():
    sb = get_supabase_admin()
    counts = get_consumer_ledger_status_counts(sb)
    return {
        "status": "ok",
        "counts": counts,
    }


@router.get(
    "/consumers/dead-letter",
    dependencies=[Depends(require_insurer_admin)],
    summary="List dead-letter consumer entries",
)
async def list_consumer_dead_letters(
    limit: int = Query(default=50, ge=1, le=500),
):
    sb = get_supabase_admin()
    rows = list_dead_letter_consumer_entries(sb, limit=limit)
    return {
        "status": "ok",
        "count": len(rows),
        "entries": rows,
    }


@router.post(
    "/consumers/dead-letter/requeue",
    dependencies=[Depends(require_insurer_admin)],
    summary="Requeue dead-letter consumer entries",
)
async def requeue_consumer_dead_letters(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
):
    sb = get_supabase_admin()
    request_id = _request_id(request)
    result = requeue_dead_letter_consumer_entries(sb, limit=limit)
    increment_counter(
        "event_consumer_dead_letter_requeue_total",
        amount=int(result.get("ledger_requeued", 0)),
    )
    structured_log(
        logger,
        logging.INFO,
        "events.consumer.dead_letter.requeue",
        request_id=request_id,
        selected=result.get("selected", 0),
        ledger_requeued=result.get("ledger_requeued", 0),
        outbox_requeued=result.get("outbox_requeued", 0),
    )
    return {
        "status": "ok",
        **result,
    }
