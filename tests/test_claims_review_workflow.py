"""API tests for reviewer assignment and SLA queue workflow in claims router."""

import os
import sys
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.dependencies import get_current_user, require_insurer_admin
from backend.app.routers import claims


class _FakeTable:
    def __init__(self, store: "_FakeSupabase", name: str):
        self.store = store
        self.name = name
        self._action = "select"
        self._payload: Any = None
        self._filters: list[tuple[str, object]] = []
        self._in_filter: tuple[str, set[object]] | None = None
        self._maybe_single = False
        self._limit: int | None = None

    def select(self, *_args, **_kwargs):
        self._action = "select"
        return self

    def eq(self, key: str, value):
        self._filters.append((key, value))
        return self

    def in_(self, key: str, values):
        self._in_filter = (key, set(values))
        return self

    def maybe_single(self):
        self._maybe_single = True
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    def update(self, payload: dict):
        self._action = "update"
        self._payload = payload
        return self

    def insert(self, payload):
        self._action = "insert"
        self._payload = payload
        return self

    def _filtered_rows(self):
        rows = self.store.tables[self.name]
        filtered = []
        for row in rows:
            if any(row.get(k) != v for k, v in self._filters):
                continue
            if self._in_filter:
                key, values = self._in_filter
                if row.get(key) not in values:
                    continue
            filtered.append(row)
        return filtered

    def execute(self):
        rows = self._filtered_rows()

        if self._action == "select":
            data = [dict(r) for r in rows]
            if self._limit is not None:
                data = data[: self._limit]
            if self._maybe_single:
                return SimpleNamespace(data=data[0] if data else None)
            return SimpleNamespace(data=data)

        if self._action == "update":
            updated = []
            for row in rows:
                row.update(self._payload or {})
                updated.append(dict(row))
            return SimpleNamespace(data=updated)

        if self._action == "insert":
            payload = self._payload
            if isinstance(payload, list):
                inserted = payload
            elif isinstance(payload, dict):
                inserted = [payload]
            else:
                raise AssertionError("Insert payload must be dict or list[dict]")

            table = self.store.tables[self.name]
            out = []
            for item in inserted:
                if not isinstance(item, dict):
                    raise AssertionError("Insert list items must be dict")
                record = dict(item)
                if "id" not in record:
                    record["id"] = f"{self.name}-{len(table) + 1}"
                table.append(record)
                out.append(dict(record))
            if self._maybe_single:
                return SimpleNamespace(data=out[0] if out else None)
            return SimpleNamespace(data=out)

        raise AssertionError(f"Unsupported action {self._action}")


class _FakeSupabase:
    def __init__(self, *, claim_rows: list[dict]):
        self.tables = {
            "manual_claims": claim_rows,
            "insurer_profiles": [
                {"profile_id": "admin-1"},
                {"profile_id": "admin-2"},
            ],
            "profiles": [
                {"id": "admin-1", "full_name": "Admin One"},
                {"id": "admin-2", "full_name": "Admin Two"},
            ],
            "claim_reviews": [],
            "audit_events": [],
            "worker_profiles": [],
        }

    def table(self, name: str):
        if name not in self.tables:
            raise AssertionError(f"Unexpected table: {name}")
        return _FakeTable(self, name)


def _build_client(current_user: dict) -> TestClient:
    app = FastAPI()
    app.include_router(claims.router)

    async def _mock_admin():
        return current_user

    app.dependency_overrides[require_insurer_admin] = _mock_admin
    app.dependency_overrides[get_current_user] = _mock_admin
    return TestClient(app)


class TestClaimsReviewWorkflow:
    def test_assign_claim_sets_owner_and_due(self):
        recent = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        sb = _FakeSupabase(
            claim_rows=[
                {
                    "id": "claim-1",
                    "claim_status": "submitted",
                    "claimed_at": recent,
                    "assignment_state": "unassigned",
                    "assigned_reviewer_profile_id": None,
                }
            ]
        )

        with patch("backend.app.routers.claims.get_supabase_admin", return_value=sb), patch(
            "backend.app.routers.claims.enqueue_domain_event",
            new=AsyncMock(return_value=None),
        ):
            with _build_client({"id": "admin-1", "role": "insurer_admin"}) as client:
                resp = client.post(
                    "/claims/claim-1/assign",
                    json={"reviewer_profile_id": "admin-1", "due_in_hours": 12},
                )

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "assigned"
        assert payload["assigned_reviewer_profile_id"] == "admin-1"
        assert payload["review_meta"]["assignment_state"] == "assigned"
        assert payload["review_meta"]["sla_status"] in {"on_track", "due_soon"}

        claim = sb.tables["manual_claims"][0]
        assert claim["assigned_reviewer_profile_id"] == "admin-1"
        assert claim["assignment_state"] == "assigned"
        assert claim.get("review_due_at")
        assert sb.tables["audit_events"][0]["action_type"] == "claim_assigned"

    def test_assign_claim_propagates_request_id(self):
        sb = _FakeSupabase(
            claim_rows=[
                {
                    "id": "claim-req-id",
                    "claim_status": "submitted",
                    "claimed_at": "2026-04-09T10:00:00Z",
                    "assignment_state": "unassigned",
                    "assigned_reviewer_profile_id": None,
                }
            ]
        )

        with patch("backend.app.routers.claims.get_supabase_admin", return_value=sb), patch(
            "backend.app.routers.claims.enqueue_domain_event",
            new=AsyncMock(return_value=None),
        ) as mock_event:
            with _build_client({"id": "admin-1", "role": "insurer_admin"}) as client:
                resp = client.post(
                    "/claims/claim-req-id/assign",
                    json={"reviewer_profile_id": "admin-1", "due_in_hours": 8},
                    headers={"X-Request-ID": "req-assign-123"},
                )

        assert resp.status_code == 200
        assert sb.tables["audit_events"][0]["event_payload"]["request_id"] == "req-assign-123"
        assert mock_event.await_count == 1
        payload = mock_event.await_args.kwargs.get("payload")
        assert isinstance(payload, dict)
        assert payload["request_id"] == "req-assign-123"

    def test_review_rejects_if_assigned_to_other_admin(self):
        sb = _FakeSupabase(
            claim_rows=[
                {
                    "id": "claim-2",
                    "claim_status": "submitted",
                    "claimed_at": "2026-04-09T10:00:00Z",
                    "assignment_state": "assigned",
                    "assigned_reviewer_profile_id": "admin-2",
                }
            ]
        )

        with patch("backend.app.routers.claims.get_supabase_admin", return_value=sb), patch(
            "backend.app.routers.claims.enqueue_domain_event",
            new=AsyncMock(return_value=None),
        ):
            with _build_client({"id": "admin-1", "role": "insurer_admin"}) as client:
                resp = client.post(
                    "/claims/claim-2/review",
                    json={"decision": "approve", "decision_reason": "ok"},
                )

        assert resp.status_code == 409
        assert "assigned to another reviewer" in resp.json()["detail"]

    def test_review_auto_claims_unassigned_owner_and_sets_in_review(self):
        sb = _FakeSupabase(
            claim_rows=[
                {
                    "id": "claim-3",
                    "claim_status": "submitted",
                    "claimed_at": "2026-04-09T10:00:00Z",
                    "assignment_state": "unassigned",
                    "assigned_reviewer_profile_id": None,
                    "assigned_at": None,
                    "first_reviewed_at": None,
                    "review_due_at": None,
                }
            ]
        )

        with patch("backend.app.routers.claims.get_supabase_admin", return_value=sb), patch(
            "backend.app.routers.claims.enqueue_domain_event",
            new=AsyncMock(return_value=None),
        ):
            with _build_client({"id": "admin-1", "role": "insurer_admin"}) as client:
                resp = client.post(
                    "/claims/claim-3/review",
                    json={"decision": "hold", "decision_reason": "Need checks"},
                )

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["assignment_state"] == "in_review"

        claim = sb.tables["manual_claims"][0]
        assert claim["claim_status"] == "soft_hold_verification"
        assert claim["assignment_state"] == "in_review"
        assert claim["assigned_reviewer_profile_id"] == "admin-1"
        assert claim.get("first_reviewed_at")
        assert claim.get("review_due_at")

    def test_review_approve_triggers_payout_initiation(self):
        sb = _FakeSupabase(
            claim_rows=[
                {
                    "id": "claim-approve",
                    "claim_status": "submitted",
                    "claimed_at": "2026-04-09T10:00:00Z",
                    "assignment_state": "assigned",
                    "assigned_reviewer_profile_id": "admin-1",
                    "assigned_at": "2026-04-09T10:05:00Z",
                    "first_reviewed_at": None,
                    "review_due_at": "2026-04-10T10:00:00Z",
                }
            ]
        )

        with patch("backend.app.routers.claims.get_supabase_admin", return_value=sb), patch(
            "backend.app.routers.claims.enqueue_domain_event",
            new=AsyncMock(return_value=None),
        ), patch(
            "backend.app.routers.claims.initiate_payout_for_claim",
            new=AsyncMock(return_value={"status": "pending", "payout": {"id": "payout-1"}}),
        ) as mock_initiate:
            with _build_client({"id": "admin-1", "role": "insurer_admin"}) as client:
                resp = client.post(
                    "/claims/claim-approve/review",
                    json={"decision": "approve", "decision_reason": "Looks valid"},
                )

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["decision"] == "approve"
        assert payload["payout"]["status"] == "pending"
        assert mock_initiate.await_count == 1

    def test_list_claims_overdue_queue_filters_by_sla(self):
        sb = _FakeSupabase(
            claim_rows=[
                {
                    "id": "claim-overdue",
                    "claim_status": "submitted",
                    "claimed_at": "2026-04-08T10:00:00Z",
                    "assignment_state": "assigned",
                    "assigned_reviewer_profile_id": "admin-1",
                    "review_due_at": "2026-04-08T20:00:00Z",
                },
                {
                    "id": "claim-fresh",
                    "claim_status": "submitted",
                    "claimed_at": "2099-04-09T10:00:00Z",
                    "assignment_state": "assigned",
                    "assigned_reviewer_profile_id": "admin-1",
                    "review_due_at": "2099-04-10T10:00:00Z",
                },
            ]
        )

        with patch("backend.app.routers.claims.get_supabase_admin", return_value=sb):
            with _build_client({"id": "admin-1", "role": "insurer_admin"}) as client:
                resp = client.get("/claims/?queue=overdue")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["queue"] == "overdue"
        assert len(payload["claims"]) == 1
        assert payload["claims"][0]["id"] == "claim-overdue"
        assert payload["claims"][0]["review_meta"]["sla_status"] == "overdue"
