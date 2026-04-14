-- ============================================================================
-- 19a_login_ready_workers_auth_cleanup.sql
-- Covara One - Cleanup malformed synthetic auth rows (worker001..worker200)
-- ============================================================================
-- Purpose:
--   Remove previously SQL-seeded synthetic auth users that can cause Supabase
--   Auth 500 errors (e.g. "Database error querying schema").
--
-- Run this once before:
--   python scripts/provision_login_ready_workers_200.py --apply
--   backend/sql/19_login_ready_workers_200.sql
--
-- Scope:
--   - Targets only emails like worker%@synthetic.covara.dev
--   - Cleans auth child tables first (if present)
--   - Deletes auth.identities + auth.users for the target batch
--
-- Safety:
--   - Idempotent. Safe to re-run.
--   - Deleting auth.users cascades to public profile/worker rows via FK.
-- ============================================================================

set statement_timeout = '0';
set lock_timeout = '10s';
set idle_in_transaction_session_timeout = '0';

begin;

create temporary table tmp_login_worker_auth_ids on commit drop as
select u.id
from auth.users u
where lower(coalesce(u.email, '')) like 'worker%@synthetic.covara.dev';

do $$
begin
  if to_regclass('auth.mfa_factors') is not null and to_regclass('auth.mfa_challenges') is not null then
    execute 'delete from auth.mfa_challenges where factor_id::text in (select id::text from auth.mfa_factors where user_id::text in (select id::text from tmp_login_worker_auth_ids))';
  end if;

  if to_regclass('auth.mfa_factors') is not null then
    execute 'delete from auth.mfa_factors where user_id::text in (select id::text from tmp_login_worker_auth_ids)';
  end if;

  if to_regclass('auth.one_time_tokens') is not null then
    execute 'delete from auth.one_time_tokens where user_id::text in (select id::text from tmp_login_worker_auth_ids)';
  end if;

  if to_regclass('auth.sessions') is not null then
    execute 'delete from auth.sessions where user_id::text in (select id::text from tmp_login_worker_auth_ids)';
  end if;

  if to_regclass('auth.refresh_tokens') is not null then
    execute 'delete from auth.refresh_tokens where user_id::text in (select id::text from tmp_login_worker_auth_ids)';
  end if;
end $$;

delete from auth.identities
where user_id in (select id from tmp_login_worker_auth_ids)
   or lower(coalesce(provider_id, '')) like 'worker%@synthetic.covara.dev';

delete from auth.users
where id in (select id from tmp_login_worker_auth_ids)
   or lower(coalesce(email, '')) like 'worker%@synthetic.covara.dev';

-- Optional visibility for SQL editor output.
select
  'remaining_synthetic_auth_users' as metric,
  count(*)::int as value
from auth.users
where lower(coalesce(email, '')) like 'worker%@synthetic.covara.dev';

commit;

notify pgrst, 'reload schema';
