"""
Covara One - Event Bus Factory

Resolves the configured event bus backend and exposes helper
functions to publish domain events.
"""

from __future__ import annotations

import logging

from backend.app.config import settings
from backend.app.services.event_bus.contracts import DomainEvent
from backend.app.services.event_bus.in_memory import InMemoryEventBus, NoOpEventBus
from backend.app.services.event_bus.kafka_bus import KafkaEventBus

logger = logging.getLogger("covara.event_bus")

_EVENT_BUS = None


def _build_event_bus():
    backend = (settings.event_bus_backend or "inmemory").strip().lower()

    if backend == "noop":
        logger.info("Event bus backend: noop")
        return NoOpEventBus()

    if backend == "kafka":
        if not settings.kafka_bootstrap_servers:
            logger.warning(
                "EVENT_BUS_BACKEND=kafka but KAFKA_BOOTSTRAP_SERVERS is empty; "
                "falling back to in-memory bus"
            )
            return InMemoryEventBus()

        try:
            logger.info("Event bus backend: kafka")
            return KafkaEventBus(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                client_id=settings.kafka_client_id,
                topic_prefix=settings.event_bus_topic_prefix,
                security_protocol=settings.kafka_security_protocol,
            )
        except Exception as exc:
            logger.warning("Kafka bus init failed, using in-memory bus: %s", exc)
            return InMemoryEventBus()

    logger.info("Event bus backend: in-memory")
    return InMemoryEventBus()


def get_event_bus():
    global _EVENT_BUS
    if _EVENT_BUS is None:
        _EVENT_BUS = _build_event_bus()
    return _EVENT_BUS


async def publish_domain_event(event: DomainEvent) -> None:
    """Publish a pre-built domain event instance."""
    bus = get_event_bus()
    await bus.publish(event)


async def publish_event(
    event_type: str,
    payload: dict,
    key: str | None = None,
    source: str = "backend",
) -> None:
    event = DomainEvent(
        event_type=event_type,
        payload=payload,
        key=key,
        source=source,
    )
    await publish_domain_event(event)


async def flush_event_bus() -> None:
    bus = get_event_bus()
    await bus.flush()
