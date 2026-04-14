-- ============================================================================
-- 19_login_ready_workers_200.sql
-- Covara One - Synthetic Workforce Public Data Seed (200 workers)
-- ============================================================================
-- Purpose:
--   1) Upsert realistic worker profiles, policies, daily stats.
--   2) Seed diversified trigger/claim/payout/evidence data so admin KPIs
--      remain non-zero and operationally realistic (fraud, review, payouts).
--
-- Prerequisite:
--   Run `python scripts/provision_login_ready_workers_200.py --apply` first.
--   That script creates login-capable Supabase Auth users via Admin API.
--
-- Deterministic + idempotent:
--   - Uses deterministic UUIDs based on worker index.
--   - Re-running updates the same seed records.
--
-- Login format after auth provisioning:
--   - Email: worker001@synthetic.covara.dev ... worker200@synthetic.covara.dev
--   - Password (all workers): Covara#2026!
-- ============================================================================

set statement_timeout = '0';
set lock_timeout = '10s';
set idle_in_transaction_session_timeout = '0';

begin;

create or replace function pg_temp.seed_uuid(seed text)
returns uuid
language sql
immutable
as $$
  select (
    substr(md5(seed), 1, 8) || '-' ||
    substr(md5(seed), 9, 4) || '-' ||
    substr(md5(seed), 13, 4) || '-' ||
    substr(md5(seed), 17, 4) || '-' ||
    substr(md5(seed), 21, 12)
  )::uuid
$$;

do $$
begin
  if not exists (select 1 from public.zones) then
    raise exception 'zones is empty. Run 00_unified_migration.sql first.';
  end if;
end $$;

create temporary table tmp_seed_login_workers on commit drop as
with constants as (
  select
    array[
      'Aarav','Vihaan','Ishaan','Reyansh','Aditya','Arjun','Kabir','Rohan','Aman','Nikhil',
      'Karan','Varun','Siddharth','Akash','Rahul','Ritesh','Manish','Yash','Sanjay','Pranav',
      'Ananya','Aditi','Kavya','Neha','Pooja','Riya','Ira','Meera','Sana','Naina'
    ]::text[] as first_names,
    array[
      'Sharma','Patel','Khan','Yadav','Verma','Nair','Iyer','Reddy','Singh','Das',
      'Gupta','Mishra','Jain','Chopra','Bose','Kulkarni','Mehta','Pillai','Rao','Tiwari'
    ]::text[] as last_names,
    array['Swiggy','Zomato','Blinkit','Zepto','Dunzo','Porter']::text[] as platforms,
    array['Bike','Scooter','Cycle','EV Scooter']::text[] as vehicle_types
),
zone_pool as (
  select
    z.id as zone_id,
    z.city,
    coalesce(z.center_lat, 19.0760)::numeric as center_lat,
    coalesce(z.center_lng, 72.8777)::numeric as center_lng,
    row_number() over (order by z.city, z.zone_name, z.id) as zone_rn,
    count(*) over () as zone_cnt
  from public.zones z
),
worker_base as (
  select
    gs as worker_idx,
    ('worker' || lpad(gs::text, 3, '0') || '@synthetic.covara.dev') as email,
    ('+91' || lpad((9000000000 + gs)::text, 10, '0')) as phone,
    zp.zone_id,
    zp.city,
    zp.center_lat,
    zp.center_lng,
    (
      c.first_names[((gs - 1) % array_length(c.first_names, 1)) + 1] || ' ' ||
      c.last_names[((gs * 3 - 1) % array_length(c.last_names, 1)) + 1]
    )::text as full_name,
    c.platforms[((gs * 5 - 1) % array_length(c.platforms, 1)) + 1] as platform_name,
    c.vehicle_types[((gs * 7 - 1) % array_length(c.vehicle_types, 1)) + 1] as vehicle_type
  from generate_series(1, 200) gs
  join constants c on true
  join zone_pool zp
    on zp.zone_rn = ((gs - 1) % (select max(zone_cnt) from zone_pool)) + 1
)
select
  wb.worker_idx,
  pg_temp.seed_uuid('covara19-worker-auth-' || wb.worker_idx) as worker_id,
  wb.email,
  wb.full_name,
  wb.phone,
  wb.city,
  wb.zone_id,
  wb.center_lat,
  wb.center_lng,
  wb.platform_name,
  wb.vehicle_type,
  round(
    (
      62
      + ((wb.worker_idx % 17) * 4.6)
      + case wb.city
          when 'Mumbai' then 8
          when 'Delhi' then 6
          when 'Bangalore' then 5
          else 4
        end
    )::numeric,
    2
  ) as avg_hourly_income_inr,
  (wb.worker_idx % 11 <> 0) as bank_verified,
  round(
    least(0.97::numeric, greatest(0.43::numeric, (0.57 + ((wb.worker_idx % 37)::numeric / 100))::numeric)),
    2
  ) as trust_score,
  (wb.worker_idx % 13 <> 0) as gps_consent
from worker_base wb;

-- Auth rows are intentionally not mutated here.
-- Provision auth users via scripts/provision_login_ready_workers_200.py.

do $$
declare
  v_missing_auth int;
begin
  select count(*)
  into v_missing_auth
  from tmp_seed_login_workers w
  left join auth.users u on u.id = w.worker_id
  where u.id is null;

  if v_missing_auth > 0 then
    raise exception
      'Missing % synthetic auth users. Run python scripts/provision_login_ready_workers_200.py --apply first, then rerun this SQL.',
      v_missing_auth;
  end if;
end $$;

insert into public.profiles (id, role, full_name, email, phone)
select
  w.worker_id,
  'worker',
  w.full_name,
  w.email,
  w.phone
from tmp_seed_login_workers w
on conflict (id) do update
set role = 'worker',
    full_name = excluded.full_name,
    email = excluded.email,
    phone = excluded.phone;

delete from public.insurer_profiles
where profile_id in (select worker_id from tmp_seed_login_workers);

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
  w.worker_id,
  w.platform_name,
  w.city,
  w.zone_id,
  w.vehicle_type,
  w.avg_hourly_income_inr,
  w.bank_verified,
  w.trust_score,
  w.gps_consent
from tmp_seed_login_workers w
on conflict (profile_id) do update
set platform_name = excluded.platform_name,
    city = excluded.city,
    preferred_zone_id = excluded.preferred_zone_id,
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
select
  ('POL-SYN-' || lpad(w.worker_idx::text, 3, '0')),
  w.worker_id,
  w.zone_id,
  case when w.worker_idx % 5 = 0 then 'plus' else 'essential' end,
  case when w.worker_idx % 5 = 0
    then round((w.avg_hourly_income_inr * 64)::numeric, 2)
    else round((w.avg_hourly_income_inr * 46)::numeric, 2)
  end,
  case when w.worker_idx % 5 = 0
    then round((w.avg_hourly_income_inr * 0.55)::numeric, 2)
    else round((w.avg_hourly_income_inr * 0.38)::numeric, 2)
  end,
  case
    when w.worker_idx % 20 = 0 then 'cancelled'
    when w.worker_idx % 6 = 0 then 'expired'
    else 'active'
  end,
  now() - make_interval(days => 2 + (w.worker_idx % 35)),
  case
    when w.worker_idx % 20 = 0 then now() + make_interval(days => 2)
    when w.worker_idx % 6 = 0 then now() - make_interval(days => 1 + (w.worker_idx % 14))
    else now() + make_interval(days => 10 + (w.worker_idx % 30))
  end,
  now()
from tmp_seed_login_workers w
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

with stats_seed as (
  select
    w.worker_id as worker_profile_id,
    (current_date - (13 - d))::date as stat_date,
    case
      when ((w.worker_idx + d) % 29) = 0 then 0::numeric
      else round(
        case
          when extract(isodow from (current_date - (13 - d))::date) in (6, 7)
            then 7.2 + ((w.worker_idx % 4)::numeric * 0.45)
          else 8.4 + ((w.worker_idx % 5)::numeric * 0.50)
        end,
        2
      )
    end as active_hours,
    w.avg_hourly_income_inr,
    w.trust_score,
    w.gps_consent,
    w.worker_idx,
    d
  from tmp_seed_login_workers w
  cross join generate_series(0, 13) d
),
scored_stats as (
  select
    s.worker_profile_id,
    s.stat_date,
    s.active_hours,
    case
      when s.active_hours = 0 then 0
      else greatest(
        0,
        floor(s.active_hours * (1.35 + ((s.worker_idx % 3)::numeric * 0.12)))::int + ((s.d % 3) - 1)
      )
    end as completed_orders,
    s.avg_hourly_income_inr,
    s.trust_score,
    s.gps_consent,
    s.worker_idx,
    s.d
  from stats_seed s
)
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
  ss.worker_profile_id,
  ss.stat_date,
  ss.active_hours,
  ss.completed_orders,
  case
    when ss.active_hours = 0 then 0
    else ss.completed_orders + 1 + ((ss.worker_idx + ss.d) % 4)
  end as accepted_orders,
  case
    when ss.active_hours = 0 then 0
    else ((ss.worker_idx + ss.d) % 3)
  end as cancelled_orders,
  round((ss.completed_orders * (ss.avg_hourly_income_inr * (1.11 + ((ss.d % 4)::numeric * 0.02))))::numeric, 2) as gross_earnings_inr,
  case
    when ss.active_hours = 0 then 0
    else round((ss.active_hours * 60)::numeric)::int
  end as platform_login_minutes,
  case
    when ss.gps_consent then round(
      least(0.99::numeric, greatest(0.55::numeric, ss.trust_score + (((ss.d % 5) - 2)::numeric * 0.015))),
      2
    )
    else round(
      least(0.82::numeric, greatest(0.40::numeric, ss.trust_score - 0.12 + (((ss.d % 5) - 2)::numeric * 0.01))),
      2
    )
  end as gps_consistency_score
from scored_stats ss
on conflict (worker_profile_id, stat_date) do update
set active_hours = excluded.active_hours,
    completed_orders = excluded.completed_orders,
    accepted_orders = excluded.accepted_orders,
    cancelled_orders = excluded.cancelled_orders,
    gross_earnings_inr = excluded.gross_earnings_inr,
    platform_login_minutes = excluded.platform_login_minutes,
    gps_consistency_score = excluded.gps_consistency_score;

create temporary table tmp_reviewer_profile on commit drop as
select ip.profile_id
from public.insurer_profiles ip
order by ip.profile_id
limit 1;

create temporary table tmp_seed_login_claims on commit drop as
with base as (
  select
    w.worker_idx,
    w.worker_id,
    w.zone_id,
    w.city,
    w.center_lat,
    w.center_lng,
    w.avg_hourly_income_inr,
    w.trust_score,
    w.gps_consent,
    (
      now()
      - make_interval(days => (w.worker_idx % 27), hours => (w.worker_idx % 16), mins => (w.worker_idx % 53))
    )::timestamptz as started_at,
    case w.worker_idx % 6
      when 0 then 'rain'
      when 1 then 'aqi'
      when 2 then 'heat'
      when 3 then 'traffic'
      when 4 then 'outage'
      else 'demand'
    end as trigger_family,
    case
      when w.worker_idx % 5 = 0 then 'escalation'
      when w.worker_idx % 2 = 0 then 'claim'
      else 'watch'
    end as severity_band,
    case (w.worker_idx % 10)
      when 0 then 'paid'
      when 1 then 'approved'
      when 2 then 'auto_approved'
      when 3 then 'submitted'
      when 4 then 'soft_hold_verification'
      when 5 then 'fraud_escalated_review'
      when 6 then 'rejected'
      when 7 then 'post_approval_flagged'
      when 8 then 'soft_hold_verification'
      else 'submitted'
    end as claim_status
  from tmp_seed_login_workers w
),
enriched as (
  select
    b.*,
    case
      when b.trigger_family = 'rain' and b.severity_band = 'escalation' then 'RAIN_EXTREME'
      when b.trigger_family = 'rain' and b.severity_band = 'claim' then 'RAIN_HEAVY'
      when b.trigger_family = 'rain' then 'RAIN_WATCH'
      when b.trigger_family = 'aqi' and b.severity_band = 'escalation' then 'AQI_EXTREME'
      when b.trigger_family = 'aqi' and b.severity_band = 'claim' then 'AQI_SEVERE'
      when b.trigger_family = 'aqi' then 'AQI_POOR'
      when b.trigger_family = 'heat' and b.severity_band = 'escalation' then 'HEAT_EXTREME'
      when b.trigger_family = 'heat' and b.severity_band = 'claim' then 'HEAT_WAVE'
      when b.trigger_family = 'heat' then 'HEAT_ALERT'
      when b.trigger_family = 'traffic' then 'TRAFFIC_SEVERE'
      when b.trigger_family = 'outage' then 'PLATFORM_OUTAGE'
      else 'DEMAND_COLLAPSE'
    end as trigger_code,
    case
      when b.trigger_family in ('rain', 'aqi', 'heat') then 'public_source'
      else 'internal_operational'
    end as source_type,
    case
      when b.trigger_family = 'rain' and b.severity_band = 'escalation' then 132.0
      when b.trigger_family = 'rain' and b.severity_band = 'claim' then 79.0
      when b.trigger_family = 'rain' then 53.0
      when b.trigger_family = 'aqi' and b.severity_band = 'escalation' then 415.0
      when b.trigger_family = 'aqi' and b.severity_band = 'claim' then 334.0
      when b.trigger_family = 'aqi' then 248.0
      when b.trigger_family = 'heat' and b.severity_band = 'escalation' then 48.0
      when b.trigger_family = 'heat' and b.severity_band = 'claim' then 45.0
      when b.trigger_family = 'heat' then 41.0
      when b.trigger_family = 'traffic' and b.severity_band = 'escalation' then 62.0
      when b.trigger_family = 'traffic' and b.severity_band = 'claim' then 49.0
      when b.trigger_family = 'traffic' then 33.0
      when b.trigger_family = 'outage' and b.severity_band = 'escalation' then 58.0
      when b.trigger_family = 'outage' and b.severity_band = 'claim' then 36.0
      when b.trigger_family = 'outage' then 19.0
      when b.severity_band = 'escalation' then 52.0
      when b.severity_band = 'claim' then 37.0
      else 24.0
    end + ((b.worker_idx % 7) - 3)::numeric as observed_value,
    case
      when b.trigger_family = 'rain' then 'IMD rainfall trigger threshold'
      when b.trigger_family = 'aqi' then 'CPCB AQI trigger threshold'
      when b.trigger_family = 'heat' then 'IMD heat trigger threshold'
      else null
    end as official_threshold_label,
    case
      when b.trigger_family = 'rain' then '64.5 mm'
      when b.trigger_family = 'aqi' then '301+'
      when b.trigger_family = 'heat' then '45C'
      when b.trigger_family = 'traffic' then '40% delay'
      when b.trigger_family = 'outage' then '30 min outage'
      else '35% demand drop'
    end as product_threshold_value,
    case
      when b.severity_band = 'watch' then null
      else b.started_at + make_interval(hours => 2 + (b.worker_idx % 4))
    end as ended_at,
    case
      when b.claim_status in ('auto_approved', 'approved', 'paid') and b.worker_idx % 3 = 0 then 'trigger_auto'
      else 'manual'
    end as claim_mode,
    case
      when b.claim_status in ('approved', 'auto_approved', 'paid', 'rejected', 'post_approval_flagged') then 'resolved'
      when b.claim_status in ('soft_hold_verification', 'fraud_escalated_review') then 'in_review'
      else 'unassigned'
    end as assignment_state,
    format(
      'Synthetic %s disruption claim in %s (worker-%s).',
      upper(b.trigger_family),
      b.city,
      lpad(b.worker_idx::text, 3, '0')
    ) as claim_reason,
    round((b.center_lat + (((b.worker_idx % 9) - 4)::numeric * 0.0011))::numeric, 6) as stated_lat,
    round((b.center_lng + (((b.worker_idx % 9) - 4)::numeric * 0.0013))::numeric, 6) as stated_lng,
    (b.started_at + make_interval(mins => 45 + (b.worker_idx % 35)))::timestamptz as claimed_at,
    round((b.avg_hourly_income_inr * (48 + (b.worker_idx % 10)))::numeric, 2) as covered_weekly_income_b,
    (0.14 + ((b.worker_idx % 4)::numeric * 0.01))::numeric(6,4) as claim_probability_p,
    case
      when b.severity_band = 'watch' then 0.4500::numeric(6,4)
      when b.severity_band = 'claim' then 0.7600::numeric(6,4)
      else 0.9200::numeric(6,4)
    end as severity_score_s,
    round((0.6800 + ((b.worker_idx % 21)::numeric / 100))::numeric, 4) as exposure_score_e,
    round(
      least(
        0.9700::numeric,
        greatest(
          0.5200::numeric,
          b.trust_score +
          case when b.gps_consent then 0.0600 else -0.0700 end +
          (((b.worker_idx % 5) - 2)::numeric * 0.0100)
        )
      )::numeric,
      4
    ) as confidence_score_c,
    case
      when b.claim_status = 'fraud_escalated_review' then 0.4200::numeric(6,4)
      when b.claim_status = 'rejected' then 0.5500::numeric(6,4)
      when b.claim_status = 'post_approval_flagged' then 0.6200::numeric(6,4)
      when b.claim_status = 'soft_hold_verification' then 0.2400::numeric(6,4)
      when b.claim_status = 'submitted' then 0.1200::numeric(6,4)
      else 0.0600::numeric(6,4)
    end as fraud_holdback_fh
  from base b
),
scored as (
  select
    e.*,
    1.0000::numeric(6,4) as outlier_uplift_u,
    round((e.covered_weekly_income_b * 0.75)::numeric, 2) as payout_cap,
    round(
      (
        e.covered_weekly_income_b
        * e.claim_probability_p
        * e.severity_score_s
        * e.exposure_score_e
        * e.confidence_score_c
        * (1 - e.fraud_holdback_fh)
      )::numeric,
      2
    ) as expected_payout,
    round(
      greatest(
        18::numeric,
        (
          e.covered_weekly_income_b
          * e.claim_probability_p
          * e.severity_score_s
          * e.exposure_score_e
          * e.confidence_score_c
          * (1 - e.fraud_holdback_fh)
        ) / 0.78
      )::numeric,
      2
    ) as gross_premium,
    round(
      least(
        e.covered_weekly_income_b * 0.75,
        (
          e.covered_weekly_income_b
          * e.severity_score_s
          * e.exposure_score_e
          * e.confidence_score_c
          * (1 - e.fraud_holdback_fh)
        )
      )::numeric,
      2
    ) as recommended_payout
  from enriched e
)
select
  s.worker_idx,
  pg_temp.seed_uuid('covara19-trigger-' || s.worker_idx) as trigger_id,
  pg_temp.seed_uuid('covara19-claim-' || s.worker_idx) as claim_id,
  pg_temp.seed_uuid('covara19-payout-' || s.worker_idx) as payout_id,
  pg_temp.seed_uuid('covara19-evidence-' || s.worker_idx) as evidence_id,
  s.worker_id,
  s.zone_id,
  s.city,
  s.trigger_family,
  s.trigger_code,
  s.observed_value,
  s.official_threshold_label,
  s.product_threshold_value,
  s.severity_band,
  s.source_type,
  s.started_at,
  s.ended_at,
  s.claim_mode,
  s.assignment_state,
  case
    when s.claim_status in ('soft_hold_verification', 'fraud_escalated_review', 'post_approval_flagged')
      then (select profile_id from tmp_reviewer_profile limit 1)
    else null
  end as assigned_reviewer_profile_id,
  s.claim_reason,
  s.stated_lat,
  s.stated_lng,
  s.claimed_at,
  s.claim_status,
  s.covered_weekly_income_b,
  s.claim_probability_p,
  s.severity_score_s,
  s.exposure_score_e,
  s.confidence_score_c,
  s.fraud_holdback_fh,
  s.outlier_uplift_u,
  s.payout_cap,
  s.expected_payout,
  s.gross_premium,
  s.recommended_payout
from scored s;

insert into public.trigger_events (
  id,
  city,
  zone_id,
  trigger_family,
  trigger_code,
  observed_value,
  official_threshold_label,
  product_threshold_value,
  severity_band,
  source_type,
  started_at,
  ended_at
)
select
  c.trigger_id,
  c.city,
  c.zone_id,
  c.trigger_family,
  c.trigger_code,
  c.observed_value,
  c.official_threshold_label,
  c.product_threshold_value,
  c.severity_band,
  c.source_type,
  c.started_at,
  c.ended_at
from tmp_seed_login_claims c
on conflict (id) do update
set observed_value = excluded.observed_value,
    official_threshold_label = excluded.official_threshold_label,
    product_threshold_value = excluded.product_threshold_value,
    severity_band = excluded.severity_band,
    source_type = excluded.source_type,
    started_at = excluded.started_at,
    ended_at = excluded.ended_at;

insert into public.manual_claims (
  id,
  worker_profile_id,
  trigger_event_id,
  assigned_reviewer_profile_id,
  claim_mode,
  assignment_state,
  claim_reason,
  stated_lat,
  stated_lng,
  claimed_at,
  assigned_at,
  review_due_at,
  escalated_at,
  escalation_reason,
  claim_status
)
select
  c.claim_id,
  c.worker_id,
  c.trigger_id,
  c.assigned_reviewer_profile_id,
  c.claim_mode,
  c.assignment_state,
  c.claim_reason,
  c.stated_lat,
  c.stated_lng,
  c.claimed_at,
  case when c.assigned_reviewer_profile_id is not null then c.claimed_at + interval '25 minutes' else null end,
  case when c.assigned_reviewer_profile_id is not null then c.claimed_at + interval '18 hours' else null end,
  case when c.claim_status in ('fraud_escalated_review', 'post_approval_flagged') then c.claimed_at + interval '4 hours' else null end,
  case when c.claim_status in ('fraud_escalated_review', 'post_approval_flagged') then 'Synthetic fraud risk escalation scenario' else null end,
  c.claim_status
from tmp_seed_login_claims c
on conflict (id) do update
set trigger_event_id = excluded.trigger_event_id,
    assigned_reviewer_profile_id = excluded.assigned_reviewer_profile_id,
    claim_mode = excluded.claim_mode,
    assignment_state = excluded.assignment_state,
    claim_reason = excluded.claim_reason,
    stated_lat = excluded.stated_lat,
    stated_lng = excluded.stated_lng,
    claimed_at = excluded.claimed_at,
    assigned_at = excluded.assigned_at,
    review_due_at = excluded.review_due_at,
    escalated_at = excluded.escalated_at,
    escalation_reason = excluded.escalation_reason,
    claim_status = excluded.claim_status;

insert into public.claim_evidence (
  id,
  claim_id,
  evidence_type,
  storage_path,
  captured_at,
  exif_lat,
  exif_lng,
  exif_timestamp,
  integrity_score
)
select
  c.evidence_id,
  c.claim_id,
  case when c.worker_idx % 3 = 0 then 'geo' else 'photo' end,
  case when c.worker_idx % 3 = 0 then null else ('claim-evidence/synthetic/worker-' || lpad(c.worker_idx::text, 3, '0') || '.jpg') end,
  c.claimed_at - interval '6 minutes',
  round((c.stated_lat + (((c.worker_idx % 5) - 2)::numeric * 0.0002))::numeric, 6),
  round((c.stated_lng + (((c.worker_idx % 5) - 2)::numeric * 0.0002))::numeric, 6),
  c.claimed_at - interval '8 minutes',
  case
    when c.claim_status in ('fraud_escalated_review', 'rejected', 'post_approval_flagged')
      then round(greatest(0.08::numeric, 0.28::numeric - ((c.worker_idx % 5) * 0.03)::numeric), 2)
    when c.claim_status = 'soft_hold_verification'
      then round((0.62::numeric - ((c.worker_idx % 4) * 0.05)::numeric), 2)
    else round((0.82::numeric + ((c.worker_idx % 4) * 0.03)::numeric), 2)
  end
from tmp_seed_login_claims c
where c.worker_idx % 4 <> 0
on conflict (id) do update
set evidence_type = excluded.evidence_type,
    storage_path = excluded.storage_path,
    captured_at = excluded.captured_at,
    exif_lat = excluded.exif_lat,
    exif_lng = excluded.exif_lng,
    exif_timestamp = excluded.exif_timestamp,
    integrity_score = excluded.integrity_score;

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
select
  c.payout_id,
  c.claim_id,
  c.covered_weekly_income_b,
  c.claim_probability_p,
  c.severity_score_s,
  c.exposure_score_e,
  c.confidence_score_c,
  c.fraud_holdback_fh,
  c.outlier_uplift_u,
  c.payout_cap,
  c.expected_payout,
  c.gross_premium,
  c.recommended_payout,
  jsonb_build_object(
    'seed_batch', '19_login_ready_workers_200',
    'worker_index', c.worker_idx,
    'status', c.claim_status,
    'city', c.city,
    'trigger_family', c.trigger_family,
    'formula', 'min(cap, B*S*E*C*(1-FH))'
  ),
  now()
from tmp_seed_login_claims c
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

-- Quick integrity summary (non-zero KPI confidence checks)
select
  'seeded_login_workers' as metric,
  count(*)::int as value
from public.profiles
where lower(coalesce(email, '')) like 'worker%@synthetic.covara.dev';

select
  claim_status,
  count(*)::int as rows
from public.manual_claims
where id in (select claim_id from tmp_seed_login_claims)
group by claim_status
order by rows desc, claim_status;

select
  round(sum(recommended_payout)::numeric, 2) as total_recommended_payout_inr,
  round(avg(fraud_holdback_fh)::numeric, 4) as avg_fraud_holdback,
  count(*) filter (where fraud_holdback_fh > 0.30) as high_fraud_rows
from public.payout_recommendations
where id in (select payout_id from tmp_seed_login_claims);

-- Formatted login sheet (all 200 workers)
select
  p.email as login_email,
  'Covara#2026!'::text as password,
  p.full_name,
  wp.city,
  wp.platform_name,
  wp.vehicle_type,
  wp.bank_verified,
  wp.gps_consent,
  wp.trust_score
from public.profiles p
join public.worker_profiles wp on wp.profile_id = p.id
where lower(coalesce(p.email, '')) like 'worker%@synthetic.covara.dev'
order by p.email;

commit;

notify pgrst, 'reload schema';
