"""Covara One - Operations visibility router.

Provides low-overhead operational status and metrics surfaces for staging
confidence and alert-ready monitoring baselines.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request

from backend.app.config import settings
from backend.app.dependencies import require_insurer_admin
from backend.app.services.event_bus.consumer_idempotency import (
    get_consumer_ledger_status_counts,
)
from backend.app.services.event_bus.outbox import get_outbox_status_counts
from backend.app.services.observability import (
    get_metrics_snapshot,
    set_gauge,
)
from backend.app.services.review_workflow import (
    TERMINAL_CLAIM_STATUSES,
    classify_sla_status,
)
from backend.app.supabase_client import get_supabase_admin

router = APIRouter(prefix="/ops", tags=["Operations"])


def _review_queue_summary(claim_rows: list[dict[str, Any]]) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    summary = {
        "open_claims": 0,
        "unassigned": 0,
        "overdue": 0,
        "due_soon": 0,
        "escalated": 0,
        "resolved": 0,
    }

    for row in claim_rows:
        claim_status = str(row.get("claim_status") or "")
        assignment_state = str(row.get("assignment_state") or "unassigned")

        sla = classify_sla_status(
            claim_status=claim_status,
            assignment_state=assignment_state,
            review_due_at=row.get("review_due_at"),
            escalated_at=row.get("escalated_at"),
            now=now,
            due_soon_hours=settings.review_sla_due_soon_hours,
        )

        if claim_status in TERMINAL_CLAIM_STATUSES:
            summary["resolved"] += 1
            continue

        summary["open_claims"] += 1
        if assignment_state == "unassigned":
            summary["unassigned"] += 1
        if sla == "overdue":
            summary["overdue"] += 1
        elif sla == "due_soon":
            summary["due_soon"] += 1
        elif sla == "escalated":
            summary["escalated"] += 1

    return summary


def _status_count(rows: list[dict[str, Any]], field: str = "status") -> dict[str, int]:
    counts: dict[str, int] = {"total": len(rows)}
    for row in rows:
        status = str(row.get(field) or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


@router.get(
    "/metrics",
    dependencies=[Depends(require_insurer_admin)],
    summary="In-memory observability metrics snapshot",
)
def get_ops_metrics():
    return {
        "status": "ok",
        "metrics": get_metrics_snapshot(),
    }


@router.get(
    "/status",
    dependencies=[Depends(require_insurer_admin)],
    summary="Operational status overview",
)
async def get_ops_status(request: Request):
    sb = get_supabase_admin()

    outbox_counts = await get_outbox_status_counts(sb)
    consumer_counts = get_consumer_ledger_status_counts(sb)

    claim_rows = (
        sb.table("manual_claims")
        .select("claim_status, assignment_state, review_due_at, escalated_at")
        .order("claimed_at", desc=True)
        .limit(1000)
        .execute()
        .data
        or []
    )
    claim_rows = [row for row in claim_rows if isinstance(row, dict)]

    payout_rows: list[dict[str, Any]] = []
    try:
        payout_rows_raw = (
            sb.table("payout_requests")
            .select("status")
            .execute()
            .data
            or []
        )
        payout_rows = [row for row in payout_rows_raw if isinstance(row, dict)]
    except Exception:
        payout_rows = []

    review_summary = _review_queue_summary(claim_rows)
    payout_summary = _status_count(payout_rows)

    set_gauge("review_queue_open", review_summary.get("open_claims", 0))
    set_gauge("review_queue_overdue", review_summary.get("overdue", 0))
    set_gauge("review_queue_unassigned", review_summary.get("unassigned", 0))
    set_gauge("outbox_dead_letter", outbox_counts.get("dead_letter", 0))
    set_gauge("consumer_dead_letter", consumer_counts.get("dead_letter", 0))
    set_gauge(
        "payout_failure_like",
        payout_summary.get("failed", 0) + payout_summary.get("manual_review", 0),
    )

    runtime_state = {
        "redis_cache_ready": bool(getattr(request.app.state, "redis_cache_ready", False)),
        "outbox_worker_running": bool(getattr(request.app.state, "outbox_worker_running", False)),
        "kafka_consumer_running": bool(getattr(request.app.state, "kafka_consumer_running", False)),
        "outbox_last_batch": getattr(request.app.state, "outbox_last_batch", None),
        "outbox_last_batch_at": getattr(request.app.state, "outbox_last_batch_at", None),
    }

    alert_signals = {
        "payout_failures": payout_summary.get("failed", 0),
        "payout_manual_review": payout_summary.get("manual_review", 0),
        "outbox_dead_letter": outbox_counts.get("dead_letter", 0),
        "consumer_dead_letter": consumer_counts.get("dead_letter", 0),
        "review_overdue": review_summary.get("overdue", 0),
        "review_unassigned": review_summary.get("unassigned", 0),
    }

    return {
        "status": "ok",
        "event_bus": {
            "backend": settings.event_bus_backend,
            "relay_enabled": settings.event_outbox_relay_enabled,
            "consumer_enabled": settings.event_consumer_enabled,
            "outbox": outbox_counts,
            "consumer_ledger": consumer_counts,
        },
        "review_queue": review_summary,
        "payouts": payout_summary,
        "runtime": runtime_state,
        "alert_signals": alert_signals,
    }
