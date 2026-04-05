"""
Tests for Kafka consumer message mapping and dispatch.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.event_bus.kafka_consumer import (
    message_to_domain_event,
    process_kafka_message,
)


class _DummySB:
    pass


class TestKafkaConsumer:
    def test_message_to_domain_event_valid(self):
        message = {
            "event_id": "evt-1",
            "event_type": "claim.auto_processed",
            "occurred_at": "2026-04-05T00:00:00+00:00",
            "source": "test",
            "key": "worker-1",
            "payload": {"claim_id": "claim-1"},
        }

        event = message_to_domain_event(message)

        assert event is not None
        assert event.event_id == "evt-1"
        assert event.event_type == "claim.auto_processed"
        assert event.payload["claim_id"] == "claim-1"

    def test_message_to_domain_event_invalid_without_type(self):
        message = {
            "event_id": "evt-2",
            "payload": {"claim_id": "claim-2"},
        }

        event = message_to_domain_event(message)

        assert event is None

    @patch("backend.app.services.event_bus.kafka_consumer.dispatch_event_to_consumers", new_callable=AsyncMock)
    def test_process_kafka_message_dispatches(self, mock_dispatch):
        mock_dispatch.return_value = {
            "processed": 1,
            "skipped": 0,
            "results": [],
        }

        message = {
            "event_id": "evt-3",
            "event_type": "claim.auto_processed",
            "occurred_at": "2026-04-05T00:00:00+00:00",
            "source": "test",
            "key": "worker-1",
            "payload": {"claim_id": "claim-3"},
        }

        result = asyncio.run(process_kafka_message(_DummySB(), message))

        assert result["processed"] is True
        assert result["event_type"] == "claim.auto_processed"
        assert mock_dispatch.await_count == 1

    @patch("backend.app.services.event_bus.kafka_consumer.dispatch_event_to_consumers", new_callable=AsyncMock)
    def test_process_kafka_message_invalid_payload(self, mock_dispatch):
        result = asyncio.run(process_kafka_message(_DummySB(), {"payload": {}}))

        assert result["processed"] is False
        assert result["reason"] == "invalid_message"
        assert mock_dispatch.await_count == 0
