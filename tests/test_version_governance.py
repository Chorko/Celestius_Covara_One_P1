"""Unit tests for rule/model version governance helpers."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.version_governance import (
    apply_version_rollout,
    resolve_decision_versions,
)


class _FakeTable:
    def __init__(self, store: "_FakeSupabase", name: str):
        self.store = store
        self.name = name
        self._action = "select"
        self._payload = None
        self._filters: list[tuple[str, object]] = []
        self._in_filters: list[tuple[str, set[object]]] = []
        self._orders: list[tuple[str, bool]] = []
        self._maybe_single = False

    def select(self, *_args, **_kwargs):
        self._action = "select"
        return self

    def eq(self, key: str, value):
        self._filters.append((key, value))
        return self

    def in_(self, key: str, values):
        self._in_filters.append((key, set(values)))
        return self

    def order(self, key: str, desc: bool = False):
        self._orders.append((key, bool(desc)))
        return self

    def maybe_single(self):
        self._maybe_single = True
        return self

    def update(self, payload: dict):
        self._action = "update"
        self._payload = payload
        return self

    def _row_matches(self, row: dict) -> bool:
        if any(row.get(key) != value for key, value in self._filters):
            return False
        for key, values in self._in_filters:
            if row.get(key) not in values:
                return False
        return True

    def _filtered_rows(self) -> list[dict]:
        rows = self.store.tables[self.name]
        return [row for row in rows if self._row_matches(row)]

    def execute(self):
        if self._action == "select":
            rows = [dict(row) for row in self._filtered_rows()]
            # Stable multi-sort: apply in reverse order of requested sorts.
            for key, desc in reversed(self._orders):
                rows.sort(key=lambda row: str(row.get(key) or ""), reverse=desc)
            if self._maybe_single:
                return SimpleNamespace(data=rows[0] if rows else None)
            return SimpleNamespace(data=rows)

        if self._action == "update":
            updated = []
            for row in self.store.tables[self.name]:
                if not self._row_matches(row):
                    continue
                row.update(self._payload or {})
                updated.append(dict(row))
            return SimpleNamespace(data=updated)

        raise AssertionError(f"Unsupported action {self._action}")


class _FakeSupabase:
    def __init__(self, *, rule_rows: list[dict] | None = None, model_rows: list[dict] | None = None):
        self.tables = {
            "rule_versions": rule_rows or [],
            "model_versions": model_rows or [],
        }

    def table(self, name: str):
        if name not in self.tables:
            raise AssertionError(f"Unexpected table requested: {name}")
        return _FakeTable(self, name)


def test_resolve_decision_versions_falls_back_without_registry_rows():
    sb = _FakeSupabase(rule_rows=[], model_rows=[])

    result = resolve_decision_versions(sb, worker_profile_id="worker-001")

    assert result["rule_version"]["selection_source"] == "fallback"
    assert result["model_version"]["selection_source"] == "fallback"
    assert result["rule_version"]["key"]
    assert result["model_version"]["key"]


def test_resolve_decision_versions_selects_canary_when_percentage_is_100():
    sb = _FakeSupabase(
        rule_rows=[
            {
                "id": "rule-full",
                "version_key": "ruleset-base",
                "status": "active",
                "rollout_mode": "full",
                "rollout_percentage": 100,
                "cohort_key": None,
                "cohort_salt": "rule-salt",
                "priority": 1,
                "is_active": True,
            },
            {
                "id": "rule-canary",
                "version_key": "ruleset-canary",
                "status": "canary",
                "rollout_mode": "canary",
                "rollout_percentage": 100,
                "cohort_key": None,
                "cohort_salt": "rule-salt",
                "priority": 5,
                "is_active": True,
            },
        ],
        model_rows=[
            {
                "id": "model-full",
                "version_key": "fraud-model-base",
                "status": "active",
                "rollout_mode": "full",
                "rollout_percentage": 100,
                "cohort_key": None,
                "cohort_salt": "model-salt",
                "priority": 1,
                "is_active": True,
            },
            {
                "id": "model-canary",
                "version_key": "fraud-model-canary",
                "status": "canary",
                "rollout_mode": "canary",
                "rollout_percentage": 100,
                "cohort_key": None,
                "cohort_salt": "model-salt",
                "priority": 5,
                "is_active": True,
            },
        ],
    )

    result = resolve_decision_versions(sb, worker_profile_id="worker-019")

    assert result["rule_version"]["id"] == "rule-canary"
    assert result["model_version"]["id"] == "model-canary"


def test_apply_version_rollout_sets_single_active_target():
    sb = _FakeSupabase(
        rule_rows=[
            {
                "id": "rule-a",
                "version_key": "ruleset-a",
                "status": "active",
                "rollout_mode": "full",
                "rollout_percentage": 100,
                "cohort_key": None,
                "is_active": True,
            },
            {
                "id": "rule-b",
                "version_key": "ruleset-b",
                "status": "draft",
                "rollout_mode": "full",
                "rollout_percentage": 100,
                "cohort_key": None,
                "is_active": False,
            },
        ],
        model_rows=[],
    )

    result = apply_version_rollout(
        sb,
        kind="rule",
        version_id="rule-b",
        mode="canary",
        rollout_percentage=25,
    )

    assert result["version_id"] == "rule-b"
    assert result["is_active"] is True
    assert result["status"] == "canary"
    assert result["rollout_mode"] == "canary"
    assert result["rollout_percentage"] == 25

    rows = sb.tables["rule_versions"]
    row_a = next(row for row in rows if row["id"] == "rule-a")
    row_b = next(row for row in rows if row["id"] == "rule-b")
    assert row_a["is_active"] is False
    assert row_b["is_active"] is True
