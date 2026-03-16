-- ============================================================
-- 07_grant_patch.sql
-- DEVTrails — Schema permission grants + PostgREST cache reload
--
-- Run this in the Supabase SQL Editor if you get:
--   "Database error querying schema"
-- It is safe to re-run at any time.
-- ============================================================

-- 1. Ensure anon and authenticated roles can see the public schema
GRANT USAGE ON SCHEMA public TO anon, authenticated;

-- 2. Grant table-level permissions to authenticated users
GRANT SELECT, INSERT, UPDATE, DELETE
  ON ALL TABLES IN SCHEMA public TO authenticated;

-- 3. Grant read-only access to anon for public-facing tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;

-- 4. Ensure future tables also inherit these grants
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO anon;

-- 5. Grant sequence access so inserts with generated IDs work
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO authenticated;

-- 6. Tell PostgREST to reload its schema cache immediately
--    (eliminates "Database error querying schema" without a server restart)
NOTIFY pgrst, 'reload schema';
