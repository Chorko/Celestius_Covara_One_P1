-- ============================================================
-- 22_rule_model_version_governance.sql
-- Covara One — RuleOps / ModelOps Version Governance
--
-- Goals:
-- 1) Add registry tables for rule/model versions.
-- 2) Persist version IDs with claims and review decisions.
-- 3) Support controlled full/canary/cohort rollout metadata.
-- ============================================================

set statement_timeout = '0';
set lock_timeout = '10s';
set idle_in_transaction_session_timeout = '0';

begin;

create table if not exists public.rule_versions (
  id uuid primary key default gen_random_uuid(),
  version_key text not null unique,
  description text,
  status text not null default 'draft' check (status in ('draft', 'active', 'canary', 'retired')),
  rollout_mode text not null default 'full' check (rollout_mode in ('full', 'canary', 'cohort')),
  rollout_percentage integer not null default 100 check (rollout_percentage >= 0 and rollout_percentage <= 100),
  cohort_key text,
  cohort_salt text not null default 'covara-rule-rollout',
  priority integer not null default 0,
  is_active boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  activated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.model_versions (
  id uuid primary key default gen_random_uuid(),
  version_key text not null unique,
  model_family text not null default 'fraud',
  description text,
  status text not null default 'draft' check (status in ('draft', 'active', 'canary', 'retired')),
  rollout_mode text not null default 'full' check (rollout_mode in ('full', 'canary', 'cohort')),
  rollout_percentage integer not null default 100 check (rollout_percentage >= 0 and rollout_percentage <= 100),
  cohort_key text,
  cohort_salt text not null default 'covara-model-rollout',
  priority integer not null default 0,
  is_active boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  activated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_rule_versions_active
  on public.rule_versions(is_active, status, priority desc);

create index if not exists idx_model_versions_active
  on public.model_versions(is_active, status, priority desc);

create or replace function public.touch_updated_at_column()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_rule_versions_updated_at on public.rule_versions;
create trigger trg_rule_versions_updated_at
before update on public.rule_versions
for each row execute function public.touch_updated_at_column();

drop trigger if exists trg_model_versions_updated_at on public.model_versions;
create trigger trg_model_versions_updated_at
before update on public.model_versions
for each row execute function public.touch_updated_at_column();

alter table public.manual_claims
  add column if not exists rule_version_id uuid references public.rule_versions(id) on delete set null,
  add column if not exists model_version_id uuid references public.model_versions(id) on delete set null;

alter table public.claim_reviews
  add column if not exists rule_version_id uuid references public.rule_versions(id) on delete set null,
  add column if not exists model_version_id uuid references public.model_versions(id) on delete set null;

create index if not exists idx_manual_claims_rule_version
  on public.manual_claims(rule_version_id, claimed_at desc);

create index if not exists idx_manual_claims_model_version
  on public.manual_claims(model_version_id, claimed_at desc);

create index if not exists idx_claim_reviews_rule_version
  on public.claim_reviews(rule_version_id, reviewed_at desc);

create index if not exists idx_claim_reviews_model_version
  on public.claim_reviews(model_version_id, reviewed_at desc);

alter table public.rule_versions enable row level security;
alter table public.model_versions enable row level security;

drop policy if exists "rule_versions_select_active_or_admin" on public.rule_versions;
create policy "rule_versions_select_active_or_admin"
on public.rule_versions
for select to authenticated
using (is_active = true or public.current_user_role() = 'insurer_admin');

drop policy if exists "rule_versions_service_manage" on public.rule_versions;
create policy "rule_versions_service_manage"
on public.rule_versions
for all to service_role
using (true)
with check (true);

drop policy if exists "model_versions_select_active_or_admin" on public.model_versions;
create policy "model_versions_select_active_or_admin"
on public.model_versions
for select to authenticated
using (is_active = true or public.current_user_role() = 'insurer_admin');

drop policy if exists "model_versions_service_manage" on public.model_versions;
create policy "model_versions_service_manage"
on public.model_versions
for all to service_role
using (true)
with check (true);

insert into public.rule_versions (
  version_key,
  description,
  status,
  rollout_mode,
  rollout_percentage,
  priority,
  is_active,
  metadata,
  activated_at
)
values (
  'ruleset_2026_04_12',
  'Baseline ruleset aligned to enterprise patch rollout (Apr 2026).',
  'active',
  'full',
  100,
  0,
  false,
  '{"origin":"migration_22","type":"baseline"}'::jsonb,
  now()
)
on conflict (version_key) do nothing;

insert into public.model_versions (
  version_key,
  model_family,
  description,
  status,
  rollout_mode,
  rollout_percentage,
  priority,
  is_active,
  metadata,
  activated_at
)
values (
  'fraud_model_heuristic_v1',
  'fraud',
  'Baseline heuristic+ML hybrid fraud model context.',
  'active',
  'full',
  100,
  0,
  false,
  '{"origin":"migration_22","type":"baseline"}'::jsonb,
  now()
)
on conflict (version_key) do nothing;

-- Ensure at least one active row per registry.
update public.rule_versions
set is_active = true,
    status = 'active',
    rollout_mode = 'full',
    rollout_percentage = 100,
    activated_at = now()
where id = (
  select id
  from public.rule_versions
  where version_key = 'ruleset_2026_04_12'
  order by created_at asc
  limit 1
)
and not exists (
  select 1
  from public.rule_versions
  where is_active = true
    and status in ('active', 'canary')
);

update public.model_versions
set is_active = true,
    status = 'active',
    rollout_mode = 'full',
    rollout_percentage = 100,
    activated_at = now()
where id = (
  select id
  from public.model_versions
  where version_key = 'fraud_model_heuristic_v1'
  order by created_at asc
  limit 1
)
and not exists (
  select 1
  from public.model_versions
  where is_active = true
    and status in ('active', 'canary')
);

with active_rule as (
  select id
  from public.rule_versions
  where is_active = true
    and status in ('active', 'canary')
  order by priority desc, activated_at desc nulls last, created_at desc
  limit 1
), active_model as (
  select id
  from public.model_versions
  where is_active = true
    and status in ('active', 'canary')
  order by priority desc, activated_at desc nulls last, created_at desc
  limit 1
)
update public.manual_claims mc
set rule_version_id = coalesce(mc.rule_version_id, (select id from active_rule)),
    model_version_id = coalesce(mc.model_version_id, (select id from active_model))
where mc.rule_version_id is null
   or mc.model_version_id is null;

update public.claim_reviews cr
set rule_version_id = coalesce(cr.rule_version_id, mc.rule_version_id),
    model_version_id = coalesce(cr.model_version_id, mc.model_version_id)
from public.manual_claims mc
where cr.claim_id = mc.id
  and (cr.rule_version_id is null or cr.model_version_id is null);

-- Update atomic persistence RPC so claim insert path stores version IDs.
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
      review_due_at,
      rule_version_id,
      model_version_id
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
      nullif(p_claim ->> 'review_due_at', '')::timestamptz,
      nullif(p_claim ->> 'rule_version_id', '')::uuid,
      nullif(p_claim ->> 'model_version_id', '')::uuid
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

commit;

notify pgrst, 'reload schema';
