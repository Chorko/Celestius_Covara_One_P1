"""Unit tests for review assignment and SLA helper logic."""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.review_workflow import (  # noqa: E402
    build_review_meta,
    classify_sla_status,
    compute_review_due_at,
)


class TestReviewWorkflowHelpers:
    def test_compute_review_due_at_from_claimed_at(self):
        claimed_at = "2026-04-09T10:00:00Z"
        due = compute_review_due_at(claimed_at, sla_hours=24)
        assert due == "2026-04-10T10:00:00Z"

    def test_classify_sla_status_overdue(self):
        now = datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc)
        due = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        status = classify_sla_status(
            claim_status="submitted",
            assignment_state="assigned",
            review_due_at=due,
            escalated_at=None,
            now=now,
            due_soon_hours=4,
        )
        assert status == "overdue"

    def test_build_review_meta_tracks_owner_and_reviewability(self):
        now = datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc)
        due = (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        claim = {
            "claim_status": "submitted",
            "assignment_state": "assigned",
            "assigned_reviewer_profile_id": "admin-1",
            "review_due_at": due,
            "claimed_at": "2026-04-09T06:00:00Z",
        }
        meta = build_review_meta(
            claim=claim,
            reviewer_names_by_id={"admin-1": "Ops Admin"},
            current_user_id="admin-1",
            now=now,
            due_soon_hours=4,
        )
        assert meta["assigned_reviewer_name"] == "Ops Admin"
        assert meta["sla_status"] == "due_soon"
        assert meta["can_current_user_review"] is True
        assert meta["claim_age_hours"] == 6.0
