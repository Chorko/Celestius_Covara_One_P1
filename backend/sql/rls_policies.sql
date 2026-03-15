-- DEVTrails Row Level Security (RLS) Security Patch
-- Prevents unauthorized access when using the frontend `anon` key.
-- Service Role (backend operations) bypasses RLS naturally in Supabase.

-- ==========================================
-- 1. Helper Function for Safe Role Checks
-- ==========================================
-- We abstract the role lookup to avoid messy joins and infinite recursion.
CREATE OR REPLACE FUNCTION public.current_user_role()
RETURNS text
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
  SELECT role FROM profiles WHERE id = auth.uid();
$$;

-- ==========================================
-- 2. Enforce RLS on Core Tables
-- ==========================================
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE worker_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE insurer_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE manual_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE claim_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE claim_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE payout_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE trigger_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE zones ENABLE ROW LEVEL SECURITY;

-- ==========================================
-- 3. Profiles & Context Tables
-- ==========================================

-- PROFILES: Users read their own, Admins read all. 
CREATE POLICY "Profiles: Users can read own" ON profiles FOR SELECT TO authenticated USING (id = auth.uid());
CREATE POLICY "Profiles: Admins can read all" ON profiles FOR SELECT TO authenticated USING (public.current_user_role() = 'insurer_admin');

-- WORKER_PROFILES: Workers read their own context, Admins read all pipeline data.
CREATE POLICY "WorkerProfiles: Workers can read own" ON worker_profiles FOR SELECT TO authenticated USING (profile_id = auth.uid());
CREATE POLICY "WorkerProfiles: Admins can read all" ON worker_profiles FOR SELECT TO authenticated USING (public.current_user_role() = 'insurer_admin');

-- INSURER_PROFILES: Only admins can view the insurer directory. Workers have no access.
CREATE POLICY "InsurerProfiles: Admins can read all" ON insurer_profiles FOR SELECT TO authenticated USING (public.current_user_role() = 'insurer_admin');

-- ==========================================
-- 4. Claims & Evidence (The Worker Loop)
-- ==========================================

-- MANUAL_CLAIMS
-- Workers can view their own history and submit new claims (insert).
CREATE POLICY "Claims: Workers can read own" ON manual_claims FOR SELECT TO authenticated USING (worker_profile_id = auth.uid());
CREATE POLICY "Claims: Workers can insert own" ON manual_claims FOR INSERT TO authenticated WITH CHECK (worker_profile_id = auth.uid());
-- Admins can view the central queue and modify (e.g., status updates to 'approved')
CREATE POLICY "Claims: Admins can read all" ON manual_claims FOR SELECT TO authenticated USING (public.current_user_role() = 'insurer_admin');
CREATE POLICY "Claims: Admins can update all" ON manual_claims FOR UPDATE TO authenticated USING (public.current_user_role() = 'insurer_admin');

-- CLAIM_EVIDENCE
-- Evidence requires an indirect join to verify claim ownership for the worker.
CREATE POLICY "Evidence: Workers can read own" ON claim_evidence FOR SELECT TO authenticated 
USING (claim_id IN (SELECT id FROM manual_claims WHERE worker_profile_id = auth.uid()));

CREATE POLICY "Evidence: Workers can insert own" ON claim_evidence FOR INSERT TO authenticated 
WITH CHECK (claim_id IN (SELECT id FROM manual_claims WHERE worker_profile_id = auth.uid()));

CREATE POLICY "Evidence: Admins can read all" ON claim_evidence FOR SELECT TO authenticated 
USING (public.current_user_role() = 'insurer_admin');

-- ==========================================
-- 5. Review & Payouts (The Insurer Loop)
-- ==========================================

-- CLAIM_REVIEWS
-- Workers CANNOT read or write. Purely internal.
CREATE POLICY "Reviews: Admins can read all" ON claim_reviews FOR SELECT TO authenticated USING (public.current_user_role() = 'insurer_admin');
CREATE POLICY "Reviews: Admins can insert" ON claim_reviews FOR INSERT TO authenticated 
WITH CHECK (public.current_user_role() = 'insurer_admin' AND reviewer_profile_id = auth.uid());

-- PAYOUT_RECOMMENDATIONS
-- Highly sensitive logic output. Written ONLY by the Service Role (backend).
-- Workers can only read the receipt for their own claims.
CREATE POLICY "Payouts: Workers can read own" ON payout_recommendations FOR SELECT TO authenticated 
USING (claim_id IN (SELECT id FROM manual_claims WHERE worker_profile_id = auth.uid()));

CREATE POLICY "Payouts: Admins can read all" ON payout_recommendations FOR SELECT TO authenticated 
USING (public.current_user_role() = 'insurer_admin');

-- ==========================================
-- 6. Shared Feeds (Triggers & Zones)
-- ==========================================
-- Both worker UI algorithms and admin dashboards need read-only access to LIVE system models.
CREATE POLICY "Triggers: Read access for all authenticated" ON trigger_events FOR SELECT TO authenticated USING (true);
CREATE POLICY "Zones: Read access for all authenticated" ON zones FOR SELECT TO authenticated USING (true);

-- STORAGE BUCKET NOTE (Not SQL, but conceptually related):
-- The 'claim-evidence' bucket must have equivalent RLS in the Storage schema.
-- e.g. "Workers can upload if authenticated"
