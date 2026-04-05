"""
Covara One - Event Bus Contracts

Defines a broker-agnostic domain event shape and event bus interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    payload: dict[str, Any]
    key: str | None = None
    source: str = "backend"
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: str = field(default_factory=_utc_now_iso)


class EventBus(Protocol):
    async def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event."""

    async def publish_many(self, events: list[DomainEvent]) -> None:
        """Publish multiple events."""

    async def flush(self) -> None:
        """Flush pending writes where applicable."""
