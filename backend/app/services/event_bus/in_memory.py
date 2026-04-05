"""
Covara One - In-Memory Event Bus

Safe default event bus for local development and environments
without an external broker.
"""

from __future__ import annotations

import logging

from backend.app.services.event_bus.contracts import DomainEvent

logger = logging.getLogger("covara.event_bus")


class InMemoryEventBus:
    """Simple in-memory event collector with bounded retention."""

    def __init__(self, max_events: int = 5000):
        self._events: list[DomainEvent] = []
        self._max_events = max_events

    async def publish(self, event: DomainEvent) -> None:
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events :]

        logger.info(
            "Event published (in-memory): %s id=%s key=%s",
            event.event_type,
            event.event_id,
            event.key,
        )

    async def publish_many(self, events: list[DomainEvent]) -> None:
        for event in events:
            await self.publish(event)

    async def flush(self) -> None:
        # No-op for in-memory implementation.
        return

    def snapshot(self) -> list[DomainEvent]:
        """Expose a copy for diagnostics and tests."""
        return list(self._events)


class NoOpEventBus:
    """No-op bus for disabled eventing paths."""

    async def publish(self, event: DomainEvent) -> None:
        logger.debug("Event dropped (noop): %s", event.event_type)

    async def publish_many(self, events: list[DomainEvent]) -> None:
        for event in events:
            await self.publish(event)

    async def flush(self) -> None:
        return
