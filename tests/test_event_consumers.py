"""
Tests for event consumer dispatch and handlers.
"""

import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.event_bus.consumer_dispatch import (
    _handle_auto_claim_notification,
    _handle_auto_claim_rewards,
    dispatch_event_to_consumers,
)
from backend.app.services.event_bus.consumer_idempotency import (
    ConsumeLease,
    begin_consume,
    consume_idempotently,
    requeue_dead_letter_consumer_entries,
)
from backend.app.services.event_bus.contracts import DomainEvent


class _DummySB:
    pass


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
            rows = self._rows()
            for row in rows:
                row.update(self._update_payload)
            return _Resp(rows)
        return _Resp(self._rows())


class _StateSB:
    def __init__(self, state: dict):
        self.state = state

    def table(self, name: str):
        return _Table(name, self.state)


class TestEventConsumerDispatch:
    @patch("backend.app.services.event_bus.consumer_dispatch.consume_idempotently")
    def test_dispatch_claim_auto_processed_invokes_two_consumers(self, mock_consume):
        mock_consume.side_effect = [
            {"processed": True, "reason": "succeeded"},
            {"processed": False, "reason": "already_succeeded"},
        ]

        event = DomainEvent(
            event_id="evt-1",
            event_type="claim.auto_processed",
            payload={
                "worker_id": "worker-1",
                "claim_id": "claim-1",
                "decision": "auto_approve",
                "claim_status": "auto_approved",
                "fraud_score": 0.1,
            },
        )

        result = asyncio.run(dispatch_event_to_consumers(_DummySB(), event))

        assert result["consumers"] == 2
        assert result["processed"] == 1
        assert result["skipped"] == 1
        assert len(result["results"]) == 2

    def test_dispatch_unknown_event_type_noop(self):
        event = DomainEvent(
            event_id="evt-2",
            event_type="claim.submitted",
            payload={"claim_id": "claim-2"},
        )

        result = asyncio.run(dispatch_event_to_consumers(_DummySB(), event))

        assert result["consumers"] == 0
        assert result["processed"] == 0
        assert result["skipped"] == 0


class TestEventConsumerHandlers:
    @patch("backend.app.services.twilio_service.send_whatsapp_template")
    @patch("backend.app.services.event_bus.consumer_dispatch._get_worker_phone")
    def test_auto_claim_notification_handler(self, mock_get_phone, mock_send_template):
        mock_get_phone.return_value = "+919999999999"
        mock_send_template.return_value = {"success": True, "mock": True}

        event = DomainEvent(
            event_id="evt-3",
            event_type="claim.auto_processed",
            payload={
                "worker_id": "worker-1",
                "claim_id": "abcde12345",
                "claim_status": "auto_approved",
                "trigger_code": "HEAVY_RAIN",
                "payout_amount": 1500,
            },
        )

        result = asyncio.run(_handle_auto_claim_notification(_DummySB(), event))

        assert result["sent"] is True
        assert result["template"] == "claim_auto_approved"

    @patch("backend.app.services.rewards_engine.award_clean_claim")
    def test_auto_claim_rewards_handler(self, mock_award_clean_claim):
        mock_award_clean_claim.return_value = {
            "success": True,
            "coins_awarded": 25,
            "new_balance": 125,
        }

        event = DomainEvent(
            event_id="evt-4",
            event_type="claim.auto_processed",
            payload={
                "worker_id": "worker-1",
                "claim_id": "claim-4",
                "decision": "auto_approve",
                "fraud_score": 0.11,
            },
        )

        result = asyncio.run(_handle_auto_claim_rewards(_DummySB(), event))

        assert result["awarded"] is True
        assert result["coins_awarded"] == 25

    @patch("backend.app.services.rewards_engine.award_clean_claim")
    def test_auto_claim_rewards_handler_skips_non_qualifying(self, mock_award_clean_claim):
        event = DomainEvent(
            event_id="evt-5",
            event_type="claim.auto_processed",
            payload={
                "worker_id": "worker-1",
                "claim_id": "claim-5",
                "decision": "needs_review",
                "fraud_score": 0.30,
            },
        )

        result = asyncio.run(_handle_auto_claim_rewards(_DummySB(), event))

        assert result["awarded"] is False
        assert result["reason"] == "criteria_not_met"
        assert mock_award_clean_claim.call_count == 0


class TestConsumerDeadLetter:
    def test_begin_consume_skips_existing_dead_letter_entry(self):
        table = MagicMock()

        insert_query = MagicMock()
        insert_query.execute.side_effect = Exception(
            "duplicate key value violates unique constraint "
            "event_consumer_ledger_consumer_event_uniq"
        )
        table.insert.return_value = insert_query

        select_query = MagicMock()
        select_query.execute.return_value = _Resp(
            {
                "id": "ledger-dead",
                "status": "dead_letter",
                "attempt_count": 5,
            }
        )

        select_chain = MagicMock()
        select_chain.eq.return_value = select_chain
        select_chain.maybe_single.return_value = select_query
        table.select.return_value = select_chain

        sb = MagicMock()
        sb.table.return_value = table

        event = DomainEvent(
            event_id="evt-dead-lease",
            event_type="claim.auto_processed",
            payload={},
        )

        lease = begin_consume(sb=sb, consumer_name="test_consumer", event=event)

        assert lease.should_process is False
        assert lease.reason == "dead_lettered"
        assert lease.attempt_count == 5
        assert lease.ledger_id == "ledger-dead"
        assert table.update.call_count == 0

    @patch("backend.app.services.event_bus.consumer_idempotency._consumer_max_attempts", return_value=3)
    @patch("backend.app.services.event_bus.consumer_idempotency.mark_consume_failed")
    @patch("backend.app.services.event_bus.consumer_idempotency.begin_consume")
    def test_consume_idempotently_raises_before_max_attempts(
        self,
        mock_begin,
        mock_mark_failed,
        _mock_max_attempts,
    ):
        mock_begin.return_value = ConsumeLease(
            should_process=True,
            ledger_id="ledger-1",
            attempt_count=2,
            reason="retry_acquired",
        )

        async def _failing_handler(_event):
            raise RuntimeError("transient failure")

        event = DomainEvent(
            event_id="evt-fail-1",
            event_type="claim.auto_processed",
            payload={},
        )

        try:
            asyncio.run(
                consume_idempotently(
                    sb=_DummySB(),
                    consumer_name="test_consumer",
                    event=event,
                    handler=_failing_handler,
                )
            )
            assert False, "Expected transient failure to be raised"
        except RuntimeError as exc:
            assert "transient failure" in str(exc)

        assert mock_mark_failed.call_count == 1
        assert mock_mark_failed.call_args.kwargs["dead_letter"] is False

    @patch("backend.app.services.event_bus.consumer_idempotency._consumer_max_attempts", return_value=3)
    @patch("backend.app.services.event_bus.consumer_idempotency.mark_consume_failed")
    @patch("backend.app.services.event_bus.consumer_idempotency.begin_consume")
    def test_consume_idempotently_dead_letters_at_max_attempts(
        self,
        mock_begin,
        mock_mark_failed,
        _mock_max_attempts,
    ):
        mock_begin.return_value = ConsumeLease(
            should_process=True,
            ledger_id="ledger-2",
            attempt_count=3,
            reason="retry_acquired",
        )

        async def _failing_handler(_event):
            raise RuntimeError("permanent failure")

        event = DomainEvent(
            event_id="evt-fail-2",
            event_type="claim.auto_processed",
            payload={},
        )

        result = asyncio.run(
            consume_idempotently(
                sb=_DummySB(),
                consumer_name="test_consumer",
                event=event,
                handler=_failing_handler,
            )
        )

        assert result["processed"] is False
        assert result["reason"] == "dead_lettered"
        assert mock_mark_failed.call_count == 1
        assert mock_mark_failed.call_args.kwargs["dead_letter"] is True

    def test_requeue_dead_letter_consumer_entries(self):
        state = {
            "event_consumer_ledger": [
                {
                    "id": "ledger-1",
                    "event_id": "evt-1",
                    "status": "dead_letter",
                    "dead_lettered_at": "2026-04-05T10:00:00+00:00",
                },
                {
                    "id": "ledger-2",
                    "event_id": "evt-2",
                    "status": "dead_letter",
                    "dead_lettered_at": "2026-04-05T11:00:00+00:00",
                },
            ],
            "event_outbox": [
                {"event_id": "evt-1", "status": "processed", "retry_count": 2},
                {"event_id": "evt-2", "status": "processed", "retry_count": 1},
            ],
        }
        sb = _StateSB(state)

        result = requeue_dead_letter_consumer_entries(sb, limit=1)

        assert result["selected"] == 1
        assert result["ledger_requeued"] == 1
        assert result["outbox_requeued"] == 1

        first_ledger = next(
            row for row in state["event_consumer_ledger"] if row["id"] == "ledger-1"
        )
        second_ledger = next(
            row for row in state["event_consumer_ledger"] if row["id"] == "ledger-2"
        )
        first_outbox = next(
            row for row in state["event_outbox"] if row["event_id"] == "evt-1"
        )

        assert first_ledger["status"] == "failed"
        assert first_ledger["dead_lettered_at"] is None
        assert first_outbox["status"] == "pending"
        assert first_outbox["retry_count"] == 0

        # limit=1 should leave the second entry untouched
        assert second_ledger["status"] == "dead_letter"
