-- Covara One helper 24
-- Purpose: remove null/placeholder worker profile fields that make dashboard sections look unseeded.
-- Safe to run multiple times (idempotent updates).

begin;

-- 1) Backfill missing worker phone numbers in profiles.
with missing_phones as (
  select
    p.id,
    row_number() over (order by p.created_at, p.id) as rn
  from public.profiles p
  where p.role = 'worker'
    and nullif(btrim(p.phone), '') is null
)
update public.profiles p
set phone = '+91' || (9600000000::bigint + mp.rn)::text
from missing_phones mp
where p.id = mp.id;

-- 2) Normalize worker profile placeholders and fill missing zone links.
with default_zone as (
  select z.id as zone_id
  from public.zones z
  order by z.city, z.zone_name
  limit 1
),
city_zone as (
  select lower(z.city) as city_key, min(z.id::text)::uuid as zone_id
  from public.zones z
  group by lower(z.city)
),
policy_city as (
  select
    p.worker_profile_id as profile_id,
    z.city
  from public.policies p
  join public.zones z on z.id = p.zone_id
  where p.status = 'active'
),
profile_targets as (
  select
    wp.profile_id,
    case
      when nullif(btrim(wp.city), '') is null or lower(btrim(wp.city)) = 'pending local'
        then coalesce(nullif(btrim(pc.city), ''), 'Mumbai')
      else wp.city
    end as target_city,
    case
      when nullif(btrim(wp.platform_name), '') is null or lower(btrim(wp.platform_name)) = 'pending assignment'
        then 'Swiggy'
      else wp.platform_name
    end as target_platform,
    case
      when nullif(btrim(wp.vehicle_type), '') is null then 'Bike'
      else wp.vehicle_type
    end as target_vehicle,
    coalesce(
      wp.trust_score,
      case
        when wp.bank_verified and wp.gps_consent then 0.82
        when wp.bank_verified then 0.76
        else 0.68
      end
    ) as target_trust
  from public.worker_profiles wp
  left join policy_city pc on pc.profile_id = wp.profile_id
)
update public.worker_profiles wp
set
  city = pt.target_city,
  platform_name = pt.target_platform,
  vehicle_type = pt.target_vehicle,
  trust_score = pt.target_trust,
  preferred_zone_id = coalesce(
    wp.preferred_zone_id,
    cz.zone_id,
    dz.zone_id
  )
from profile_targets pt
left join city_zone cz on cz.city_key = lower(pt.target_city)
cross join default_zone dz
where wp.profile_id = pt.profile_id
  and (
    nullif(btrim(wp.city), '') is null
    or lower(btrim(wp.city)) = 'pending local'
    or nullif(btrim(wp.platform_name), '') is null
    or lower(btrim(wp.platform_name)) = 'pending assignment'
    or nullif(btrim(wp.vehicle_type), '') is null
    or wp.trust_score is null
    or wp.preferred_zone_id is null
  );

-- 3) Ensure every active policy has a zone_id.
with default_zone as (
  select z.id as zone_id
  from public.zones z
  order by z.city, z.zone_name
  limit 1
),
city_zone as (
  select lower(z.city) as city_key, min(z.id::text)::uuid as zone_id
  from public.zones z
  group by lower(z.city)
),
policy_targets as (
  select
    p.id as policy_row_id,
    coalesce(p.zone_id, wp.preferred_zone_id, cz.zone_id, dz.zone_id) as target_zone
  from public.policies p
  join public.worker_profiles wp on wp.profile_id = p.worker_profile_id
  left join city_zone cz on cz.city_key = lower(wp.city)
  cross join default_zone dz
  where p.status = 'active'
    and p.zone_id is null
)
update public.policies p
set
  zone_id = pt.target_zone,
  updated_at = now()
from policy_targets pt
where p.id = pt.policy_row_id
  and pt.target_zone is not null;

commit;

-- Optional verification query:
-- select
--   (select count(*) from public.profiles where role='worker' and nullif(btrim(phone), '') is null) as worker_phone_nulls,
--   (select count(*) from public.worker_profiles where lower(btrim(city))='pending local' or lower(btrim(platform_name))='pending assignment' or preferred_zone_id is null or vehicle_type is null or trust_score is null) as worker_profile_gaps,
--   (select count(*) from public.policies where status='active' and zone_id is null) as active_policy_zone_gaps;
