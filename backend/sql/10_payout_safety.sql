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

-- 2. Add disruption_event_id to manual_claims for idempotent payout tracking
--    This links each claim to the canonical disruption event identity,
--    ensuring that even if the same trigger re-fires, only one payout
--    is issued per worker per disruption window.
alter table public.manual_claims
    add column if not exists disruption_event_id uuid
        references public.disruption_events(id) on delete set null;

comment on column public.manual_claims.disruption_event_id is
  'FK to disruption_events.id. Used for idempotent payout enforcement: '
  'one approved/paid claim per worker per disruption event window, '
  'regardless of how many trigger_events fired for the same window.';

-- 3. Worker-event uniqueness: one approved/paid payout per worker per event
--    Keyed on disruption_event_id (not trigger_event_id) to handle re-fires:
--    multiple trigger_events can map to the same disruption window.
--    This is a partial unique index: only enforced for successful claim states.
drop index if exists public.idx_unique_worker_event;

create unique index if not exists idx_unique_worker_disruption_event
    on public.manual_claims(worker_profile_id, disruption_event_id)
    where claim_status in ('approved', 'paid', 'auto_approved')
      and disruption_event_id is not null;

comment on index public.idx_unique_worker_disruption_event is
  'Ensures one payout per worker per disruption event window. '
  'Uses disruption_event_id (not trigger_event_id) to handle trigger re-fires. '
  'Only applies to approved/paid/auto_approved claims with a linked event.';

-- 3. Enable RLS and add least-privilege policies
alter table public.disruption_events enable row level security;

-- Admins can perform all operations
drop policy if exists "DisruptionEvents: Admins can read all" on public.disruption_events;
drop policy if exists "DisruptionEvents: Admins can insert" on public.disruption_events;
drop policy if exists "DisruptionEvents: Admins can update" on public.disruption_events;
drop policy if exists "DisruptionEvents: Authenticated can read" on public.disruption_events;

create policy "DisruptionEvents: Admins can read all"
on public.disruption_events
for select
to authenticated
using (public.current_user_role() = 'insurer_admin');

create policy "DisruptionEvents: Admins can insert"
on public.disruption_events
for insert
to authenticated
with check (public.current_user_role() = 'insurer_admin');

create policy "DisruptionEvents: Admins can update"
on public.disruption_events
for update
to authenticated
using (public.current_user_role() = 'insurer_admin');

-- Workers can read validated disruption events (for claim eligibility checks)
create policy "DisruptionEvents: Authenticated can read validated"
on public.disruption_events
for select
to authenticated
using (validated = true);

-- 4. Grant access to new table (RLS enforces row-level restrictions)
grant select, insert, update, delete
  on public.disruption_events to authenticated;

-- Reload PostgREST schema cache
notify pgrst, 'reload schema';
