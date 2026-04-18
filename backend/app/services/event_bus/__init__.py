"""Event bus abstractions and adapters."""

from backend.app.services.event_bus.consumer_idempotency import (
	consume_idempotently,
	begin_consume,
	mark_consume_failed,
	mark_consume_succeeded,
)
from backend.app.services.event_bus.contracts import DomainEvent
from backend.app.services.event_bus.factory import (
	flush_event_bus,
	get_event_bus,
	publish_domain_event,
	publish_event,
)


async def dispatch_event_to_consumers(*args, **kwargs):
	from backend.app.services.event_bus.consumer_dispatch import (
		dispatch_event_to_consumers as _dispatch,
	)

	return await _dispatch(*args, **kwargs)


async def run_kafka_consumer_loop(*args, **kwargs):
	from backend.app.services.event_bus.kafka_consumer import (
		run_kafka_consumer_loop as _run_consumer,
	)

	return await _run_consumer(*args, **kwargs)

__all__ = [
	"DomainEvent",
	"get_event_bus",
	"publish_event",
	"publish_domain_event",
	"flush_event_bus",
	"consume_idempotently",
	"begin_consume",
	"mark_consume_failed",
	"mark_consume_succeeded",
	"dispatch_event_to_consumers",
	"run_kafka_consumer_loop",
]
