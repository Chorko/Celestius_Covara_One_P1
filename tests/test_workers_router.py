"""API tests for workers trust-history endpoints."""

import os
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.dependencies import require_insurer_admin, require_worker
from backend.app.routers import workers


class _FakeTable:
    def __init__(self, store: "_FakeSupabase", name: str):
        self.store = store
        self.name = name
        self._action = "select"
        self._filters: list[tuple[str, object]] = []
        self._maybe_single = False
        self._order_field: str | None = None
        self._order_desc = False
        self._limit: int | None = None

    def select(self, *_args, **_kwargs):
        self._action = "select"
        return self

    def eq(self, key: str, value):
        self._filters.append((key, value))
        return self

    def maybe_single(self):
        self._maybe_single = True
        return self

    def order(self, field: str, desc: bool = False):
        self._order_field = field
        self._order_desc = desc
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    def _filtered_rows(self) -> list[dict]:
        rows = self.store.tables[self.name]
        filtered: list[dict] = []
        for row in rows:
            if any(row.get(k) != v for k, v in self._filters):
                continue
            filtered.append(row)
        return filtered

    def execute(self):
        if self._action != "select":
            raise AssertionError(f"Unsupported action {self._action}")

        data = [dict(r) for r in self._filtered_rows()]
        if self._order_field:
            data.sort(
                key=lambda item: item.get(self._order_field) or "",
                reverse=self._order_desc,
            )
        if self._limit is not None:
            data = data[: self._limit]

        if self._maybe_single:
            return SimpleNamespace(data=data[0] if data else None)
        return SimpleNamespace(data=data)


class _FakeSupabase:
    def __init__(self):
        self.tables = {
            "worker_profiles": [
                {"profile_id": "worker-1", "trust_score": 0.73},
                {"profile_id": "worker-2", "trust_score": 0.88},
            ],
            "trust_score_history": [
                {
                    "id": "h-1",
                    "worker_profile_id": "worker-1",
                    "event_type": "post_approval_flag",
                    "previous_trust_score": 0.88,
                    "delta": -0.15,
                    "new_trust_score": 0.73,
                    "created_at": "2026-04-15T10:00:00Z",
                },
                {
                    "id": "h-2",
                    "worker_profile_id": "worker-1",
                    "event_type": "manual_adjustment",
                    "previous_trust_score": 0.9,
                    "delta": -0.02,
                    "new_trust_score": 0.88,
                    "created_at": "2026-04-14T10:00:00Z",
                },
            ],
        }

    def table(self, name: str):
        if name not in self.tables:
            raise AssertionError(f"Unexpected table requested: {name}")
        return _FakeTable(self, name)


def _build_client(worker_user: dict, admin_user: dict) -> TestClient:
    app = FastAPI()
    app.include_router(workers.router)

    async def _mock_worker():
        return worker_user

    async def _mock_admin():
        return admin_user

    app.dependency_overrides[require_worker] = _mock_worker
    app.dependency_overrides[require_insurer_admin] = _mock_admin
    return TestClient(app)


def test_worker_can_fetch_own_trust_history():
    sb = _FakeSupabase()

    with patch("backend.app.routers.workers.get_supabase_admin", return_value=sb):
        with _build_client(
            worker_user={"id": "worker-1", "role": "worker"},
            admin_user={"id": "admin-1", "role": "insurer_admin"},
        ) as client:
            resp = client.get("/workers/me/trust-history?limit=5")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["worker_profile_id"] == "worker-1"
    assert payload["current_trust_score"] == 0.73
    assert payload["count"] == 2
    assert payload["history"][0]["id"] == "h-1"


def test_admin_can_fetch_worker_trust_history():
    sb = _FakeSupabase()

    with patch("backend.app.routers.workers.get_supabase_admin", return_value=sb):
        with _build_client(
            worker_user={"id": "worker-1", "role": "worker"},
            admin_user={"id": "admin-1", "role": "insurer_admin"},
        ) as client:
            resp = client.get("/workers/worker-1/trust-history?limit=1")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["worker_profile_id"] == "worker-1"
    assert payload["current_trust_score"] == 0.73
    assert payload["count"] == 1
    assert payload["history"][0]["id"] == "h-1"
