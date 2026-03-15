-- DEVTrails RLS Rollback Patch
-- Executes DROP POLICY commands to cleanly revert the system to an open state.
-- WARNING: Running this drops all Row Level Security constraints on the tables!

-- 1. Drop Policies on Profiles & Context
DROP POLICY IF EXISTS "Profiles: Users can read own" ON profiles;
DROP POLICY IF EXISTS "Profiles: Admins can read all" ON profiles;

DROP POLICY IF EXISTS "WorkerProfiles: Workers can read own" ON worker_profiles;
DROP POLICY IF EXISTS "WorkerProfiles: Admins can read all" ON worker_profiles;

DROP POLICY IF EXISTS "InsurerProfiles: Admins can read all" ON insurer_profiles;

-- 2. Drop Policies on Claims & Evidence
DROP POLICY IF EXISTS "Claims: Workers can read own" ON manual_claims;
DROP POLICY IF EXISTS "Claims: Workers can insert own" ON manual_claims;
DROP POLICY IF EXISTS "Claims: Admins can read all" ON manual_claims;
DROP POLICY IF EXISTS "Claims: Admins can update all" ON manual_claims;

DROP POLICY IF EXISTS "Evidence: Workers can read own" ON claim_evidence;
DROP POLICY IF EXISTS "Evidence: Workers can insert own" ON claim_evidence;
DROP POLICY IF EXISTS "Evidence: Admins can read all" ON claim_evidence;

-- 3. Drop Policies on Review & Payouts
DROP POLICY IF EXISTS "Reviews: Admins can read all" ON claim_reviews;
DROP POLICY IF EXISTS "Reviews: Admins can insert" ON claim_reviews;

DROP POLICY IF EXISTS "Payouts: Workers can read own" ON payout_recommendations;
DROP POLICY IF EXISTS "Payouts: Admins can read all" ON payout_recommendations;

-- 4. Drop Policies on Feeds
DROP POLICY IF EXISTS "Triggers: Read access for all authenticated" ON trigger_events;
DROP POLICY IF EXISTS "Zones: Read access for all authenticated" ON zones;

-- 5. Disable RLS (Optional, depending if you want to leave it on but empty)
ALTER TABLE profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE worker_profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE insurer_profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE manual_claims DISABLE ROW LEVEL SECURITY;
ALTER TABLE claim_evidence DISABLE ROW LEVEL SECURITY;
ALTER TABLE claim_reviews DISABLE ROW LEVEL SECURITY;
ALTER TABLE payout_recommendations DISABLE ROW LEVEL SECURITY;
ALTER TABLE trigger_events DISABLE ROW LEVEL SECURITY;
ALTER TABLE zones DISABLE ROW LEVEL SECURITY;

-- 6. Drop the Custom Role Check Function
DROP FUNCTION IF EXISTS public.current_user_role();
