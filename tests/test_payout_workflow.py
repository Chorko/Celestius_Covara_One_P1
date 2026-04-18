"""Focused tests for payout initiation and settlement workflow hardening."""

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.payout_provider import PayoutProviderResponse
from backend.app.services.observability import (
    get_metrics_snapshot,
    reset_metrics_for_tests,
)
from backend.app.services.payout_workflow import (
    _insert_transition,
    _insert_settlement_event_row,
    _update_payout_request_row,
    _update_settlement_event_row,
    get_payout_trace_for_claim,
    ingest_settlement_webhook,
    initiate_payout_for_claim,
)


class _FakeTable:
    def __init__(self, store: "_FakeSupabase", name: str):
        self.store = store
        self.name = name
        self._action = "select"
        self._payload: Any = None
        self._filters: list[tuple[str, object]] = []
        self._maybe_single = False

    def select(self, *_args, **_kwargs):
        self._action = "select"
        return self

    def eq(self, key: str, value):
        self._filters.append((key, value))
        return self

    def maybe_single(self):
        self._maybe_single = True
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def update(self, payload: dict):
        self._action = "update"
        self._payload = payload
        return self

    def insert(self, payload):
        self._action = "insert"
        self._payload = payload
        return self

    def _filtered_rows(self) -> list[dict]:
        rows = self.store.tables[self.name]
        filtered = []
        for row in rows:
            if any(row.get(k) != v for k, v in self._filters):
                continue
            filtered.append(row)
        return filtered

    def execute(self):
        rows = self._filtered_rows()

        if self._action == "select":
            data = [dict(r) for r in rows]
            if self._maybe_single:
                return SimpleNamespace(data=data[0] if data else None)
            return SimpleNamespace(data=data)

        if self._action == "update":
            updated = []
            for row in rows:
                if (
                    self.name == "payout_requests"
                    and self.store.legacy_payout_status_check
                    and isinstance(self._payload, dict)
                    and self._payload.get("status") == "settled"
                ):
                    raise Exception(
                        'new row for relation "payout_requests" violates check constraint "payout_requests_status_check"'
                    )
                row.update(self._payload or {})
                updated.append(dict(row))
            return SimpleNamespace(data=updated)

        if self._action == "insert":
            payload = self._payload
            if isinstance(payload, list):
                inserted = payload
            elif isinstance(payload, dict):
                inserted = [payload]
            else:
                raise AssertionError("Insert payload must be dict or list[dict]")

            table = self.store.tables[self.name]
            out = []
            for item in inserted:
                if not isinstance(item, dict):
                    raise AssertionError("Insert list items must be dict")

                if self.name == "payout_settlement_events":
                    if (
                        self.store.settlement_requires_payout_request_id
                        and not item.get("payout_request_id")
                    ):
                        raise Exception(
                            'null value in column "payout_request_id" of relation "payout_settlement_events" violates not-null constraint'
                        )
                    for existing in table:
                        if (
                            existing.get("provider_key") == item.get("provider_key")
                            and existing.get("provider_event_id")
                            == item.get("provider_event_id")
                        ):
                            raise Exception(
                                "duplicate key value violates unique constraint provider_event_id"
                            )

                record = dict(item)
                if "id" not in record or record["id"] is None:
                    record["id"] = f"{self.name}-{len(table) + 1}"
                table.append(record)
                out.append(dict(record))

            if self._maybe_single:
                return SimpleNamespace(data=out[0] if out else None)
            return SimpleNamespace(data=out)

        raise AssertionError(f"Unsupported action {self._action}")


class _FakeSupabase:
    def __init__(
        self,
        *,
        claim_status: str = "approved",
        bank_verified: bool = True,
        settlement_requires_payout_request_id: bool = False,
        legacy_payout_status_check: bool = False,
    ):
        self.settlement_requires_payout_request_id = settlement_requires_payout_request_id
        self.legacy_payout_status_check = legacy_payout_status_check
        self.tables = {
            "manual_claims": [
                {
                    "id": "claim-1",
                    "worker_profile_id": "worker-1",
                    "claim_status": claim_status,
                    "rule_version_id": "rule-v1",
                    "model_version_id": "model-v1",
                }
            ],
            "payout_recommendations": [
                {
                    "id": "payout-rec-1",
                    "claim_id": "claim-1",
                    "recommended_payout": 1250.0,
                    "explanation_json": {
                        "fraud_analysis": {
                            "fraud_band": "medium",
                            "device_trust": {
                                "device_trust_tier": "medium",
                                "signal_confidence": "high",
                                "attestation_verdict": "passed",
                                "risk_signals": ["none"],
                            },
                        }
                    },
                }
            ],
            "worker_profiles": [
                {
                    "profile_id": "worker-1",
                    "bank_verified": bank_verified,
                    "phone_number": "+911234567890",
                }
            ],
            "payout_requests": [],
            "payout_settlement_events": [],
            "payout_status_transitions": [],
            "audit_events": [],
            "event_outbox": [],
            "rule_versions": [{"id": "rule-v1", "version_key": "ruleset_2026_04_12"}],
            "model_versions": [{"id": "model-v1", "version_key": "fraud_model_heuristic_v1"}],
        }

    def table(self, name: str):
        if name not in self.tables:
            raise AssertionError(f"Unexpected table: {name}")
        return _FakeTable(self, name)


class _StubProvider:
    def __init__(
        self,
        *,
        provider_key: str = "simulated_gateway",
        init_status: str = "pending",
        signature_valid: bool = True,
    ):
        self.provider_key = provider_key
        self.init_status = init_status
        self.signature_valid = signature_valid

    async def initiate_payout(self, _command):
        return PayoutProviderResponse(
            provider_key=self.provider_key,
            provider_reference_id="provider-ref-1",
            status=self.init_status,
            accepted=self.init_status not in {"failed", "manual_review"},
            raw_status=self.init_status,
            failure_code="provider_failed" if self.init_status == "failed" else None,
            failure_reason="provider failed" if self.init_status == "failed" else None,
            metadata={"stub": True},
        )

    def verify_webhook_signature(self, _payload: bytes, _signature_header: str | None) -> bool:
        return self.signature_valid


def _counter_value(snapshot: dict, name: str, labels: dict | None = None) -> int:
    labels = labels or {}
    for row in snapshot.get("counters", []):
        if row.get("name") == name and row.get("labels") == labels:
            return int(row.get("value", 0))
    return 0


class TestPayoutWorkflow:
    def setup_method(self):
        reset_metrics_for_tests()

    def test_initiate_payout_creates_request_and_transitions(self):
        sb = _FakeSupabase(claim_status="approved", bank_verified=True)

        with patch(
            "backend.app.services.payout_workflow.get_payout_provider",
            return_value=_StubProvider(init_status="pending"),
        ), patch(
            "backend.app.services.payout_workflow.enqueue_domain_event",
            new=AsyncMock(return_value={"status": "processed"}),
        ):
            result = asyncio.run(
                initiate_payout_for_claim(
                    sb,
                    claim_id="claim-1",
                    initiated_by_profile_id="admin-1",
                    trigger_source="tests",
                )
            )

        assert result["status"] == "pending"
        assert result["trust_stamp"]["fraud_score_band"] == "medium"
        assert result["trust_stamp"]["device_trust_tier"] == "medium"
        assert (
            result["trust_stamp"]["version_governance"]["rule_version"]["key"]
            == "ruleset_2026_04_12"
        )
        assert len(sb.tables["payout_requests"]) == 1
        payout = sb.tables["payout_requests"][0]
        assert payout["status"] == "pending"
        assert payout["provider_key"] == "simulated_gateway"
        assert payout["provider_reference_id"] == "provider-ref-1"

        transitions = sb.tables["payout_status_transitions"]
        assert len(transitions) == 2
        assert transitions[0]["new_status"] == "initiated"
        assert transitions[1]["new_status"] == "pending"

        snapshot = get_metrics_snapshot()
        assert _counter_value(
            snapshot,
            "payout_initiation_outcome_total",
            labels={"status": "pending"},
        ) == 1

    def test_initiate_without_bank_verification_goes_manual_review(self):
        sb = _FakeSupabase(claim_status="approved", bank_verified=False)

        with patch(
            "backend.app.services.payout_workflow.enqueue_domain_event",
            new=AsyncMock(return_value={"status": "processed"}),
        ):
            result = asyncio.run(
                initiate_payout_for_claim(
                    sb,
                    claim_id="claim-1",
                    initiated_by_profile_id="admin-1",
                    trigger_source="tests",
                )
            )

        assert result["status"] == "manual_review"
        payout = sb.tables["payout_requests"][0]
        assert payout["status"] == "manual_review"
        assert payout["failure_code"] == "bank_not_verified"
        assert payout["retry_count"] == 1
        assert payout.get("next_retry_at")

    def test_webhook_rejects_invalid_signature(self):
        sb = _FakeSupabase(claim_status="approved", bank_verified=True)
        sb.tables["payout_requests"].append(
            {
                "id": "payout-1",
                "claim_id": "claim-1",
                "worker_profile_id": "worker-1",
                "provider_key": "simulated_gateway",
                "provider_reference_id": "provider-ref-1",
                "correlation_id": "corr-1",
                "idempotency_key": "idem-1",
                "status": "pending",
                "retry_count": 0,
            }
        )

        payload = {
            "event_id": "evt-1",
            "reference_id": "provider-ref-1",
            "status": "settled",
        }
        body = json.dumps(payload).encode("utf-8")

        with patch(
            "backend.app.services.payout_workflow.get_payout_provider",
            return_value=_StubProvider(signature_valid=False),
        ):
            result = asyncio.run(
                ingest_settlement_webhook(
                    sb,
                    provider_key="simulated_gateway",
                    payload_bytes=body,
                    signature_header="bad-signature",
                    source_ip="127.0.0.1",
                )
            )

        assert result["status"] == "rejected"
        assert result["signature_valid"] is False
        assert sb.tables["payout_requests"][0]["status"] == "pending"

        snapshot = get_metrics_snapshot()
        assert _counter_value(snapshot, "payout_webhook_signature_failures_total") == 1
        assert _counter_value(
            snapshot,
            "payout_failure_total",
            labels={"reason": "webhook_signature_failed"},
        ) == 1

    def test_webhook_rejects_missing_signature(self):
        sb = _FakeSupabase(claim_status="approved", bank_verified=True)
        sb.tables["payout_requests"].append(
            {
                "id": "payout-1",
                "claim_id": "claim-1",
                "worker_profile_id": "worker-1",
                "provider_key": "simulated_gateway",
                "provider_reference_id": "provider-ref-1",
                "correlation_id": "corr-1",
                "idempotency_key": "idem-1",
                "status": "pending",
                "retry_count": 0,
            }
        )

        payload = {
            "event_id": "evt-missing-signature",
            "reference_id": "provider-ref-1",
            "status": "settled",
        }
        body = json.dumps(payload).encode("utf-8")

        with patch(
            "backend.app.services.payout_workflow.get_payout_provider",
            return_value=_StubProvider(signature_valid=False),
        ):
            result = asyncio.run(
                ingest_settlement_webhook(
                    sb,
                    provider_key="simulated_gateway",
                    payload_bytes=body,
                    signature_header=None,
                    source_ip="127.0.0.1",
                )
            )

        assert result["status"] == "rejected"
        assert result["signature_valid"] is False
        assert sb.tables["payout_requests"][0]["status"] == "pending"

    def test_duplicate_webhook_event_id_is_idempotent(self):
        sb = _FakeSupabase(claim_status="approved", bank_verified=True)
        sb.tables["payout_requests"].append(
            {
                "id": "payout-1",
                "claim_id": "claim-1",
                "worker_profile_id": "worker-1",
                "provider_key": "simulated_gateway",
                "provider_reference_id": "provider-ref-1",
                "correlation_id": "corr-1",
                "idempotency_key": "idem-1",
                "status": "pending",
                "retry_count": 0,
            }
        )

        payload = {
            "event_id": "evt-duplicate",
            "reference_id": "provider-ref-1",
            "status": "settled",
        }
        body = json.dumps(payload).encode("utf-8")

        with patch(
            "backend.app.services.payout_workflow.get_payout_provider",
            return_value=_StubProvider(signature_valid=True),
        ), patch(
            "backend.app.services.payout_workflow.enqueue_domain_event",
            new=AsyncMock(return_value={"status": "processed"}),
        ):
            first = asyncio.run(
                ingest_settlement_webhook(
                    sb,
                    provider_key="simulated_gateway",
                    payload_bytes=body,
                    signature_header="ok",
                    source_ip="127.0.0.1",
                )
            )
            second = asyncio.run(
                ingest_settlement_webhook(
                    sb,
                    provider_key="simulated_gateway",
                    payload_bytes=body,
                    signature_header="ok",
                    source_ip="127.0.0.1",
                )
            )

        assert first["status"] == "processed"
        assert second["status"] == "duplicate"
        assert sb.tables["payout_requests"][0]["status"] == "settled"
        assert sb.tables["manual_claims"][0]["claim_status"] == "paid"

    def test_failed_webhook_moves_to_failed_and_sets_retry(self):
        sb = _FakeSupabase(claim_status="approved", bank_verified=True)
        sb.tables["payout_requests"].append(
            {
                "id": "payout-1",
                "claim_id": "claim-1",
                "worker_profile_id": "worker-1",
                "provider_key": "simulated_gateway",
                "provider_reference_id": "provider-ref-1",
                "correlation_id": "corr-1",
                "idempotency_key": "idem-1",
                "status": "pending",
                "retry_count": 0,
                "next_retry_at": None,
            }
        )

        payload = {
            "event_id": "evt-failed",
            "reference_id": "provider-ref-1",
            "status": "failed",
        }
        body = json.dumps(payload).encode("utf-8")

        with patch(
            "backend.app.services.payout_workflow.get_payout_provider",
            return_value=_StubProvider(signature_valid=True),
        ), patch(
            "backend.app.services.payout_workflow.enqueue_domain_event",
            new=AsyncMock(return_value={"status": "processed"}),
        ):
            result = asyncio.run(
                ingest_settlement_webhook(
                    sb,
                    provider_key="simulated_gateway",
                    payload_bytes=body,
                    signature_header="ok",
                    source_ip="127.0.0.1",
                )
            )

        assert result["status"] == "processed"
        payout = sb.tables["payout_requests"][0]
        assert payout["status"] == "failed"
        assert payout["retry_count"] == 1
        assert payout["next_retry_at"] is not None

    def test_get_payout_trace_includes_trust_stamp(self):
        sb = _FakeSupabase(claim_status="approved", bank_verified=True)
        sb.tables["payout_requests"].append(
            {
                "id": "payout-1",
                "claim_id": "claim-1",
                "worker_profile_id": "worker-1",
                "provider_key": "simulated_gateway",
                "provider_reference_id": "provider-ref-1",
                "status": "pending",
                "retry_count": 0,
            }
        )

        trace = get_payout_trace_for_claim(sb, "claim-1")

        assert trace["claim_id"] == "claim-1"
        assert trace["payout"]["id"] == "payout-1"
        assert trace["trust_stamp"]["fraud_score_band"] == "medium"
        assert trace["trust_stamp"]["attestation_verdict"] == "passed"
        assert (
            trace["trust_stamp"]["version_governance"]["model_version"]["key"]
            == "fraud_model_heuristic_v1"
        )

    def test_insert_settlement_event_falls_back_when_columns_missing(self):
        class _FallbackTable:
            def __init__(self):
                self.calls: list[dict[str, Any]] = []
                self._payload: dict[str, Any] | None = None

            def insert(self, payload: dict[str, Any]):
                self._payload = payload
                return self

            def execute(self):
                assert self._payload is not None
                self.calls.append(dict(self._payload))
                if len(self.calls) == 1:
                    raise Exception(
                        "Could not find the 'payload_hash' column of 'payout_settlement_events' in the schema cache"
                    )
                if len(self.calls) == 2:
                    raise Exception(
                        "Could not find the 'processing_status' column of 'payout_settlement_events' in the schema cache"
                    )
                return SimpleNamespace(data=[{"id": "evt-1", **self._payload}])

        class _FallbackSB:
            def __init__(self):
                self.table_impl = _FallbackTable()

            def table(self, name: str):
                assert name == "payout_settlement_events"
                return self.table_impl

        sb = _FallbackSB()
        row = {
            "provider_key": "simulated_gateway",
            "provider_event_id": "evt-1",
            "payload": {"status": "settled"},
            "payload_hash": "abc123",
            "processing_status": "received",
        }

        inserted = _insert_settlement_event_row(sb, row)

        assert inserted and inserted[0]["id"] == "evt-1"
        assert len(sb.table_impl.calls) == 3
        assert "payload_hash" in sb.table_impl.calls[0]
        assert "payload_hash" not in sb.table_impl.calls[1]
        assert "processing_status" in sb.table_impl.calls[1]
        assert "processing_status" not in sb.table_impl.calls[2]

    def test_update_settlement_event_falls_back_when_columns_missing(self):
        class _FallbackTable:
            def __init__(self):
                self.calls: list[dict[str, Any]] = []
                self._payload: dict[str, Any] | None = None

            def update(self, payload: dict[str, Any]):
                self._payload = payload
                return self

            def eq(self, _key: str, _value: str):
                return self

            def execute(self):
                assert self._payload is not None
                self.calls.append(dict(self._payload))
                if len(self.calls) == 1:
                    raise Exception(
                        "Could not find the 'processing_status' column of 'payout_settlement_events' in the schema cache"
                    )
                if len(self.calls) == 2:
                    raise Exception(
                        "Could not find the 'error_message' column of 'payout_settlement_events' in the schema cache"
                    )
                return SimpleNamespace(data=[{"id": "evt-1", **self._payload}])

        class _FallbackSB:
            def __init__(self):
                self.table_impl = _FallbackTable()

            def table(self, name: str):
                assert name == "payout_settlement_events"
                return self.table_impl

        sb = _FallbackSB()
        _update_settlement_event_row(
            sb,
            "evt-1",
            {
                "processing_status": "processed",
                "error_message": None,
                "processed_at": "2026-01-01T00:00:00Z",
            },
        )

        assert len(sb.table_impl.calls) == 3
        assert "processing_status" in sb.table_impl.calls[0]
        assert "processing_status" not in sb.table_impl.calls[1]
        assert "error_message" in sb.table_impl.calls[1]
        assert "error_message" not in sb.table_impl.calls[2]

    def test_update_payout_request_falls_back_when_columns_missing(self):
        class _FallbackTable:
            def __init__(self):
                self.calls: list[dict[str, Any]] = []
                self._payload: dict[str, Any] | None = None

            def update(self, payload: dict[str, Any]):
                self._payload = payload
                return self

            def eq(self, _key: str, _value: str):
                return self

            def execute(self):
                assert self._payload is not None
                self.calls.append(dict(self._payload))
                if len(self.calls) == 1:
                    raise Exception(
                        "Could not find the 'settled_at' column of 'payout_requests' in the schema cache"
                    )
                return SimpleNamespace(data=[{"id": "payout-1", **self._payload}])

        class _FallbackSB:
            def __init__(self):
                self.table_impl = _FallbackTable()

            def table(self, name: str):
                assert name == "payout_requests"
                return self.table_impl

        sb = _FallbackSB()
        applied = _update_payout_request_row(
            sb,
            "payout-1",
            {
                "status": "settled",
                "settled_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        )

        assert len(sb.table_impl.calls) == 2
        assert "settled_at" in sb.table_impl.calls[0]
        assert "settled_at" not in sb.table_impl.calls[1]
        assert "settled_at" not in applied
        assert applied["status"] == "settled"

    def test_webhook_handles_settlement_table_not_null_payout_request_id(self):
        sb = _FakeSupabase(
            claim_status="approved",
            bank_verified=True,
            settlement_requires_payout_request_id=True,
        )
        sb.tables["payout_requests"].append(
            {
                "id": "payout-1",
                "claim_id": "claim-1",
                "worker_profile_id": "worker-1",
                "provider_key": "simulated_gateway",
                "provider_reference_id": "provider-ref-1",
                "correlation_id": "corr-1",
                "idempotency_key": "idem-1",
                "status": "pending",
                "retry_count": 0,
            }
        )

        payload = {
            "event_id": "evt-not-null",
            "claim_id": "claim-1",
            "status": "settled",
        }
        body = json.dumps(payload).encode("utf-8")

        with patch(
            "backend.app.services.payout_workflow.get_payout_provider",
            return_value=_StubProvider(signature_valid=True),
        ), patch(
            "backend.app.services.payout_workflow.enqueue_domain_event",
            new=AsyncMock(return_value={"status": "processed"}),
        ):
            result = asyncio.run(
                ingest_settlement_webhook(
                    sb,
                    provider_key="simulated_gateway",
                    payload_bytes=body,
                    signature_header="ok",
                    source_ip="127.0.0.1",
                )
            )

        assert result["status"] == "processed"
        assert sb.tables["payout_requests"][0]["status"] == "settled"
        assert sb.tables["manual_claims"][0]["claim_status"] == "paid"
        assert len(sb.tables["payout_settlement_events"]) == 1
        assert sb.tables["payout_settlement_events"][0]["payout_request_id"] == "payout-1"

    def test_update_payout_request_maps_settled_to_paid_on_legacy_status_constraint(self):
        class _FallbackTable:
            def __init__(self):
                self.calls: list[dict[str, Any]] = []
                self._payload: dict[str, Any] | None = None

            def update(self, payload: dict[str, Any]):
                self._payload = payload
                return self

            def eq(self, _key: str, _value: str):
                return self

            def execute(self):
                assert self._payload is not None
                self.calls.append(dict(self._payload))
                if len(self.calls) == 1:
                    raise Exception(
                        'new row for relation "payout_requests" violates check constraint "payout_requests_status_check"'
                    )
                return SimpleNamespace(data=[{"id": "payout-1", **self._payload}])

        class _FallbackSB:
            def __init__(self):
                self.table_impl = _FallbackTable()

            def table(self, name: str):
                assert name == "payout_requests"
                return self.table_impl

        sb = _FallbackSB()
        applied = _update_payout_request_row(
            sb,
            "payout-1",
            {
                "status": "settled",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        )

        assert len(sb.table_impl.calls) == 2
        assert sb.table_impl.calls[0]["status"] == "settled"
        assert sb.table_impl.calls[1]["status"] == "paid"
        assert applied["status"] == "paid"

    def test_webhook_maps_settled_to_paid_for_legacy_status_constraint(self):
        sb = _FakeSupabase(
            claim_status="approved",
            bank_verified=True,
            settlement_requires_payout_request_id=True,
            legacy_payout_status_check=True,
        )
        sb.tables["payout_requests"].append(
            {
                "id": "payout-1",
                "claim_id": "claim-1",
                "worker_profile_id": "worker-1",
                "provider_key": "simulated_gateway",
                "provider_reference_id": "provider-ref-1",
                "correlation_id": "corr-1",
                "idempotency_key": "idem-1",
                "status": "processing",
                "retry_count": 0,
            }
        )

        payload = {
            "event_id": "evt-legacy-status",
            "claim_id": "claim-1",
            "status": "settled",
        }
        body = json.dumps(payload).encode("utf-8")

        with patch(
            "backend.app.services.payout_workflow.get_payout_provider",
            return_value=_StubProvider(signature_valid=True),
        ), patch(
            "backend.app.services.payout_workflow.enqueue_domain_event",
            new=AsyncMock(return_value={"status": "processed"}),
        ):
            result = asyncio.run(
                ingest_settlement_webhook(
                    sb,
                    provider_key="simulated_gateway",
                    payload_bytes=body,
                    signature_header="ok",
                    source_ip="127.0.0.1",
                )
            )

        assert result["status"] == "processed"
        assert sb.tables["payout_requests"][0]["status"] == "paid"
        assert sb.tables["manual_claims"][0]["claim_status"] == "paid"

    def test_insert_transition_falls_back_to_legacy_columns(self):
        class _FallbackTable:
            def __init__(self):
                self.calls: list[dict[str, Any]] = []
                self._payload: dict[str, Any] | None = None

            def insert(self, payload: dict[str, Any]):
                self._payload = payload
                return self

            def execute(self):
                assert self._payload is not None
                self.calls.append(dict(self._payload))
                if len(self.calls) == 1:
                    raise Exception(
                        "Could not find the 'actor_type' column of 'payout_status_transitions' in the schema cache"
                    )
                if len(self.calls) == 2:
                    raise Exception(
                        "Could not find the 'previous_status' column of 'payout_status_transitions' in the schema cache"
                    )
                return SimpleNamespace(data=[{"id": "tr-1", **self._payload}])

        class _FallbackSB:
            def __init__(self):
                self.table_impl = _FallbackTable()

            def table(self, name: str):
                assert name == "payout_status_transitions"
                return self.table_impl

        sb = _FallbackSB()
        _insert_transition(
            sb,
            payout_request_id="payout-1",
            previous_status="processing",
            new_status="settled",
            reason="webhook:settled",
            actor_type="provider_webhook",
            actor_profile_id=None,
            metadata={"provider_event_id": "evt-1"},
        )

        assert len(sb.table_impl.calls) == 3
        assert "actor_type" in sb.table_impl.calls[0]
        assert "actor_type" not in sb.table_impl.calls[1]
        assert "to_status" in sb.table_impl.calls[2]

    def test_webhook_allows_manual_review_to_settled(self):
        sb = _FakeSupabase(
            claim_status="approved",
            bank_verified=True,
            settlement_requires_payout_request_id=True,
        )
        sb.tables["payout_requests"].append(
            {
                "id": "payout-1",
                "claim_id": "claim-1",
                "worker_profile_id": "worker-1",
                "provider_key": "simulated_gateway",
                "provider_reference_id": "provider-ref-1",
                "correlation_id": "corr-1",
                "idempotency_key": "idem-1",
                "status": "manual_review",
                "retry_count": 0,
            }
        )

        payload = {
            "event_id": "evt-manual-review-settle",
            "claim_id": "claim-1",
            "status": "settled",
        }
        body = json.dumps(payload).encode("utf-8")

        with patch(
            "backend.app.services.payout_workflow.get_payout_provider",
            return_value=_StubProvider(signature_valid=True),
        ), patch(
            "backend.app.services.payout_workflow.enqueue_domain_event",
            new=AsyncMock(return_value={"status": "processed"}),
        ):
            result = asyncio.run(
                ingest_settlement_webhook(
                    sb,
                    provider_key="simulated_gateway",
                    payload_bytes=body,
                    signature_header="ok",
                    source_ip="127.0.0.1",
                )
            )

        assert result["status"] == "processed"
        assert sb.tables["payout_requests"][0]["status"] == "settled"
        assert sb.tables["manual_claims"][0]["claim_status"] == "paid"
