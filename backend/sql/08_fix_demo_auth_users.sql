-- ============================================================
-- 08_fix_demo_auth_users.sql
-- DEVTrails — Fix broken demo auth accounts
--
-- Run this IN ORDER in the Supabase SQL Editor.
-- This replaces the direct auth.users INSERT from 06_synthetic_seed.sql
-- with a safe cleanup + profile-fix approach.
--
-- AFTER running this SQL, create the two demo users manually via:
--   Supabase Dashboard → Authentication → Users → Add user
--   admin@demo.com   / demo1234  (tick "Auto Confirm User")
--   worker@demo.com  / demo1234  (tick "Auto Confirm User")
-- Then run STEP 3 below to set roles.
-- ============================================================

-- ── STEP 1: Remove broken raw-SQL-inserted demo accounts ────────────────────
-- These were inserted directly into auth.users which GoTrue rejects in
-- newer Supabase versions, causing 500 on /auth/v1/token.

DELETE FROM auth.identities
WHERE user_id IN (
  SELECT id FROM auth.users
  WHERE email IN ('worker@demo.com', 'admin@demo.com')
);

DELETE FROM auth.users
WHERE email IN ('worker@demo.com', 'admin@demo.com');

-- Also clean up any orphaned profiles left behind
DELETE FROM public.profiles
WHERE email IN ('worker@demo.com', 'admin@demo.com');

-- ── STEP 2: (Do in the Dashboard NOW) ───────────────────────────────────────
-- Go to: Authentication → Users → Add user → Create new user
--   Email: admin@demo.com    Password: demo1234   ✓ Auto Confirm User
--   Email: worker@demo.com   Password: demo1234   ✓ Auto Confirm User
--
-- The handle_new_user trigger will auto-create the profiles rows.
-- Then come back and run STEP 3.

-- ── STEP 3: Fix roles after Dashboard user creation ─────────────────────────
-- Run this AFTER creating the two users in the Dashboard.

UPDATE public.profiles
SET role = 'insurer_admin', full_name = 'Demo Admin'
WHERE email = 'admin@demo.com';

UPDATE public.profiles
SET full_name = 'Demo Worker'
WHERE email = 'worker@demo.com';

-- Verify both rows exist with correct roles
SELECT id, email, role, full_name FROM public.profiles
WHERE email IN ('worker@demo.com', 'admin@demo.com');
