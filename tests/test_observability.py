"""Focused unit tests for observability primitives."""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.observability import (
    bind_request_id,
    export_metrics_prometheus,
    get_metrics_snapshot,
    get_request_id,
    increment_counter,
    observe_timing_ms,
    resolve_request_id,
    reset_metrics_for_tests,
    set_gauge,
    track_slo_breach_age_seconds,
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

    def test_prometheus_export_renders_counter_gauge_and_timer_rows(self):
        increment_counter("claims_total", labels={"outcome": "created"})
        set_gauge("outbox_dead_letter", 4)
        observe_timing_ms("http_request_latency_ms", 50.0, labels={"path": "/ops/status"})

        snapshot = get_metrics_snapshot()
        prometheus = export_metrics_prometheus(snapshot)

        assert "# TYPE claims_total counter" in prometheus
        assert 'claims_total{outcome="created"} 1' in prometheus
        assert "# TYPE outbox_dead_letter gauge" in prometheus
        assert "outbox_dead_letter 4.0" in prometheus
        assert "# TYPE http_request_latency_ms_count counter" in prometheus
        assert 'http_request_latency_ms_count{path="/ops/status"} 1' in prometheus

    def test_track_slo_breach_age_is_monotonic_and_resets_when_cleared(self):
        with patch(
            "backend.app.services.observability.time.monotonic",
            side_effect=[100.0, 108.6, 109.0],
        ):
            first_age = track_slo_breach_age_seconds("outbox_dead_letter", True)
            second_age = track_slo_breach_age_seconds("outbox_dead_letter", True)
            cleared_age = track_slo_breach_age_seconds("outbox_dead_letter", False)

        assert first_age == 0
        assert second_age == 8
        assert cleared_age is None

        with patch(
            "backend.app.services.observability.time.monotonic",
            return_value=200.0,
        ):
            restarted_age = track_slo_breach_age_seconds("outbox_dead_letter", True)

        assert restarted_age == 0
