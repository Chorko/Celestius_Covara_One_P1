"""
Tests for outbox operational helper functions.
"""

import asyncio
import sys
import os
from copy import deepcopy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.event_bus.outbox import (
    get_outbox_status_counts,
    list_dead_letter_outbox_events,
    requeue_dead_letter_outbox_events,
)


class _Resp:
    def __init__(self, data=None):
        self.data = data


class _Table:
    def __init__(self, name: str, state: dict):
        self.name = name
        self.state = state
        self._filters = []
        self._limit = None
        self._order = None
        self._desc = False
        self._update_payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        return self

    def order(self, field, desc=False):
        self._order = field
        self._desc = desc
        return self

    def limit(self, value):
        self._limit = value
        return self

    def update(self, payload):
        self._update_payload = payload
        return self

    def _rows(self):
        rows = self.state.setdefault(self.name, [])
        result = rows
        for field, value in self._filters:
            result = [row for row in result if row.get(field) == value]
        if self._order:
            result = sorted(
                result,
                key=lambda row: row.get(self._order) or "",
                reverse=self._desc,
            )
        if self._limit is not None:
            result = result[: self._limit]
        return result

    def execute(self):
        if self._update_payload is not None:
            matched = self._rows()
            for row in matched:
                row.update(deepcopy(self._update_payload))
            return _Resp(matched)

        return _Resp(self._rows())


class _SB:
    def __init__(self, state):
        self.state = state

    def table(self, name: str):
        return _Table(name, self.state)


class TestEventOutboxOps:
    def test_get_outbox_status_counts(self):
        sb = _SB(
            {
                "event_outbox": [
                    {"event_id": "1", "status": "pending"},
                    {"event_id": "2", "status": "pending"},
                    {"event_id": "3", "status": "processed"},
                    {"event_id": "4", "status": "failed"},
                    {"event_id": "5", "status": "dead_letter"},
                ]
            }
        )

        counts = asyncio.run(get_outbox_status_counts(sb))

        assert counts["pending"] == 2
        assert counts["processed"] == 1
        assert counts["failed"] == 1
        assert counts["dead_letter"] == 1
        assert counts["total"] == 5

    def test_list_dead_letter_outbox_events(self):
        sb = _SB(
            {
                "event_outbox": [
                    {
                        "event_id": "older",
                        "status": "dead_letter",
                        "dead_lettered_at": "2026-04-05T09:00:00+00:00",
                    },
                    {
                        "event_id": "newer",
                        "status": "dead_letter",
                        "dead_lettered_at": "2026-04-05T10:00:00+00:00",
                    },
                    {
                        "event_id": "failed-only",
                        "status": "failed",
                        "dead_lettered_at": None,
                    },
                ]
            }
        )

        rows = asyncio.run(list_dead_letter_outbox_events(sb, limit=10))

        assert len(rows) == 2
        assert rows[0]["event_id"] == "newer"
        assert rows[1]["event_id"] == "older"

    def test_requeue_dead_letter_outbox_events(self):
        state = {
            "event_outbox": [
                {
                    "event_id": "oldest",
                    "status": "dead_letter",
                    "retry_count": 10,
                    "last_error": "boom",
                    "dead_lettered_at": "2026-04-05T08:00:00+00:00",
                },
                {
                    "event_id": "newest",
                    "status": "dead_letter",
                    "retry_count": 11,
                    "last_error": "boom2",
                    "dead_lettered_at": "2026-04-05T09:00:00+00:00",
                },
            ]
        }
        sb = _SB(state)

        result = asyncio.run(requeue_dead_letter_outbox_events(sb, limit=1))

        assert result["selected"] == 1
        assert result["requeued"] == 1

        oldest = next(row for row in state["event_outbox"] if row["event_id"] == "oldest")
        newest = next(row for row in state["event_outbox"] if row["event_id"] == "newest")

        assert oldest["status"] == "pending"
        assert oldest["retry_count"] == 0
        assert oldest["last_error"] is None
        assert oldest["dead_lettered_at"] is None

        # Limit=1 should leave the newer row untouched.
        assert newest["status"] == "dead_letter"
