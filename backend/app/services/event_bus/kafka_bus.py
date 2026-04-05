"""
Covara One - Kafka Event Bus Adapter

Kafka adapter behind abstraction. It uses aiokafka when installed.
If aiokafka is not available or broker is not configured, caller
should fall back to another bus implementation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.services.event_bus.contracts import DomainEvent

logger = logging.getLogger("covara.event_bus")


class KafkaEventBus:
    def __init__(
        self,
        bootstrap_servers: str,
        client_id: str,
        topic_prefix: str,
        security_protocol: str = "PLAINTEXT",
    ):
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self.topic_prefix = topic_prefix
        self.security_protocol = security_protocol
        self._producer: Any = None

    async def _ensure_producer(self) -> None:
        if self._producer is not None:
            return

        try:
            from aiokafka import AIOKafkaProducer
        except Exception as exc:
            raise RuntimeError(
                "aiokafka is required for EVENT_BUS_BACKEND=kafka"
            ) from exc

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            client_id=self.client_id,
            security_protocol=self.security_protocol,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        )
        await self._producer.start()

    def _topic_for_event(self, event_type: str) -> str:
        suffix = event_type.replace(" ", "_").replace("/", ".")
        return f"{self.topic_prefix}.{suffix}"

    async def publish(self, event: DomainEvent) -> None:
        await self._ensure_producer()
        topic = self._topic_for_event(event.event_type)

        message = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at,
            "source": event.source,
            "key": event.key,
            "payload": event.payload,
        }

        key_bytes = event.key.encode("utf-8") if event.key else None
        await self._producer.send_and_wait(topic, message, key=key_bytes)

        logger.info(
            "Event published (kafka): %s id=%s key=%s topic=%s",
            event.event_type,
            event.event_id,
            event.key,
            topic,
        )

    async def publish_many(self, events: list[DomainEvent]) -> None:
        for event in events:
            await self.publish(event)

    async def flush(self) -> None:
        if self._producer is None:
            return
        await self._producer.flush()

    async def close(self) -> None:
        if self._producer is None:
            return
        await self._producer.stop()
        self._producer = None
