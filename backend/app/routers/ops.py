"""Covara One - Operations visibility router.

Provides low-overhead operational status and metrics surfaces for staging
confidence and alert-ready monitoring baselines.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

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
from backend.app.services.version_governance import (
    apply_version_rollout,
    get_version_registry_snapshot,
)
from backend.app.supabase_client import get_supabase_admin

router = APIRouter(prefix="/ops", tags=["Operations"])


class VersionRolloutUpdateRequest(BaseModel):
    kind: str = Field(description="rule or model")
    version_id: str
    mode: str = Field(default="full", description="full | canary | cohort")
    rollout_percentage: int | None = Field(default=None, ge=0, le=100)
    cohort_key: str | None = None


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


def _evaluate_slo_breaches(
    *,
    outbox_counts: dict[str, int],
    consumer_counts: dict[str, int],
    review_summary: dict[str, int],
    payout_summary: dict[str, int],
) -> dict[str, Any]:
    thresholds = {
        "outbox_dead_letter": settings.ops_slo_outbox_dead_letter_max,
        "consumer_dead_letter": settings.ops_slo_consumer_dead_letter_max,
        "review_overdue": settings.ops_slo_review_overdue_max,
        "review_unassigned": settings.ops_slo_review_unassigned_max,
        "payout_failures": settings.ops_slo_payout_failures_max,
        "payout_manual_review": settings.ops_slo_payout_manual_review_max,
    }

    observed = {
        "outbox_dead_letter": int(outbox_counts.get("dead_letter", 0)),
        "consumer_dead_letter": int(consumer_counts.get("dead_letter", 0)),
        "review_overdue": int(review_summary.get("overdue", 0)),
        "review_unassigned": int(review_summary.get("unassigned", 0)),
        "payout_failures": int(payout_summary.get("failed", 0)),
        "payout_manual_review": int(payout_summary.get("manual_review", 0)),
    }

    runbook_links = {
        "outbox_dead_letter": "docs/PAYOUT_EVENT_REQUEUE_RUNBOOK.md#step-a--outbox-dead-letter-recovery",
        "consumer_dead_letter": "docs/PAYOUT_EVENT_REQUEUE_RUNBOOK.md#step-b--consumer-dead-letter-recovery",
        "review_overdue": "docs/DEPLOYMENT_RELEASE_RUNBOOK.md",
        "review_unassigned": "docs/DEPLOYMENT_RELEASE_RUNBOOK.md",
        "payout_failures": "docs/PAYOUT_EVENT_REQUEUE_RUNBOOK.md#verification-checklist",
        "payout_manual_review": "docs/PAYOUT_EVENT_REQUEUE_RUNBOOK.md#verification-checklist",
    }

    actions = {
        "outbox_dead_letter": "Run outbox dead-letter list/requeue batches and verify backlog trend after each batch.",
        "consumer_dead_letter": "Run consumer dead-letter list/requeue batches and verify idempotent replay progression.",
        "review_overdue": "Increase reviewer throughput or rebalance assignments and clear overdue queue first.",
        "review_unassigned": "Assign claim owners and enforce assignment SLA for unassigned claims.",
        "payout_failures": "Inspect payout failures, route unstable transitions to manual_review, and replay only safe dead-letter events.",
        "payout_manual_review": "Triage manual_review queue and resolve blocked provider/state-machine transitions.",
    }

    breaches: list[dict[str, Any]] = []
    for metric, threshold in thresholds.items():
        value = observed[metric]
        if value > threshold:
            breaches.append(
                {
                    "metric": metric,
                    "observed": value,
                    "threshold": threshold,
                    "runbook": runbook_links.get(metric),
                    "recommended_action": actions.get(metric),
                }
            )

    return {
        "status": "breach" if breaches else "ok",
        "thresholds": thresholds,
        "observed": observed,
        "breaches": breaches,
    }


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
    "/version-governance",
    dependencies=[Depends(require_insurer_admin)],
    summary="Rule/model governance registry snapshot",
)
def get_version_governance_snapshot():
    sb = get_supabase_admin()
    snapshot = get_version_registry_snapshot(sb)
    return {
        "status": "ok",
        **snapshot,
    }


@router.post(
    "/version-governance/activate",
    dependencies=[Depends(require_insurer_admin)],
    summary="Activate or adjust a rule/model rollout",
)
def activate_version_governance_rollout(body: VersionRolloutUpdateRequest):
    sb = get_supabase_admin()

    try:
        rollout = apply_version_rollout(
            sb,
            kind=body.kind,
            version_id=body.version_id,
            mode=body.mode,
            rollout_percentage=body.rollout_percentage,
            cohort_key=body.cohort_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "rollout": rollout,
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
    slo = _evaluate_slo_breaches(
        outbox_counts=outbox_counts,
        consumer_counts=consumer_counts,
        review_summary=review_summary,
        payout_summary=payout_summary,
    )

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
        "slo": slo,
    }


@router.get(
    "/slo",
    dependencies=[Depends(require_insurer_admin)],
    summary="SLO thresholds and breach view",
)
async def get_ops_slo_status():
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

    slo = _evaluate_slo_breaches(
        outbox_counts=outbox_counts,
        consumer_counts=consumer_counts,
        review_summary=review_summary,
        payout_summary=payout_summary,
    )

    return {
        "status": "ok",
        "slo": slo,
    }
