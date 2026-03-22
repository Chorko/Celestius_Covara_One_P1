-- ============================================================
-- 09_link_demo_users.sql
-- DEVTrails — Re-link demo accounts after Dashboard recreation
--
-- Run this AFTER completing ALL steps in 08_fix_demo_auth_users.sql
-- (including creating users via Supabase Dashboard and running STEP 3)
--
-- Why this is needed:
--   When 08 STEP 1 deleted the raw-SQL-inserted profiles, a CASCADE
--   also wiped all seed data tied to the demo accounts (worker_profiles,
--   stats, shifts, claims, payouts, reviews). After recreating users via
--   Dashboard (new random UUIDs), those rows need to be re-inserted.
-- ============================================================

DO $$
DECLARE
  new_worker uuid;
  new_admin  uuid;
BEGIN
  SELECT id INTO new_worker FROM public.profiles WHERE email = 'worker@demo.com';
  SELECT id INTO new_admin  FROM public.profiles WHERE email = 'admin@demo.com';

  IF new_worker IS NULL THEN
    RAISE EXCEPTION 'worker@demo.com not found in profiles. Complete 08_fix_demo_auth_users.sql first.';
  END IF;
  IF new_admin IS NULL THEN
    RAISE EXCEPTION 'admin@demo.com not found in profiles. Complete 08_fix_demo_auth_users.sql first.';
  END IF;

  -- Ensure correct roles (safe to run again even if 08 step 3 already did it)
  UPDATE public.profiles SET role = 'insurer_admin', full_name = 'Demo Admin'  WHERE id = new_admin;
  UPDATE public.profiles SET role = 'worker',        full_name = 'Demo Worker' WHERE id = new_worker;

  -- Remove trigger-created stub rows (they have correct UUIDs but wrong data)
  DELETE FROM public.worker_profiles WHERE profile_id = new_worker;
  DELETE FROM public.worker_profiles WHERE profile_id = new_admin;

  -- ── 1. Worker Profile ──────────────────────────────────────────────────
  INSERT INTO public.worker_profiles
    (profile_id, platform_name, city, preferred_zone_id, vehicle_type,
     avg_hourly_income_inr, bank_verified, trust_score, gps_consent)
  VALUES
    (new_worker, 'Swiggy', 'Mumbai', 'b7a1c2d3-e4f5-5678-abcd-100000000001',
     'Bike', 90.00, true, 0.86, true)
  ON CONFLICT (profile_id) DO UPDATE SET
    platform_name         = EXCLUDED.platform_name,
    city                  = EXCLUDED.city,
    preferred_zone_id     = EXCLUDED.preferred_zone_id,
    vehicle_type          = EXCLUDED.vehicle_type,
    avg_hourly_income_inr = EXCLUDED.avg_hourly_income_inr,
    bank_verified         = EXCLUDED.bank_verified,
    trust_score           = EXCLUDED.trust_score,
    gps_consent           = EXCLUDED.gps_consent;

  -- ── 2. Insurer (admin) Profile ─────────────────────────────────────────
  INSERT INTO public.insurer_profiles (profile_id, company_name, job_title)
  VALUES (new_admin, 'DEVTrails Insurance Ops', 'Demo Administrator')
  ON CONFLICT (profile_id) DO UPDATE SET
    company_name = EXCLUDED.company_name,
    job_title    = EXCLUDED.job_title;

  -- ── 3. Worker Shifts ───────────────────────────────────────────────────
  -- Delete old rows by ID in case they survive from a previous run
  DELETE FROM public.worker_shifts
  WHERE id IN (
    'cccc0000-0000-0000-0000-000000000011'::uuid,
    'cccc0000-0000-0000-0000-000000000012'::uuid,
    'cccc0000-0000-0000-0000-000000000013'::uuid
  );
  INSERT INTO public.worker_shifts
    (id, worker_profile_id, shift_date, shift_start, shift_end, zone_id)
  VALUES
    ('cccc0000-0000-0000-0000-000000000011', new_worker, '2026-03-10',
     '2026-03-10T07:00:00+05:30', '2026-03-10T18:00:00+05:30',
     'b7a1c2d3-e4f5-5678-abcd-100000000001'),
    ('cccc0000-0000-0000-0000-000000000012', new_worker, '2026-03-12',
     '2026-03-12T08:00:00+05:30', '2026-03-12T19:00:00+05:30',
     'b7a1c2d3-e4f5-5678-abcd-100000000001'),
    ('cccc0000-0000-0000-0000-000000000013', new_worker, '2026-03-14',
     '2026-03-14T09:00:00+05:30', '2026-03-14T20:00:00+05:30',
     'b7a1c2d3-e4f5-5678-abcd-100000000001');

  -- ── 4. Daily Platform Stats (14 days) ─────────────────────────────────
  DELETE FROM public.platform_worker_daily_stats
  WHERE id::text LIKE 'dddd0000-0000-0000-0000-0000000000%'
    AND id::text >= 'dddd0000-0000-0000-0000-000000000043'
    AND id::text <= 'dddd0000-0000-0000-0000-000000000056';

  INSERT INTO public.platform_worker_daily_stats
    (id, worker_profile_id, stat_date, active_hours, completed_orders,
     accepted_orders, cancelled_orders, gross_earnings_inr,
     platform_login_minutes, gps_consistency_score)
  VALUES
    ('dddd0000-0000-0000-0000-000000000043', new_worker, '2026-03-02',  9.0, 17, 20, 1, 1530.00, 570, 0.91),
    ('dddd0000-0000-0000-0000-000000000044', new_worker, '2026-03-03',  8.5, 16, 19, 0, 1360.00, 540, 0.89),
    ('dddd0000-0000-0000-0000-000000000045', new_worker, '2026-03-04', 10.5, 22, 26, 1, 1890.00, 660, 0.93),
    ('dddd0000-0000-0000-0000-000000000046', new_worker, '2026-03-05',  7.0, 13, 15, 2, 1170.00, 450, 0.85),
    ('dddd0000-0000-0000-0000-000000000047', new_worker, '2026-03-06',  0.0,  0,  0, 0,    0.00,   0, 0.00),
    ('dddd0000-0000-0000-0000-000000000048', new_worker, '2026-03-07', 11.0, 24, 28, 0, 1980.00, 690, 0.95),
    ('dddd0000-0000-0000-0000-000000000049', new_worker, '2026-03-08',  8.0, 15, 18, 1, 1350.00, 510, 0.88),
    ('dddd0000-0000-0000-0000-000000000050', new_worker, '2026-03-09',  9.5, 19, 22, 0, 1710.00, 600, 0.92),
    ('dddd0000-0000-0000-0000-000000000051', new_worker, '2026-03-10',  5.5,  9, 12, 3,  825.00, 360, 0.76),
    ('dddd0000-0000-0000-0000-000000000052', new_worker, '2026-03-11', 10.0, 21, 25, 1, 1890.00, 630, 0.94),
    ('dddd0000-0000-0000-0000-000000000053', new_worker, '2026-03-12',  9.0, 18, 21, 0, 1620.00, 570, 0.91),
    ('dddd0000-0000-0000-0000-000000000054', new_worker, '2026-03-13',  7.5, 14, 17, 2, 1260.00, 480, 0.87),
    ('dddd0000-0000-0000-0000-000000000055', new_worker, '2026-03-14',  8.5, 16, 19, 1, 1440.00, 540, 0.90),
    ('dddd0000-0000-0000-0000-000000000056', new_worker, '2026-03-15', 10.0, 20, 23, 0, 1800.00, 630, 0.93);

  -- ── 5. Manual Claims ───────────────────────────────────────────────────
  DELETE FROM public.manual_claims
  WHERE id IN (
    '11110000-0000-0000-0000-000000000008'::uuid,
    '11110000-0000-0000-0000-000000000009'::uuid
  );
  INSERT INTO public.manual_claims
    (id, worker_profile_id, trigger_event_id, claim_mode, claim_reason,
     stated_lat, stated_lng, claimed_at, shift_id, claim_status)
  VALUES
    ('11110000-0000-0000-0000-000000000008', new_worker,
     'ffff0000-0000-0000-0000-000000000001',
     'trigger_auto',
     'Heavy rain in Andheri West caused widespread waterlogging. Roads submerged near Link Road. Could not access pickup locations for 4 hours.',
     19.1365, 72.8288, '2026-03-10T11:00:00+05:30',
     'cccc0000-0000-0000-0000-000000000011', 'auto_approved'),
    ('11110000-0000-0000-0000-000000000009', new_worker,
     'ffff0000-0000-0000-0000-000000000003',
     'manual',
     'Moderate rain causing slow traffic in Andheri area. Deliveries delayed significantly, multiple orders timed out before pickup.',
     19.1372, 72.8295, '2026-03-14T15:30:00+05:30',
     'cccc0000-0000-0000-0000-000000000013', 'soft_hold_verification');

  -- ── 6. Claim Evidence ──────────────────────────────────────────────────
  DELETE FROM public.claim_evidence
  WHERE id IN (
    '22220000-0000-0000-0000-000000000010'::uuid,
    '22220000-0000-0000-0000-000000000011'::uuid
  );
  INSERT INTO public.claim_evidence
    (id, claim_id, evidence_type, storage_path, captured_at,
     exif_lat, exif_lng, exif_timestamp, integrity_score)
  VALUES
    ('22220000-0000-0000-0000-000000000010',
     '11110000-0000-0000-0000-000000000008', 'photo',
     'claim-evidence/demo-rain-andheri-01.jpg',
     '2026-03-10T10:55:00+05:30', 19.1363, 72.8286,
     '2026-03-10T10:55:00+05:30', 0.91),
    ('22220000-0000-0000-0000-000000000011',
     '11110000-0000-0000-0000-000000000008', 'geo', NULL,
     '2026-03-10T11:00:00+05:30', 19.1365, 72.8288,
     '2026-03-10T11:00:00+05:30', 0.94);

  -- ── 7. Payout Recommendations ──────────────────────────────────────────
  DELETE FROM public.payout_recommendations
  WHERE id IN (
    '33330000-0000-0000-0000-000000000008'::uuid,
    '33330000-0000-0000-0000-000000000009'::uuid
  );
  INSERT INTO public.payout_recommendations
    (id, claim_id, covered_weekly_income_b, claim_probability_p,
     severity_score_s, exposure_score_e, confidence_score_c,
     fraud_holdback_fh, outlier_uplift_u, payout_cap,
     expected_payout, gross_premium, recommended_payout, explanation_json)
  VALUES
    ('33330000-0000-0000-0000-000000000008',
     '11110000-0000-0000-0000-000000000008',
     3402.00, 0.1500, 0.7800, 0.8300, 0.9000, 0.0400, 1.00,
     2551.50, 280.12, 359.13, 2110.45,
     '{"ai_summary": "Auto-triggered rain claim in Andheri-W zone for Demo Worker. IMD heavy rainfall threshold (64.5mm) exceeded at 72mm. Worker GPS confirmed in-zone during active shift. Evidence photo EXIF timestamp matches claimed timeframe. Confidence score high (0.90). Fraud holdback low (0.04). Recommended payout of Rs 2,110.45 against a cap of Rs 2,551.50.", "pipeline_stages_passed": 8, "manual_hold_reasons": []}'::jsonb),
    ('33330000-0000-0000-0000-000000000009',
     '11110000-0000-0000-0000-000000000009',
     3402.00, 0.1500, 0.4200, 0.7500, 0.8200, 0.0800, 1.00,
     2551.50, 109.80, 140.77, 788.42,
     '{"ai_summary": "Manual claim by Demo Worker during rain watch event in Andheri-W. Rain at 52mm is above the 48mm watch threshold but below the 64.5mm heavy-rain claim threshold. Manual claim path applied. Evidence not yet submitted. Pending review.", "pipeline_stages_passed": 6, "manual_hold_reasons": ["watch_level_trigger", "manual_claim_multiplier_applied"]}'::jsonb);

  -- ── 8. Claim Review (Demo Admin approved Demo Worker rain claim) ────────
  DELETE FROM public.claim_reviews
  WHERE id = '44440000-0000-0000-0000-000000000004'::uuid;
  INSERT INTO public.claim_reviews
    (id, claim_id, reviewer_profile_id, fraud_score, geo_confidence_score,
     evidence_completeness_score, decision, decision_reason, reviewed_at)
  VALUES
    ('44440000-0000-0000-0000-000000000004',
     '11110000-0000-0000-0000-000000000008', new_admin,
     0.08, 0.94, 0.91, 'approve',
     'Auto-triggered rain claim with strong photo and GPS evidence. EXIF timestamp aligns with shift window. Heavy rain threshold confirmed via IMD data (72mm). Approved for recommended payout.',
     '2026-03-10T15:30:00+05:30');

END $$;


-- ── RLS: Allow insurer_admin to INSERT into trigger_events (Simulate) ──────
DROP POLICY IF EXISTS "Triggers: Admins can insert mock" ON public.trigger_events;
CREATE POLICY "Triggers: Admins can insert mock"
ON public.trigger_events
FOR INSERT
TO authenticated
WITH CHECK (public.current_user_role() = 'insurer_admin');


-- ── Flush PostgREST schema cache ────────────────────────────────────────────
NOTIFY pgrst, 'reload schema';


-- ── Verification ────────────────────────────────────────────────────────────
-- Run these queries after the script to confirm data is linked:

-- 1. Both accounts with correct roles:
SELECT id, email, role, full_name FROM public.profiles
WHERE email IN ('worker@demo.com', 'admin@demo.com');

-- 2. Demo worker profile (should show Swiggy, Mumbai):
SELECT wp.platform_name, wp.city, wp.trust_score, p.full_name
FROM public.worker_profiles wp
JOIN public.profiles p ON p.id = wp.profile_id
WHERE p.email = 'worker@demo.com';

-- 3. Demo worker stats (should return 14 rows):
SELECT COUNT(*) AS stat_rows FROM public.platform_worker_daily_stats
WHERE worker_profile_id = (SELECT id FROM public.profiles WHERE email='worker@demo.com');

-- 4. Demo worker claims (should return 2 rows):
SELECT id, claim_status, claim_mode FROM public.manual_claims
WHERE worker_profile_id = (SELECT id FROM public.profiles WHERE email='worker@demo.com');
