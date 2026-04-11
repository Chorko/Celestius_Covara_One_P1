"""Focused unit tests for observability primitives."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.observability import (
    bind_request_id,
    get_metrics_snapshot,
    get_request_id,
    increment_counter,
    observe_timing_ms,
    resolve_request_id,
    reset_metrics_for_tests,
    set_gauge,
    unbind_request_id,
)


def _find_counter_value(snapshot: dict, name: str, labels: dict | None = None) -> int:
    labels = labels or {}
    for row in snapshot.get("counters", []):
        if row.get("name") == name and row.get("labels") == labels:
            return int(row.get("value", 0))
    return 0


class TestObservabilityPrimitives:
    def setup_method(self):
        reset_metrics_for_tests()

    def test_resolve_request_id_prefers_explicit_header(self):
        request_id = resolve_request_id("req-123", "corr-999")
        assert request_id == "req-123"

    def test_context_bind_and_unbind(self):
        assert get_request_id() is None

        token = bind_request_id("req-context-1")
        assert get_request_id() == "req-context-1"

        unbind_request_id(token)
        assert get_request_id() is None

    def test_metrics_snapshot_includes_counters_gauges_and_timers(self):
        increment_counter("claims_total", labels={"outcome": "created"})
        increment_counter("claims_total", labels={"outcome": "created"})
        set_gauge("outbox_dead_letter", 3)
        observe_timing_ms("http_request_latency_ms", 120.5, labels={"path": "/health"})

        snapshot = get_metrics_snapshot()

        assert _find_counter_value(
            snapshot,
            "claims_total",
            labels={"outcome": "created"},
        ) == 2

        gauges = snapshot.get("gauges", [])
        assert any(
            row.get("name") == "outbox_dead_letter" and row.get("value") == 3.0
            for row in gauges
        )

        timers = snapshot.get("timers", [])
        latency_rows = [
            row for row in timers
            if row.get("name") == "http_request_latency_ms"
            and row.get("labels") == {"path": "/health"}
        ]
        assert len(latency_rows) == 1
        assert latency_rows[0].get("count") == 1
        assert latency_rows[0].get("max_ms") == 120.5
