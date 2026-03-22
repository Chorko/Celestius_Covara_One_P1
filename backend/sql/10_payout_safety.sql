-- ══════════════════════════════════════════════════════════════════════
-- DEVTrails — Payout Safety & Idempotency (Gap §4.1)
-- ══════════════════════════════════════════════════════════════════════
-- Purpose:
--   Prevent duplicate payouts via event_id uniqueness and worker-event
--   constraints. Each disruption window gets a deterministic event_id
--   so that retries and duplicate trigger-firings never produce
--   repeated payouts for the same worker + event.
-- ══════════════════════════════════════════════════════════════════════

-- 1. Disruption event identity table
create table if not exists public.disruption_events (
    id uuid primary key default gen_random_uuid(),
    -- Deterministic event ID: hash(zone_id + trigger_family + window_start)
    event_id text unique not null,
    zone_id uuid references public.zones(id),
    trigger_family text not null,
    window_start timestamptz not null,
    window_end timestamptz,
    validated boolean not null default false,
    created_at timestamptz not null default now()
);

comment on table public.disruption_events is
  'Unique disruption event identity for idempotent payout execution. '
  'event_id is deterministic: zone_id + trigger_family + window_start.';

comment on column public.disruption_events.event_id is
  'Deterministic unique identifier: prevents the same disruption window '
  'from generating multiple event records.';

-- 2. Worker-event uniqueness: one approved/paid payout per worker per event
--    This is a partial unique index: only enforced for successful claim states.
create unique index if not exists idx_unique_worker_event
    on public.manual_claims(worker_profile_id, trigger_event_id)
    where claim_status in ('approved', 'paid', 'auto_approved');

comment on index public.idx_unique_worker_event is
  'Ensures one payout per worker per trigger event. '
  'Only applies to approved/paid/auto_approved claims.';

-- 3. Grant access to new table
grant select, insert, update, delete
  on public.disruption_events to authenticated;
grant select on public.disruption_events to anon;

-- Reload PostgREST schema cache
notify pgrst, 'reload schema';
