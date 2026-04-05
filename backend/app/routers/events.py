"""
Covara One - Events Router

Operational endpoints for event bus outbox relay control.
"""

from fastapi import APIRouter, Depends, Query

from backend.app.config import settings
from backend.app.dependencies import require_insurer_admin
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
    limit: int = Query(default=settings.event_outbox_relay_batch_size, ge=1, le=500),
):
    sb = get_supabase_admin()
    result = await relay_pending_outbox_events(sb, batch_size=limit)
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
    limit: int = Query(default=50, ge=1, le=500),
):
    sb = get_supabase_admin()
    events = await list_dead_letter_outbox_events(sb, limit=limit)
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
    limit: int = Query(default=100, ge=1, le=1000),
):
    sb = get_supabase_admin()
    result = await requeue_dead_letter_outbox_events(sb, limit=limit)
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
    limit: int = Query(default=100, ge=1, le=1000),
):
    sb = get_supabase_admin()
    result = requeue_dead_letter_consumer_entries(sb, limit=limit)
    return {
        "status": "ok",
        **result,
    }
