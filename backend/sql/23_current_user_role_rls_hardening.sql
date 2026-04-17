-- ============================================================
-- 23_current_user_role_rls_hardening.sql
-- Covara One — RLS recursion hardening for role helper
--
-- Why:
--   In some environments, current_user_role() can be redefined without
--   SECURITY DEFINER, which causes policy recursion when profiles RLS also
--   references current_user_role().
--
-- Effect:
--   Restores SECURITY DEFINER + stable search_path for the helper.
-- ============================================================

create or replace function public.current_user_role()
returns text
language sql
security definer
set search_path = public
stable
as $$
  select p.role
  from public.profiles p
  where p.id = auth.uid()
  limit 1
$$;

revoke all on function public.current_user_role() from public;
grant execute on function public.current_user_role() to authenticated, service_role;

notify pgrst, 'reload schema';
