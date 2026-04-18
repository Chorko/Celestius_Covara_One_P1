"""Unit tests for policy service helpers."""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.policy_service import (
    _personalize_weekly_premium,
    expire_stale_policies_for_worker,
)


class _PoliciesTable:
    def __init__(self, *, fail_on_update: bool = False):
        self.fail_on_update = fail_on_update
        self.update_payload = None
        self.filters: list[tuple[str, object]] = []
        self.lt_filter: tuple[str, object] | None = None
        self.executed = False

    def update(self, payload: dict):
        if self.fail_on_update:
            raise RuntimeError("update failed")
        self.update_payload = payload
        return self

    def eq(self, key: str, value):
        self.filters.append((key, value))
        return self

    def lt(self, key: str, value):
        self.lt_filter = (key, value)
        return self

    def execute(self):
        self.executed = True
        return SimpleNamespace(data=[])


class _FakeSupabase:
    def __init__(self, table: _PoliciesTable):
        self._table = table

    def table(self, name: str):
        if name != "policies":
            raise AssertionError(f"Unexpected table: {name}")
        return self._table


class TestPolicyService:
    def test_expire_stale_policies_updates_active_rows(self):
        table = _PoliciesTable()
        sb = _FakeSupabase(table)

        expire_stale_policies_for_worker(sb, "worker-123")

        assert table.executed is True
        assert table.update_payload is not None
        assert table.update_payload["status"] == "expired"
        assert ("worker_profile_id", "worker-123") in table.filters
        assert ("status", "active") in table.filters
        assert table.lt_filter is not None
        assert table.lt_filter[0] == "valid_until"

    def test_expire_stale_policies_is_non_blocking_on_errors(self):
        table = _PoliciesTable(fail_on_update=True)
        sb = _FakeSupabase(table)

        expire_stale_policies_for_worker(sb, "worker-123")

        # No exception should be raised for quote/activation callers.
        assert table.executed is False

    def test_personalized_premium_is_deterministic_per_worker(self):
        worker_id = "7f18266c-e1ff-454e-89ba-88c1642cd781"
        value_1 = _personalize_weekly_premium(18.0, worker_id, "essential")
        value_2 = _personalize_weekly_premium(18.0, worker_id, "essential")

        assert value_1 == value_2
        assert value_1 >= 18.0
        assert value_1 <= 72.0

    def test_personalized_premium_spreads_floor_workers(self):
        worker_a = "7f18266c-e1ff-454e-89ba-88c1642cd781"
        worker_b = "5bc3eb9f-7c4d-4baa-8057-9d73cfafdd8d"

        premium_a = _personalize_weekly_premium(18.0, worker_a, "essential")
        premium_b = _personalize_weekly_premium(18.0, worker_b, "essential")

        assert premium_a != premium_b
