-- Covara Unified Enterprise Patch
-- Date: 2026-04-12
-- Purpose: Idempotent compatibility + security hardening for current Supabase schema
-- Apply in Supabase SQL editor as one script.

begin;

do $$
begin
  perform pg_advisory_xact_lock(hashtext('covara_unified_enterprise_patch_2026_04_12'));
end $$;

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Preflight guards
-- ---------------------------------------------------------------------------
do $$
begin
  if to_regclass('public.profiles') is null then
    raise exception 'Required table missing: public.profiles';
  end if;
  if to_regclass('public.worker_profiles') is null then
    raise exception 'Required table missing: public.worker_profiles';
  end if;
  if to_regclass('public.manual_claims') is null then
    raise exception 'Required table missing: public.manual_claims';
  end if;
  if to_regclass('public.payout_recommendations') is null then
    raise exception 'Required table missing: public.payout_recommendations';
  end if;
  if to_regclass('public.event_outbox') is null then
    raise exception 'Required table missing: public.event_outbox';
  end if;
  if to_regclass('public.event_consumer_ledger') is null then
    raise exception 'Required table missing: public.event_consumer_ledger';
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Helper function used by RLS policies
-- ---------------------------------------------------------------------------
create or replace function public.current_user_role()
returns text
language sql
stable
set search_path = public
as $$
  select p.role
  from public.profiles p
  where p.id = auth.uid()
  limit 1
$$;

grant execute on function public.current_user_role() to authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Compatibility table: policies
-- ---------------------------------------------------------------------------
create table if not exists public.policies (
  id uuid primary key default gen_random_uuid(),
  policy_id text unique not null,
  worker_profile_id uuid not null references public.worker_profiles(profile_id) on delete cascade,
  zone_id uuid references public.zones(id),
  plan_type text not null check (plan_type in ('essential', 'plus')),
  coverage_amount numeric(10,2) not null,
  premium_amount numeric(10,2) not null,
  status text not null check (status in ('active', 'expired', 'cancelled')),
  activated_at timestamptz not null default now(),
  valid_until timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_policies_worker_active
  on public.policies(worker_profile_id)
  where status = 'active';

-- ---------------------------------------------------------------------------
-- manual_claims compatibility columns and constraints
-- ---------------------------------------------------------------------------
alter table public.manual_claims
  add column if not exists assigned_reviewer_profile_id uuid references public.insurer_profiles(profile_id) on delete set null,
  add column if not exists assignment_state text,
  add column if not exists assigned_at timestamptz,
  add column if not exists review_due_at timestamptz,
  add column if not exists first_reviewed_at timestamptz,
  add column if not exists last_reviewed_at timestamptz,
  add column if not exists escalated_at timestamptz,
  add column if not exists escalation_reason text;

update public.manual_claims
set assignment_state = 'unassigned'
where assignment_state is null;

alter table public.manual_claims
  alter column assignment_state set default 'unassigned';

alter table public.manual_claims
  drop constraint if exists manual_claims_assignment_state_check;

alter table public.manual_claims
  add constraint manual_claims_assignment_state_check
  check (assignment_state in ('unassigned', 'assigned', 'in_review', 'escalated', 'resolved'));

create index if not exists idx_manual_claims_assigned_reviewer
  on public.manual_claims(assigned_reviewer_profile_id)
  where assigned_reviewer_profile_id is not null;

create index if not exists idx_manual_claims_review_due
  on public.manual_claims(review_due_at)
  where claim_status in ('submitted', 'soft_hold_verification', 'fraud_escalated_review');

create unique index if not exists idx_unique_worker_event
  on public.manual_claims(worker_profile_id, trigger_event_id)
  where trigger_event_id is not null
    and claim_status in ('approved', 'paid', 'auto_approved');

-- ---------------------------------------------------------------------------
-- Payout workflow tables
-- ---------------------------------------------------------------------------
create table if not exists public.payout_requests (
  id uuid primary key default gen_random_uuid(),
  claim_id uuid not null references public.manual_claims(id) on delete cascade,
  worker_profile_id uuid not null references public.worker_profiles(profile_id) on delete cascade,
  amount numeric(12,2) not null check (amount > 0),
  currency text not null default 'INR',
  payout_method text not null default 'upi',
  provider text not null default 'mock',
  provider_payout_id text,
  idempotency_key text not null,
  status text not null default 'initiated' check (
    status in ('initiated', 'submitted', 'processing', 'paid', 'failed', 'manual_review')
  ),
  failure_reason text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (claim_id),
  unique (idempotency_key)
);

do $$
begin
  -- Compatibility bridge when payout_requests already exists from legacy schema.
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'payout_requests' and column_name = 'created_at'
  ) then
    alter table public.payout_requests add column created_at timestamptz not null default now();
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'payout_requests' and column_name = 'provider'
  ) then
    alter table public.payout_requests add column provider text;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'payout_requests' and column_name = 'provider_payout_id'
  ) then
    alter table public.payout_requests add column provider_payout_id text;
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'payout_requests' and column_name = 'provider_key'
  ) then
    update public.payout_requests
    set provider = coalesce(provider, provider_key, 'mock')
    where provider is null;
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'payout_requests' and column_name = 'provider_reference_id'
  ) then
    update public.payout_requests
    set provider_payout_id = coalesce(provider_payout_id, provider_reference_id)
    where provider_payout_id is null;
  end if;
end $$;

create index if not exists idx_payout_requests_worker_status
  on public.payout_requests(worker_profile_id, status, created_at desc);

create index if not exists idx_payout_requests_provider_id
  on public.payout_requests(provider, provider_payout_id)
  where provider_payout_id is not null;

create table if not exists public.payout_settlement_events (
  id uuid primary key default gen_random_uuid(),
  payout_request_id uuid not null references public.payout_requests(id) on delete cascade,
  provider text not null,
  provider_event_id text not null,
  event_type text not null,
  event_time timestamptz,
  payload jsonb not null,
  signature_valid boolean,
  processed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (provider, provider_event_id)
);

do $$
begin
  -- Compatibility bridge when payout_settlement_events already exists from legacy schema.
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'payout_settlement_events' and column_name = 'created_at'
  ) then
    alter table public.payout_settlement_events add column created_at timestamptz not null default now();
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'payout_settlement_events' and column_name = 'received_at'
  ) then
    alter table public.payout_settlement_events add column received_at timestamptz;
    update public.payout_settlement_events
    set received_at = coalesce(received_at, created_at, processed_at, now())
    where received_at is null;
    alter table public.payout_settlement_events alter column received_at set default now();
    alter table public.payout_settlement_events alter column received_at set not null;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'payout_settlement_events' and column_name = 'provider'
  ) then
    alter table public.payout_settlement_events add column provider text;
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'payout_settlement_events' and column_name = 'provider_key'
  ) then
    update public.payout_settlement_events
    set provider = coalesce(provider, provider_key, 'mock')
    where provider is null;
  end if;
end $$;

create index if not exists idx_payout_settlement_events_request
  on public.payout_settlement_events(payout_request_id, created_at desc);

create table if not exists public.payout_status_transitions (
  id uuid primary key default gen_random_uuid(),
  payout_request_id uuid not null references public.payout_requests(id) on delete cascade,
  from_status text,
  to_status text not null,
  reason text,
  actor_profile_id uuid references public.profiles(id),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_payout_status_transitions_request
  on public.payout_status_transitions(payout_request_id, created_at desc);

create table if not exists public.kyc_verification_events (
  id uuid primary key default gen_random_uuid(),
  provider text not null default 'sandbox',
  verification_type text not null check (
    verification_type in (
      'otp_send',
      'otp_verify',
      'aadhaar_initiate',
      'aadhaar_verify',
      'bank_verify',
      'pan_verify'
    )
  ),
  actor_profile_id uuid references public.profiles(id) on delete set null,
  subject_ref text,
  reference_id text,
  provider_status_code integer,
  success boolean not null default false,
  verified boolean,
  request_meta jsonb not null default '{}'::jsonb,
  risk_flags jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_kyc_verification_events_created
  on public.kyc_verification_events(created_at desc);

create index if not exists idx_kyc_verification_events_type
  on public.kyc_verification_events(verification_type, created_at desc);

create index if not exists idx_kyc_verification_events_subject
  on public.kyc_verification_events(subject_ref);

-- ---------------------------------------------------------------------------
-- Event outbox + consumer ledger hardening
-- ---------------------------------------------------------------------------
alter table public.event_outbox
  add column if not exists dead_lettered_at timestamptz;

alter table public.event_outbox
  drop constraint if exists event_outbox_status_chk;

alter table public.event_outbox
  add constraint event_outbox_status_chk
  check (status in ('pending', 'failed', 'processed', 'dead_letter'));

create index if not exists idx_event_outbox_status_available
  on public.event_outbox(status, available_at, created_at);

create index if not exists idx_event_outbox_event_type
  on public.event_outbox(event_type, created_at desc);

create index if not exists idx_event_outbox_dead_letter
  on public.event_outbox(status, dead_lettered_at desc)
  where status = 'dead_letter';

-- Dedupe before enforcing unique constraint
with ranked as (
  select
    ctid,
    row_number() over (
      partition by consumer_name, event_id
      order by coalesce(last_attempt_at, first_seen_at) desc, id desc
    ) as rn
  from public.event_consumer_ledger
)
delete from public.event_consumer_ledger e
using ranked r
where e.ctid = r.ctid
  and r.rn > 1;

alter table public.event_consumer_ledger
  add column if not exists dead_lettered_at timestamptz;

alter table public.event_consumer_ledger
  drop constraint if exists event_consumer_ledger_status_chk;

alter table public.event_consumer_ledger
  add constraint event_consumer_ledger_status_chk
  check (status in ('processing', 'succeeded', 'failed', 'dead_letter'));

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'event_consumer_ledger_consumer_event_uniq'
      and conrelid = 'public.event_consumer_ledger'::regclass
  ) then
    alter table public.event_consumer_ledger
      add constraint event_consumer_ledger_consumer_event_uniq unique (consumer_name, event_id);
  end if;
end $$;

create index if not exists idx_event_consumer_ledger_status
  on public.event_consumer_ledger(status, first_seen_at);

create index if not exists idx_event_consumer_ledger_event
  on public.event_consumer_ledger(event_id);

create index if not exists idx_event_consumer_ledger_dead_letter
  on public.event_consumer_ledger(status, dead_lettered_at desc)
  where status = 'dead_letter';

-- ---------------------------------------------------------------------------
-- Coins + threshold query performance
-- ---------------------------------------------------------------------------
create index if not exists idx_coins_ledger_profile_created
  on public.coins_ledger(profile_id, created_at desc);

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'coins_ledger'
      and column_name = 'activity_type'
  ) then
    execute 'create index if not exists idx_coins_ledger_activity_type on public.coins_ledger(activity_type, created_at desc)';
  elsif exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'coins_ledger'
      and column_name = 'activity'
  ) then
    execute 'create index if not exists idx_coins_ledger_activity on public.coins_ledger(profile_id, activity, created_at desc)';
  end if;
end $$;

do $$
begin
  begin
    create or replace view public.driver_coin_balance as
    select
      cl.profile_id,
      coalesce(sum(cl.coins), 0)::int as balance,
      max(cl.created_at) as last_activity_at
    from public.coins_ledger cl
    group by cl.profile_id;
  exception
    when sqlstate '42P16' then
      -- Legacy view shape includes earned/redeemed counters and last_activity.
      -- Preserve that shape and append last_activity_at for forward compatibility.
      create or replace view public.driver_coin_balance as
      select
        cl.profile_id,
        coalesce(sum(cl.coins), 0) as balance,
        count(*) filter (where cl.coins > 0) as total_earned_txns,
        count(*) filter (where cl.coins < 0) as total_redeemed_txns,
        max(cl.created_at) as last_activity,
        max(cl.created_at) as last_activity_at
      from public.coins_ledger cl
      group by cl.profile_id;
  end;
end $$;

create unique index if not exists idx_zone_thresholds_lookup
  on public.zone_monthly_thresholds(zone_id, year_month, metric);

create index if not exists idx_zone_thresholds_expires
  on public.zone_monthly_thresholds(expires_at);

-- ---------------------------------------------------------------------------
-- Atomic claim persistence RPC (claim + recommendation + outbox)
-- ---------------------------------------------------------------------------
create or replace function public.persist_claim_with_outbox(
  p_claim jsonb,
  p_payout jsonb,
  p_event_type text,
  p_event_key text default null,
  p_event_source text default 'backend',
  p_event_payload jsonb default '{}'::jsonb
)
returns table (
  claim_id uuid,
  event_id uuid,
  duplicate_skipped boolean
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_claim_id uuid;
  v_event_id uuid := gen_random_uuid();
  v_constraint_name text;
begin
  begin
    insert into public.manual_claims (
      worker_profile_id,
      trigger_event_id,
      claim_mode,
      claim_reason,
      stated_lat,
      stated_lng,
      claimed_at,
      shift_id,
      claim_status,
      assignment_state,
      review_due_at
    )
    values (
      (p_claim ->> 'worker_profile_id')::uuid,
      nullif(p_claim ->> 'trigger_event_id', '')::uuid,
      coalesce(nullif(p_claim ->> 'claim_mode', ''), 'manual'),
      coalesce(nullif(p_claim ->> 'claim_reason', ''), 'Claim submitted'),
      nullif(p_claim ->> 'stated_lat', '')::numeric,
      nullif(p_claim ->> 'stated_lng', '')::numeric,
      coalesce(nullif(p_claim ->> 'claimed_at', '')::timestamptz, now()),
      nullif(p_claim ->> 'shift_id', '')::uuid,
      coalesce(nullif(p_claim ->> 'claim_status', ''), 'submitted'),
      coalesce(nullif(p_claim ->> 'assignment_state', ''), 'unassigned'),
      nullif(p_claim ->> 'review_due_at', '')::timestamptz
    )
    returning id into v_claim_id;
  exception when unique_violation then
    get stacked diagnostics v_constraint_name = constraint_name;

    if coalesce(p_claim ->> 'claim_mode', '') = 'trigger_auto'
       and (
         coalesce(v_constraint_name, '') ilike '%idx_unique_worker_event%'
         or coalesce(v_constraint_name, '') ilike '%worker_profile_id%trigger_event%'
       )
    then
      return query
      select null::uuid, null::uuid, true;
      return;
    end if;

    raise;
  end;

  insert into public.payout_recommendations (
    claim_id,
    covered_weekly_income_b,
    claim_probability_p,
    severity_score_s,
    exposure_score_e,
    confidence_score_c,
    fraud_holdback_fh,
    outlier_uplift_u,
    payout_cap,
    expected_payout,
    gross_premium,
    recommended_payout,
    explanation_json,
    created_at
  )
  values (
    v_claim_id,
    coalesce(nullif(p_payout ->> 'covered_weekly_income_b', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'claim_probability_p', '')::numeric, 0.15),
    coalesce(nullif(p_payout ->> 'severity_score_s', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'exposure_score_e', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'confidence_score_c', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'fraud_holdback_fh', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'outlier_uplift_u', '')::numeric, 1.0),
    coalesce(nullif(p_payout ->> 'payout_cap', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'expected_payout', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'gross_premium', '')::numeric, 0),
    coalesce(nullif(p_payout ->> 'recommended_payout', '')::numeric, 0),
    coalesce(p_payout -> 'explanation_json', '{}'::jsonb),
    coalesce(nullif(p_payout ->> 'created_at', '')::timestamptz, now())
  );

  insert into public.event_outbox (
    event_id,
    event_type,
    event_key,
    event_source,
    event_payload,
    status,
    retry_count,
    available_at,
    created_at
  )
  values (
    v_event_id,
    p_event_type,
    p_event_key,
    coalesce(nullif(p_event_source, ''), 'backend'),
    coalesce(p_event_payload, '{}'::jsonb) || jsonb_build_object('claim_id', v_claim_id),
    'pending',
    0,
    now(),
    now()
  );

  return query
  select v_claim_id, v_event_id, false;
end;
$$;

grant execute on function public.persist_claim_with_outbox(
  jsonb,
  jsonb,
  text,
  text,
  text,
  jsonb
) to authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Row-level security and policies
-- ---------------------------------------------------------------------------
alter table public.policies enable row level security;
alter table public.claim_reviews enable row level security;
alter table public.insurer_profiles enable row level security;
alter table public.payout_requests enable row level security;
alter table public.payout_settlement_events enable row level security;
alter table public.payout_status_transitions enable row level security;
alter table public.kyc_verification_events enable row level security;
alter table public.event_outbox enable row level security;
alter table public.event_consumer_ledger enable row level security;
alter table public.coins_ledger enable row level security;
alter table public.zone_monthly_thresholds enable row level security;
alter table public.disruption_events enable row level security;
alter table public.validated_regional_incidents enable row level security;

-- policies table

drop policy if exists policies_worker_select_own on public.policies;
create policy policies_worker_select_own
  on public.policies
  for select
  to authenticated
  using (worker_profile_id = auth.uid());

drop policy if exists policies_worker_insert_own on public.policies;
create policy policies_worker_insert_own
  on public.policies
  for insert
  to authenticated
  with check (worker_profile_id = auth.uid());

drop policy if exists policies_worker_update_own on public.policies;
create policy policies_worker_update_own
  on public.policies
  for update
  to authenticated
  using (worker_profile_id = auth.uid())
  with check (worker_profile_id = auth.uid());

drop policy if exists policies_admin_select_all on public.policies;
create policy policies_admin_select_all
  on public.policies
  for select
  to authenticated
  using (public.current_user_role() = 'admin');

drop policy if exists policies_admin_update_all on public.policies;
create policy policies_admin_update_all
  on public.policies
  for update
  to authenticated
  using (public.current_user_role() = 'admin')
  with check (public.current_user_role() = 'admin');

drop policy if exists policies_service_manage on public.policies;
create policy policies_service_manage
  on public.policies
  for all
  to service_role
  using (true)
  with check (true);

-- insurer_profiles

drop policy if exists insurer_profiles_select_own on public.insurer_profiles;
create policy insurer_profiles_select_own
  on public.insurer_profiles
  for select
  to authenticated
  using (profile_id = auth.uid());

drop policy if exists insurer_profiles_insert_own on public.insurer_profiles;
create policy insurer_profiles_insert_own
  on public.insurer_profiles
  for insert
  to authenticated
  with check (profile_id = auth.uid());

drop policy if exists insurer_profiles_update_own on public.insurer_profiles;
create policy insurer_profiles_update_own
  on public.insurer_profiles
  for update
  to authenticated
  using (profile_id = auth.uid())
  with check (profile_id = auth.uid());

drop policy if exists insurer_profiles_admin_select_all on public.insurer_profiles;
create policy insurer_profiles_admin_select_all
  on public.insurer_profiles
  for select
  to authenticated
  using (public.current_user_role() = 'admin');

drop policy if exists insurer_profiles_admin_update_all on public.insurer_profiles;
create policy insurer_profiles_admin_update_all
  on public.insurer_profiles
  for update
  to authenticated
  using (public.current_user_role() = 'admin')
  with check (public.current_user_role() = 'admin');

drop policy if exists insurer_profiles_service_manage on public.insurer_profiles;
create policy insurer_profiles_service_manage
  on public.insurer_profiles
  for all
  to service_role
  using (true)
  with check (true);

-- claim_reviews

drop policy if exists claim_reviews_admin_read on public.claim_reviews;
create policy claim_reviews_admin_read
  on public.claim_reviews
  for select
  to authenticated
  using (public.current_user_role() = 'admin');

drop policy if exists claim_reviews_admin_write on public.claim_reviews;
create policy claim_reviews_admin_write
  on public.claim_reviews
  for insert
  to authenticated
  with check (public.current_user_role() = 'admin');

drop policy if exists claim_reviews_service_manage on public.claim_reviews;
create policy claim_reviews_service_manage
  on public.claim_reviews
  for all
  to service_role
  using (true)
  with check (true);

-- payout_requests

drop policy if exists payout_requests_worker_read_own on public.payout_requests;
create policy payout_requests_worker_read_own
  on public.payout_requests
  for select
  to authenticated
  using (worker_profile_id = auth.uid());

drop policy if exists payout_requests_admin_read_all on public.payout_requests;
create policy payout_requests_admin_read_all
  on public.payout_requests
  for select
  to authenticated
  using (public.current_user_role() = 'admin');

drop policy if exists payout_requests_service_manage on public.payout_requests;
create policy payout_requests_service_manage
  on public.payout_requests
  for all
  to service_role
  using (true)
  with check (true);

-- payout_settlement_events

drop policy if exists payout_settlement_events_worker_read_own on public.payout_settlement_events;
create policy payout_settlement_events_worker_read_own
  on public.payout_settlement_events
  for select
  to authenticated
  using (
    exists (
      select 1
      from public.payout_requests pr
      where pr.id = payout_request_id
        and pr.worker_profile_id = auth.uid()
    )
  );

drop policy if exists payout_settlement_events_admin_read_all on public.payout_settlement_events;
create policy payout_settlement_events_admin_read_all
  on public.payout_settlement_events
  for select
  to authenticated
  using (public.current_user_role() = 'admin');

drop policy if exists payout_settlement_events_service_manage on public.payout_settlement_events;
create policy payout_settlement_events_service_manage
  on public.payout_settlement_events
  for all
  to service_role
  using (true)
  with check (true);

-- payout_status_transitions

drop policy if exists payout_status_transitions_worker_read_own on public.payout_status_transitions;
create policy payout_status_transitions_worker_read_own
  on public.payout_status_transitions
  for select
  to authenticated
  using (
    exists (
      select 1
      from public.payout_requests pr
      where pr.id = payout_request_id
        and pr.worker_profile_id = auth.uid()
    )
  );

drop policy if exists payout_status_transitions_admin_read_all on public.payout_status_transitions;
create policy payout_status_transitions_admin_read_all
  on public.payout_status_transitions
  for select
  to authenticated
  using (public.current_user_role() = 'admin');

drop policy if exists payout_status_transitions_service_manage on public.payout_status_transitions;
create policy payout_status_transitions_service_manage
  on public.payout_status_transitions
  for all
  to service_role
  using (true)
  with check (true);

-- kyc_verification_events

drop policy if exists kyc_verification_events_admin_read_all on public.kyc_verification_events;
create policy kyc_verification_events_admin_read_all
  on public.kyc_verification_events
  for select
  to authenticated
  using (public.current_user_role() in ('admin', 'insurer_admin'));

drop policy if exists kyc_verification_events_service_manage on public.kyc_verification_events;
create policy kyc_verification_events_service_manage
  on public.kyc_verification_events
  for all
  to service_role
  using (true)
  with check (true);

-- event_outbox

drop policy if exists event_outbox_admin_read_all on public.event_outbox;
create policy event_outbox_admin_read_all
  on public.event_outbox
  for select
  to authenticated
  using (public.current_user_role() = 'admin');

drop policy if exists event_outbox_service_manage on public.event_outbox;
create policy event_outbox_service_manage
  on public.event_outbox
  for all
  to service_role
  using (true)
  with check (true);

-- event_consumer_ledger

drop policy if exists event_consumer_ledger_admin_read_all on public.event_consumer_ledger;
create policy event_consumer_ledger_admin_read_all
  on public.event_consumer_ledger
  for select
  to authenticated
  using (public.current_user_role() = 'admin');

drop policy if exists event_consumer_ledger_service_manage on public.event_consumer_ledger;
create policy event_consumer_ledger_service_manage
  on public.event_consumer_ledger
  for all
  to service_role
  using (true)
  with check (true);

-- coins_ledger

drop policy if exists coins_ledger_read_own on public.coins_ledger;
create policy coins_ledger_read_own
  on public.coins_ledger
  for select
  to authenticated
  using (profile_id = auth.uid());

drop policy if exists coins_ledger_admin_read_all on public.coins_ledger;
create policy coins_ledger_admin_read_all
  on public.coins_ledger
  for select
  to authenticated
  using (public.current_user_role() = 'admin');

drop policy if exists coins_ledger_service_manage on public.coins_ledger;
create policy coins_ledger_service_manage
  on public.coins_ledger
  for all
  to service_role
  using (true)
  with check (true);

-- zone_monthly_thresholds

drop policy if exists zone_thresholds_read_authenticated on public.zone_monthly_thresholds;
create policy zone_thresholds_read_authenticated
  on public.zone_monthly_thresholds
  for select
  to authenticated
  using (true);

drop policy if exists zone_thresholds_service_manage on public.zone_monthly_thresholds;
create policy zone_thresholds_service_manage
  on public.zone_monthly_thresholds
  for all
  to service_role
  using (true)
  with check (true);

-- disruption_events

drop policy if exists disruption_events_read_scoped on public.disruption_events;
create policy disruption_events_read_scoped
  on public.disruption_events
  for select
  to authenticated
  using (
    public.current_user_role() = 'admin'
    or zone_id in (
      select wp.preferred_zone_id
      from public.worker_profiles wp
      where wp.profile_id = auth.uid()
    )
  );

drop policy if exists disruption_events_service_manage on public.disruption_events;
create policy disruption_events_service_manage
  on public.disruption_events
  for all
  to service_role
  using (true)
  with check (true);

-- validated_regional_incidents

drop policy if exists validated_regional_incidents_read_scoped on public.validated_regional_incidents;
create policy validated_regional_incidents_read_scoped
  on public.validated_regional_incidents
  for select
  to authenticated
  using (
    public.current_user_role() = 'admin'
    or zone_id in (
      select wp.preferred_zone_id
      from public.worker_profiles wp
      where wp.profile_id = auth.uid()
    )
  );

drop policy if exists validated_regional_incidents_service_manage on public.validated_regional_incidents;
create policy validated_regional_incidents_service_manage
  on public.validated_regional_incidents
  for all
  to service_role
  using (true)
  with check (true);

-- ---------------------------------------------------------------------------
-- Grants/revokes
-- ---------------------------------------------------------------------------
revoke all on table public.payout_requests from anon;
revoke all on table public.payout_settlement_events from anon;
revoke all on table public.payout_status_transitions from anon;
revoke all on table public.event_outbox from anon;
revoke all on table public.event_consumer_ledger from anon;
revoke all on table public.coins_ledger from anon;
revoke all on table public.policies from anon;
revoke all on table public.kyc_verification_events from anon;

grant select on public.policies to authenticated;
grant insert, update on public.policies to authenticated;
grant all on public.policies to service_role;

grant select on public.payout_requests to authenticated;
grant select on public.payout_settlement_events to authenticated;
grant select on public.payout_status_transitions to authenticated;
grant all on public.payout_requests to service_role;
grant all on public.payout_settlement_events to service_role;
grant all on public.payout_status_transitions to service_role;

grant select on public.kyc_verification_events to authenticated;
grant all on public.kyc_verification_events to service_role;

grant select on public.event_outbox to authenticated;
grant select on public.event_consumer_ledger to authenticated;
grant all on public.event_outbox to service_role;
grant all on public.event_consumer_ledger to service_role;

grant select on public.coins_ledger to authenticated;
grant all on public.coins_ledger to service_role;

grant select on public.driver_coin_balance to authenticated;
grant select on public.driver_coin_balance to service_role;

grant select on public.zone_monthly_thresholds to authenticated;
grant all on public.zone_monthly_thresholds to service_role;

-- Force PostgREST schema cache refresh
notify pgrst, 'reload schema';

commit;
