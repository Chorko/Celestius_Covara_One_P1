"""API tests for operations visibility endpoints."""

import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.dependencies import require_insurer_admin
from backend.app.routers import ops


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows
        self._limit = None

    def select(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, value):
        self._limit = value
        return self

    def execute(self):
        rows = list(self._rows)
        if self._limit is not None:
            rows = rows[: self._limit]
        return SimpleNamespace(data=rows)


class _FakeSupabase:
    def __init__(self):
        self.tables = {
            "manual_claims": [
                {
                    "claim_status": "submitted",
                    "assignment_state": "unassigned",
                    "review_due_at": "2026-04-01T10:00:00Z",
                    "escalated_at": None,
                },
                {
                    "claim_status": "soft_hold_verification",
                    "assignment_state": "assigned",
                    "review_due_at": "2099-01-01T10:00:00Z",
                    "escalated_at": None,
                },
                {
                    "claim_status": "fraud_escalated_review",
                    "assignment_state": "escalated",
                    "review_due_at": "2099-01-02T10:00:00Z",
                    "escalated_at": "2026-04-09T09:00:00Z",
                },
            ],
            "payout_requests": [
                {"status": "failed"},
                {"status": "manual_review"},
                {"status": "settled"},
            ],
        }

    def table(self, name: str):
        if name not in self.tables:
            raise AssertionError(f"Unexpected table requested: {name}")
        return _FakeTable(self.tables[name])


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(ops.router)
    app.state.redis_cache_ready = True
    app.state.outbox_worker_running = True
    app.state.kafka_consumer_running = False
    app.state.outbox_last_batch = {"processed": 3}
    app.state.outbox_last_batch_at = 1234567890

    async def _mock_admin():
        return {"id": "admin-1", "role": "insurer_admin"}

    app.dependency_overrides[require_insurer_admin] = _mock_admin
    return TestClient(app)


class TestOpsRouter:
    def test_get_ops_status(self):
        sb = _FakeSupabase()
        with patch("backend.app.routers.ops.get_supabase_admin", return_value=sb), patch(
            "backend.app.routers.ops.get_outbox_status_counts",
            new=AsyncMock(return_value={
                "pending": 4,
                "failed": 2,
                "processed": 10,
                "dead_letter": 1,
                "total": 17,
            }),
        ), patch(
            "backend.app.routers.ops.get_consumer_ledger_status_counts",
            return_value={
                "processing": 1,
                "succeeded": 20,
                "failed": 2,
                "dead_letter": 3,
                "total": 26,
            },
        ):
            with _build_client() as client:
                resp = client.get("/ops/status")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "ok"
        assert payload["event_bus"]["outbox"]["dead_letter"] == 1
        assert payload["event_bus"]["consumer_ledger"]["dead_letter"] == 3
        assert payload["review_queue"]["open_claims"] == 3
        assert payload["review_queue"]["unassigned"] == 1
        assert payload["review_queue"]["overdue"] >= 1
        assert payload["payouts"]["failed"] == 1
        assert payload["payouts"]["manual_review"] == 1
        assert payload["alert_signals"]["review_unassigned"] == 1
        assert payload["slo"]["status"] in {"ok", "breach"}
        assert "thresholds" in payload["slo"]
        assert "observed" in payload["slo"]

    def test_get_ops_metrics(self):
        fake_snapshot = {
            "generated_at": "2026-04-09T12:00:00Z",
            "uptime_seconds": 10,
            "counters": [{"name": "x", "labels": {}, "value": 1}],
            "gauges": [],
            "timers": [],
        }
        with patch("backend.app.routers.ops.get_metrics_snapshot", return_value=fake_snapshot):
            with _build_client() as client:
                resp = client.get("/ops/metrics")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "ok"
        assert payload["metrics"] == fake_snapshot

    def test_get_version_governance_snapshot(self):
        fake_snapshot = {
            "active_selection": {
                "rule_version": {"key": "ruleset_2026_04_12"},
                "model_version": {"key": "fraud_model_heuristic_v1"},
            },
            "rule_versions": [{"id": "rule-1", "version_key": "ruleset_2026_04_12"}],
            "model_versions": [{"id": "model-1", "version_key": "fraud_model_heuristic_v1"}],
        }

        with patch("backend.app.routers.ops.get_supabase_admin", return_value=_FakeSupabase()), patch(
            "backend.app.routers.ops.get_version_registry_snapshot",
            return_value=fake_snapshot,
        ):
            with _build_client() as client:
                resp = client.get("/ops/version-governance")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "ok"
        assert payload["active_selection"]["rule_version"]["key"] == "ruleset_2026_04_12"

    def test_activate_version_governance_rollout_bad_request(self):
        with patch("backend.app.routers.ops.get_supabase_admin", return_value=_FakeSupabase()), patch(
            "backend.app.routers.ops.apply_version_rollout",
            side_effect=ValueError("cohort_key is required when mode='cohort'"),
        ):
            with _build_client() as client:
                resp = client.post(
                    "/ops/version-governance/activate",
                    json={
                        "kind": "rule",
                        "version_id": "rule-123",
                        "mode": "cohort",
                    },
                )

        assert resp.status_code == 400
        assert "cohort_key is required" in resp.json()["detail"]

    def test_get_ops_slo_status(self):
        sb = _FakeSupabase()
        with patch("backend.app.routers.ops.get_supabase_admin", return_value=sb), patch(
            "backend.app.routers.ops.get_outbox_status_counts",
            new=AsyncMock(return_value={
                "pending": 4,
                "failed": 2,
                "processed": 10,
                "dead_letter": 1,
                "total": 17,
            }),
        ), patch(
            "backend.app.routers.ops.get_consumer_ledger_status_counts",
            return_value={
                "processing": 1,
                "succeeded": 20,
                "failed": 2,
                "dead_letter": 3,
                "total": 26,
            },
        ):
            with _build_client() as client:
                resp = client.get("/ops/slo")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "ok"
        assert "slo" in payload
        assert payload["slo"]["status"] in {"ok", "breach"}
        assert "thresholds" in payload["slo"]
        assert "observed" in payload["slo"]
