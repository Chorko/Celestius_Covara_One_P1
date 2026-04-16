-- ============================================================
-- 21_3month_history_seed.sql
-- Covara One — 90-Day Synthetic History Extension
--
-- Run after worker/auth provisioning + core synthetic seed scripts.
-- Idempotent and safe to re-run.
-- ============================================================

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

create temporary table tmp_3m_workers on commit drop as
select
  row_number() over (order by p.email)::int as worker_idx,
  p.id as worker_profile_id,
  wp.city,
  wp.preferred_zone_id as zone_id,
  coalesce(wp.avg_hourly_income_inr, 130)::numeric as avg_hourly_income_inr,
  coalesce(wp.trust_score, 0.75)::numeric as trust_score,
  coalesce(wp.gps_consent, false) as gps_consent
from public.profiles p
join public.worker_profiles wp on wp.profile_id = p.id
where lower(coalesce(p.email, '')) like 'worker%@synthetic.covara.dev';

-- 90 days of daily worker stats for dashboard realism.
with stats_seed as (
  select
    w.worker_profile_id,
    (current_date - d)::date as stat_date,
    w.avg_hourly_income_inr,
    w.trust_score,
    w.gps_consent,
    w.worker_idx,
    d,
    case
      when ((w.worker_idx + d) % 31) = 0 then 0::numeric
      when extract(isodow from (current_date - d)::date) in (6, 7)
        then round((6.6 + ((w.worker_idx % 5)::numeric * 0.42))::numeric, 2)
      else round((8.1 + ((w.worker_idx % 6)::numeric * 0.38))::numeric, 2)
    end as active_hours
  from tmp_3m_workers w
  cross join generate_series(0, 89) d
), scored as (
  select
    s.*,
    case
      when s.active_hours = 0 then 0
      else greatest(
        0,
        floor(s.active_hours * (1.26 + ((s.worker_idx % 4)::numeric * 0.10)))::int + ((s.d % 3) - 1)
      )
    end as completed_orders
  from stats_seed s
)
insert into public.platform_worker_daily_stats (
  id,
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
  pg_temp.seed_uuid('covara21-stat-' || sc.worker_profile_id || '-' || sc.stat_date) as id,
  sc.worker_profile_id,
  sc.stat_date,
  sc.active_hours,
  sc.completed_orders,
  case
    when sc.active_hours = 0 then 0
    else sc.completed_orders + 1 + ((sc.worker_idx + sc.d) % 3)
  end as accepted_orders,
  case
    when sc.active_hours = 0 then 0
    else ((sc.worker_idx + sc.d) % 2)
  end as cancelled_orders,
  round((sc.completed_orders * (sc.avg_hourly_income_inr * (1.10 + ((sc.d % 4)::numeric * 0.015))))::numeric, 2) as gross_earnings_inr,
  case when sc.active_hours = 0 then 0 else round((sc.active_hours * 60)::numeric)::int end as platform_login_minutes,
  case
    when sc.gps_consent then round(
      least(0.99::numeric, greatest(0.56::numeric, sc.trust_score + (((sc.d % 5) - 2)::numeric * 0.012))),
      2
    )
    else round(
      least(0.84::numeric, greatest(0.42::numeric, sc.trust_score - 0.11 + (((sc.d % 5) - 2)::numeric * 0.010))),
      2
    )
  end as gps_consistency_score
from scored sc
on conflict (worker_profile_id, stat_date) do update
set active_hours = excluded.active_hours,
    completed_orders = excluded.completed_orders,
    accepted_orders = excluded.accepted_orders,
    cancelled_orders = excluded.cancelled_orders,
    gross_earnings_inr = excluded.gross_earnings_inr,
    platform_login_minutes = excluded.platform_login_minutes,
    gps_consistency_score = excluded.gps_consistency_score;

-- Reward history depth: monthly engagement + claim reward events.
insert into public.coins_ledger (
  id,
  profile_id,
  activity,
  coins,
  description,
  reference_id,
  created_at
)
select
  pg_temp.seed_uuid('covara21-coins-' || w.worker_profile_id || '-' || m.month_offset || '-' || m.activity),
  w.worker_profile_id,
  m.activity,
  m.coins,
  m.description,
  null,
  (date_trunc('day', now()) - make_interval(days => (m.month_offset * 30) + ((w.worker_idx % 9) + 1)))::timestamptz
from tmp_3m_workers w
cross join (
  values
    (0, 'weekly_active', 10, 'Weekly active worker bonus'),
    (1, 'weekly_active', 10, 'Weekly active worker bonus'),
    (2, 'weekly_active', 10, 'Weekly active worker bonus'),
    (0, 'claim_approved', 25, 'Reward for approved claim')
) as m(month_offset, activity, coins, description)
on conflict (id) do nothing;

-- Quick verification
select
  count(distinct worker_profile_id)::int as seeded_workers,
  count(*)::int as stats_rows_90d
from public.platform_worker_daily_stats
where stat_date >= (current_date - 89);

select
  activity,
  count(*)::int as rows,
  sum(coins)::int as total_coins
from public.coins_ledger
where created_at >= (now() - interval '95 days')
group by activity
order by activity;

commit;

notify pgrst, 'reload schema';
