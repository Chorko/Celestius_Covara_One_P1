-- ============================================================================
-- 23_reset_demo9_runtime_state.sql
--
-- Purpose:
--   Reset DEMO9 workers to a clean post-seed runtime baseline after demos/tests.
--
-- What it resets:
--   - Claim/payout runtime artifacts for DEMO9 workers
--   - Stripe checkout audit rows for DEMO9 workers
--   - Coins ledger for DEMO9 workers
--   - Reapplies baseline worker profile trust/KYC posture
--   - Reapplies baseline active Essential policies
--
-- What it does NOT reset:
--   - auth.users / profiles identities (kept intact)
--
-- Usage:
--   Run entire file in Supabase SQL Editor after test runs.
-- ============================================================================

begin;

create temporary table if not exists tmp_demo9_reset_seed (
  email text primary key,
  policy_id text not null,
  platform_name text not null,
  city text not null,
  vehicle_type text not null,
  avg_hourly_income_inr numeric(10,2) not null,
  bank_verified boolean not null,
  trust_score numeric(4,2) not null,
  gps_consent boolean not null
) on commit drop;

truncate tmp_demo9_reset_seed;
insert into tmp_demo9_reset_seed (
  email,
  policy_id,
  platform_name,
  city,
  vehicle_type,
  avg_hourly_income_inr,
  bank_verified,
  trust_score,
  gps_consent
)
values
  ('demo.auto01@synthetic.covara.dev',   'POL-DEMO9-AUTO01',   'Swiggy',  'Mumbai', 'Bike',    120.00, true, 0.94, true),
  ('demo.auto02@synthetic.covara.dev',   'POL-DEMO9-AUTO02',   'Zomato',  'Mumbai', 'Scooter', 112.00, true, 0.91, true),
  ('demo.auto03@synthetic.covara.dev',   'POL-DEMO9-AUTO03',   'Zepto',   'Mumbai', 'Bike',    105.00, true, 0.89, true),
  ('demo.review01@synthetic.covara.dev', 'POL-DEMO9-REVIEW01', 'Swiggy',  'Mumbai', 'Bike',     98.00, true, 0.72, true),
  ('demo.review02@synthetic.covara.dev', 'POL-DEMO9-REVIEW02', 'Blinkit', 'Mumbai', 'Scooter',  92.00, true, 0.68, true),
  ('demo.review03@synthetic.covara.dev', 'POL-DEMO9-REVIEW03', 'Porter',  'Mumbai', 'Bike',     88.00, true, 0.64, false),
  ('demo.fraud01@synthetic.covara.dev',  'POL-DEMO9-FRAUD01',  'Swiggy',  'Mumbai', 'Bike',     90.00, false, 0.42, false),
  ('demo.fraud02@synthetic.covara.dev',  'POL-DEMO9-FRAUD02',  'Zomato',  'Mumbai', 'Scooter',  86.00, false, 0.36, false),
  ('demo.fraud03@synthetic.covara.dev',  'POL-DEMO9-FRAUD03',  'Blinkit', 'Mumbai', 'Cycle',    82.00, false, 0.31, false)
on conflict (email) do update
set policy_id = excluded.policy_id,
    platform_name = excluded.platform_name,
    city = excluded.city,
    vehicle_type = excluded.vehicle_type,
    avg_hourly_income_inr = excluded.avg_hourly_income_inr,
    bank_verified = excluded.bank_verified,
    trust_score = excluded.trust_score,
    gps_consent = excluded.gps_consent;

create temporary table if not exists tmp_demo9_reset_profiles (
  profile_id uuid primary key,
  email text not null,
  policy_id text not null,
  platform_name text not null,
  city text not null,
  vehicle_type text not null,
  avg_hourly_income_inr numeric(10,2) not null,
  bank_verified boolean not null,
  trust_score numeric(4,2) not null,
  gps_consent boolean not null
) on commit drop;

truncate tmp_demo9_reset_profiles;
insert into tmp_demo9_reset_profiles (
  profile_id,
  email,
  policy_id,
  platform_name,
  city,
  vehicle_type,
  avg_hourly_income_inr,
  bank_verified,
  trust_score,
  gps_consent
)
select
  p.id,
  s.email,
  s.policy_id,
  s.platform_name,
  s.city,
  s.vehicle_type,
  s.avg_hourly_income_inr,
  s.bank_verified,
  s.trust_score,
  s.gps_consent
from public.profiles p
join tmp_demo9_reset_seed s
  on lower(p.email) = lower(s.email);

create temporary table if not exists tmp_demo9_reset_claims (
  id uuid primary key
) on commit drop;

truncate tmp_demo9_reset_claims;
insert into tmp_demo9_reset_claims (id)
select mc.id
from public.manual_claims mc
where mc.worker_profile_id in (select profile_id from tmp_demo9_reset_profiles)
   or mc.assigned_reviewer_profile_id in (select profile_id from tmp_demo9_reset_profiles);

create temporary table if not exists tmp_demo9_reset_payout_requests (
  id uuid primary key
) on commit drop;

truncate tmp_demo9_reset_payout_requests;
insert into tmp_demo9_reset_payout_requests (id)
select pr.id
from public.payout_requests pr
where pr.worker_profile_id in (select profile_id from tmp_demo9_reset_profiles)
   or pr.claim_id in (select id from tmp_demo9_reset_claims);

-- Cleanup runtime artifacts

delete from public.payout_settlement_events
where payout_request_id in (select id from tmp_demo9_reset_payout_requests);

delete from public.payout_status_transitions
where payout_request_id in (select id from tmp_demo9_reset_payout_requests);

delete from public.payout_requests
where id in (select id from tmp_demo9_reset_payout_requests);

delete from public.payout_recommendations
where claim_id in (select id from tmp_demo9_reset_claims);

delete from public.claim_evidence
where claim_id in (select id from tmp_demo9_reset_claims);

delete from public.claim_reviews
where claim_id in (select id from tmp_demo9_reset_claims)
   or reviewer_profile_id in (select profile_id from tmp_demo9_reset_profiles);

delete from public.manual_claims
where id in (select id from tmp_demo9_reset_claims);

delete from public.coins_ledger
where profile_id in (select profile_id from tmp_demo9_reset_profiles);

delete from public.audit_events
where actor_profile_id in (select profile_id from tmp_demo9_reset_profiles)
   or (
     entity_type = 'stripe_checkout'
     and coalesce(event_payload->>'worker_profile_id', '') in (
       select profile_id::text from tmp_demo9_reset_profiles
     )
   );

delete from public.policies
where worker_profile_id in (select profile_id from tmp_demo9_reset_profiles)
   or policy_id in (select policy_id from tmp_demo9_reset_profiles);

-- Reapply baseline worker profiles
insert into public.worker_profiles (
  profile_id,
  platform_name,
  city,
  preferred_zone_id,
  vehicle_type,
  avg_hourly_income_inr,
  bank_verified,
  trust_score,
  gps_consent
)
select
  d.profile_id,
  d.platform_name,
  d.city,
  (
    select z.id
    from public.zones z
    where lower(z.city) = lower(d.city)
    order by case when z.zone_name = 'Andheri-W' then 0 else 1 end, z.zone_name
    limit 1
  ) as preferred_zone_id,
  d.vehicle_type,
  d.avg_hourly_income_inr,
  d.bank_verified,
  d.trust_score,
  d.gps_consent
from tmp_demo9_reset_profiles d
on conflict (profile_id) do update
set platform_name = excluded.platform_name,
    city = excluded.city,
    preferred_zone_id = coalesce(excluded.preferred_zone_id, public.worker_profiles.preferred_zone_id),
    vehicle_type = excluded.vehicle_type,
    avg_hourly_income_inr = excluded.avg_hourly_income_inr,
    bank_verified = excluded.bank_verified,
    trust_score = excluded.trust_score,
    gps_consent = excluded.gps_consent;

-- Reapply baseline active policies
insert into public.policies (
  policy_id,
  worker_profile_id,
  zone_id,
  plan_type,
  coverage_amount,
  premium_amount,
  status,
  activated_at,
  valid_until,
  updated_at
)
select
  d.policy_id,
  d.profile_id,
  (
    select z.id
    from public.zones z
    where lower(z.city) = lower(d.city)
    order by case when z.zone_name = 'Andheri-W' then 0 else 1 end, z.zone_name
    limit 1
  ) as zone_id,
  'essential',
  3000,
  28,
  'active',
  now() - interval '1 day',
  now() + interval '6 days',
  now()
from tmp_demo9_reset_profiles d
on conflict (policy_id) do update
set worker_profile_id = excluded.worker_profile_id,
    zone_id = excluded.zone_id,
    plan_type = excluded.plan_type,
    coverage_amount = excluded.coverage_amount,
    premium_amount = excluded.premium_amount,
    status = excluded.status,
    activated_at = excluded.activated_at,
    valid_until = excluded.valid_until,
    updated_at = excluded.updated_at;

commit;

-- Verification snapshot
select
  d.email,
  d.profile_id,
  wp.platform_name,
  wp.bank_verified,
  wp.trust_score,
  p.policy_id,
  p.status,
  p.valid_until
from tmp_demo9_reset_profiles d
left join public.worker_profiles wp on wp.profile_id = d.profile_id
left join public.policies p on p.worker_profile_id = d.profile_id and p.status = 'active'
order by d.email;
