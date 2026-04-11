"""
Covara One - Review workflow helpers.

Provides assignment/SLA utilities used by claims review routes and admin queue views.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

TERMINAL_CLAIM_STATUSES = {
    "approved",
    "auto_approved",
    "rejected",
    "paid",
    "post_approval_flagged",
}


def parse_iso_datetime(value: Any) -> datetime | None:
    """Parse an ISO datetime value into UTC."""
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def to_iso_z(dt: datetime) -> str:
    """Format datetime in UTC with a trailing Z."""
    return (
        dt.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def compute_review_due_at(
    claimed_at: str | datetime | None,
    sla_hours: int,
    now: datetime | None = None,
) -> str:
    """Compute due timestamp from claimed_at with SLA hour window."""
    base = parse_iso_datetime(claimed_at) or now or datetime.now(timezone.utc)
    hours = max(1, int(sla_hours))
    return to_iso_z(base + timedelta(hours=hours))


def classify_sla_status(
    claim_status: str,
    assignment_state: str | None,
    review_due_at: str | datetime | None,
    escalated_at: str | datetime | None,
    now: datetime | None = None,
    due_soon_hours: int = 4,
) -> str:
    """Classify SLA state for a claim review."""
    if claim_status in TERMINAL_CLAIM_STATUSES or assignment_state == "resolved":
        return "resolved"

    if assignment_state == "escalated" or parse_iso_datetime(escalated_at):
        return "escalated"

    due_dt = parse_iso_datetime(review_due_at)
    if not due_dt:
        return "not_set"

    ref = now or datetime.now(timezone.utc)
    remaining_hours = (due_dt - ref).total_seconds() / 3600.0
    if remaining_hours <= 0:
        return "overdue"

    if remaining_hours <= max(1, int(due_soon_hours)):
        return "due_soon"

    return "on_track"


def build_review_meta(
    claim: dict[str, Any],
    reviewer_names_by_id: dict[str, str] | None = None,
    current_user_id: str | None = None,
    now: datetime | None = None,
    due_soon_hours: int = 4,
) -> dict[str, Any]:
    """Build normalized assignment/SLA metadata for list/detail responses."""
    reviewer_names_by_id = reviewer_names_by_id or {}
    ref = now or datetime.now(timezone.utc)

    claim_status = claim.get("claim_status") or "submitted"
    assignment_state = claim.get("assignment_state") or "unassigned"
    assigned_reviewer_id = claim.get("assigned_reviewer_profile_id")
    escalated_at = claim.get("escalated_at")
    review_due_at = claim.get("review_due_at")

    sla_status = classify_sla_status(
        claim_status=claim_status,
        assignment_state=assignment_state,
        review_due_at=review_due_at,
        escalated_at=escalated_at,
        now=ref,
        due_soon_hours=due_soon_hours,
    )

    claimed_dt = parse_iso_datetime(claim.get("claimed_at"))
    due_dt = parse_iso_datetime(review_due_at)

    claim_age_hours = None
    if claimed_dt:
        claim_age_hours = round((ref - claimed_dt).total_seconds() / 3600.0, 2)

    hours_to_due = None
    if due_dt:
        hours_to_due = round((due_dt - ref).total_seconds() / 3600.0, 2)

    can_current_user_review = False
    if current_user_id and claim_status not in TERMINAL_CLAIM_STATUSES:
        can_current_user_review = (
            not assigned_reviewer_id or assigned_reviewer_id == current_user_id
        )

    assigned_name = (
        reviewer_names_by_id.get(assigned_reviewer_id, "")
        if assigned_reviewer_id
        else ""
    )

    return {
        "assignment_state": assignment_state,
        "assigned_reviewer_profile_id": assigned_reviewer_id,
        "assigned_reviewer_name": assigned_name,
        "assigned_at": claim.get("assigned_at"),
        "review_due_at": review_due_at,
        "sla_status": sla_status,
        "claim_age_hours": claim_age_hours,
        "hours_to_due": hours_to_due,
        "is_overdue": sla_status == "overdue",
        "can_current_user_review": can_current_user_review,
    }
