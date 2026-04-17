"""Unit tests for trust score lifecycle service."""

import os
import sys
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.trust_service import (
    apply_trust_score_delta,
    list_worker_trust_history,
)


class _FakeTable:
    def __init__(self, store: "_FakeSupabase", name: str):
        self.store = store
        self.name = name
        self._action = "select"
        self._payload: Any = None
        self._filters: list[tuple[str, object]] = []
        self._maybe_single = False
        self._limit: int | None = None
        self._order_field: str | None = None
        self._order_desc = False

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

    def update(self, payload: dict):
        self._action = "update"
        self._payload = payload
        return self

    def insert(self, payload: dict | list[dict]):
        self._action = "insert"
        self._payload = payload
        return self

    def _filtered_rows(self) -> list[dict]:
        rows = self.store.tables[self.name]
        out: list[dict] = []
        for row in rows:
            if any(row.get(key) != value for key, value in self._filters):
                continue
            out.append(row)
        return out

    def execute(self):
        rows = self._filtered_rows()

        if self._action == "select":
            data = [dict(r) for r in rows]
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

        if self._action == "update":
            updated: list[dict] = []
            for row in rows:
                row.update(self._payload or {})
                updated.append(dict(row))
            return SimpleNamespace(data=updated)

        if self._action == "insert":
            payload = self._payload
            entries = payload if isinstance(payload, list) else [payload]
            inserted: list[dict] = []
            for entry in entries:
                record = dict(entry)
                if "id" not in record:
                    record["id"] = f"{self.name}-{len(self.store.tables[self.name]) + 1}"
                self.store.tables[self.name].append(record)
                inserted.append(dict(record))
            if self._maybe_single:
                return SimpleNamespace(data=inserted[0] if inserted else None)
            return SimpleNamespace(data=inserted)

        raise AssertionError(f"Unsupported action {self._action}")


class _FakeSupabase:
    def __init__(self):
        self.tables = {
            "worker_profiles": [
                {
                    "profile_id": "worker-1",
                    "trust_score": 0.75,
                }
            ],
            "trust_score_history": [],
        }

    def table(self, name: str):
        if name not in self.tables:
            raise AssertionError(f"Unexpected table requested: {name}")
        return _FakeTable(self, name)


def test_apply_trust_score_delta_updates_worker_and_history():
    sb = _FakeSupabase()

    result = apply_trust_score_delta(
        sb,
        worker_profile_id="worker-1",
        delta=-0.15,
        event_type="post_approval_flag",
        claim_id="claim-1",
        severity="moderate",
        reason="Suspicious replay",
        actor_profile_id="admin-1",
        metadata={"request_id": "req-1"},
    )

    assert result["worker_profile_id"] == "worker-1"
    assert result["previous_trust_score"] == 0.75
    assert result["new_trust_score"] == 0.6

    worker_row = sb.tables["worker_profiles"][0]
    assert worker_row["trust_score"] == 0.6

    assert len(sb.tables["trust_score_history"]) == 1
    hist = sb.tables["trust_score_history"][0]
    assert hist["event_type"] == "post_approval_flag"
    assert hist["claim_id"] == "claim-1"
    assert hist["previous_trust_score"] == 0.75
    assert hist["delta"] == -0.15
    assert hist["new_trust_score"] == 0.6


def test_apply_trust_score_delta_clamps_to_zero_floor():
    sb = _FakeSupabase()
    sb.tables["worker_profiles"][0]["trust_score"] = 0.1

    result = apply_trust_score_delta(
        sb,
        worker_profile_id="worker-1",
        delta=-0.9,
        event_type="post_approval_flag",
    )

    assert result["previous_trust_score"] == 0.1
    assert result["new_trust_score"] == 0.0
    assert sb.tables["worker_profiles"][0]["trust_score"] == 0.0


def test_list_worker_trust_history_returns_newest_first():
    sb = _FakeSupabase()
    sb.tables["trust_score_history"] = [
        {
            "id": "h1",
            "worker_profile_id": "worker-1",
            "created_at": "2026-04-12T10:00:00Z",
            "new_trust_score": 0.71,
        },
        {
            "id": "h2",
            "worker_profile_id": "worker-1",
            "created_at": "2026-04-13T10:00:00Z",
            "new_trust_score": 0.66,
        },
    ]

    rows = list_worker_trust_history(sb, worker_profile_id="worker-1", limit=10)

    assert [row["id"] for row in rows] == ["h2", "h1"]
