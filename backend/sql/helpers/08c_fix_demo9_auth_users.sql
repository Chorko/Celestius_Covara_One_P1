-- ==========================================================================
-- 08c_fix_demo9_auth_users.sql
-- Covara One - DEMO9 Worker Auth Recovery Helper
-- ==========================================================================
-- Purpose:
--   Recover DEMO9 synthetic worker accounts when Supabase Auth returns 500
--   for these emails (for example: "Database error querying schema").
--
-- Target accounts:
--   demo.auto01@synthetic.covara.dev
--   demo.auto02@synthetic.covara.dev
--   demo.auto03@synthetic.covara.dev
--   demo.review01@synthetic.covara.dev
--   demo.review02@synthetic.covara.dev
--   demo.review03@synthetic.covara.dev
--   demo.fraud01@synthetic.covara.dev
--   demo.fraud02@synthetic.covara.dev
--   demo.fraud03@synthetic.covara.dev
--
-- Run workflow (two-pass):
--   Pass 1:
--     1) Run this script once (it cleans stale/corrupt rows).
--     2) Recreate the 9 Auth users in Supabase Dashboard (Auto Confirm ON)
--        with password: Covara#2026!
--   Pass 2:
--     3) Run this script again (it syncs profiles/worker_profiles/policies).
--
-- Notes:
--   - Idempotent.
--   - Safe to rerun.
--   - Also targets legacy deterministic DEMO9 IDs d900...0001..0009.
-- ==========================================================================

set statement_timeout = '0';
set lock_timeout = '10s';
set idle_in_transaction_session_timeout = '0';

begin;

create temporary table if not exists tmp_demo9_emails (
  email text primary key,
  full_name text not null,
  phone text not null,
  policy_id text not null,
  platform_name text not null,
  city text not null,
  vehicle_type text not null,
  avg_hourly_income_inr numeric(10,2) not null,
  bank_verified boolean not null,
  trust_score numeric(4,2) not null,
  gps_consent boolean not null
) on commit drop;

truncate tmp_demo9_emails;

insert into tmp_demo9_emails (
  email,
  full_name,
  phone,
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
  ('demo.auto01@synthetic.covara.dev',   'DEMO9 AUTO01',   '+919900000001', 'POL-DEMO9-AUTO01',   'Swiggy',  'Mumbai', 'Bike',    120.00, true, 0.94, true),
  ('demo.auto02@synthetic.covara.dev',   'DEMO9 AUTO02',   '+919900000002', 'POL-DEMO9-AUTO02',   'Zomato',  'Mumbai', 'Scooter', 112.00, true, 0.91, true),
  ('demo.auto03@synthetic.covara.dev',   'DEMO9 AUTO03',   '+919900000003', 'POL-DEMO9-AUTO03',   'Zepto',   'Mumbai', 'Bike',    105.00, true, 0.89, true),
  ('demo.review01@synthetic.covara.dev', 'DEMO9 REVIEW01', '+919900000004', 'POL-DEMO9-REVIEW01', 'Swiggy',  'Mumbai', 'Bike',     98.00, true, 0.72, true),
  ('demo.review02@synthetic.covara.dev', 'DEMO9 REVIEW02', '+919900000005', 'POL-DEMO9-REVIEW02', 'Blinkit', 'Mumbai', 'Scooter',  92.00, true, 0.68, true),
  ('demo.review03@synthetic.covara.dev', 'DEMO9 REVIEW03', '+919900000006', 'POL-DEMO9-REVIEW03', 'Porter',  'Mumbai', 'Bike',     88.00, true, 0.64, false),
  ('demo.fraud01@synthetic.covara.dev',  'DEMO9 FRAUD01',  '+919900000007', 'POL-DEMO9-FRAUD01',  'Swiggy',  'Mumbai', 'Bike',     90.00, false, 0.42, false),
  ('demo.fraud02@synthetic.covara.dev',  'DEMO9 FRAUD02',  '+919900000008', 'POL-DEMO9-FRAUD02',  'Zomato',  'Mumbai', 'Scooter',  86.00, false, 0.36, false),
  ('demo.fraud03@synthetic.covara.dev',  'DEMO9 FRAUD03',  '+919900000009', 'POL-DEMO9-FRAUD03',  'Blinkit', 'Mumbai', 'Cycle',    82.00, false, 0.31, false)
on conflict (email) do update
set full_name = excluded.full_name,
    phone = excluded.phone,
    policy_id = excluded.policy_id,
    platform_name = excluded.platform_name,
    city = excluded.city,
    vehicle_type = excluded.vehicle_type,
    avg_hourly_income_inr = excluded.avg_hourly_income_inr,
    bank_verified = excluded.bank_verified,
    trust_score = excluded.trust_score,
    gps_consent = excluded.gps_consent;

create temporary table if not exists tmp_demo9_target_ids (
  id uuid primary key
) on commit drop;

truncate tmp_demo9_target_ids;

insert into tmp_demo9_target_ids (id)
select unnest(array[
  'd9000000-0000-0000-0000-000000000001'::uuid,
  'd9000000-0000-0000-0000-000000000002'::uuid,
  'd9000000-0000-0000-0000-000000000003'::uuid,
  'd9000000-0000-0000-0000-000000000004'::uuid,
  'd9000000-0000-0000-0000-000000000005'::uuid,
  'd9000000-0000-0000-0000-000000000006'::uuid,
  'd9000000-0000-0000-0000-000000000007'::uuid,
  'd9000000-0000-0000-0000-000000000008'::uuid,
  'd9000000-0000-0000-0000-000000000009'::uuid
])
on conflict (id) do nothing;

insert into tmp_demo9_target_ids (id)
select u.id
from auth.users u
join tmp_demo9_emails e on lower(u.email) = lower(e.email)
on conflict (id) do nothing;

insert into tmp_demo9_target_ids (id)
select p.id
from public.profiles p
join tmp_demo9_emails e on lower(p.email) = lower(e.email)
on conflict (id) do nothing;

create temporary table if not exists tmp_demo9_target_claims (
  id uuid primary key
) on commit drop;

truncate tmp_demo9_target_claims;

insert into tmp_demo9_target_claims (id)
select mc.id
from public.manual_claims mc
where mc.worker_profile_id in (select id from tmp_demo9_target_ids)
   or mc.assigned_reviewer_profile_id in (select id from tmp_demo9_target_ids);

create temporary table if not exists tmp_demo9_target_payout_requests (
  id uuid primary key
) on commit drop;

truncate tmp_demo9_target_payout_requests;

insert into tmp_demo9_target_payout_requests (id)
select pr.id
from public.payout_requests pr
where pr.worker_profile_id in (select id from tmp_demo9_target_ids)
   or pr.claim_id in (select id from tmp_demo9_target_claims);

-- Public schema dependent cleanup
delete from public.payout_settlement_events
where payout_request_id in (select id from tmp_demo9_target_payout_requests);

delete from public.payout_status_transitions
where payout_request_id in (select id from tmp_demo9_target_payout_requests);

delete from public.payout_requests
where id in (select id from tmp_demo9_target_payout_requests);

delete from public.payout_recommendations
where claim_id in (select id from tmp_demo9_target_claims);

delete from public.claim_evidence
where claim_id in (select id from tmp_demo9_target_claims);

delete from public.claim_reviews
where claim_id in (select id from tmp_demo9_target_claims)
   or reviewer_profile_id in (select id from tmp_demo9_target_ids);

delete from public.manual_claims
where id in (select id from tmp_demo9_target_claims);

delete from public.policies
where worker_profile_id in (select id from tmp_demo9_target_ids)
   or policy_id in (select policy_id from tmp_demo9_emails);

delete from public.platform_order_events
where worker_profile_id in (select id from tmp_demo9_target_ids);

delete from public.platform_worker_daily_stats
where worker_profile_id in (select id from tmp_demo9_target_ids);

delete from public.worker_shifts
where worker_profile_id in (select id from tmp_demo9_target_ids);

delete from public.coins_ledger
where profile_id in (select id from tmp_demo9_target_ids);

update public.audit_events
set actor_profile_id = null
where actor_profile_id in (select id from tmp_demo9_target_ids);

update public.kyc_verification_events
set actor_profile_id = null
where actor_profile_id in (select id from tmp_demo9_target_ids);

delete from public.insurer_profiles
where profile_id in (select id from tmp_demo9_target_ids);

delete from public.worker_profiles
where profile_id in (select id from tmp_demo9_target_ids);

delete from public.profiles
where id in (select id from tmp_demo9_target_ids)
   or lower(coalesce(email, '')) in (select lower(email) from tmp_demo9_emails);

-- Auth child tables cleanup
do $$
begin
  if to_regclass('auth.mfa_factors') is not null and to_regclass('auth.mfa_challenges') is not null then
    execute 'delete from auth.mfa_challenges where factor_id::text in (select id::text from auth.mfa_factors where user_id::text in (select id::text from tmp_demo9_target_ids))';
  end if;

  if to_regclass('auth.mfa_factors') is not null then
    execute 'delete from auth.mfa_factors where user_id::text in (select id::text from tmp_demo9_target_ids)';
  end if;

  if to_regclass('auth.one_time_tokens') is not null then
    execute 'delete from auth.one_time_tokens where user_id::text in (select id::text from tmp_demo9_target_ids)';
  end if;

  if to_regclass('auth.sessions') is not null then
    execute 'delete from auth.sessions where user_id::text in (select id::text from tmp_demo9_target_ids)';
  end if;

  if to_regclass('auth.refresh_tokens') is not null then
    execute 'delete from auth.refresh_tokens where user_id::text in (select id::text from tmp_demo9_target_ids)';
  end if;
end $$;

delete from auth.identities
where user_id::text in (select id::text from tmp_demo9_target_ids)
   or lower(coalesce(provider_id, '')) in (select lower(email) from tmp_demo9_emails);

delete from auth.users
where id in (select id from tmp_demo9_target_ids)
   or lower(coalesce(email, '')) in (select lower(email) from tmp_demo9_emails);

-- Pass-2 sync block: runs only after users are recreated in Auth.
do $$
declare
  rec record;
  v_zone_id uuid;
  v_daily_orders_base integer;
  v_daily_hours_base numeric;
  v_daily_gps_base numeric;
  v_streak_coins integer;
  v_claim_coins integer;
  v_redeem_coins integer;
begin
  select z.id
  into v_zone_id
  from public.zones z
  where lower(z.city) = 'mumbai'
  order by case when z.zone_name = 'Andheri-W' then 0 else 1 end, z.zone_name
  limit 1;

  for rec in
    select
      u.id as profile_id,
      e.email,
      e.full_name,
      e.phone,
      e.policy_id,
      e.platform_name,
      e.city,
      e.vehicle_type,
      e.avg_hourly_income_inr,
      e.bank_verified,
      e.trust_score,
      e.gps_consent
    from tmp_demo9_emails e
    join auth.users u on lower(u.email) = lower(e.email)
  loop
    insert into public.profiles (id, role, full_name, email, phone)
    values (rec.profile_id, 'worker', rec.full_name, rec.email, rec.phone)
    on conflict (id) do update
    set role = 'worker',
        full_name = excluded.full_name,
        email = excluded.email,
        phone = excluded.phone;

    delete from public.insurer_profiles where profile_id = rec.profile_id;

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
    values (
      rec.profile_id,
      rec.platform_name,
      rec.city,
      v_zone_id,
      rec.vehicle_type,
      rec.avg_hourly_income_inr,
      rec.bank_verified,
      rec.trust_score,
      rec.gps_consent
    )
    on conflict (profile_id) do update
    set platform_name = excluded.platform_name,
        city = excluded.city,
        preferred_zone_id = coalesce(excluded.preferred_zone_id, public.worker_profiles.preferred_zone_id),
        vehicle_type = excluded.vehicle_type,
        avg_hourly_income_inr = excluded.avg_hourly_income_inr,
        bank_verified = excluded.bank_verified,
        trust_score = excluded.trust_score,
        gps_consent = excluded.gps_consent;

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
    values (
      rec.policy_id,
      rec.profile_id,
      v_zone_id,
      'essential',
      3000,
      28,
      'active',
      now() - interval '1 day',
      now() + interval '6 days',
      now()
    )
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

    if rec.email like 'demo.auto%' then
      v_daily_orders_base := 26;
      v_daily_hours_base := 9.0;
      v_daily_gps_base := 0.95;
      v_streak_coins := 120;
      v_claim_coins := 60;
      v_redeem_coins := -25;
    elsif rec.email like 'demo.review%' then
      v_daily_orders_base := 17;
      v_daily_hours_base := 7.2;
      v_daily_gps_base := 0.78;
      v_streak_coins := 70;
      v_claim_coins := 35;
      v_redeem_coins := -30;
    else
      v_daily_orders_base := 9;
      v_daily_hours_base := 5.8;
      v_daily_gps_base := 0.48;
      v_streak_coins := 25;
      v_claim_coins := 12;
      v_redeem_coins := -20;
    end if;

    insert into public.worker_shifts (
      worker_profile_id,
      shift_date,
      shift_start,
      shift_end,
      zone_id
    )
    values
      (
        rec.profile_id,
        current_date,
        now() - interval '3 hour',
        now() + interval '4 hour',
        v_zone_id
      ),
      (
        rec.profile_id,
        current_date - 1,
        date_trunc('day', now() - interval '1 day') + interval '10 hour',
        date_trunc('day', now() - interval '1 day') + interval '19 hour',
        v_zone_id
      );

    insert into public.platform_worker_daily_stats (
      worker_profile_id,
      stat_date,
      active_hours,
      completed_orders,
      accepted_orders,
      cancelled_orders,
      gross_earnings_inr,
      platform_login_minutes,
      gps_consistency_score
    )
    select
      rec.profile_id,
      (current_date - gs.day_offset)::date,
      greatest(3.5::numeric, v_daily_hours_base - (gs.day_offset * 0.25)),
      greatest(0, v_daily_orders_base - (gs.day_offset * 2)),
      greatest(0, (v_daily_orders_base - (gs.day_offset * 2)) + 3),
      case
        when rec.email like 'demo.fraud%' then 3 + gs.day_offset
        else 1 + (gs.day_offset / 2)
      end,
      round(
        greatest(0, v_daily_orders_base - (gs.day_offset * 2))
        * rec.avg_hourly_income_inr
        * 0.55,
        2
      ),
      round(
        greatest(
          210::numeric,
          (v_daily_hours_base - (gs.day_offset * 0.25)) * 60
        )
      )::integer,
      greatest(
        0.18::numeric,
        least(
          0.99::numeric,
          v_daily_gps_base - (gs.day_offset * 0.015)
        )
      )
    from generate_series(0, 6) as gs(day_offset);

    insert into public.coins_ledger (
      profile_id,
      activity,
      coins,
      description,
      reference_id,
      created_at
    )
    values
      (
        rec.profile_id,
        'weekly_streak_bonus',
        v_streak_coins,
        'DEMO9 seeded weekly streak bonus',
        rec.policy_id || ':streak',
        now() - interval '3 days'
      ),
      (
        rec.profile_id,
        'claim_settlement_bonus',
        v_claim_coins,
        'DEMO9 seeded claim settlement reward',
        rec.policy_id || ':claim',
        now() - interval '2 days'
      ),
      (
        rec.profile_id,
        'partner_perk_redemption',
        v_redeem_coins,
        'DEMO9 seeded partner perk redemption',
        rec.policy_id || ':redeem',
        now() - interval '1 day'
      );
  end loop;
end $$;

commit;

notify pgrst, 'reload schema';
