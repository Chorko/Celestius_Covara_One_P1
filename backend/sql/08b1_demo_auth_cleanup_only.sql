-- ==========================================================================
-- 08b1_demo_auth_cleanup_only.sql
-- Covara One - Demo Auth Cleanup Only (timeout-safe chunk)
-- ==========================================================================
-- Purpose:
--   Cleanup stale demo worker/admin rows in small runtime window.
--
-- Run:
--   1) Execute this script.
--   2) Recreate users in Supabase Auth dashboard:
--      - worker@demo.com / demo1234 (Auto Confirm ON)
--      - admin@demo.com  / demo1234 (Auto Confirm ON)
--   3) Then run 08b2_demo_auth_sync_seed_only.sql.
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

-- Public schema cleanup
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

-- Auth cleanup
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

commit;

notify pgrst, 'reload schema';
