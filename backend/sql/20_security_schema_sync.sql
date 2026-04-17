-- ============================================================
-- 20_security_schema_sync.sql
-- Covara One — Security + Schema Sync Patch
--
-- Run after 00_unified_migration.sql on existing environments.
-- Idempotent and safe to re-run.
-- ============================================================

-- Ensure internal operational source mapping exists.
insert into public.reference_sources (
  ref_id,
  source_name,
  source_type,
  what_it_provides,
  use_in_project,
  link
)
values (
  'R11',
  'Covara Internal Operational Signals',
  'internal',
  'Internal traffic, outage, and demand operations signals',
  'Operational trigger source mapping for traffic/outage style events',
  'https://covara.one/docs/internal-operational-signals'
)
on conflict (ref_id) do nothing;

-- Backfill invalid source_ref values used by old trigger evaluator behavior.
update public.trigger_events
set source_ref_id = 'R11'
where source_ref_id = 'internal';

-- Enforce private evidence bucket default posture.
update storage.buckets
set public = false
where id = 'claim-evidence';

-- Encourage strict positive payout amounts for all new writes.
do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'payout_requests_amount_positive_check'
  ) then
    alter table public.payout_requests
      add constraint payout_requests_amount_positive_check
      check (amount > 0) not valid;
  end if;
end $$;

-- Default trust score for new worker profiles.
alter table public.worker_profiles
  alter column trust_score set default 0.75;

-- Ensure manual claims have an updated_at timestamp and mutation trigger.
alter table public.manual_claims
  add column if not exists updated_at timestamptz not null default now();

create or replace function public.set_manual_claims_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_manual_claims_updated_at on public.manual_claims;

create trigger trg_manual_claims_updated_at
before update on public.manual_claims
for each row
execute function public.set_manual_claims_updated_at();

-- Keep worker claim-history queries fast.
create index if not exists idx_manual_claims_worker_profile
  on public.manual_claims(worker_profile_id);

notify pgrst, 'reload schema';
