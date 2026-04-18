"""
API and unit tests for the policies router.

Covers:
- Quote response integrity (including plan uplift factor)
- Policy activation persistence payload alignment with DB schema
- Explicit failure behavior when policy storage is unavailable
"""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.dependencies import require_worker
from backend.app.routers import policies


class _WorkerProfilesTable:
    def __init__(self, row: dict):
        self._row = row

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return SimpleNamespace(data=self._row)


class _PoliciesTable:
    def __init__(self, *, fail_on_upsert: bool = False):
        self.fail_on_upsert = fail_on_upsert
        self.last_row = None
        self.last_on_conflict = None

    def upsert(self, row: dict, on_conflict: str | None = None):
        if self.fail_on_upsert:
            raise RuntimeError("policies table unavailable")
        self.last_row = row
        self.last_on_conflict = on_conflict
        return self

    def execute(self):
        return SimpleNamespace(data=[self.last_row] if self.last_row else [])


class _FakeSupabase:
    def __init__(self, worker_row: dict, policies_table: _PoliciesTable):
        self.worker_table = _WorkerProfilesTable(worker_row)
        self.policies_table = policies_table

    def table(self, name: str):
        if name == "worker_profiles":
            return self.worker_table
        if name == "policies":
            return self.policies_table
        raise AssertionError(f"Unexpected table requested: {name}")


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(policies.router)

    async def _mock_worker():
        return {"id": "worker-1", "role": "worker"}

    app.dependency_overrides[require_worker] = _mock_worker
    return TestClient(app)


class TestPoliciesRouter:
    def test_quote_includes_plan_uplift_factor(self):
        worker_row = {
            "profile_id": "worker-1",
            "avg_hourly_income_inr": 125,
            "trust_score": 0.82,
            "bank_verified": True,
        }
        sb = _FakeSupabase(worker_row, _PoliciesTable())

        async def _run_quote():
            with patch("backend.app.routers.policies.get_supabase_admin", return_value=sb):
                # Use the undecorated handler body to avoid FastAPI cache init requirements.
                return await policies.get_premium_quote.__wrapped__(
                    plan="plus",
                    user={"id": "worker-1", "role": "worker"},
                )

        payload = asyncio.run(_run_quote())
        assert payload["plan"] == "plus"
        assert payload["weekly_premium_inr"] >= 30
        assert payload["weekly_premium_inr"] <= 96
        assert payload["plan_uplift_factor"] == 1.5

    def test_activate_policy_persists_schema_aligned_row(self):
        worker_row = {
            "profile_id": "worker-1",
            "preferred_zone_id": "zone-abc",
        }
        policies_table = _PoliciesTable()
        sb = _FakeSupabase(worker_row, policies_table)

        with patch("backend.app.routers.policies.get_supabase_admin", return_value=sb):
            with _build_client() as client:
                resp = client.post("/policies/activate", json={"plan": "plus"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["plan"] == "plus"
        assert body["weekly_benefit_w"] == 4500
        assert body["weekly_premium_inr"] >= 30
        assert body["weekly_premium_inr"] <= 96
        assert body["zone_id"] == "zone-abc"

        assert policies_table.last_on_conflict == "policy_id"
        assert policies_table.last_row is not None
        assert policies_table.last_row["worker_profile_id"] == "worker-1"
        assert policies_table.last_row["plan_type"] == "plus"
        assert policies_table.last_row["coverage_amount"] == 4500.0
        assert policies_table.last_row["premium_amount"] == body["weekly_premium_inr"]
        assert policies_table.last_row["status"] == "active"

    def test_activate_policy_returns_503_when_storage_unavailable(self):
        worker_row = {
            "profile_id": "worker-1",
            "preferred_zone_id": "zone-abc",
        }
        sb = _FakeSupabase(worker_row, _PoliciesTable(fail_on_upsert=True))

        with patch("backend.app.routers.policies.get_supabase_admin", return_value=sb):
            with _build_client() as client:
                resp = client.post("/policies/activate", json={"plan": "essential"})

        assert resp.status_code == 503
        assert "Policy storage unavailable" in resp.json()["detail"]
