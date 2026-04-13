-- ==========================================================================
-- 08_fix_demo_auth_users.sql
-- Covara One - Demo Auth Recovery Helper
-- ==========================================================================
-- Purpose:
--   Recover demo login accounts when Supabase Auth returns 500 errors
--   (e.g., "Database error querying schema" / "Database error finding users").
--
-- How to use:
--   1) Run this script once to clean stale demo rows and normalize profile state.
--   2) In Supabase Dashboard -> Authentication -> Users, create (or recreate):
--      - worker@demo.com / demo1234
--      - admin@demo.com  / demo1234
--      with "Auto Confirm User" enabled.
--   3) Run this script again to sync roles, profile extension tables,
--      and realistic worker demo persona data (zone, stats, claims, policy).
--   4) If Auth API still returns 500, restart the Supabase project and retry.
--
-- Notes:
--   - This script is idempotent.
--   - It performs a hard cleanup of known legacy seeded auth rows,
--     including dependent public rows that can block auth.users deletion.
--   - If worker/admin users are recreated in Supabase Dashboard,
--     rerunning this script will normalize profile + extension rows.
-- ==========================================================================

begin;

-- --------------------------------------------------------------------------
-- Step 0: identify target legacy IDs/emails from synthetic auth seed.
-- --------------------------------------------------------------------------
create temporary table if not exists tmp_demo_seed_ids (
  id uuid primary key
) on commit drop;

truncate tmp_demo_seed_ids;

insert into tmp_demo_seed_ids (id)
select unnest(array[
  'aaaa0000-0000-0000-0000-000000000001'::uuid,
  'aaaa0000-0000-0000-0000-000000000002'::uuid,
  'aaaa0000-0000-0000-0000-000000000003'::uuid,
  'aaaa0000-0000-0000-0000-000000000004'::uuid,
  'aaaa0000-0000-0000-0000-000000000005'::uuid,
  'aaaa0000-0000-0000-0000-000000000006'::uuid,
  'aaaa0000-0000-0000-0000-000000000101'::uuid,
  'aaaa0000-0000-0000-0000-000000000102'::uuid,
  'aaaa0000-0000-0000-0000-000000000201'::uuid,
  'aaaa0000-0000-0000-0000-000000000202'::uuid
])
on conflict (id) do nothing;

create temporary table if not exists tmp_demo_target_ids (
  id uuid primary key
) on commit drop;

truncate tmp_demo_target_ids;

insert into tmp_demo_target_ids (id)
select id from tmp_demo_seed_ids
union
select u.id
from auth.users u
where lower(coalesce(u.email, '')) in (
  'worker@demo.com',
  'admin@demo.com',
  'ravi.kumar@demo.devtrails.in',
  'priya.sharma@demo.devtrails.in',
  'arun.patel@demo.devtrails.in',
  'meena.devi@demo.devtrails.in',
  'suresh.yadav@demo.devtrails.in',
  'fatima.khan@demo.devtrails.in',
  'neha.sharma@devtrails.insurance',
  'vijay.mehta@devtrails.insurance'
);

-- --------------------------------------------------------------------------
-- Step A: remove dependent public rows before touching auth.users.
-- This avoids FK-blocked deletes on projects where legacy constraints are
-- not ON DELETE CASCADE.
-- --------------------------------------------------------------------------
create temporary table if not exists tmp_demo_target_claims (
  id uuid primary key
) on commit drop;

truncate tmp_demo_target_claims;

insert into tmp_demo_target_claims (id)
select mc.id
from public.manual_claims mc
where mc.worker_profile_id in (select id from tmp_demo_target_ids)
   or mc.assigned_reviewer_profile_id in (select id from tmp_demo_target_ids);

create temporary table if not exists tmp_demo_target_payout_requests (
  id uuid primary key
) on commit drop;

truncate tmp_demo_target_payout_requests;

insert into tmp_demo_target_payout_requests (id)
select pr.id
from public.payout_requests pr
where pr.worker_profile_id in (select id from tmp_demo_target_ids)
   or pr.claim_id in (select id from tmp_demo_target_claims);

delete from public.payout_settlement_events
where payout_request_id in (select id from tmp_demo_target_payout_requests);

delete from public.payout_status_transitions
where payout_request_id in (select id from tmp_demo_target_payout_requests);

delete from public.payout_requests
where id in (select id from tmp_demo_target_payout_requests);

delete from public.payout_recommendations
where claim_id in (select id from tmp_demo_target_claims);

delete from public.claim_evidence
where claim_id in (select id from tmp_demo_target_claims);

delete from public.claim_reviews
where claim_id in (select id from tmp_demo_target_claims)
   or reviewer_profile_id in (select id from tmp_demo_target_ids);

delete from public.manual_claims
where id in (select id from tmp_demo_target_claims);

delete from public.policies
where worker_profile_id in (select id from tmp_demo_target_ids);

delete from public.platform_order_events
where worker_profile_id in (select id from tmp_demo_target_ids);

delete from public.platform_worker_daily_stats
where worker_profile_id in (select id from tmp_demo_target_ids);

delete from public.worker_shifts
where worker_profile_id in (select id from tmp_demo_target_ids);

delete from public.coins_ledger
where profile_id in (select id from tmp_demo_target_ids);

update public.audit_events
set actor_profile_id = null
where actor_profile_id in (select id from tmp_demo_target_ids);

update public.kyc_verification_events
set actor_profile_id = null
where actor_profile_id in (select id from tmp_demo_target_ids);

delete from public.insurer_profiles
where profile_id in (select id from tmp_demo_target_ids);

delete from public.worker_profiles
where profile_id in (select id from tmp_demo_target_ids);

delete from public.profiles
where id in (select id from tmp_demo_target_ids)
   or lower(coalesce(email, '')) in (
     'worker@demo.com',
     'admin@demo.com',
     'ravi.kumar@demo.devtrails.in',
     'priya.sharma@demo.devtrails.in',
     'arun.patel@demo.devtrails.in',
     'meena.devi@demo.devtrails.in',
     'suresh.yadav@demo.devtrails.in',
     'fatima.khan@demo.devtrails.in',
     'neha.sharma@devtrails.insurance',
     'vijay.mehta@devtrails.insurance'
   );

-- --------------------------------------------------------------------------
-- Step B: clear auth child rows, then purge stale/corrupt auth users.
-- --------------------------------------------------------------------------
do $$
begin
  if to_regclass('auth.mfa_factors') is not null and to_regclass('auth.mfa_challenges') is not null then
    execute 'delete from auth.mfa_challenges where factor_id::text in (select id::text from auth.mfa_factors where user_id::text in (select id::text from tmp_demo_target_ids))';
  end if;

  if to_regclass('auth.mfa_factors') is not null then
    execute 'delete from auth.mfa_factors where user_id::text in (select id::text from tmp_demo_target_ids)';
  end if;

  if to_regclass('auth.one_time_tokens') is not null then
    execute 'delete from auth.one_time_tokens where user_id::text in (select id::text from tmp_demo_target_ids)';
  end if;

  if to_regclass('auth.sessions') is not null then
    execute 'delete from auth.sessions where user_id::text in (select id::text from tmp_demo_target_ids)';
  end if;

  if to_regclass('auth.refresh_tokens') is not null then
    execute 'delete from auth.refresh_tokens where user_id::text in (select id::text from tmp_demo_target_ids)';
  end if;
end $$;

delete from auth.identities
where user_id::text in (select id::text from tmp_demo_target_ids)
   or lower(coalesce(provider_id, '')) in (
     'worker@demo.com',
     'admin@demo.com',
     'ravi.kumar@demo.devtrails.in',
     'priya.sharma@demo.devtrails.in',
     'arun.patel@demo.devtrails.in',
     'meena.devi@demo.devtrails.in',
     'suresh.yadav@demo.devtrails.in',
     'fatima.khan@demo.devtrails.in',
     'neha.sharma@devtrails.insurance',
     'vijay.mehta@devtrails.insurance'
   );

delete from auth.users
where id in (select id from tmp_demo_target_ids)
   or lower(coalesce(email, '')) in (
     'worker@demo.com',
     'admin@demo.com',
     'ravi.kumar@demo.devtrails.in',
     'priya.sharma@demo.devtrails.in',
     'arun.patel@demo.devtrails.in',
     'meena.devi@demo.devtrails.in',
     'suresh.yadav@demo.devtrails.in',
     'fatima.khan@demo.devtrails.in',
     'neha.sharma@devtrails.insurance',
     'vijay.mehta@devtrails.insurance'
   );

-- --------------------------------------------------------------------------
-- Step C: if demo auth users now exist, normalize role + profile rows.
-- --------------------------------------------------------------------------

do $$
declare
  v_worker_id uuid;
  v_admin_id uuid;
  v_mumbai_zone_id uuid;
begin
  select id into v_worker_id from auth.users where lower(email) = 'worker@demo.com' limit 1;
  select id into v_admin_id  from auth.users where lower(email) = 'admin@demo.com'  limit 1;

  select z.id
  into v_mumbai_zone_id
  from public.zones z
  where lower(z.city) = 'mumbai'
  order by
    case when z.zone_name = 'Andheri-W' then 0 else 1 end,
    z.zone_name
  limit 1;

  if v_worker_id is not null then
    insert into public.profiles (id, role, full_name, email, phone)
    values (v_worker_id, 'worker', 'Demo Worker', 'worker@demo.com', '+919999900001')
    on conflict (id) do update
    set role = 'worker',
        full_name = 'Demo Worker',
        email = 'worker@demo.com',
        phone = '+919999900001';

    delete from public.insurer_profiles where profile_id = v_worker_id;

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
      v_worker_id,
      'Swiggy',
      'Mumbai',
      v_mumbai_zone_id,
      'Bike',
      90.00,
      true,
      0.86,
      true
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
  end if;

  if v_admin_id is not null then
      insert into public.profiles (id, role, full_name, email, phone)
      values (v_admin_id, 'insurer_admin', 'Demo Admin', 'admin@demo.com', '+919999900002')
      on conflict (id) do update
      set role = 'insurer_admin',
        full_name = 'Demo Admin',
        email = 'admin@demo.com',
        phone = '+919999900002';

    delete from public.worker_profiles where profile_id = v_admin_id;

    insert into public.insurer_profiles (profile_id, company_name, job_title)
    values (v_admin_id, 'DEVTrails Insurance Ops', 'Demo Administrator')
    on conflict (profile_id) do update
    set company_name = excluded.company_name,
        job_title = excluded.job_title;
  end if;
end $$;

-- --------------------------------------------------------------------------
-- Step D: seed realistic worker demo persona after auth/profile recovery.
-- --------------------------------------------------------------------------
do $$
declare
  v_worker_id uuid;
  v_mumbai_zone_id uuid;
  v_zone_lat numeric;
  v_zone_lng numeric;
  v_trigger_auto uuid;
  v_trigger_hold uuid;
  v_claim_auto uuid;
  v_claim_hold uuid;
  v_payout_auto uuid;
  v_payout_hold uuid;
begin
  select id into v_worker_id from auth.users where lower(email) = 'worker@demo.com' limit 1;
  if v_worker_id is null then
    return;
  end if;

  select z.id, z.center_lat, z.center_lng
  into v_mumbai_zone_id, v_zone_lat, v_zone_lng
  from public.zones z
  where lower(z.city) = 'mumbai'
  order by
    case when z.zone_name = 'Andheri-W' then 0 else 1 end,
    z.zone_name
  limit 1;

  v_zone_lat := coalesce(v_zone_lat, 19.1364);
  v_zone_lng := coalesce(v_zone_lng, 72.8296);

  -- Keep the latest 14-day worker chart realistic and deterministic.
  delete from public.platform_worker_daily_stats
  where worker_profile_id = v_worker_id
    and stat_date >= current_date - interval '13 days';

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
    v_worker_id,
    day_series.stat_date,
    case when extract(isodow from day_series.stat_date) in (6, 7) then 8.5 else 9.75 end,
    day_series.completed_orders,
    day_series.completed_orders + 2,
    1,
    (day_series.completed_orders * (116 + (day_series.offset_idx % 4) * 7))::numeric,
    case when extract(isodow from day_series.stat_date) in (6, 7) then 510 else 585 end,
    least(0.97, 0.84 + ((day_series.offset_idx % 5) * 0.025))::numeric
  from (
    select
      gs as offset_idx,
      (current_date - (13 - gs))::date as stat_date,
      case
        when extract(isodow from (current_date - (13 - gs))::date) in (6, 7)
          then 12 + (gs % 3)
        else 9 + (gs % 4)
      end as completed_orders
    from generate_series(0, 13) gs
  ) as day_series;

  -- Deterministic IDs for rerunnable demo trigger/claim/payout rows.
  v_trigger_auto := (
    substr(md5('demo-worker-trigger-auto'), 1, 8) || '-' ||
    substr(md5('demo-worker-trigger-auto'), 9, 4) || '-' ||
    substr(md5('demo-worker-trigger-auto'), 13, 4) || '-' ||
    substr(md5('demo-worker-trigger-auto'), 17, 4) || '-' ||
    substr(md5('demo-worker-trigger-auto'), 21, 12)
  )::uuid;

  v_trigger_hold := (
    substr(md5('demo-worker-trigger-hold'), 1, 8) || '-' ||
    substr(md5('demo-worker-trigger-hold'), 9, 4) || '-' ||
    substr(md5('demo-worker-trigger-hold'), 13, 4) || '-' ||
    substr(md5('demo-worker-trigger-hold'), 17, 4) || '-' ||
    substr(md5('demo-worker-trigger-hold'), 21, 12)
  )::uuid;

  v_claim_auto := (
    substr(md5('demo-worker-claim-auto'), 1, 8) || '-' ||
    substr(md5('demo-worker-claim-auto'), 9, 4) || '-' ||
    substr(md5('demo-worker-claim-auto'), 13, 4) || '-' ||
    substr(md5('demo-worker-claim-auto'), 17, 4) || '-' ||
    substr(md5('demo-worker-claim-auto'), 21, 12)
  )::uuid;

  v_claim_hold := (
    substr(md5('demo-worker-claim-hold'), 1, 8) || '-' ||
    substr(md5('demo-worker-claim-hold'), 9, 4) || '-' ||
    substr(md5('demo-worker-claim-hold'), 13, 4) || '-' ||
    substr(md5('demo-worker-claim-hold'), 17, 4) || '-' ||
    substr(md5('demo-worker-claim-hold'), 21, 12)
  )::uuid;

  v_payout_auto := (
    substr(md5('demo-worker-payout-auto'), 1, 8) || '-' ||
    substr(md5('demo-worker-payout-auto'), 9, 4) || '-' ||
    substr(md5('demo-worker-payout-auto'), 13, 4) || '-' ||
    substr(md5('demo-worker-payout-auto'), 17, 4) || '-' ||
    substr(md5('demo-worker-payout-auto'), 21, 12)
  )::uuid;

  v_payout_hold := (
    substr(md5('demo-worker-payout-hold'), 1, 8) || '-' ||
    substr(md5('demo-worker-payout-hold'), 9, 4) || '-' ||
    substr(md5('demo-worker-payout-hold'), 13, 4) || '-' ||
    substr(md5('demo-worker-payout-hold'), 17, 4) || '-' ||
    substr(md5('demo-worker-payout-hold'), 21, 12)
  )::uuid;

  insert into public.trigger_events (
    id,
    city,
    zone_id,
    trigger_family,
    trigger_code,
    observed_value,
    severity_band,
    source_type,
    started_at,
    ended_at
  )
  values
    (
      v_trigger_auto,
      'Mumbai',
      v_mumbai_zone_id,
      'rain',
      'RAIN_HEAVY',
      77.0,
      'claim',
      'mock',
      now() - interval '1 day 2 hours',
      now() - interval '1 day'
    ),
    (
      v_trigger_hold,
      'Mumbai',
      v_mumbai_zone_id,
      'traffic',
      'TRAFFIC_SEVERE',
      49.0,
      'watch',
      'mock',
      now() - interval '4 days 3 hours',
      now() - interval '4 days 2 hours'
    )
  on conflict (id) do update
  set
    observed_value = excluded.observed_value,
    severity_band = excluded.severity_band,
    source_type = excluded.source_type,
    started_at = excluded.started_at,
    ended_at = excluded.ended_at;

  insert into public.manual_claims (
    id,
    worker_profile_id,
    trigger_event_id,
    claim_mode,
    assignment_state,
    claim_reason,
    stated_lat,
    stated_lng,
    claimed_at,
    claim_status
  )
  values
    (
      v_claim_auto,
      v_worker_id,
      v_trigger_auto,
      'trigger_auto',
      'resolved',
      'Auto-triggered demo claim after heavy rain disruption in Andheri-W.',
      round((v_zone_lat + 0.0012)::numeric, 6),
      round((v_zone_lng - 0.0011)::numeric, 6),
      now() - interval '1 day 55 minutes',
      'auto_approved'
    ),
    (
      v_claim_hold,
      v_worker_id,
      v_trigger_hold,
      'manual',
      'in_review',
      'Demo review case for partial route blockage and low visibility.',
      round((v_zone_lat - 0.0015)::numeric, 6),
      round((v_zone_lng + 0.0010)::numeric, 6),
      now() - interval '4 days 40 minutes',
      'soft_hold_verification'
    )
  on conflict (id) do update
  set
    trigger_event_id = excluded.trigger_event_id,
    claim_mode = excluded.claim_mode,
    assignment_state = excluded.assignment_state,
    claim_reason = excluded.claim_reason,
    stated_lat = excluded.stated_lat,
    stated_lng = excluded.stated_lng,
    claimed_at = excluded.claimed_at,
    claim_status = excluded.claim_status;

  insert into public.payout_recommendations (
    id,
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
  values
    (
      v_payout_auto,
      v_claim_auto,
      4120,
      0.15,
      0.78,
      0.84,
      0.89,
      0.08,
      1.00,
      3000,
      606,
      28,
      1500,
      jsonb_build_object('seed', '08_fix_demo_auth_users', 'scenario', 'auto_approved'),
      now()
    ),
    (
      v_payout_hold,
      v_claim_hold,
      3920,
      0.15,
      0.51,
      0.79,
      0.74,
      0.22,
      1.00,
      3000,
      347,
      28,
      920,
      jsonb_build_object('seed', '08_fix_demo_auth_users', 'scenario', 'soft_hold_verification'),
      now()
    )
  on conflict (id) do update
  set
    covered_weekly_income_b = excluded.covered_weekly_income_b,
    claim_probability_p = excluded.claim_probability_p,
    severity_score_s = excluded.severity_score_s,
    exposure_score_e = excluded.exposure_score_e,
    confidence_score_c = excluded.confidence_score_c,
    fraud_holdback_fh = excluded.fraud_holdback_fh,
    outlier_uplift_u = excluded.outlier_uplift_u,
    payout_cap = excluded.payout_cap,
    expected_payout = excluded.expected_payout,
    gross_premium = excluded.gross_premium,
    recommended_payout = excluded.recommended_payout,
    explanation_json = excluded.explanation_json,
    created_at = excluded.created_at;

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
    'POL-DEMO-WORKER-ESSENTIAL',
    v_worker_id,
    v_mumbai_zone_id,
    'essential',
    3000,
    28,
    'active',
    now() - interval '2 days',
    now() + interval '5 days',
    now()
  )
  on conflict (policy_id) do update
  set
    worker_profile_id = excluded.worker_profile_id,
    zone_id = excluded.zone_id,
    plan_type = excluded.plan_type,
    coverage_amount = excluded.coverage_amount,
    premium_amount = excluded.premium_amount,
    status = excluded.status,
    activated_at = excluded.activated_at,
    valid_until = excluded.valid_until,
    updated_at = excluded.updated_at;
end $$;

commit;

notify pgrst, 'reload schema';
