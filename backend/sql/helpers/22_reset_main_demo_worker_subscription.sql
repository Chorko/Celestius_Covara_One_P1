-- ============================================================================
-- 22_reset_main_demo_worker_subscription.sql
--
-- Purpose:
--   Reset one demo worker's Stripe subscription/payment footprint so the worker
--   can repurchase coverage repeatedly during demos.
--
-- Default target:
--   worker@demo.com
--
-- Safe behavior:
--   - Removes policy rows for the target worker
--   - Removes policy-purchase reward coin ledger rows
--   - Removes stripe_checkout audit events for that worker
--   - Leaves worker profile/auth intact
--
-- Usage:
--   1) Edit the email value in tmp_reset_worker_target if needed
--   2) Run entire file in Supabase SQL Editor
-- ============================================================================

begin;

create temporary table if not exists tmp_reset_worker_target (
  email text primary key
) on commit drop;

truncate tmp_reset_worker_target;
insert into tmp_reset_worker_target (email)
values ('worker@demo.com');

create temporary table if not exists tmp_reset_worker_ids (
  id uuid primary key
) on commit drop;

truncate tmp_reset_worker_ids;
insert into tmp_reset_worker_ids (id)
select p.id
from public.profiles p
join tmp_reset_worker_target t
  on lower(p.email) = lower(t.email)
on conflict (id) do nothing;

-- Remove subscription rows so worker can buy again immediately.
delete from public.policies
where worker_profile_id in (select id from tmp_reset_worker_ids);

-- Remove policy-purchase reward rows tied to checkout cycles.
delete from public.coins_ledger
where profile_id in (select id from tmp_reset_worker_ids)
  and activity = 'policy_purchase';

-- Remove Stripe checkout audit rows for a clean payment timeline in demos.
delete from public.audit_events
where entity_type = 'stripe_checkout'
  and (
    actor_profile_id in (select id from tmp_reset_worker_ids)
    or coalesce(event_payload->>'worker_profile_id', '') in (
      select id::text from tmp_reset_worker_ids
    )
  );

commit;

-- Verification snapshot
select
  p.email,
  p.id as profile_id,
  (
    select count(*)
    from public.policies pol
    where pol.worker_profile_id = p.id
  ) as remaining_policies,
  (
    select count(*)
    from public.coins_ledger cl
    where cl.profile_id = p.id and cl.activity = 'policy_purchase'
  ) as remaining_policy_purchase_coins,
  (
    select count(*)
    from public.audit_events ae
    where ae.entity_type = 'stripe_checkout'
      and (
        ae.actor_profile_id = p.id
        or coalesce(ae.event_payload->>'worker_profile_id', '') = p.id::text
      )
  ) as remaining_stripe_checkout_events
from public.profiles p
join tmp_reset_worker_target t
  on lower(p.email) = lower(t.email);
