-- ══════════════════════════════════════════════════════════════════════
-- DEVTrails — Unified Extensions Migration (v13)
-- ══════════════════════════════════════════════════════════════════════
-- This migration consolidates all post-launch schema extensions into
-- a single, idempotent script with proper RLS from the start.
--
-- Contents:
--   §1  Disruption Events (payout safety & idempotency)
--   §2  Worker-Event Uniqueness (duplicate payout prevention)
--   §3  Claim State Machine Expansion (8-state lifecycle)
--   §4  Review Decision Expansion
--   §5  Validated Regional Incidents (fast-lane cache)
--   §6  Worker Phone Numbers (contact data)
--
-- ┌─────────────────────────────────────────────────────────────────┐
-- │  MIGRATION PATH — choose ONE of the two options below.         │
-- │  Running both will cause duplicate-object errors.              │
-- ├─────────────────────────────────────────────────────────────────┤
-- │  Option A — Fresh install (recommended for new environments):  │
-- │    1. Apply migrations 01–09 in order.                         │
-- │    2. Apply THIS file (13_unified_extensions.sql).             │
-- │    3. DO NOT apply 10_payout_safety.sql,                       │
-- │       11_claim_states.sql, or 12_region_validation_cache.sql.  │
-- │       Those scripts are fully superseded by this file.         │
-- ├─────────────────────────────────────────────────────────────────┤
-- │  Option B — Existing environment that already ran 10, 11, 12:  │
-- │    1. DO NOT apply this file.                                  │
-- │    2. The individual scripts 10, 11, 12 have already applied   │
-- │       all equivalent schema changes; this file is redundant.   │
-- └─────────────────────────────────────────────────────────────────┘
-- ══════════════════════════════════════════════════════════════════════

-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §1  DISRUPTION EVENTS — Payout Safety & Idempotency            │
-- └──────────────────────────────────────────────────────────────────┘
-- Each disruption window gets a deterministic event_id so that
-- retries and duplicate trigger-firings never produce repeated payouts.

create table if not exists public.disruption_events (
    id            uuid primary key default gen_random_uuid(),
    event_id      text unique not null,        -- deterministic: hash(zone + family + window)
    zone_id       uuid references public.zones(id),
    trigger_family text not null,
    window_start  timestamptz not null,
    window_end    timestamptz,
    validated     boolean not null default false,
    created_at    timestamptz not null default now()
);

comment on table public.disruption_events is
  'Unique disruption event identity for idempotent payout execution. '
  'event_id = hash(zone_id + trigger_family + window_start).';

-- RLS: workers read-only, service role full access
alter table public.disruption_events enable row level security;

create policy "disruption_events_select_authenticated"
  on public.disruption_events for select to authenticated
  using (true);

create policy "disruption_events_manage_service"
  on public.disruption_events for all to service_role
  using (true) with check (true);

-- Ensure authenticated cannot write directly
grant select on public.disruption_events to authenticated;
grant all   on public.disruption_events to service_role;


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §2  WORKER-EVENT UNIQUENESS — One payout per worker per event   │
-- └──────────────────────────────────────────────────────────────────┘
-- Partial unique index: enforced only for successful claim states.
-- Prevents the same worker from getting two payouts for one disruption.

create unique index if not exists idx_unique_worker_event
    on public.manual_claims(worker_profile_id, trigger_event_id)
    where claim_status in ('approved', 'paid', 'auto_approved');

comment on index public.idx_unique_worker_event is
  'Ensures one payout per worker per trigger event. '
  'Only applies to approved/paid/auto_approved claims.';


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §3  CLAIM STATE MACHINE EXPANSION (8 states)                   │
-- └──────────────────────────────────────────────────────────────────┘
-- New lifecycle: submitted → auto_approved / soft_hold_verification /
-- fraud_escalated_review → approved → paid → post_approval_flagged

-- Drop old constraint (may not exist on fresh DBs — IF EXISTS is safe)
alter table public.manual_claims
  drop constraint if exists manual_claims_claim_status_check;

-- Migrate legacy data (idempotent — no-ops on fresh DBs)
update public.manual_claims
  set claim_status = 'soft_hold_verification'
  where claim_status = 'held';

-- Only convert auto-triggered approvals; manual admin approvals stay 'approved'
update public.manual_claims
  set claim_status = 'auto_approved'
  where claim_status = 'approved'
    and claim_mode = 'auto';

-- Add the expanded 8-state constraint
alter table public.manual_claims
  add constraint manual_claims_claim_status_check
  check (claim_status in (
    'submitted',
    'auto_approved',
    'soft_hold_verification',
    'fraud_escalated_review',
    'approved',
    'rejected',
    'paid',
    'post_approval_flagged'
  ));

comment on constraint manual_claims_claim_status_check on public.manual_claims is
  'Expanded 8-state claim lifecycle with soft-hold and post-approval flagging.';


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §4  REVIEW DECISION EXPANSION                                  │
-- └──────────────────────────────────────────────────────────────────┘

alter table public.claim_reviews
  drop constraint if exists claim_reviews_decision_check;

alter table public.claim_reviews
  add constraint claim_reviews_decision_check
  check (decision in (
    'approve',
    'hold',
    'escalate',
    'reject',
    'flag_post_approval',
    'downgrade_trust'
  ));


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §5  VALIDATED REGIONAL INCIDENTS — Fast-Lane Cache              │
-- └──────────────────────────────────────────────────────────────────┘
-- Cache validated regional incidents so that claims in the same
-- zone/trigger/window skip repeated manual review.
-- Individual fraud checks are NEVER bypassed by fast-lane.

create table if not exists public.validated_regional_incidents (
    id                       uuid primary key default gen_random_uuid(),
    zone_id                  uuid not null references public.zones(id),
    trigger_family           text not null,
    incident_start           timestamptz not null,
    incident_end             timestamptz,
    validation_source        text not null check (
      validation_source in ('trusted_workers', 'admin', 'news_feed', 'public_api')
    ),
    confirming_worker_count  integer not null default 0,
    cluster_spike_detected   boolean not null default false,
    validated_at             timestamptz not null default now(),
    unique(zone_id, trigger_family, incident_start)
);

comment on table public.validated_regional_incidents is
  'Cache of validated regional incidents for fast-lane claim processing. '
  'Fast-lane reduces manual review but never bypasses individual fraud checks.';

comment on column public.validated_regional_incidents.cluster_spike_detected is
  'If true, fast-lane auto-release is paused and cluster-level validation '
  'is required to protect the liquidity pool.';

-- RLS: workers read-only, service role full access
alter table public.validated_regional_incidents enable row level security;

create policy "validated_incidents_select_authenticated"
  on public.validated_regional_incidents for select to authenticated
  using (true);

create policy "validated_incidents_manage_service"
  on public.validated_regional_incidents for all to service_role
  using (true) with check (true);

grant select on public.validated_regional_incidents to authenticated;
grant all   on public.validated_regional_incidents to service_role;


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §6  WORKER PHONE NUMBERS                                       │
-- └──────────────────────────────────────────────────────────────────┘
-- Add phone_number column and seed Indian +91 mobile numbers

alter table public.worker_profiles
  add column if not exists phone_number text;

comment on column public.worker_profiles.phone_number is
  'Worker mobile number for contact and WhatsApp notifications.';

-- Seed random 10-digit Indian mobile numbers for existing workers
-- who do not already have a phone number set.
update public.worker_profiles
  set phone_number = '+91' || (
    lpad(floor(random() * 10000000000)::bigint::text, 10, '0')
  )
  where phone_number is null;


-- ══════════════════════════════════════════════════════════════════════
-- Reload PostgREST schema cache so new tables/columns are visible
-- ══════════════════════════════════════════════════════════════════════
notify pgrst, 'reload schema';
