"""
Covara One - Kafka Event Consumer Runner

Consumes Kafka domain-event topics and dispatches them into
idempotent in-process consumer handlers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from backend.app.config import settings
from backend.app.services.event_bus.consumer_dispatch import dispatch_event_to_consumers
from backend.app.services.event_bus.contracts import DomainEvent
from backend.app.supabase_client import get_supabase_admin

logger = logging.getLogger("covara.kafka_consumer")


def message_to_domain_event(message: dict[str, Any]) -> DomainEvent | None:
    """Map a Kafka payload into a DomainEvent instance."""
    event_type = message.get("event_type")
    event_id = message.get("event_id")

    if not event_type or not event_id:
        return None

    payload = message.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    event_kwargs: dict[str, Any] = {
        "event_id": str(event_id),
        "event_type": str(event_type),
        "source": str(message.get("source") or "backend"),
        "key": (str(message.get("key")) if message.get("key") is not None else None),
        "payload": payload,
    }

    occurred_at = message.get("occurred_at")
    if occurred_at:
        event_kwargs["occurred_at"] = str(occurred_at)

    return DomainEvent(**event_kwargs)


async def process_kafka_message(sb, message: dict[str, Any]) -> dict[str, Any]:
    """Process one Kafka message by dispatching it to registered consumers."""
    event = message_to_domain_event(message)
    if event is None:
        return {
            "processed": False,
            "reason": "invalid_message",
        }

    dispatch_result = await dispatch_event_to_consumers(sb=sb, event=event)
    return {
        "processed": True,
        "event_type": event.event_type,
        "dispatch": dispatch_result,
    }


class KafkaEventConsumerRunner:
    def __init__(
        self,
        bootstrap_servers: str,
        topic_prefix: str,
        group_id: str,
        client_id: str,
        security_protocol: str = "PLAINTEXT",
        auto_offset_reset: str = "latest",
        poll_timeout_ms: int = 1000,
        max_records: int = 100,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic_prefix = topic_prefix
        self.group_id = group_id
        self.client_id = client_id
        self.security_protocol = security_protocol
        self.auto_offset_reset = auto_offset_reset
        self.poll_timeout_ms = poll_timeout_ms
        self.max_records = max_records
        self._consumer: Any = None
        self._offset_and_metadata_cls: Any = None

    async def _ensure_consumer(self) -> None:
        if self._consumer is not None:
            return

        try:
            from aiokafka import AIOKafkaConsumer
            from aiokafka.structs import OffsetAndMetadata
        except Exception as exc:
            raise RuntimeError("aiokafka is required for Kafka event consumer") from exc

        self._offset_and_metadata_cls = OffsetAndMetadata

        self._consumer = AIOKafkaConsumer(
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            client_id=self.client_id,
            security_protocol=self.security_protocol,
            auto_offset_reset=self.auto_offset_reset,
            # Manual commits are required so failed records are retried.
            enable_auto_commit=False,
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )

        await self._consumer.start()

        topic_pattern = re.compile(rf"^{re.escape(self.topic_prefix)}\\..+$")
        self._consumer.subscribe(pattern=topic_pattern)

        logger.info(
            "Kafka consumer started: bootstrap=%s group=%s topic_prefix=%s",
            self.bootstrap_servers,
            self.group_id,
            self.topic_prefix,
        )

    async def close(self) -> None:
        if self._consumer is None:
            return

        await self._consumer.stop()
        self._consumer = None
        self._offset_and_metadata_cls = None

    async def _commit_record_offset(self, topic_partition: Any, offset: int) -> None:
        """Commit one successfully handled record offset for its partition."""
        if self._consumer is None:
            return

        next_offset = int(offset) + 1
        if self._offset_and_metadata_cls is not None:
            commit_payload = {
                topic_partition: self._offset_and_metadata_cls(next_offset, ""),
            }
        else:
            commit_payload = {topic_partition: next_offset}

        await self._consumer.commit(offsets=commit_payload)

    async def run_forever(self) -> None:
        try:
            await self._ensure_consumer()
        except Exception as exc:
            logger.warning("Kafka consumer unavailable, runner disabled: %s", exc)
            return

        try:
            while True:
                batches = await self._consumer.getmany(
                    timeout_ms=self.poll_timeout_ms,
                    max_records=self.max_records,
                )
                if not batches:
                    continue

                sb = get_supabase_admin()
                for topic_partition, records in batches.items():
                    for record in records:
                        raw_message = record.value
                        if not isinstance(raw_message, dict):
                            logger.warning(
                                "Skipping Kafka record with non-dict payload topic=%s offset=%s",
                                getattr(record, "topic", "unknown"),
                                getattr(record, "offset", "unknown"),
                            )
                            # Bad payloads are not recoverable; commit and move on.
                            await self._commit_record_offset(
                                topic_partition=topic_partition,
                                offset=getattr(record, "offset", -1),
                            )
                            continue

                        try:
                            await process_kafka_message(sb=sb, message=raw_message)
                            await self._commit_record_offset(
                                topic_partition=topic_partition,
                                offset=getattr(record, "offset", -1),
                            )
                        except Exception as exc:
                            logger.warning(
                                "Kafka message processing failed topic=%s offset=%s error=%s",
                                getattr(record, "topic", "unknown"),
                                getattr(record, "offset", "unknown"),
                                exc,
                            )
                            # Do not commit on failure so Kafka can redeliver.
        except asyncio.CancelledError:
            raise
        finally:
            await self.close()


async def run_kafka_consumer_loop() -> None:
    """Build and run the Kafka consumer loop from environment settings."""
    runner = KafkaEventConsumerRunner(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        topic_prefix=settings.event_bus_topic_prefix,
        group_id=settings.event_consumer_group_id,
        client_id=f"{settings.kafka_client_id}-consumer",
        security_protocol=settings.kafka_security_protocol,
        auto_offset_reset=settings.event_consumer_auto_offset_reset,
        poll_timeout_ms=max(100, settings.event_consumer_poll_timeout_ms),
        max_records=max(1, settings.event_consumer_max_records),
    )
    await runner.run_forever()
