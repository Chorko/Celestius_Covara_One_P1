-- ============================================================================
-- Covara One - Migration 15
-- Payout provider abstraction persistence + settlement webhook idempotency
-- ============================================================================

create table if not exists public.payout_requests (
    id uuid primary key default gen_random_uuid(),
    claim_id uuid not null references public.manual_claims(id) on delete cascade,
    worker_profile_id uuid not null references public.worker_profiles(profile_id) on delete cascade,
    payout_recommendation_id uuid references public.payout_recommendations(id) on delete set null,
    amount numeric(10,2) not null check (amount >= 0),
    currency text not null default 'INR',
    provider_key text not null,
    provider_reference_id text,
    correlation_id text not null,
    idempotency_key text not null,
    status text not null default 'initiated' check (
      status in ('initiated','pending','processing','settled','failed','reversed','cancelled','manual_review')
    ),
    failure_code text,
    failure_reason text,
    retry_count integer not null default 0,
    next_retry_at timestamptz,
    initiated_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    settled_at timestamptz,
    initiated_by_profile_id uuid references public.profiles(id) on delete set null,
    initiation_source text,
    metadata jsonb not null default '{}'::jsonb,
    unique (claim_id),
    unique (idempotency_key)
);

create unique index if not exists idx_payout_requests_provider_reference
  on public.payout_requests(provider_key, provider_reference_id)
  where provider_reference_id is not null;

create index if not exists idx_payout_requests_status
  on public.payout_requests(status, next_retry_at, updated_at desc);

create table if not exists public.payout_settlement_events (
    id uuid primary key default gen_random_uuid(),
    payout_request_id uuid references public.payout_requests(id) on delete set null,
    provider_key text not null,
    provider_event_id text not null,
    provider_reference_id text,
    event_type text not null,
    signature_valid boolean not null default false,
    processing_status text not null default 'received' check (
      processing_status in ('received','processed','duplicate','rejected','failed')
    ),
    error_message text,
    payload jsonb not null default '{}'::jsonb,
    payload_hash text,
    source_ip text,
    received_at timestamptz not null default now(),
    processed_at timestamptz,
    unique (provider_key, provider_event_id)
);

create index if not exists idx_payout_settlement_events_request
  on public.payout_settlement_events(payout_request_id, received_at desc);

create table if not exists public.payout_status_transitions (
    id uuid primary key default gen_random_uuid(),
    payout_request_id uuid not null references public.payout_requests(id) on delete cascade,
    previous_status text,
    new_status text not null,
    transition_reason text,
    actor_type text not null default 'system' check (
      actor_type in ('system','provider_webhook','admin')
    ),
    actor_profile_id uuid references public.profiles(id) on delete set null,
    transition_metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_payout_status_transitions_request
  on public.payout_status_transitions(payout_request_id, created_at);

alter table public.payout_requests enable row level security;
alter table public.payout_settlement_events enable row level security;
alter table public.payout_status_transitions enable row level security;

drop policy if exists "Payout Requests: Workers can read own" on public.payout_requests;
drop policy if exists "Payout Requests: Admins can read all" on public.payout_requests;
drop policy if exists "Payout Requests: Service manage" on public.payout_requests;
drop policy if exists "Payout Settlements: Workers can read own" on public.payout_settlement_events;
drop policy if exists "Payout Settlements: Admins can read all" on public.payout_settlement_events;
drop policy if exists "Payout Settlements: Service manage" on public.payout_settlement_events;
drop policy if exists "Payout Transitions: Workers can read own" on public.payout_status_transitions;
drop policy if exists "Payout Transitions: Admins can read all" on public.payout_status_transitions;
drop policy if exists "Payout Transitions: Service manage" on public.payout_status_transitions;

create policy "Payout Requests: Workers can read own" on public.payout_requests for select to authenticated using (worker_profile_id = auth.uid());
create policy "Payout Requests: Admins can read all" on public.payout_requests for select to authenticated using (public.current_user_role() = 'insurer_admin');
create policy "Payout Requests: Service manage" on public.payout_requests for all to service_role using (true) with check (true);

create policy "Payout Settlements: Workers can read own" on public.payout_settlement_events for select to authenticated using (
  payout_request_id in (
    select id from public.payout_requests where worker_profile_id = auth.uid()
  )
);
create policy "Payout Settlements: Admins can read all" on public.payout_settlement_events for select to authenticated using (public.current_user_role() = 'insurer_admin');
create policy "Payout Settlements: Service manage" on public.payout_settlement_events for all to service_role using (true) with check (true);

create policy "Payout Transitions: Workers can read own" on public.payout_status_transitions for select to authenticated using (
  payout_request_id in (
    select id from public.payout_requests where worker_profile_id = auth.uid()
  )
);
create policy "Payout Transitions: Admins can read all" on public.payout_status_transitions for select to authenticated using (public.current_user_role() = 'insurer_admin');
create policy "Payout Transitions: Service manage" on public.payout_status_transitions for all to service_role using (true) with check (true);

grant select on public.payout_requests to authenticated;
grant select on public.payout_settlement_events to authenticated;
grant select on public.payout_status_transitions to authenticated;

grant all on public.payout_requests to service_role;
grant all on public.payout_settlement_events to service_role;
grant all on public.payout_status_transitions to service_role;
