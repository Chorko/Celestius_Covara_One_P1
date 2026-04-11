"""Covara One - Lightweight observability primitives.

Provides:
- request/correlation id helpers
- structured logging helper
- in-memory metrics registry (counters, gauges, timers)

Intentionally lightweight for local/staging visibility without requiring
external telemetry infrastructure.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


_REQUEST_ID_CTX: ContextVar[str | None] = ContextVar("covara_request_id", default=None)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _labels_key(labels: dict[str, Any] | None) -> str:
    if not labels:
        return ""

    normalized = []
    for key in sorted(labels.keys()):
        value = labels[key]
        normalized.append(f"{key}={value}")
    return "|".join(normalized)


def _labels_from_key(encoded: str) -> dict[str, str]:
    if not encoded:
        return {}

    labels: dict[str, str] = {}
    parts = encoded.split("|")
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        labels[key] = value
    return labels


def resolve_request_id(
    incoming_request_id: str | None,
    incoming_correlation_id: str | None = None,
) -> str:
    """Resolve canonical request id from incoming headers or generate one."""
    candidate = (incoming_request_id or incoming_correlation_id or "").strip()
    return candidate if candidate else str(uuid4())


def bind_request_id(request_id: str) -> Token[str | None]:
    """Bind request id into context var for downstream helpers."""
    return _REQUEST_ID_CTX.set(request_id)


def unbind_request_id(token: Token[str | None]) -> None:
    _REQUEST_ID_CTX.reset(token)


def get_request_id() -> str | None:
    return _REQUEST_ID_CTX.get()


def structured_log(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit a structured JSON log entry with optional request correlation."""
    payload = {
        "ts": _utc_now_iso(),
        "event": event,
    }

    request_id = fields.pop("request_id", None) or get_request_id()
    if request_id:
        payload["request_id"] = request_id

    for key, value in fields.items():
        if value is not None:
            payload[key] = value

    logger.log(level, json.dumps(payload, sort_keys=True, default=str))


@dataclass
class _TimerAggregate:
    count: int = 0
    sum_ms: float = 0.0
    max_ms: float = 0.0


class InMemoryMetrics:
    """Thread-safe in-memory metrics registry for baseline ops visibility."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, dict[str, int]] = {}
        self._gauges: dict[str, dict[str, float]] = {}
        self._timers: dict[str, dict[str, _TimerAggregate]] = {}

    def increment(
        self,
        name: str,
        amount: int = 1,
        labels: dict[str, Any] | None = None,
    ) -> None:
        encoded = _labels_key(labels)
        with self._lock:
            metric = self._counters.setdefault(name, {})
            metric[encoded] = metric.get(encoded, 0) + int(amount)

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, Any] | None = None,
    ) -> None:
        encoded = _labels_key(labels)
        with self._lock:
            metric = self._gauges.setdefault(name, {})
            metric[encoded] = float(value)

    def observe_timing_ms(
        self,
        name: str,
        value_ms: float,
        labels: dict[str, Any] | None = None,
    ) -> None:
        encoded = _labels_key(labels)
        with self._lock:
            metric = self._timers.setdefault(name, {})
            bucket = metric.setdefault(encoded, _TimerAggregate())
            bucket.count += 1
            bucket.sum_ms += float(value_ms)
            bucket.max_ms = max(bucket.max_ms, float(value_ms))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = [
                {
                    "name": name,
                    "labels": _labels_from_key(encoded),
                    "value": value,
                }
                for name, rows in self._counters.items()
                for encoded, value in rows.items()
            ]
            gauges = [
                {
                    "name": name,
                    "labels": _labels_from_key(encoded),
                    "value": value,
                }
                for name, rows in self._gauges.items()
                for encoded, value in rows.items()
            ]
            timers = [
                {
                    "name": name,
                    "labels": _labels_from_key(encoded),
                    "count": agg.count,
                    "sum_ms": round(agg.sum_ms, 4),
                    "avg_ms": round((agg.sum_ms / agg.count), 4) if agg.count else 0.0,
                    "max_ms": round(agg.max_ms, 4),
                }
                for name, rows in self._timers.items()
                for encoded, agg in rows.items()
            ]

        return {
            "generated_at": _utc_now_iso(),
            "uptime_seconds": round(time.monotonic(), 2),
            "counters": counters,
            "gauges": gauges,
            "timers": timers,
        }

    def reset(self) -> None:
        with self._lock:
            self._counters = {}
            self._gauges = {}
            self._timers = {}


_METRICS = InMemoryMetrics()


def increment_counter(name: str, amount: int = 1, labels: dict[str, Any] | None = None) -> None:
    _METRICS.increment(name=name, amount=amount, labels=labels)


def set_gauge(name: str, value: float, labels: dict[str, Any] | None = None) -> None:
    _METRICS.set_gauge(name=name, value=value, labels=labels)


def observe_timing_ms(name: str, value_ms: float, labels: dict[str, Any] | None = None) -> None:
    _METRICS.observe_timing_ms(name=name, value_ms=value_ms, labels=labels)


def get_metrics_snapshot() -> dict[str, Any]:
    return _METRICS.snapshot()


def reset_metrics_for_tests() -> None:
    _METRICS.reset()
