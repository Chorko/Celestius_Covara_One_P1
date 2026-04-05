# Event Bus and Kafka Roadmap

## Goal

Move claim orchestration from synchronous request loops to event-driven processing while preserving current behavior during migration.

## Current state

- Event bus abstraction exists in backend/app/services/event_bus.
- Default backend is in-memory for local/dev safety.
- Kafka adapter exists but is enabled only when EVENT_BUS_BACKEND=kafka.
- Claims and auto-claim flows emit domain events.
- Outbox durability is implemented (event_outbox table + relay service).
- Claim submission and auto-claim writes are transaction-coupled to outbox via SQL RPC persist_claim_with_outbox.
- Outbox retry path supports dead-letter transition after configurable max retries.
- Consumer idempotency ledger table + Python helper module are in place for consumer rollout.
- Admin relay endpoint is available at POST /events/outbox/relay.
- Background outbox relay worker is available in app lifespan (config-gated).
- Dead-letter operations endpoints are available for list + requeue workflows.
- First idempotent consumers are implemented for claim.auto_processed (worker notification + clean-claim rewards).
- Kafka consumer runner is available to dispatch broker events into the same idempotent handlers.
- Consumer max-attempt handling now transitions exhausted consumers to dead_letter.
- Consumer-ledger operational endpoints are available for status, dead-letter listing, and requeue.

## Domain events (initial)

- claim.submitted
- claim.reviewed
- claim.offline_synced
- trigger.processing_started
- claim.auto_processed
- claims.auto_process.summary
- claims.auto_process.completed

## Migration phases

Phase 1: Abstraction and contracts
- Keep in-memory backend as default.
- Emit domain events from existing synchronous flows.

Phase 2: Outbox reliability
- Outbox table and relay are implemented.
- Transaction-wrapped claim + payout + event writes are implemented.
- Consumer-side idempotency ledger scaffolding is implemented.
- Concrete consumers are wired to ledger helper with dead-letter escalation.
- Next: add dedicated DLQ forwarding workers and alerting hooks.

Phase 3: Kafka rollout
- Enable Kafka adapter in non-local environments.
- Add retry policy and dead-letter topic.
- Partition by worker_id or zone_id based on consumer ordering needs.

Phase 4: Async consumers
- Notification and clean-claim rewards are now consumer-driven for claim.auto_processed events.
- Next: move additional heavy enrichments and non-critical side effects to consumers.
- Keep request path limited to validation and persistence.

## Operational defaults

Use these env variables:

- EVENT_BUS_BACKEND=inmemory|kafka|noop
- EVENT_BUS_TOPIC_PREFIX=covara
- EVENT_BUS_PUBLISH_ON_WRITE=true|false
- EVENT_BUS_INLINE_CONSUMER_ENABLED=true|false
- EVENT_OUTBOX_RELAY_BATCH_SIZE=100
- EVENT_OUTBOX_RELAY_ENABLED=true|false
- EVENT_OUTBOX_RELAY_INTERVAL_SECONDS=15
- EVENT_OUTBOX_MAX_RETRIES=10
- EVENT_CONSUMER_ENABLED=true|false
- EVENT_CONSUMER_GROUP_ID=covara-event-consumers
- EVENT_CONSUMER_AUTO_OFFSET_RESET=latest|earliest
- EVENT_CONSUMER_POLL_TIMEOUT_MS=1000
- EVENT_CONSUMER_MAX_RECORDS=100
- EVENT_CONSUMER_MAX_ATTEMPTS=5
- KAFKA_BOOTSTRAP_SERVERS=host:9092
- KAFKA_CLIENT_ID=covara-backend
- KAFKA_SECURITY_PROTOCOL=PLAINTEXT

## Safety notes

- Kafka adapter requires aiokafka at runtime.
- If Kafka is configured but unavailable, startup should fall back to safe behavior by configuration choice.
- Outbox relay marks exhausted events as dead_letter to avoid infinite retry loops.
- Consumer idempotency must key on (consumer_name, event_id) before side effects.
- Consumer retries transition to dead_letter after EVENT_CONSUMER_MAX_ATTEMPTS.
