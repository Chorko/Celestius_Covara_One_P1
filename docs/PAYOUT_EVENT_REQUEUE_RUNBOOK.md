# Payout/Event Dead-Letter Requeue Runbook

## Purpose

This runbook defines a replay-safe process to recover from payout and event-delivery dead-letter growth without creating duplicate settlements.

Scope:
- Outbox dead-letter events (`event_outbox`)
- Consumer dead-letter entries (`event_consumer_ledger`)

Safety principles:
- Requeue in small batches.
- Verify signature/idempotency boundaries before replay.
- Confirm dead-letter backlog decreases and settlement integrity remains stable.

---

## Preconditions

1. Confirm current operations status:
   - `GET /ops/status`
   - `GET /events/outbox/status`
   - `GET /events/consumers/status`

2. Capture baseline counters:
   - outbox dead-letter count
   - consumer dead-letter count
   - payout failure/manual-review counts

3. Ensure webhook signature validation is enabled and healthy:
   - `PAYOUT_PROVIDER_WEBHOOK_SECRET` set and non-default

---

## Step A — Outbox Dead-Letter Recovery

1. List oldest dead-letter outbox events:
   - `GET /events/outbox/dead-letter?limit=100`

2. Requeue first recovery batch:
   - `POST /events/outbox/dead-letter/requeue?limit=25`

3. Trigger relay pass if required:
   - `POST /events/outbox/relay?batch_size=100`

4. Verify progress:
   - `GET /events/outbox/status`
   - `GET /ops/status`

5. Repeat in bounded batches until dead-letter trend is stable/decreasing.

---

## Step B — Consumer Dead-Letter Recovery

1. List consumer dead-letter entries:
   - `GET /events/consumers/dead-letter?limit=100`

2. Requeue consumer dead-letter batch:
   - `POST /events/consumers/dead-letter/requeue?limit=25`

3. Verify progress:
   - `GET /events/consumers/status`
   - `GET /ops/status`

4. Repeat with capped batch size until backlog is cleared or risk threshold is reached.

---

## Verification Checklist

- `outbox.dead_letter` is trending down after each batch.
- `consumer.dead_letter` is trending down after each batch.
- No duplicate payout settlement records are created.
- `payout_requests.status` transitions remain valid (no illegal jumps).
- Claim and payout event timelines remain auditable and correlated by request/event IDs.

---

## Stop Conditions and Escalation

Stop requeue and escalate if any of the following happens:
- Dead-letter backlog grows after two consecutive recovery batches.
- Duplicate settlement suspicion appears.
- Webhook signature failures spike.
- Payout transition errors indicate state-machine violations.

Escalation actions:
1. Pause further requeue operations.
2. Keep problematic events in dead-letter.
3. Route affected claims to `manual_review`.
4. Open incident with event IDs + claim IDs + request IDs attached.

---

## Audit Trail Requirements

For each recovery window, record:
- UTC start/end timestamps
- Operator identity
- Batch limits used
- Count before/after for outbox and consumer dead-letter
- Any claims routed to manual review
- Incident link (if escalation occurred)
