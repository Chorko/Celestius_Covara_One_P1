-- DEVTrails RLS Rollback Patch
-- Executes DROP POLICY commands to cleanly revert the system to an open state.
-- WARNING: Running this drops all Row Level Security constraints on the tables.

DROP POLICY IF EXISTS "Profiles: Users can read own" ON public.profiles;
DROP POLICY IF EXISTS "Profiles: Admins can read all" ON public.profiles;

DROP POLICY IF EXISTS "WorkerProfiles: Workers can read own" ON public.worker_profiles;
DROP POLICY IF EXISTS "WorkerProfiles: Admins can read all" ON public.worker_profiles;

DROP POLICY IF EXISTS "InsurerProfiles: Admins can read all" ON public.insurer_profiles;

DROP POLICY IF EXISTS "Claims: Workers can read own" ON public.manual_claims;
DROP POLICY IF EXISTS "Claims: Workers can insert own" ON public.manual_claims;
DROP POLICY IF EXISTS "Claims: Admins can read all" ON public.manual_claims;
DROP POLICY IF EXISTS "Claims: Admins can update all" ON public.manual_claims;

DROP POLICY IF EXISTS "Evidence: Workers can read own" ON public.claim_evidence;
DROP POLICY IF EXISTS "Evidence: Workers can insert own" ON public.claim_evidence;
DROP POLICY IF EXISTS "Evidence: Admins can read all" ON public.claim_evidence;

DROP POLICY IF EXISTS "Reviews: Admins can read all" ON public.claim_reviews;
DROP POLICY IF EXISTS "Reviews: Admins can insert" ON public.claim_reviews;

DROP POLICY IF EXISTS "Payouts: Workers can read own" ON public.payout_recommendations;
DROP POLICY IF EXISTS "Payouts: Admins can read all" ON public.payout_recommendations;

DROP POLICY IF EXISTS "Triggers: Read access for all authenticated" ON public.trigger_events;
DROP POLICY IF EXISTS "Zones: Read access for all authenticated" ON public.zones;

ALTER TABLE public.profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.worker_profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.insurer_profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.manual_claims DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_evidence DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_reviews DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.payout_recommendations DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.trigger_events DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.zones DISABLE ROW LEVEL SECURITY;

-- Tables from extensions (10, 12, 13) — safe even if tables don't exist yet
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'disruption_events') THEN
    DROP POLICY IF EXISTS "Workers can view disruption_events" ON public.disruption_events;
    DROP POLICY IF EXISTS "Service role can manage disruption_events" ON public.disruption_events;
    DROP POLICY IF EXISTS "disruption_events_select_authenticated" ON public.disruption_events;
    DROP POLICY IF EXISTS "disruption_events_manage_service" ON public.disruption_events;
    ALTER TABLE public.disruption_events DISABLE ROW LEVEL SECURITY;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'validated_regional_incidents') THEN
    DROP POLICY IF EXISTS "Workers can view validated incidents" ON public.validated_regional_incidents;
    DROP POLICY IF EXISTS "Service role can manage validated incidents" ON public.validated_regional_incidents;
    DROP POLICY IF EXISTS "validated_incidents_select_authenticated" ON public.validated_regional_incidents;
    DROP POLICY IF EXISTS "validated_incidents_manage_service" ON public.validated_regional_incidents;
    ALTER TABLE public.validated_regional_incidents DISABLE ROW LEVEL SECURITY;
  END IF;
END $$;

DROP FUNCTION IF EXISTS public.current_user_role();
