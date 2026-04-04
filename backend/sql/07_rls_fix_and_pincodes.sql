-- ══════════════════════════════════════════════════════════════════════
-- Covara One — SQL Patch: RLS Fix + Pincode Column + Zone Calibration
-- ══════════════════════════════════════════════════════════════════════
-- Run in Supabase SQL Editor ONCE after 00_unified_migration.sql.
-- Safe to re-run (uses IF NOT EXISTS / OR REPLACE / ON CONFLICT).
--
-- Fixes:
--   1. RLS policy violation on claim_reviews INSERT
--   2. Adds pincode column to zones table
--   3. Populates pincodes for seeded zones
-- ══════════════════════════════════════════════════════════════════════


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §1  FIX: claim_reviews RLS violation                            │
-- └──────────────────────────────────────────────────────────────────┘
-- Problem: Admin user can't insert into claim_reviews because the
-- current policy requires reviewer_profile_id = auth.uid() AND
-- current_user_role() = 'insurer_admin'. The second check works but
-- only if the admin's profile has role='insurer_admin' in profiles.
-- If the insurer_profiles table doesn't have a row for this admin,
-- the foreign key check on reviewer_profile_id fails silently as
-- an RLS violation.
--
-- Fix: Also allow service_role bypass + fix insurer_profiles policies.

-- Drop and recreate the Reviews policies to be more robust
DROP POLICY IF EXISTS "Reviews: Admins can read all" ON public.claim_reviews;
DROP POLICY IF EXISTS "Reviews: Admins can insert" ON public.claim_reviews;
DROP POLICY IF EXISTS "Reviews: Service role bypass" ON public.claim_reviews;

-- Allow admins to read all reviews
CREATE POLICY "Reviews: Admins can read all"
  ON public.claim_reviews FOR SELECT TO authenticated
  USING (public.current_user_role() = 'insurer_admin');

-- Allow admins to insert — use profile matching, not just uid()
-- The reviewer_profile_id must match a profile with insurer_admin role
CREATE POLICY "Reviews: Admins can insert"
  ON public.claim_reviews FOR INSERT TO authenticated
  WITH CHECK (
    public.current_user_role() = 'insurer_admin'
    AND EXISTS (
      SELECT 1 FROM public.insurer_profiles
      WHERE profile_id = reviewer_profile_id
    )
  );

-- Service role bypass for backend API calls
CREATE POLICY "Reviews: Service role bypass"
  ON public.claim_reviews FOR ALL TO service_role
  USING (true) WITH CHECK (true);


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §2  FIX: insurer_profiles policies                              │
-- └──────────────────────────────────────────────────────────────────┘
-- Allow admins to insert their own insurer_profile row (needed for FK)

DROP POLICY IF EXISTS "InsurerProfiles: Admins can insert own" ON public.insurer_profiles;

CREATE POLICY "InsurerProfiles: Admins can insert own"
  ON public.insurer_profiles FOR INSERT TO authenticated
  WITH CHECK (
    public.current_user_role() = 'insurer_admin'
    AND profile_id = auth.uid()
  );

-- Service role bypass
DROP POLICY IF EXISTS "InsurerProfiles: Service role bypass" ON public.insurer_profiles;
CREATE POLICY "InsurerProfiles: Service role bypass"
  ON public.insurer_profiles FOR ALL TO service_role
  USING (true) WITH CHECK (true);


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §3  ADD: pincode column to zones                                │
-- └──────────────────────────────────────────────────────────────────┘
-- Indian PIN codes are 6-digit postal codes issued by India Post.
-- These map neighborhoods precisely and are universally understood.

ALTER TABLE public.zones
  ADD COLUMN IF NOT EXISTS pincode TEXT;

-- Add a comment explaining the format
COMMENT ON COLUMN public.zones.pincode IS
  '6-digit India Post PIN code for this zone (e.g. 400053 for Andheri-West).';

-- Populate pincodes for seeded zones
UPDATE public.zones SET pincode = '400053' WHERE zone_name = 'Andheri-W'       AND city = 'Mumbai';
UPDATE public.zones SET pincode = '400051' WHERE zone_name = 'Bandra-Kurla'    AND city = 'Mumbai';
UPDATE public.zones SET pincode = '110001' WHERE zone_name = 'Connaught-Place' AND city = 'Delhi';
UPDATE public.zones SET pincode = '110017' WHERE zone_name = 'Saket-South'     AND city = 'Delhi';
UPDATE public.zones SET pincode = '560034' WHERE zone_name = 'Koramangala'     AND city = 'Bangalore';
UPDATE public.zones SET pincode = '560038' WHERE zone_name = 'Indiranagar'     AND city = 'Bangalore';
UPDATE public.zones SET pincode = '500081' WHERE zone_name = 'Madhapur'        AND city = 'Hyderabad';
UPDATE public.zones SET pincode = '500032' WHERE zone_name = 'Gachibowli'      AND city = 'Hyderabad';


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §4  VERIFY: Ensure admin demo user has insurer_profile row      │
-- └──────────────────────────────────────────────────────────────────┘
-- This INSERT is idempotent — safe to re-run.
-- If admin@demo.com's insurer_profiles row is missing, this creates it.
-- The admin user UUID from 06_synthetic_seed.sql is known.

DO $$
DECLARE
  admin_id UUID;
BEGIN
  -- Find the admin demo user
  SELECT p.id INTO admin_id
  FROM public.profiles p
  WHERE p.role = 'insurer_admin'
  LIMIT 1;

  IF admin_id IS NOT NULL THEN
    -- Ensure insurer_profiles row exists
    INSERT INTO public.insurer_profiles (profile_id, company_name, job_title)
    VALUES (admin_id, 'Covara One Insurance', 'Risk Operations Manager')
    ON CONFLICT (profile_id) DO NOTHING;
    RAISE NOTICE 'Insurer profile verified for admin ID: %', admin_id;
  ELSE
    RAISE NOTICE 'No insurer_admin found in profiles — run 06_synthetic_seed.sql first.';
  END IF;
END $$;


-- ══════════════════════════════════════════════════════════════════════
-- Reload PostgREST schema cache
-- ══════════════════════════════════════════════════════════════════════

NOTIFY pgrst, 'reload schema';

-- ══════════════════════════════════════════════════════════════════════
-- Patch complete. Run in Supabase SQL Editor to apply.
-- ══════════════════════════════════════════════════════════════════════
