-- ==========================================================================
-- 08b_demo_auth_recovery_fast.sql
-- Covara One - Fast Demo Auth Recovery (low-timeout version)
-- ==========================================================================
-- Purpose:
--   Recover worker@demo.com and admin@demo.com quickly when the full
--   08_fix_demo_auth_users.sql times out in the SQL Editor.
--
-- Run pattern:
--   Pass 1: run this script (it cleans stale demo rows).
--           Then recreate users in Supabase Auth dashboard:
--             - worker@demo.com / demo1234 (Auto Confirm)
--             - admin@demo.com  / demo1234 (Auto Confirm)
--   Pass 2: run this script again (it syncs role/profile + seeds persona).
--
-- If your connection is unstable and this still times out, use chunked mode:
--   1) 08b1_demo_auth_cleanup_only.sql
--   2) recreate users in Auth dashboard
--   3) 08b2_demo_auth_sync_seed_only.sql
--
-- Notes:
--   - Narrow scope: only demo worker/admin accounts.
--   - Idempotent.
-- ==========================================================================

set statement_timeout = '0';
set lock_timeout = '10s';
set idle_in_transaction_session_timeout = '0';

begin;

create temporary table if not exists tmp_demo_target_ids_fast (
  id uuid primary key
) on commit drop;

truncate tmp_demo_target_ids_fast;

insert into tmp_demo_target_ids_fast (id)
select unnest(array[
  'aaaa0000-0000-0000-0000-000000000201'::uuid,
  'aaaa0000-0000-0000-0000-000000000202'::uuid
])
on conflict (id) do nothing;

insert into tmp_demo_target_ids_fast (id)
select u.id
from auth.users u
where lower(coalesce(u.email, '')) in ('worker@demo.com', 'admin@demo.com')
on conflict (id) do nothing;

create temporary table if not exists tmp_demo_target_claims_fast (
  id uuid primary key
) on commit drop;

truncate tmp_demo_target_claims_fast;

insert into tmp_demo_target_claims_fast (id)
select mc.id
from public.manual_claims mc
where mc.worker_profile_id in (select id from tmp_demo_target_ids_fast)
   or mc.assigned_reviewer_profile_id in (select id from tmp_demo_target_ids_fast);

create temporary table if not exists tmp_demo_target_payout_requests_fast (
  id uuid primary key
) on commit drop;

truncate tmp_demo_target_payout_requests_fast;

insert into tmp_demo_target_payout_requests_fast (id)
select pr.id
from public.payout_requests pr
where pr.worker_profile_id in (select id from tmp_demo_target_ids_fast)
   or pr.claim_id in (select id from tmp_demo_target_claims_fast);

-- Dependent cleanup (public schema)
delete from public.payout_settlement_events
where payout_request_id in (select id from tmp_demo_target_payout_requests_fast);

delete from public.payout_status_transitions
where payout_request_id in (select id from tmp_demo_target_payout_requests_fast);

delete from public.payout_requests
where id in (select id from tmp_demo_target_payout_requests_fast);

delete from public.payout_recommendations
where claim_id in (select id from tmp_demo_target_claims_fast);

delete from public.claim_evidence
where claim_id in (select id from tmp_demo_target_claims_fast);

delete from public.claim_reviews
where claim_id in (select id from tmp_demo_target_claims_fast)
   or reviewer_profile_id in (select id from tmp_demo_target_ids_fast);

delete from public.manual_claims
where id in (select id from tmp_demo_target_claims_fast);

delete from public.policies
where worker_profile_id in (select id from tmp_demo_target_ids_fast);

delete from public.platform_order_events
where worker_profile_id in (select id from tmp_demo_target_ids_fast);

delete from public.platform_worker_daily_stats
where worker_profile_id in (select id from tmp_demo_target_ids_fast);

delete from public.worker_shifts
where worker_profile_id in (select id from tmp_demo_target_ids_fast);

delete from public.coins_ledger
where profile_id in (select id from tmp_demo_target_ids_fast);

update public.audit_events
set actor_profile_id = null
where actor_profile_id in (select id from tmp_demo_target_ids_fast);

update public.kyc_verification_events
set actor_profile_id = null
where actor_profile_id in (select id from tmp_demo_target_ids_fast);

delete from public.insurer_profiles
where profile_id in (select id from tmp_demo_target_ids_fast);

delete from public.worker_profiles
where profile_id in (select id from tmp_demo_target_ids_fast);

delete from public.profiles
where id in (select id from tmp_demo_target_ids_fast)
   or lower(coalesce(email, '')) in ('worker@demo.com', 'admin@demo.com');

-- Auth child tables cleanup
do $$
begin
  if to_regclass('auth.mfa_factors') is not null and to_regclass('auth.mfa_challenges') is not null then
    execute 'delete from auth.mfa_challenges where factor_id::text in (select id::text from auth.mfa_factors where user_id::text in (select id::text from tmp_demo_target_ids_fast))';
  end if;

  if to_regclass('auth.mfa_factors') is not null then
    execute 'delete from auth.mfa_factors where user_id::text in (select id::text from tmp_demo_target_ids_fast)';
  end if;

  if to_regclass('auth.one_time_tokens') is not null then
    execute 'delete from auth.one_time_tokens where user_id::text in (select id::text from tmp_demo_target_ids_fast)';
  end if;

  if to_regclass('auth.sessions') is not null then
    execute 'delete from auth.sessions where user_id::text in (select id::text from tmp_demo_target_ids_fast)';
  end if;

  if to_regclass('auth.refresh_tokens') is not null then
    execute 'delete from auth.refresh_tokens where user_id::text in (select id::text from tmp_demo_target_ids_fast)';
  end if;
end $$;

delete from auth.identities
where user_id::text in (select id::text from tmp_demo_target_ids_fast)
   or lower(coalesce(provider_id, '')) in ('worker@demo.com', 'admin@demo.com');

delete from auth.users
where id in (select id from tmp_demo_target_ids_fast)
   or lower(coalesce(email, '')) in ('worker@demo.com', 'admin@demo.com');

-- Sync if demo auth users exist (run this script again after recreating users)
do $$
declare
  v_worker_id uuid;
  v_admin_id uuid;
  v_mumbai_zone_id uuid;
  v_zone_lat numeric;
  v_zone_lng numeric;
  v_trigger_auto uuid;
  v_claim_auto uuid;
  v_payout_auto uuid;
begin
  select id into v_worker_id from auth.users where lower(email) = 'worker@demo.com' limit 1;
  select id into v_admin_id  from auth.users where lower(email) = 'admin@demo.com'  limit 1;

  select z.id, z.center_lat, z.center_lng
  into v_mumbai_zone_id, v_zone_lat, v_zone_lng
  from public.zones z
  where lower(z.city) = 'mumbai'
  order by case when z.zone_name = 'Andheri-W' then 0 else 1 end, z.zone_name
  limit 1;

  v_zone_lat := coalesce(v_zone_lat, 19.1364);
  v_zone_lng := coalesce(v_zone_lng, 72.8296);

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

    v_trigger_auto := (
      substr(md5('demo-worker-trigger-auto-fast'), 1, 8) || '-' ||
      substr(md5('demo-worker-trigger-auto-fast'), 9, 4) || '-' ||
      substr(md5('demo-worker-trigger-auto-fast'), 13, 4) || '-' ||
      substr(md5('demo-worker-trigger-auto-fast'), 17, 4) || '-' ||
      substr(md5('demo-worker-trigger-auto-fast'), 21, 12)
    )::uuid;

    v_claim_auto := (
      substr(md5('demo-worker-claim-auto-fast'), 1, 8) || '-' ||
      substr(md5('demo-worker-claim-auto-fast'), 9, 4) || '-' ||
      substr(md5('demo-worker-claim-auto-fast'), 13, 4) || '-' ||
      substr(md5('demo-worker-claim-auto-fast'), 17, 4) || '-' ||
      substr(md5('demo-worker-claim-auto-fast'), 21, 12)
    )::uuid;

    v_payout_auto := (
      substr(md5('demo-worker-payout-auto-fast'), 1, 8) || '-' ||
      substr(md5('demo-worker-payout-auto-fast'), 9, 4) || '-' ||
      substr(md5('demo-worker-payout-auto-fast'), 13, 4) || '-' ||
      substr(md5('demo-worker-payout-auto-fast'), 17, 4) || '-' ||
      substr(md5('demo-worker-payout-auto-fast'), 21, 12)
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
    values (
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
    )
    on conflict (id) do update
    set observed_value = excluded.observed_value,
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
    values (
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
    )
    on conflict (id) do update
    set trigger_event_id = excluded.trigger_event_id,
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
    values (
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
      jsonb_build_object('seed', '08b_demo_auth_recovery_fast', 'scenario', 'auto_approved'),
      now()
    )
    on conflict (id) do update
    set covered_weekly_income_b = excluded.covered_weekly_income_b,
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
    set worker_profile_id = excluded.worker_profile_id,
        zone_id = excluded.zone_id,
        plan_type = excluded.plan_type,
        coverage_amount = excluded.coverage_amount,
        premium_amount = excluded.premium_amount,
        status = excluded.status,
        activated_at = excluded.activated_at,
        valid_until = excluded.valid_until,
        updated_at = excluded.updated_at;
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

commit;

notify pgrst, 'reload schema';
