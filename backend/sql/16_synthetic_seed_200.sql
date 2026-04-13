-- ============================================================
-- 16_synthetic_seed_200.sql
-- Covara One - Scale Seed Pack (200 rows)
--
-- Adds 200 synthetic trigger events, manual claims, and payout
-- recommendations for dashboard and review stress-testing.
-- Safe to re-run (deterministic UUIDs + upserts).
--
-- Run AFTER:
--   - 00_unified_migration.sql
--   - 01_enterprise_alignment_patch_2026_04_12.sql
--   - 06_synthetic_seed.sql (recommended baseline identities/workers)
-- ============================================================

begin;

do $$
begin
  if not exists (select 1 from public.worker_profiles) then
    raise exception 'worker_profiles is empty. Run 06_synthetic_seed.sql first.';
  end if;

  if not exists (select 1 from public.zones) then
    raise exception 'zones is empty. Run base migration/seed scripts first.';
  end if;
end $$;

create temporary table tmp_seed_200 on commit drop as
with worker_pool as (
  select
    wp.profile_id,
    wp.city,
    wp.preferred_zone_id,
    row_number() over (order by wp.profile_id) as rn
  from public.worker_profiles wp
),
worker_count as (
  select count(*)::int as cnt from worker_pool
),
zone_pool as (
  select
    z.id as zone_id,
    z.city,
    z.center_lat,
    z.center_lng,
    row_number() over (order by z.id) as rn
  from public.zones z
),
zone_count as (
  select count(*)::int as cnt from zone_pool
),
seed_base as (
  select
    gs as seed_n,
    ((gs - 1) % (select cnt from worker_count)) + 1 as worker_rn,
    ((gs - 1) % (select cnt from zone_count)) + 1 as zone_rn
  from generate_series(1, 200) as gs
),
selected as (
  select
    sb.seed_n,
    wp.profile_id as worker_profile_id,
    coalesce(wp.preferred_zone_id, zp.zone_id) as zone_id
  from seed_base sb
  join worker_pool wp on wp.rn = sb.worker_rn
  join zone_pool zp on zp.rn = sb.zone_rn
),
enriched as (
  select
    s.seed_n,
    s.worker_profile_id,
    z.id as zone_id,
    z.city,
    z.center_lat,
    z.center_lng,
    case s.seed_n % 6
      when 0 then 'rain'
      when 1 then 'aqi'
      when 2 then 'heat'
      when 3 then 'traffic'
      when 4 then 'outage'
      else 'demand'
    end as trigger_family,
    case
      when s.seed_n % 5 = 0 then 'escalation'
      when s.seed_n % 2 = 0 then 'claim'
      else 'watch'
    end as severity_band
  from selected s
  join public.zones z on z.id = s.zone_id
),
timed as (
  select
    e.*,
    (
      now()
      - make_interval(days => (e.seed_n % 35), hours => (e.seed_n % 19), mins => (e.seed_n % 47))
    )::timestamptz as started_at
  from enriched e
),
classified as (
  select
    t.*,
    case
      when t.trigger_family = 'rain' and t.severity_band = 'escalation' then 'RAIN_EXTREME'
      when t.trigger_family = 'rain' and t.severity_band = 'claim' then 'RAIN_HEAVY'
      when t.trigger_family = 'rain' then 'RAIN_WATCH'
      when t.trigger_family = 'aqi' and t.severity_band = 'escalation' then 'AQI_EXTREME'
      when t.trigger_family = 'aqi' and t.severity_band = 'claim' then 'AQI_SEVERE'
      when t.trigger_family = 'aqi' then 'AQI_POOR'
      when t.trigger_family = 'heat' and t.severity_band = 'escalation' then 'HEAT_EXTREME'
      when t.trigger_family = 'heat' and t.severity_band = 'claim' then 'HEAT_WAVE'
      when t.trigger_family = 'heat' then 'HEAT_ALERT'
      when t.trigger_family = 'traffic' then 'TRAFFIC_SEVERE'
      when t.trigger_family = 'outage' then 'PLATFORM_OUTAGE'
      else 'DEMAND_COLLAPSE'
    end as trigger_code,
    case
      when t.trigger_family = 'rain' then 'R3'
      when t.trigger_family = 'aqi' then 'R1'
      when t.trigger_family = 'heat' then 'R4'
      else null
    end as source_ref_id,
    case
      when t.trigger_family in ('rain', 'aqi', 'heat') then 'public_source'
      else 'internal_operational'
    end as source_type,
    case
      when t.trigger_family = 'rain' and t.severity_band = 'escalation' then 130.0
      when t.trigger_family = 'rain' and t.severity_band = 'claim' then 78.0
      when t.trigger_family = 'rain' then 52.0
      when t.trigger_family = 'aqi' and t.severity_band = 'escalation' then 420.0
      when t.trigger_family = 'aqi' and t.severity_band = 'claim' then 335.0
      when t.trigger_family = 'aqi' then 245.0
      when t.trigger_family = 'heat' and t.severity_band = 'escalation' then 48.0
      when t.trigger_family = 'heat' and t.severity_band = 'claim' then 45.0
      when t.trigger_family = 'heat' then 41.0
      when t.trigger_family = 'traffic' and t.severity_band = 'escalation' then 62.0
      when t.trigger_family = 'traffic' and t.severity_band = 'claim' then 48.0
      when t.trigger_family = 'traffic' then 32.0
      when t.trigger_family = 'outage' and t.severity_band = 'escalation' then 58.0
      when t.trigger_family = 'outage' and t.severity_band = 'claim' then 35.0
      when t.trigger_family = 'outage' then 18.0
      when t.severity_band = 'escalation' then 52.0
      when t.severity_band = 'claim' then 36.0
      else 24.0
    end + ((t.seed_n % 7) - 3)::numeric as observed_value,
    case
      when t.trigger_family = 'rain' then 'IMD heavy rainfall threshold'
      when t.trigger_family = 'aqi' then 'CPCB AQI threshold'
      when t.trigger_family = 'heat' then 'IMD heat threshold'
      else null
    end as official_threshold_label,
    case
      when t.trigger_family = 'rain' then '64.5 mm'
      when t.trigger_family = 'aqi' then '301+'
      when t.trigger_family = 'heat' then '45C'
      when t.trigger_family = 'traffic' then '40% delay'
      when t.trigger_family = 'outage' then '30 min outage'
      else '35% demand drop'
    end as product_threshold_value
  from timed t
),
scored as (
  select
    c.*,
    case
      when c.seed_n % 8 = 0 then 'approved'
      when c.seed_n % 8 = 1 then 'paid'
      when c.seed_n % 8 = 2 then 'auto_approved'
      when c.seed_n % 8 = 3 then 'soft_hold_verification'
      when c.seed_n % 8 = 4 then 'fraud_escalated_review'
      when c.seed_n % 8 = 5 then 'rejected'
      else 'submitted'
    end as claim_status
  from classified c
),
final_seed as (
  select
    s.seed_n,
    (
      substr(md5('covara-16-trigger-' || s.seed_n::text), 1, 8) || '-' ||
      substr(md5('covara-16-trigger-' || s.seed_n::text), 9, 4) || '-' ||
      substr(md5('covara-16-trigger-' || s.seed_n::text), 13, 4) || '-' ||
      substr(md5('covara-16-trigger-' || s.seed_n::text), 17, 4) || '-' ||
      substr(md5('covara-16-trigger-' || s.seed_n::text), 21, 12)
    )::uuid as trigger_id,
    (
      substr(md5('covara-16-claim-' || s.seed_n::text), 1, 8) || '-' ||
      substr(md5('covara-16-claim-' || s.seed_n::text), 9, 4) || '-' ||
      substr(md5('covara-16-claim-' || s.seed_n::text), 13, 4) || '-' ||
      substr(md5('covara-16-claim-' || s.seed_n::text), 17, 4) || '-' ||
      substr(md5('covara-16-claim-' || s.seed_n::text), 21, 12)
    )::uuid as claim_id,
    (
      substr(md5('covara-16-payout-' || s.seed_n::text), 1, 8) || '-' ||
      substr(md5('covara-16-payout-' || s.seed_n::text), 9, 4) || '-' ||
      substr(md5('covara-16-payout-' || s.seed_n::text), 13, 4) || '-' ||
      substr(md5('covara-16-payout-' || s.seed_n::text), 17, 4) || '-' ||
      substr(md5('covara-16-payout-' || s.seed_n::text), 21, 12)
    )::uuid as payout_id,
    s.worker_profile_id,
    s.zone_id,
    s.city,
    s.center_lat,
    s.center_lng,
    s.trigger_family,
    s.trigger_code,
    s.source_ref_id,
    s.observed_value,
    s.official_threshold_label,
    s.product_threshold_value,
    s.severity_band,
    s.source_type,
    s.started_at,
    case
      when s.seed_n % 4 = 0 then s.started_at + interval '3 hours'
      else null
    end as ended_at,
    case
      when s.severity_band in ('claim', 'escalation') and s.seed_n % 3 = 0 then 'trigger_auto'
      else 'manual'
    end as claim_mode,
    case
      when s.claim_status in ('approved', 'paid', 'auto_approved', 'rejected') then 'resolved'
      when s.claim_status in ('soft_hold_verification', 'fraud_escalated_review') then 'in_review'
      else 'unassigned'
    end as assignment_state,
    (
      'Synthetic seed batch 16 claim #' || s.seed_n ||
      ' - ' || upper(s.trigger_family) || ' disruption in ' || s.city
    ) as claim_reason,
    round((s.center_lat + (((s.seed_n % 9) - 4)::numeric * 0.0012))::numeric, 6) as stated_lat,
    round((s.center_lng + (((s.seed_n % 9) - 4)::numeric * 0.0014))::numeric, 6) as stated_lng,
    (s.started_at + interval '90 minutes') as claimed_at,
    s.claim_status,
    round((2800 + ((s.seed_n % 22) * 130))::numeric, 2) as covered_weekly_income_b,
    0.1500::numeric(6,4) as claim_probability_p,
    case
      when s.severity_band = 'watch' then 0.4500::numeric(6,4)
      when s.severity_band = 'claim' then 0.7600::numeric(6,4)
      else 0.9400::numeric(6,4)
    end as severity_score_s,
    round((0.7000 + ((s.seed_n % 21)::numeric / 100))::numeric, 4) as exposure_score_e,
    round((0.6800 + ((s.seed_n % 18)::numeric / 100))::numeric, 4) as confidence_score_c,
    case
      when s.claim_status in ('fraud_escalated_review', 'rejected') then 0.4500::numeric(6,4)
      when s.claim_status = 'soft_hold_verification' then 0.2200::numeric(6,4)
      else 0.0800::numeric(6,4)
    end as fraud_holdback_fh
  from scored s
)
select
  fs.*,
  1.0000::numeric(6,4) as outlier_uplift_u,
  round((fs.covered_weekly_income_b * 0.75)::numeric, 2) as payout_cap,
  round(
    (
      fs.covered_weekly_income_b
      * fs.claim_probability_p
      * fs.severity_score_s
      * fs.exposure_score_e
      * fs.confidence_score_c
      * (1 - fs.fraud_holdback_fh)
    )::numeric,
    2
  ) as expected_payout,
  round(
    (
      (
        fs.covered_weekly_income_b
        * fs.claim_probability_p
        * fs.severity_score_s
        * fs.exposure_score_e
        * fs.confidence_score_c
        * (1 - fs.fraud_holdback_fh)
      ) / 0.78
    )::numeric,
    2
  ) as gross_premium,
  round(
    least(
      fs.covered_weekly_income_b * 0.75,
      fs.covered_weekly_income_b
      * fs.severity_score_s
      * fs.exposure_score_e
      * fs.confidence_score_c
      * (1 - fs.fraud_holdback_fh)
    )::numeric,
    2
  ) as recommended_payout
from final_seed fs;

insert into public.trigger_events (
  id,
  city,
  zone_id,
  trigger_family,
  trigger_code,
  source_ref_id,
  observed_value,
  official_threshold_label,
  product_threshold_value,
  severity_band,
  source_type,
  started_at,
  ended_at
)
select
  trigger_id,
  city,
  zone_id,
  trigger_family,
  trigger_code,
  source_ref_id,
  observed_value,
  official_threshold_label,
  product_threshold_value,
  severity_band,
  source_type,
  started_at,
  ended_at
from tmp_seed_200
on conflict (id) do update
set
  observed_value = excluded.observed_value,
  severity_band = excluded.severity_band,
  source_type = excluded.source_type,
  started_at = excluded.started_at,
  ended_at = excluded.ended_at,
  product_threshold_value = excluded.product_threshold_value;

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
select
  claim_id,
  worker_profile_id,
  trigger_id,
  claim_mode,
  assignment_state,
  claim_reason,
  stated_lat,
  stated_lng,
  claimed_at,
  claim_status
from tmp_seed_200
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
select
  payout_id,
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
  jsonb_build_object(
    'seed_batch', '16_synthetic_seed_200',
    'seed_number', seed_n,
    'notes', 'Synthetic stress-test payout recommendation'
  ),
  now()
from tmp_seed_200
on conflict (id) do update
set
  covered_weekly_income_b = excluded.covered_weekly_income_b,
  claim_probability_p = excluded.claim_probability_p,
  severity_score_s = excluded.severity_score_s,
  exposure_score_e = excluded.exposure_score_e,
  confidence_score_c = excluded.confidence_score_c,
  fraud_holdback_fh = excluded.fraud_holdback_fh,
  payout_cap = excluded.payout_cap,
  expected_payout = excluded.expected_payout,
  gross_premium = excluded.gross_premium,
  recommended_payout = excluded.recommended_payout,
  explanation_json = excluded.explanation_json,
  created_at = excluded.created_at;

select 'seed_batch_16_rows' as metric, count(*)::int as value from tmp_seed_200;

commit;
