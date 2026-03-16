-- ============================================================
-- 06_synthetic_seed.sql
-- DEVTrails — Synthetic Seed Data
--
-- Run AFTER 01–04 have been applied.
-- Seeds realistic demo data based on the DEVTrails_Synthetic_Seed_Pack.
-- Safe to re-run (uses ON CONFLICT / upserts).
-- ============================================================

-- ────────────────────────────────────────────────────────────
-- 0. Reference Sources (R1–R10)
-- ────────────────────────────────────────────────────────────
INSERT INTO public.reference_sources (ref_id, source_name, source_type, what_it_provides, use_in_project, link) VALUES
  ('R1',  'CPCB National Air Quality Index',              'Official / public',          'AQI category bands, interpretation',                   'AQI trigger thresholds and README reference layer',        'https://www.cpcb.nic.in/national-air-quality-index/'),
  ('R2',  'OGD Real-Time Air Quality Index dataset',      'Official / public data',     'Machine-readable AQI observations by location',        'AQI ingestion / trigger feed design',                      'https://www.data.gov.in/catalog/real-time-air-quality-index'),
  ('R3',  'IMD Heavy Rainfall Warning Services',          'Official / public',          'Heavy / very heavy rainfall warning categories',        'Rain trigger anchors and escalation logic',                'https://mausam.imd.gov.in/imd_latest/contents/pdf/pubbrochures/Heavy%20Rainfall%20Warning%20Services.pdf'),
  ('R4',  'IMD Heat Wave Warning Services',               'Official / public',          'Heat-wave and severe heat guidance',                    'Heat trigger anchors and escalation logic',                'https://mausam.imd.gov.in/imd_latest/contents/pdf/pubbrochures/Heat%20Wave%20Warning%20Services.pdf'),
  ('R5',  'NDMA Heat Wave guidance',                      'Official / public',          'National heat-wave preparedness guidance',              'Secondary support for heat thresholds',                    'https://ndma.gov.in/Natural-Hazards/Heat-Wave'),
  ('R6',  'NITI Aayog - India''s booming gig economy',    'Official / policy report',   'Gig/platform worker context, sector framing',          'Worker-profile schema context and README motivation',      'https://www.niti.gov.in/sites/default/files/2022-06/India%27s-booming-gig-and-platform-economy_English.pdf'),
  ('R7',  'Breiman (2001) Random Forests',                'Academic',                   'Baseline model reference',                             'Claim probability baseline justification',                 'https://www.stat.berkeley.edu/~breiman/randomforest2001.pdf'),
  ('R8',  'Chen & Guestrin (2016) XGBoost',               'Academic',                   'Benchmark model reference',                            'Future benchmark justification',                           'https://arxiv.org/abs/1603.02754'),
  ('R9',  'Loss Data Analytics - Premium Foundations',     'Open actuarial text',        'Premium principle and actuarial framing',               'Pricing/payout README reference block',                    'https://openacttexts.github.io/Loss-Data-Analytics/ChapPremiumFoundations.html'),
  ('R10', 'Mikosch - Non-Life Insurance Mathematics',     'Academic / textbook',        'Non-life insurance mathematical framing',               'Pricing/payout README reference block',                    'https://link.springer.com/book/10.1007/978-3-642-20548-3')
ON CONFLICT (ref_id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 1. Zones (8 zones across 4 Indian cities)
-- ────────────────────────────────────────────────────────────
INSERT INTO public.zones (id, city, zone_name, center_lat, center_lng) VALUES
  ('b7a1c2d3-e4f5-5678-abcd-100000000001', 'Mumbai',    'Andheri-W',       19.136400, 72.829600),
  ('b7a1c2d3-e4f5-5678-abcd-100000000002', 'Mumbai',    'Bandra-Kurla',    19.059600, 72.865600),
  ('b7a1c2d3-e4f5-5678-abcd-100000000003', 'Delhi',     'Connaught-Place', 28.631500, 77.216700),
  ('b7a1c2d3-e4f5-5678-abcd-100000000004', 'Delhi',     'Saket-South',     28.524400, 77.206600),
  ('b7a1c2d3-e4f5-5678-abcd-100000000005', 'Bangalore', 'Koramangala',     12.935200, 77.624500),
  ('b7a1c2d3-e4f5-5678-abcd-100000000006', 'Bangalore', 'Indiranagar',     12.978400, 77.640800),
  ('b7a1c2d3-e4f5-5678-abcd-100000000007', 'Hyderabad', 'Madhapur',        17.448600, 78.390800),
  ('b7a1c2d3-e4f5-5678-abcd-100000000008', 'Hyderabad', 'Gachibowli',      17.440100, 78.348900)
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 2. Auth Users + Profiles
-- Insert into auth.users first (satisfies FK on profiles.id).
-- The handle_new_user trigger will auto-create profiles (role=worker)
-- and worker_profiles (placeholder data). We then UPDATE the rows
-- to set correct roles, names, and delete stale worker_profiles
-- for admin users.
-- ────────────────────────────────────────────────────────────

-- Step 2-pre: Clean up existing demo accounts for safe re-run.
-- All FK constraints are ON DELETE CASCADE, so deleting from auth.users
-- cascades through profiles → worker_profiles/insurer_profiles → claims → evidence/payouts/reviews.
-- Audit events use ON DELETE SET NULL, so those rows are preserved but actor_profile_id becomes null.
DELETE FROM auth.identities WHERE user_id IN (SELECT id FROM auth.users WHERE email IN ('worker@demo.com', 'admin@demo.com'));
DELETE FROM auth.users WHERE email IN ('worker@demo.com', 'admin@demo.com');

-- Step 2a: Insert auth users. The trigger fires and auto-creates
-- profiles (role='worker') + worker_profiles (placeholder) for each.
INSERT INTO auth.users (
  id, instance_id, aud, role, email,
  encrypted_password, email_confirmed_at,
  created_at, updated_at,
  raw_app_meta_data, raw_user_meta_data
) VALUES
  ('aaaa0000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
   'ravi.kumar@demo.devtrails.in',
   crypt('demopassword', gen_salt('bf')), now(), now(), now(),
   '{"provider": "email", "providers": ["email"]}'::jsonb,
   '{"full_name": "Ravi Kumar"}'::jsonb),
  ('aaaa0000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
   'priya.sharma@demo.devtrails.in',
   crypt('demopassword', gen_salt('bf')), now(), now(), now(),
   '{"provider": "email", "providers": ["email"]}'::jsonb,
   '{"full_name": "Priya Sharma"}'::jsonb),
  ('aaaa0000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
   'arun.patel@demo.devtrails.in',
   crypt('demopassword', gen_salt('bf')), now(), now(), now(),
   '{"provider": "email", "providers": ["email"]}'::jsonb,
   '{"full_name": "Arun Patel"}'::jsonb),
  ('aaaa0000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
   'meena.devi@demo.devtrails.in',
   crypt('demopassword', gen_salt('bf')), now(), now(), now(),
   '{"provider": "email", "providers": ["email"]}'::jsonb,
   '{"full_name": "Meena Devi"}'::jsonb),
  ('aaaa0000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
   'suresh.yadav@demo.devtrails.in',
   crypt('demopassword', gen_salt('bf')), now(), now(), now(),
   '{"provider": "email", "providers": ["email"]}'::jsonb,
   '{"full_name": "Suresh Yadav"}'::jsonb),
  ('aaaa0000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
   'fatima.khan@demo.devtrails.in',
   crypt('demopassword', gen_salt('bf')), now(), now(), now(),
   '{"provider": "email", "providers": ["email"]}'::jsonb,
   '{"full_name": "Fatima Khan"}'::jsonb),
  -- Demo quick-access accounts
  ('aaaa0000-0000-0000-0000-000000000201', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
   'worker@demo.com',
   crypt('demo1234', gen_salt('bf')), now(), now(), now(),
   '{"provider": "email", "providers": ["email"]}'::jsonb,
   '{"full_name": "Demo Worker"}'::jsonb),
  ('aaaa0000-0000-0000-0000-000000000202', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
   'admin@demo.com',
   crypt('demo1234', gen_salt('bf')), now(), now(), now(),
   '{"provider": "email", "providers": ["email"]}'::jsonb,
   '{"full_name": "Demo Admin"}'::jsonb),
  ('aaaa0000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
   'neha.sharma@devtrails.insurance',
   crypt('demopassword', gen_salt('bf')), now(), now(), now(),
   '{"provider": "email", "providers": ["email"]}'::jsonb,
   '{"full_name": "Neha Sharma"}'::jsonb),
  ('aaaa0000-0000-0000-0000-000000000102', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
   'vijay.mehta@devtrails.insurance',
   crypt('demopassword', gen_salt('bf')), now(), now(), now(),
   '{"provider": "email", "providers": ["email"]}'::jsonb,
   '{"full_name": "Vijay Mehta"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- Step 2b: Auth identities (required for Supabase email login)
INSERT INTO auth.identities (
  id, user_id, provider_id, provider, identity_data, last_sign_in_at, created_at, updated_at
) VALUES
  ('aaaa0000-0000-0000-0000-000000000001', 'aaaa0000-0000-0000-0000-000000000001', 'ravi.kumar@demo.devtrails.in',   'email', '{"sub": "aaaa0000-0000-0000-0000-000000000001", "email": "ravi.kumar@demo.devtrails.in"}'::jsonb,   now(), now(), now()),
  ('aaaa0000-0000-0000-0000-000000000002', 'aaaa0000-0000-0000-0000-000000000002', 'priya.sharma@demo.devtrails.in', 'email', '{"sub": "aaaa0000-0000-0000-0000-000000000002", "email": "priya.sharma@demo.devtrails.in"}'::jsonb, now(), now(), now()),
  ('aaaa0000-0000-0000-0000-000000000003', 'aaaa0000-0000-0000-0000-000000000003', 'arun.patel@demo.devtrails.in',   'email', '{"sub": "aaaa0000-0000-0000-0000-000000000003", "email": "arun.patel@demo.devtrails.in"}'::jsonb,   now(), now(), now()),
  ('aaaa0000-0000-0000-0000-000000000004', 'aaaa0000-0000-0000-0000-000000000004', 'meena.devi@demo.devtrails.in',   'email', '{"sub": "aaaa0000-0000-0000-0000-000000000004", "email": "meena.devi@demo.devtrails.in"}'::jsonb,   now(), now(), now()),
  ('aaaa0000-0000-0000-0000-000000000005', 'aaaa0000-0000-0000-0000-000000000005', 'suresh.yadav@demo.devtrails.in', 'email', '{"sub": "aaaa0000-0000-0000-0000-000000000005", "email": "suresh.yadav@demo.devtrails.in"}'::jsonb, now(), now(), now()),
  ('aaaa0000-0000-0000-0000-000000000006', 'aaaa0000-0000-0000-0000-000000000006', 'fatima.khan@demo.devtrails.in',  'email', '{"sub": "aaaa0000-0000-0000-0000-000000000006", "email": "fatima.khan@demo.devtrails.in"}'::jsonb,  now(), now(), now()),
  ('aaaa0000-0000-0000-0000-000000000201', 'aaaa0000-0000-0000-0000-000000000201', 'worker@demo.com',             'email', '{"sub": "aaaa0000-0000-0000-0000-000000000201", "email": "worker@demo.com"}'::jsonb,             now(), now(), now()),
  ('aaaa0000-0000-0000-0000-000000000202', 'aaaa0000-0000-0000-0000-000000000202', 'admin@demo.com',              'email', '{"sub": "aaaa0000-0000-0000-0000-000000000202", "email": "admin@demo.com"}'::jsonb,              now(), now(), now()),
  ('aaaa0000-0000-0000-0000-000000000101', 'aaaa0000-0000-0000-0000-000000000101', 'neha.sharma@devtrails.insurance','email', '{"sub": "aaaa0000-0000-0000-0000-000000000101", "email": "neha.sharma@devtrails.insurance"}'::jsonb,now(), now(), now()),
  ('aaaa0000-0000-0000-0000-000000000102', 'aaaa0000-0000-0000-0000-000000000102', 'vijay.mehta@devtrails.insurance','email', '{"sub": "aaaa0000-0000-0000-0000-000000000102", "email": "vijay.mehta@devtrails.insurance"}'::jsonb,now(), now(), now())
ON CONFLICT (id) DO NOTHING;

-- Step 2c: Fix worker profiles with full names and phone numbers
-- (The trigger already created these rows with defaults)
UPDATE public.profiles SET full_name = 'Ravi Kumar',   phone = '+919876543210' WHERE id = 'aaaa0000-0000-0000-0000-000000000001';
UPDATE public.profiles SET full_name = 'Priya Sharma',  phone = '+919876543211' WHERE id = 'aaaa0000-0000-0000-0000-000000000002';
UPDATE public.profiles SET full_name = 'Arun Patel',    phone = '+919876543212' WHERE id = 'aaaa0000-0000-0000-0000-000000000003';
UPDATE public.profiles SET full_name = 'Meena Devi',    phone = '+919876543213' WHERE id = 'aaaa0000-0000-0000-0000-000000000004';
UPDATE public.profiles SET full_name = 'Suresh Yadav',  phone = '+919876543214' WHERE id = 'aaaa0000-0000-0000-0000-000000000005';
UPDATE public.profiles SET full_name = 'Fatima Khan',   phone = '+919876543215' WHERE id = 'aaaa0000-0000-0000-0000-000000000006';

-- Step 2d: Fix demo worker profile
UPDATE public.profiles SET full_name = 'Demo Worker', phone = '+919999900001' WHERE id = 'aaaa0000-0000-0000-0000-000000000201';

-- Step 2e: Fix admin profiles — change role from default 'worker' to 'insurer_admin'
UPDATE public.profiles SET role = 'insurer_admin', full_name = 'Neha Sharma', phone = '+919800000001' WHERE id = 'aaaa0000-0000-0000-0000-000000000101';
UPDATE public.profiles SET role = 'insurer_admin', full_name = 'Vijay Mehta', phone = '+919800000002' WHERE id = 'aaaa0000-0000-0000-0000-000000000102';
UPDATE public.profiles SET role = 'insurer_admin', full_name = 'Demo Admin',  phone = '+919999900002' WHERE id = 'aaaa0000-0000-0000-0000-000000000202';

-- Step 2f: Remove the auto-created worker_profiles for admin users
-- (trigger created placeholder worker_profiles for everyone)
DELETE FROM public.worker_profiles WHERE profile_id IN (
  'aaaa0000-0000-0000-0000-000000000101',
  'aaaa0000-0000-0000-0000-000000000102',
  'aaaa0000-0000-0000-0000-000000000202'
);


-- ────────────────────────────────────────────────────────────
-- 3. Worker Profiles
-- ────────────────────────────────────────────────────────────
INSERT INTO public.worker_profiles (profile_id, platform_name, city, preferred_zone_id, vehicle_type, avg_hourly_income_inr, bank_verified, trust_score, gps_consent) VALUES
  ('aaaa0000-0000-0000-0000-000000000001', 'Swiggy',  'Mumbai',    'b7a1c2d3-e4f5-5678-abcd-100000000001', 'Bike',    85.00, true,  0.88, true),
  ('aaaa0000-0000-0000-0000-000000000002', 'Zomato',  'Mumbai',    'b7a1c2d3-e4f5-5678-abcd-100000000002', 'Bike',    78.00, true,  0.82, true),
  ('aaaa0000-0000-0000-0000-000000000003', 'Swiggy',  'Delhi',     'b7a1c2d3-e4f5-5678-abcd-100000000003', 'Scooter', 92.00, true,  0.91, true),
  ('aaaa0000-0000-0000-0000-000000000004', 'Zepto',   'Delhi',     'b7a1c2d3-e4f5-5678-abcd-100000000004', 'Cycle',   55.00, false, 0.65, true),
  ('aaaa0000-0000-0000-0000-000000000005', 'Zomato',  'Bangalore', 'b7a1c2d3-e4f5-5678-abcd-100000000005', 'Bike',    80.00, true,  0.85, true),
  ('aaaa0000-0000-0000-0000-000000000006', 'Swiggy',  'Hyderabad', 'b7a1c2d3-e4f5-5678-abcd-100000000007', 'Bike',    72.00, true,  0.79, false),
  ('aaaa0000-0000-0000-0000-000000000201', 'Swiggy',  'Mumbai',    'b7a1c2d3-e4f5-5678-abcd-100000000001', 'Bike',    90.00, true,  0.86, true)
ON CONFLICT (profile_id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 4. Insurer Profiles
-- ────────────────────────────────────────────────────────────
INSERT INTO public.insurer_profiles (profile_id, company_name, job_title) VALUES
  ('aaaa0000-0000-0000-0000-000000000101', 'DEVTrails Insurance Ops',  'Claims Adjuster'),
  ('aaaa0000-0000-0000-0000-000000000102', 'DEVTrails Insurance Ops',  'Senior Underwriter'),
  ('aaaa0000-0000-0000-0000-000000000202', 'DEVTrails Insurance Ops',  'Demo Administrator')
ON CONFLICT (profile_id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 5. Worker Shifts (recent shifts for claim overlap testing)
-- ────────────────────────────────────────────────────────────
INSERT INTO public.worker_shifts (id, worker_profile_id, shift_date, shift_start, shift_end, zone_id) VALUES
  -- Ravi (Mumbai Andheri) — 3 recent shifts
  ('cccc0000-0000-0000-0000-000000000001', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-10', '2026-03-10T08:00:00+05:30', '2026-03-10T18:00:00+05:30', 'b7a1c2d3-e4f5-5678-abcd-100000000001'),
  ('cccc0000-0000-0000-0000-000000000002', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-11', '2026-03-11T09:00:00+05:30', '2026-03-11T20:00:00+05:30', 'b7a1c2d3-e4f5-5678-abcd-100000000001'),
  ('cccc0000-0000-0000-0000-000000000003', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-12', '2026-03-12T07:00:00+05:30', '2026-03-12T17:00:00+05:30', 'b7a1c2d3-e4f5-5678-abcd-100000000001'),
  -- Priya (Mumbai Bandra) — 2 shifts
  ('cccc0000-0000-0000-0000-000000000004', 'aaaa0000-0000-0000-0000-000000000002', '2026-03-10', '2026-03-10T10:00:00+05:30', '2026-03-10T21:00:00+05:30', 'b7a1c2d3-e4f5-5678-abcd-100000000002'),
  ('cccc0000-0000-0000-0000-000000000005', 'aaaa0000-0000-0000-0000-000000000002', '2026-03-11', '2026-03-11T11:00:00+05:30', '2026-03-11T22:00:00+05:30', 'b7a1c2d3-e4f5-5678-abcd-100000000002'),
  -- Arun (Delhi CP)
  ('cccc0000-0000-0000-0000-000000000006', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-11', '2026-03-11T06:00:00+05:30', '2026-03-11T16:00:00+05:30', 'b7a1c2d3-e4f5-5678-abcd-100000000003'),
  ('cccc0000-0000-0000-0000-000000000007', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-13', '2026-03-13T07:00:00+05:30', '2026-03-13T18:00:00+05:30', 'b7a1c2d3-e4f5-5678-abcd-100000000003'),
  -- Meena (Delhi Saket)
  ('cccc0000-0000-0000-0000-000000000008', 'aaaa0000-0000-0000-0000-000000000004', '2026-03-12', '2026-03-12T08:00:00+05:30', '2026-03-12T19:00:00+05:30', 'b7a1c2d3-e4f5-5678-abcd-100000000004'),
  -- Suresh (Bangalore Koramangala)
  ('cccc0000-0000-0000-0000-000000000009', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-13', '2026-03-13T09:00:00+05:30', '2026-03-13T21:00:00+05:30', 'b7a1c2d3-e4f5-5678-abcd-100000000005'),
  -- Fatima (Hyderabad Madhapur)
  ('cccc0000-0000-0000-0000-000000000010', 'aaaa0000-0000-0000-0000-000000000006', '2026-03-15', '2026-03-15T10:00:00+05:30', '2026-03-15T20:00:00+05:30', 'b7a1c2d3-e4f5-5678-abcd-100000000007'),
  -- Demo Worker (Mumbai Andheri) — 3 shifts
  ('cccc0000-0000-0000-0000-000000000011', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-10', '2026-03-10T07:00:00+05:30', '2026-03-10T18:00:00+05:30', 'b7a1c2d3-e4f5-5678-abcd-100000000001'),
  ('cccc0000-0000-0000-0000-000000000012', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-12', '2026-03-12T08:00:00+05:30', '2026-03-12T19:00:00+05:30', 'b7a1c2d3-e4f5-5678-abcd-100000000001'),
  ('cccc0000-0000-0000-0000-000000000013', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-14', '2026-03-14T09:00:00+05:30', '2026-03-14T20:00:00+05:30', 'b7a1c2d3-e4f5-5678-abcd-100000000001')
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 6. Platform Worker Daily Stats (14 days for each major worker)
-- ────────────────────────────────────────────────────────────
INSERT INTO public.platform_worker_daily_stats (id, worker_profile_id, stat_date, active_hours, completed_orders, accepted_orders, cancelled_orders, gross_earnings_inr, platform_login_minutes, gps_consistency_score) VALUES
  -- Ravi Kumar (Mumbai) — 14 days
  ('dddd0000-0000-0000-0000-000000000001', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-02', 9.5,  18, 22, 1, 1615.00, 600, 0.92),
  ('dddd0000-0000-0000-0000-000000000002', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-03', 8.0,  15, 18, 2, 1280.00, 510, 0.89),
  ('dddd0000-0000-0000-0000-000000000003', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-04', 10.0, 21, 25, 0, 1890.00, 630, 0.94),
  ('dddd0000-0000-0000-0000-000000000004', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-05', 7.5,  14, 16, 1, 1190.00, 480, 0.88),
  ('dddd0000-0000-0000-0000-000000000005', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-06', 0.0,   0,  0, 0,    0.00,   0, 0.00),
  ('dddd0000-0000-0000-0000-000000000006', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-07', 11.0, 24, 28, 1, 2040.00, 690, 0.95),
  ('dddd0000-0000-0000-0000-000000000007', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-08', 8.5,  16, 19, 2, 1360.00, 540, 0.91),
  ('dddd0000-0000-0000-0000-000000000008', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-09', 9.0,  17, 20, 0, 1530.00, 570, 0.93),
  ('dddd0000-0000-0000-0000-000000000009', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-10', 6.0,  10, 13, 3,  850.00, 390, 0.78),
  ('dddd0000-0000-0000-0000-000000000010', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-11', 10.5, 22, 26, 1, 1870.00, 660, 0.96),
  ('dddd0000-0000-0000-0000-000000000011', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-12', 9.0,  19, 22, 0, 1615.00, 570, 0.90),
  ('dddd0000-0000-0000-0000-000000000012', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-13', 7.0,  13, 15, 2, 1105.00, 450, 0.85),
  ('dddd0000-0000-0000-0000-000000000013', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-14', 8.5,  16, 18, 1, 1360.00, 540, 0.91),
  ('dddd0000-0000-0000-0000-000000000014', 'aaaa0000-0000-0000-0000-000000000001', '2026-03-15', 10.0, 20, 24, 0, 1700.00, 630, 0.94),
  -- Arun Patel (Delhi) — 14 days
  ('dddd0000-0000-0000-0000-000000000015', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-02', 10.0, 20, 24, 1, 1840.00, 630, 0.93),
  ('dddd0000-0000-0000-0000-000000000016', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-03', 9.0,  17, 21, 0, 1564.00, 570, 0.91),
  ('dddd0000-0000-0000-0000-000000000017', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-04', 11.0, 23, 27, 2, 2116.00, 690, 0.95),
  ('dddd0000-0000-0000-0000-000000000018', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-05', 8.0,  15, 18, 1, 1380.00, 510, 0.89),
  ('dddd0000-0000-0000-0000-000000000019', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-06', 9.5,  19, 22, 0, 1748.00, 600, 0.92),
  ('dddd0000-0000-0000-0000-000000000020', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-07', 0.0,   0,  0, 0,    0.00,   0, 0.00),
  ('dddd0000-0000-0000-0000-000000000021', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-08', 10.5, 22, 25, 1, 1932.00, 660, 0.94),
  ('dddd0000-0000-0000-0000-000000000022', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-09', 7.5,  14, 17, 2, 1288.00, 480, 0.87),
  ('dddd0000-0000-0000-0000-000000000023', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-10', 9.0,  18, 21, 0, 1656.00, 570, 0.91),
  ('dddd0000-0000-0000-0000-000000000024', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-11', 8.5,  16, 19, 1, 1472.00, 540, 0.90),
  ('dddd0000-0000-0000-0000-000000000025', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-12', 10.0, 21, 25, 0, 1840.00, 630, 0.93),
  ('dddd0000-0000-0000-0000-000000000026', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-13', 7.0,  12, 15, 3, 1104.00, 450, 0.82),
  ('dddd0000-0000-0000-0000-000000000027', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-14', 9.5,  19, 23, 1, 1748.00, 600, 0.92),
  ('dddd0000-0000-0000-0000-000000000028', 'aaaa0000-0000-0000-0000-000000000003', '2026-03-15', 11.0, 24, 28, 0, 2024.00, 690, 0.96),
  -- Suresh Yadav (Bangalore) — 14 days
  ('dddd0000-0000-0000-0000-000000000029', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-02', 8.5,  16, 19, 1, 1360.00, 540, 0.90),
  ('dddd0000-0000-0000-0000-000000000030', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-03', 9.0,  18, 21, 0, 1440.00, 570, 0.91),
  ('dddd0000-0000-0000-0000-000000000031', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-04', 10.0, 20, 24, 2, 1600.00, 630, 0.93),
  ('dddd0000-0000-0000-0000-000000000032', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-05', 7.0,  13, 16, 1, 1040.00, 450, 0.86),
  ('dddd0000-0000-0000-0000-000000000033', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-06', 0.0,   0,  0, 0,    0.00,   0, 0.00),
  ('dddd0000-0000-0000-0000-000000000034', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-07', 9.5,  19, 22, 0, 1520.00, 600, 0.92),
  ('dddd0000-0000-0000-0000-000000000035', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-08', 8.0,  15, 18, 2, 1200.00, 510, 0.88),
  ('dddd0000-0000-0000-0000-000000000036', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-09', 10.5, 22, 25, 1, 1680.00, 660, 0.94),
  ('dddd0000-0000-0000-0000-000000000037', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-10', 7.5,  14, 17, 0, 1120.00, 480, 0.87),
  ('dddd0000-0000-0000-0000-000000000038', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-11', 9.0,  17, 20, 1, 1360.00, 570, 0.91),
  ('dddd0000-0000-0000-0000-000000000039', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-12', 11.0, 23, 27, 0, 1760.00, 690, 0.95),
  ('dddd0000-0000-0000-0000-000000000040', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-13', 8.5,  16, 19, 2, 1280.00, 540, 0.89),
  ('dddd0000-0000-0000-0000-000000000041', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-14', 9.0,  18, 21, 1, 1440.00, 570, 0.90),
  ('dddd0000-0000-0000-0000-000000000042', 'aaaa0000-0000-0000-0000-000000000005', '2026-03-15', 10.0, 21, 24, 0, 1600.00, 630, 0.93),
  -- Demo Worker (Mumbai) — 14 days
  ('dddd0000-0000-0000-0000-000000000043', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-02', 9.0,  17, 20, 1, 1530.00, 570, 0.91),
  ('dddd0000-0000-0000-0000-000000000044', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-03', 8.5,  16, 19, 0, 1360.00, 540, 0.89),
  ('dddd0000-0000-0000-0000-000000000045', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-04', 10.5, 22, 26, 1, 1890.00, 660, 0.93),
  ('dddd0000-0000-0000-0000-000000000046', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-05', 7.0,  13, 15, 2, 1170.00, 450, 0.85),
  ('dddd0000-0000-0000-0000-000000000047', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-06', 0.0,   0,  0, 0,    0.00,   0, 0.00),
  ('dddd0000-0000-0000-0000-000000000048', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-07', 11.0, 24, 28, 0, 1980.00, 690, 0.95),
  ('dddd0000-0000-0000-0000-000000000049', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-08', 8.0,  15, 18, 1, 1350.00, 510, 0.88),
  ('dddd0000-0000-0000-0000-000000000050', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-09', 9.5,  19, 22, 0, 1710.00, 600, 0.92),
  ('dddd0000-0000-0000-0000-000000000051', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-10', 5.5,   9, 12, 3,  825.00, 360, 0.76),
  ('dddd0000-0000-0000-0000-000000000052', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-11', 10.0, 21, 25, 1, 1890.00, 630, 0.94),
  ('dddd0000-0000-0000-0000-000000000053', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-12', 9.0,  18, 21, 0, 1620.00, 570, 0.91),
  ('dddd0000-0000-0000-0000-000000000054', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-13', 7.5,  14, 17, 2, 1260.00, 480, 0.87),
  ('dddd0000-0000-0000-0000-000000000055', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-14', 8.5,  16, 19, 1, 1440.00, 540, 0.90),
  ('dddd0000-0000-0000-0000-000000000056', 'aaaa0000-0000-0000-0000-000000000201', '2026-03-15', 10.0, 20, 23, 0, 1800.00, 630, 0.93)
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 7. Platform Order Events (sample orders for key workers)
-- ────────────────────────────────────────────────────────────
INSERT INTO public.platform_order_events (id, worker_profile_id, platform_order_id, assigned_at, picked_up_at, delivered_at, order_status, pickup_zone_id, drop_zone_id, distance_km, payout_inr) VALUES
  -- Ravi (Mumbai) — orders on disruption day
  ('eeee0000-0000-0000-0000-000000000001', 'aaaa0000-0000-0000-0000-000000000001', 'SWG-MUM-20260310-001', '2026-03-10T08:15:00+05:30', '2026-03-10T08:35:00+05:30', '2026-03-10T09:10:00+05:30', 'completed', 'b7a1c2d3-e4f5-5678-abcd-100000000001', 'b7a1c2d3-e4f5-5678-abcd-100000000001', 3.20, 72.00),
  ('eeee0000-0000-0000-0000-000000000002', 'aaaa0000-0000-0000-0000-000000000001', 'SWG-MUM-20260310-002', '2026-03-10T09:30:00+05:30', '2026-03-10T09:50:00+05:30', NULL,                        'cancelled', 'b7a1c2d3-e4f5-5678-abcd-100000000001', 'b7a1c2d3-e4f5-5678-abcd-100000000002', 5.10,  0.00),
  ('eeee0000-0000-0000-0000-000000000003', 'aaaa0000-0000-0000-0000-000000000001', 'SWG-MUM-20260310-003', '2026-03-10T10:00:00+05:30', '2026-03-10T10:25:00+05:30', '2026-03-10T11:00:00+05:30', 'completed', 'b7a1c2d3-e4f5-5678-abcd-100000000001', 'b7a1c2d3-e4f5-5678-abcd-100000000001', 2.80, 65.00),
  ('eeee0000-0000-0000-0000-000000000004', 'aaaa0000-0000-0000-0000-000000000001', 'SWG-MUM-20260310-004', '2026-03-10T11:30:00+05:30', NULL,                        NULL,                        'delayed',   'b7a1c2d3-e4f5-5678-abcd-100000000001', 'b7a1c2d3-e4f5-5678-abcd-100000000002', 6.50,  0.00),
  -- Arun (Delhi) — AQI day
  ('eeee0000-0000-0000-0000-000000000005', 'aaaa0000-0000-0000-0000-000000000003', 'SWG-DEL-20260311-001', '2026-03-11T06:30:00+05:30', '2026-03-11T06:55:00+05:30', '2026-03-11T07:30:00+05:30', 'completed', 'b7a1c2d3-e4f5-5678-abcd-100000000003', 'b7a1c2d3-e4f5-5678-abcd-100000000003', 4.00, 82.00),
  ('eeee0000-0000-0000-0000-000000000006', 'aaaa0000-0000-0000-0000-000000000003', 'SWG-DEL-20260311-002', '2026-03-11T08:00:00+05:30', '2026-03-11T08:20:00+05:30', '2026-03-11T09:05:00+05:30', 'completed', 'b7a1c2d3-e4f5-5678-abcd-100000000003', 'b7a1c2d3-e4f5-5678-abcd-100000000004', 7.20, 95.00),
  ('eeee0000-0000-0000-0000-000000000007', 'aaaa0000-0000-0000-0000-000000000003', 'SWG-DEL-20260311-003', '2026-03-11T10:00:00+05:30', NULL,                        NULL,                        'cancelled', 'b7a1c2d3-e4f5-5678-abcd-100000000003', 'b7a1c2d3-e4f5-5678-abcd-100000000003', 3.10,  0.00),
  -- Suresh (Bangalore) — traffic day
  ('eeee0000-0000-0000-0000-000000000008', 'aaaa0000-0000-0000-0000-000000000005', 'ZOM-BLR-20260313-001', '2026-03-13T09:15:00+05:30', '2026-03-13T09:40:00+05:30', '2026-03-13T10:20:00+05:30', 'completed', 'b7a1c2d3-e4f5-5678-abcd-100000000005', 'b7a1c2d3-e4f5-5678-abcd-100000000005', 2.50, 60.00),
  ('eeee0000-0000-0000-0000-000000000009', 'aaaa0000-0000-0000-0000-000000000005', 'ZOM-BLR-20260313-002', '2026-03-13T11:00:00+05:30', '2026-03-13T11:30:00+05:30', '2026-03-13T12:15:00+05:30', 'delayed',   'b7a1c2d3-e4f5-5678-abcd-100000000005', 'b7a1c2d3-e4f5-5678-abcd-100000000006', 5.80, 45.00),
  ('eeee0000-0000-0000-0000-000000000010', 'aaaa0000-0000-0000-0000-000000000005', 'ZOM-BLR-20260313-003', '2026-03-13T13:00:00+05:30', '2026-03-13T13:25:00+05:30', '2026-03-13T14:00:00+05:30', 'completed', 'b7a1c2d3-e4f5-5678-abcd-100000000005', 'b7a1c2d3-e4f5-5678-abcd-100000000005', 3.40, 68.00)
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 8. Trigger Events (diverse disruptions with proper thresholds)
-- ────────────────────────────────────────────────────────────
INSERT INTO public.trigger_events (id, city, zone_id, trigger_family, trigger_code, source_ref_id, observed_value, official_threshold_label, product_threshold_value, severity_band, source_type, started_at, ended_at) VALUES
  -- Rain: Mumbai Andheri — Heavy (claim)
  ('ffff0000-0000-0000-0000-000000000001', 'Mumbai',    'b7a1c2d3-e4f5-5678-abcd-100000000001', 'rain',    'RAIN_HEAVY',       'R3', 72.0,   'IMD heavy rainfall (64.5 mm/24h)',          '64.5 mm',        'claim',      'public_source',      '2026-03-10T06:00:00+05:30', '2026-03-10T14:00:00+05:30'),
  -- Rain: Mumbai Bandra — Extreme (escalation)
  ('ffff0000-0000-0000-0000-000000000002', 'Mumbai',    'b7a1c2d3-e4f5-5678-abcd-100000000002', 'rain',    'RAIN_EXTREME',     'R3', 130.0,  'IMD very heavy rainfall (115.6 mm/24h)',    '115.6 mm',       'escalation', 'public_source',      '2026-03-10T06:00:00+05:30', '2026-03-10T16:00:00+05:30'),
  -- Rain: Mumbai Andheri — Watch
  ('ffff0000-0000-0000-0000-000000000003', 'Mumbai',    'b7a1c2d3-e4f5-5678-abcd-100000000001', 'rain',    'RAIN_WATCH',       'R3', 52.0,   'IMD elevated rainfall (approaching heavy)', '48 mm',          'watch',      'public_source',      '2026-03-14T04:00:00+05:30', '2026-03-14T12:00:00+05:30'),
  -- AQI: Delhi CP — Very Poor (claim)
  ('ffff0000-0000-0000-0000-000000000004', 'Delhi',     'b7a1c2d3-e4f5-5678-abcd-100000000003', 'aqi',     'AQI_SEVERE',       'R1', 340.0,  'CPCB Very Poor AQI (301-400)',              '301+',           'claim',      'public_source',      '2026-03-11T06:00:00+05:30', '2026-03-11T18:00:00+05:30'),
  -- AQI: Delhi Saket — Caution (watch)
  ('ffff0000-0000-0000-0000-000000000005', 'Delhi',     'b7a1c2d3-e4f5-5678-abcd-100000000004', 'aqi',     'AQI_POOR',         'R1', 245.0,  'CPCB Poor AQI (201-300)',                   '201+',           'watch',      'public_source',      '2026-03-11T06:00:00+05:30', '2026-03-11T18:00:00+05:30'),
  -- AQI: Hyderabad Gachibowli — Severe (escalation)
  ('ffff0000-0000-0000-0000-000000000006', 'Hyderabad', 'b7a1c2d3-e4f5-5678-abcd-100000000008', 'aqi',     'AQI_EXTREME',      'R1', 420.0,  'CPCB Severe AQI (401+)',                    '401+',           'escalation', 'public_source',      '2026-03-16T06:00:00+05:30', '2026-03-16T20:00:00+05:30'),
  -- Heat: Delhi Saket — Heat wave (claim)
  ('ffff0000-0000-0000-0000-000000000007', 'Delhi',     'b7a1c2d3-e4f5-5678-abcd-100000000004', 'heat',    'HEAT_WAVE',        'R4', 46.0,   'IMD heat-wave (>=45C plains)',               '45C',            'claim',      'public_source',      '2026-03-12T06:00:00+05:30', '2026-03-12T16:00:00+05:30'),
  -- Heat: Delhi CP — Severe heat (escalation)
  ('ffff0000-0000-0000-0000-000000000008', 'Delhi',     'b7a1c2d3-e4f5-5678-abcd-100000000003', 'heat',    'HEAT_EXTREME',     'R4', 48.0,   'IMD severe heat (>=47C plains)',             '47C',            'escalation', 'public_source',      '2026-03-13T08:00:00+05:30', '2026-03-13T18:00:00+05:30'),
  -- Traffic: Bangalore Koramangala (internal operational)
  ('ffff0000-0000-0000-0000-000000000009', 'Bangalore', 'b7a1c2d3-e4f5-5678-abcd-100000000005', 'traffic', 'TRAFFIC_SEVERE',   NULL, 55.0,   NULL,                                        '40%+ delay',     'watch',      'internal_operational','2026-03-13T06:00:00+05:30', '2026-03-13T12:00:00+05:30'),
  -- Outage: Bangalore Indiranagar (internal operational)
  ('ffff0000-0000-0000-0000-000000000010', 'Bangalore', 'b7a1c2d3-e4f5-5678-abcd-100000000006', 'outage',  'PLATFORM_OUTAGE',  NULL, 45.0,   NULL,                                        '30+ min outage', 'claim',      'internal_operational','2026-03-14T09:00:00+05:30', '2026-03-14T11:00:00+05:30'),
  -- Demand: Hyderabad Madhapur (internal operational)
  ('ffff0000-0000-0000-0000-000000000011', 'Hyderabad', 'b7a1c2d3-e4f5-5678-abcd-100000000007', 'demand',  'DEMAND_COLLAPSE',  NULL, 42.0,   NULL,                                        '35%+ order drop','watch',      'internal_operational','2026-03-15T06:00:00+05:30', '2026-03-15T14:00:00+05:30'),
  -- Outage: Mumbai Bandra (internal operational)
  ('ffff0000-0000-0000-0000-000000000012', 'Mumbai',    'b7a1c2d3-e4f5-5678-abcd-100000000002', 'outage',  'PLATFORM_OUTAGE',  NULL, 62.0,   NULL,                                        '30+ min outage', 'escalation', 'internal_operational','2026-03-11T14:00:00+05:30', '2026-03-11T16:00:00+05:30')
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 9. Manual Claims (7 diverse claims across workers)
-- ────────────────────────────────────────────────────────────
INSERT INTO public.manual_claims (id, worker_profile_id, trigger_event_id, claim_mode, claim_reason, stated_lat, stated_lng, claimed_at, shift_id, claim_status) VALUES
  -- Ravi: Rain claim — auto-matched to RAIN_HEAVY trigger
  ('11110000-0000-0000-0000-000000000001', 'aaaa0000-0000-0000-0000-000000000001', 'ffff0000-0000-0000-0000-000000000001', 'trigger_auto', 'Heavy rain flooding in Andheri West area. Roads waterlogged, could not reach pickup restaurants. Multiple orders cancelled.', 19.1370, 72.8290, '2026-03-10T10:30:00+05:30', 'cccc0000-0000-0000-0000-000000000001', 'approved'),
  -- Priya: Extreme rain — manual claim
  ('11110000-0000-0000-0000-000000000002', 'aaaa0000-0000-0000-0000-000000000002', 'ffff0000-0000-0000-0000-000000000002', 'manual', 'Severe waterlogging in BKC area due to extreme rainfall. Completely unable to deliver. Bike stalled in water.', 19.0600, 72.8650, '2026-03-10T12:00:00+05:30', 'cccc0000-0000-0000-0000-000000000004', 'held'),
  -- Arun: AQI claim — auto-matched
  ('11110000-0000-0000-0000-000000000003', 'aaaa0000-0000-0000-0000-000000000003', 'ffff0000-0000-0000-0000-000000000004', 'trigger_auto', 'Severe air quality in Connaught Place. AQI above 300. Breathing difficulty during deliveries, had to stop mid-shift.', 28.6320, 77.2170, '2026-03-11T09:00:00+05:30', 'cccc0000-0000-0000-0000-000000000006', 'approved'),
  -- Meena: Heat wave — manual claim
  ('11110000-0000-0000-0000-000000000004', 'aaaa0000-0000-0000-0000-000000000004', 'ffff0000-0000-0000-0000-000000000007', 'manual', 'Extreme heat in Saket. Temperature over 46C. Got heat exhaustion symptoms — dizziness and nausea. Had to abandon shift.', 28.5250, 77.2060, '2026-03-12T13:00:00+05:30', 'cccc0000-0000-0000-0000-000000000008', 'submitted'),
  -- Suresh: Traffic disruption — manual claim
  ('11110000-0000-0000-0000-000000000005', 'aaaa0000-0000-0000-0000-000000000005', 'ffff0000-0000-0000-0000-000000000009', 'manual', 'Major traffic jam on Hosur Road near Koramangala. 55%+ delay inflation. Three orders timed out while stuck. Lost full morning earnings.', 12.9360, 77.6240, '2026-03-13T11:30:00+05:30', 'cccc0000-0000-0000-0000-000000000009', 'held'),
  -- Fatima: Demand collapse — manual claim
  ('11110000-0000-0000-0000-000000000006', 'aaaa0000-0000-0000-0000-000000000006', 'ffff0000-0000-0000-0000-000000000011', 'manual', 'Order demand collapsed in Madhapur area today. Only 3 orders in 5 hours vs usual 10-12. Platform showing very low demand zone.', 17.4490, 78.3910, '2026-03-15T15:00:00+05:30', 'cccc0000-0000-0000-0000-000000000010', 'submitted'),
  -- Ravi: Second claim — manual, no trigger match
  ('11110000-0000-0000-0000-000000000007', 'aaaa0000-0000-0000-0000-000000000001', NULL,                                   'manual', 'Restaurant closure due to health inspection. Three assigned orders could not be picked up. Stood idle for 2 hours with no reassignment.', 19.1380, 72.8300, '2026-03-14T14:00:00+05:30', 'cccc0000-0000-0000-0000-000000000003', 'rejected'),
  -- Demo Worker: Rain claim — auto-matched to RAIN_HEAVY trigger in Andheri
  ('11110000-0000-0000-0000-000000000008', 'aaaa0000-0000-0000-0000-000000000201', 'ffff0000-0000-0000-0000-000000000001', 'trigger_auto', 'Heavy rain in Andheri West caused widespread waterlogging. Roads submerged near Link Road. Could not access pickup locations for 4 hours.', 19.1365, 72.8288, '2026-03-10T11:00:00+05:30', 'cccc0000-0000-0000-0000-000000000011', 'approved'),
  -- Demo Worker: Watch-level rain — manual claim
  ('11110000-0000-0000-0000-000000000009', 'aaaa0000-0000-0000-0000-000000000201', 'ffff0000-0000-0000-0000-000000000003', 'manual', 'Moderate rain causing slow traffic in Andheri area. Deliveries delayed significantly, multiple orders timed out before pickup.', 19.1372, 72.8295, '2026-03-14T15:30:00+05:30', 'cccc0000-0000-0000-0000-000000000013', 'submitted')
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 10. Claim Evidence (diverse evidence types)
-- ────────────────────────────────────────────────────────────
INSERT INTO public.claim_evidence (id, claim_id, evidence_type, storage_path, captured_at, exif_lat, exif_lng, exif_timestamp, integrity_score) VALUES
  -- Ravi rain claim (photo + geo)
  ('22220000-0000-0000-0000-000000000001', '11110000-0000-0000-0000-000000000001', 'photo', 'claim-evidence/ravi-rain-flood-01.jpg',    '2026-03-10T10:25:00+05:30', 19.1368, 72.8294, '2026-03-10T10:25:00+05:30', 0.92),
  ('22220000-0000-0000-0000-000000000002', '11110000-0000-0000-0000-000000000001', 'geo',   NULL,                                       '2026-03-10T10:30:00+05:30', 19.1370, 72.8290, '2026-03-10T10:30:00+05:30', 0.95),
  -- Priya rain claim (photo)
  ('22220000-0000-0000-0000-000000000003', '11110000-0000-0000-0000-000000000002', 'photo', 'claim-evidence/priya-bkc-waterlog-01.jpg', '2026-03-10T11:55:00+05:30', 19.0598, 72.8648, '2026-03-10T11:55:00+05:30', 0.88),
  -- Arun AQI claim (photo + text)
  ('22220000-0000-0000-0000-000000000004', '11110000-0000-0000-0000-000000000003', 'photo', 'claim-evidence/arun-delhi-smog-01.jpg',    '2026-03-11T08:50:00+05:30', 28.6318, 77.2165, '2026-03-11T08:50:00+05:30', 0.90),
  ('22220000-0000-0000-0000-000000000005', '11110000-0000-0000-0000-000000000003', 'text',  NULL,                                       '2026-03-11T09:00:00+05:30', NULL,    NULL,    NULL,                        0.70),
  -- Meena heat claim (photo + geo)
  ('22220000-0000-0000-0000-000000000006', '11110000-0000-0000-0000-000000000004', 'photo', 'claim-evidence/meena-heat-saket-01.jpg',   '2026-03-12T12:50:00+05:30', 28.5248, 77.2058, '2026-03-12T12:50:00+05:30', 0.85),
  ('22220000-0000-0000-0000-000000000007', '11110000-0000-0000-0000-000000000004', 'geo',   NULL,                                       '2026-03-12T13:00:00+05:30', 28.5250, 77.2060, '2026-03-12T13:00:00+05:30', 0.93),
  -- Suresh traffic claim (photo)
  ('22220000-0000-0000-0000-000000000008', '11110000-0000-0000-0000-000000000005', 'photo', 'claim-evidence/suresh-traffic-blr-01.jpg', '2026-03-13T11:25:00+05:30', 12.9358, 77.6242, '2026-03-13T11:25:00+05:30', 0.87),
  -- Ravi rejected claim (no evidence — contributes to rejection)
  ('22220000-0000-0000-0000-000000000009', '11110000-0000-0000-0000-000000000007', 'text',  NULL,                                       '2026-03-14T14:00:00+05:30', NULL,    NULL,    NULL,                        0.40),
  -- Demo Worker rain claim (photo + geo)
  ('22220000-0000-0000-0000-000000000010', '11110000-0000-0000-0000-000000000008', 'photo', 'claim-evidence/demo-rain-andheri-01.jpg',   '2026-03-10T10:55:00+05:30', 19.1363, 72.8286, '2026-03-10T10:55:00+05:30', 0.91),
  ('22220000-0000-0000-0000-000000000011', '11110000-0000-0000-0000-000000000008', 'geo',   NULL,                                       '2026-03-10T11:00:00+05:30', 19.1365, 72.8288, '2026-03-10T11:00:00+05:30', 0.94)
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 11. Payout Recommendations (formula outputs B,p,S,E,C,FH,U)
-- ────────────────────────────────────────────────────────────
INSERT INTO public.payout_recommendations (id, claim_id, covered_weekly_income_b, claim_probability_p, severity_score_s, exposure_score_e, confidence_score_c, fraud_holdback_fh, outlier_uplift_u, payout_cap, expected_payout, gross_premium, recommended_payout, explanation_json) VALUES
  -- Ravi rain claim (approved, auto)
  ('33330000-0000-0000-0000-000000000001', '11110000-0000-0000-0000-000000000001',
   3213.00, 0.1500, 0.7800, 0.8300, 0.9200, 0.0300, 1.00,
   2409.75,   -- Cap = 0.75 * 3213 * 1.0
   279.57,    -- Expected = 0.15 * 3213 * 0.78 * 0.83 * 0.92 * (1-0.03)
   358.42,    -- Gross = Expected / (1 - 0.12 - 0.10) * 1.0
   2266.78,   -- Recommended = min(Cap, B*S*E*C*(1-FH))
   '{"ai_summary": "Auto-triggered rain claim in Andheri-W zone. IMD heavy rainfall threshold (64.5mm) exceeded at 72mm. Worker GPS confirmed in-zone during active shift. Evidence photo EXIF timestamp matches claimed timeframe. Confidence score high (0.92). Fraud holdback minimal (0.03). Recommended full payout of Rs 2,266.78 against a cap of Rs 2,409.75.", "pipeline_stages_passed": 8, "manual_hold_reasons": []}'::jsonb),
  -- Priya rain claim (held, manual)
  ('33330000-0000-0000-0000-000000000002', '11110000-0000-0000-0000-000000000002',
   2948.40, 0.1500, 0.9200, 0.8500, 0.7800, 0.1200, 1.00,
   2211.30,
   258.90,
   331.92,
   1830.72,
   '{"ai_summary": "Manual rain claim in Bandra-Kurla zone. Extreme rainfall (130mm) verified via IMD data. However, manual claim path triggered additional verification. Evidence photo EXIF shows slight geo-offset (boundary zone). Geo-confidence penalized to 0.78. Fraud holdback elevated to 0.12 due to manual submission multiplier. Recommended hold for admin review.", "pipeline_stages_passed": 7, "manual_hold_reasons": ["geo_confidence_below_threshold", "manual_claim_multiplier_applied"]}'::jsonb),
  -- Arun AQI claim (approved, auto)
  ('33330000-0000-0000-0000-000000000003', '11110000-0000-0000-0000-000000000003',
   3477.60, 0.1500, 0.6500, 0.8800, 0.9100, 0.0200, 1.00,
   2608.20,
   274.17,
   351.50,
   1810.74,
   '{"ai_summary": "Auto-triggered AQI claim at Connaught Place, Delhi. CPCB Very Poor AQI (340) exceeded the 301+ claim threshold. Worker confirmed active during shift via platform stats. Text evidence with breathing difficulty report corroborates. High confidence (0.91), minimal fraud holdback (0.02). Payout is Rs 1,810.74, well within cap.", "pipeline_stages_passed": 8, "manual_hold_reasons": []}'::jsonb),
  -- Meena heat claim (submitted, pending review)
  ('33330000-0000-0000-0000-000000000004', '11110000-0000-0000-0000-000000000004',
   2079.00, 0.1500, 0.8500, 0.7200, 0.6800, 0.2000, 1.00,
   1559.25,
   130.07,
   166.75,
   923.32,
   '{"ai_summary": "Manual heat claim at Saket, Delhi. Heat wave (46C) above 45C IMD threshold. Worker Meena is a cycle rider with lower bank verification status. Trust score lower (0.65) impacts confidence. GPS consent active but no bank verification reduces confidence further. Manual claim multiplier increases fraud holdback to 0.20. Recommended payout Rs 923.32 pending manual review.", "pipeline_stages_passed": 7, "manual_hold_reasons": ["low_trust_score", "no_bank_verification", "manual_claim_multiplier_applied"]}'::jsonb),
  -- Suresh traffic claim (held)
  ('33330000-0000-0000-0000-000000000005', '11110000-0000-0000-0000-000000000005',
   3024.00, 0.1500, 0.4500, 0.7800, 0.8500, 0.0800, 1.00,
   2268.00,
   123.28,
   158.05,
   895.66,
   '{"ai_summary": "Manual traffic claim in Koramangala, Bangalore. 55% delay inflation reported. Traffic is an internal operational trigger (no official government threshold). Photo evidence shows traffic congestion. Geo-confidence good. However, internal operational triggers always trigger hold for admin validation of the reported values. Recommended hold.", "pipeline_stages_passed": 7, "manual_hold_reasons": ["internal_operational_trigger_requires_validation", "manual_claim_multiplier_applied"]}'::jsonb),
  -- Fatima demand claim (submitted)
  ('33330000-0000-0000-0000-000000000006', '11110000-0000-0000-0000-000000000006',
   2721.60, 0.1500, 0.3500, 0.7000, 0.7200, 0.1500, 1.00,
   2041.20,
   71.88,
   92.15,
   464.50,
   '{"ai_summary": "Manual demand collapse claim in Madhapur, Hyderabad. Worker reports 42% order drop vs baseline. No GPS consent reduces geo-confidence significantly. Demand collapse is an internal operational threshold (35%+). Evidence limited to text description. Multiple hold reasons flagged: no GPS consent, internal trigger, below-threshold geo-confidence. Recommended payout Rs 464.50 pending thorough review.", "pipeline_stages_passed": 6, "manual_hold_reasons": ["no_gps_consent", "internal_operational_trigger", "low_evidence_completeness"]}'::jsonb),
  -- Ravi rejected claim (no trigger match)
  ('33330000-0000-0000-0000-000000000007', '11110000-0000-0000-0000-000000000007',
   3213.00, 0.1500, 0.2000, 0.5000, 0.4500, 0.4000, 1.00,
   2409.75,
   38.61,
   49.50,
   86.94,
   '{"ai_summary": "Manual claim without trigger match. Restaurant closure cited but no corresponding trigger event found in system. Evidence is text-only with no photo or geo corroboration. EXIF data absent. Evidence completeness score very low (0.40). No shift-trigger temporal overlap verified. Fraud holdback high (0.40). Multiple red flags. Recommended rejection.", "pipeline_stages_passed": 5, "manual_hold_reasons": ["no_trigger_match", "text_only_evidence", "no_geo_data", "high_fraud_score"]}'::jsonb),
  -- Demo Worker rain claim (approved, auto)
  ('33330000-0000-0000-0000-000000000008', '11110000-0000-0000-0000-000000000008',
   3402.00, 0.1500, 0.7800, 0.8300, 0.9000, 0.0400, 1.00,
   2551.50,
   280.12,
   359.13,
   2110.45,
   '{"ai_summary": "Auto-triggered rain claim in Andheri-W zone for Demo Worker. IMD heavy rainfall threshold (64.5mm) exceeded at 72mm. Worker GPS confirmed in-zone during active shift. Evidence photo EXIF timestamp matches claimed timeframe. Confidence score high (0.90). Fraud holdback low (0.04). Recommended payout of Rs 2,110.45 against a cap of Rs 2,551.50.", "pipeline_stages_passed": 8, "manual_hold_reasons": []}'::jsonb),
  -- Demo Worker watch-level rain claim (submitted, pending)
  ('33330000-0000-0000-0000-000000000009', '11110000-0000-0000-0000-000000000009',
   3402.00, 0.1500, 0.4200, 0.7500, 0.8200, 0.0800, 1.00,
   2551.50,
   109.80,
   140.77,
   788.42,
   '{"ai_summary": "Manual claim by Demo Worker during rain watch event in Andheri-W. Rain at 52mm is above the 48mm watch threshold but below the 64.5mm heavy-rain claim threshold. Manual claim path applied. Evidence not yet submitted. Pending review.", "pipeline_stages_passed": 6, "manual_hold_reasons": ["watch_level_trigger", "manual_claim_multiplier_applied"]}'::jsonb)
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 12. Claim Reviews (admin decisions for resolved claims)
-- ────────────────────────────────────────────────────────────
INSERT INTO public.claim_reviews (id, claim_id, reviewer_profile_id, fraud_score, geo_confidence_score, evidence_completeness_score, decision, decision_reason, reviewed_at) VALUES
  -- Ravi rain — approved by Neha
  ('44440000-0000-0000-0000-000000000001', '11110000-0000-0000-0000-000000000001', 'aaaa0000-0000-0000-0000-000000000101', 0.06, 0.95, 0.92, 'approve', 'Auto-triggered claim with strong evidence. GPS match confirmed. EXIF timestamp consistent. Approved for full recommended payout.', '2026-03-10T14:00:00+05:30'),
  -- Arun AQI — approved by Vijay
  ('44440000-0000-0000-0000-000000000002', '11110000-0000-0000-0000-000000000003', 'aaaa0000-0000-0000-0000-000000000102', 0.04, 0.91, 0.88, 'approve', 'AQI auto-trigger confirmed via CPCB data. Worker was active during shift. Photo evidence corroborates smog conditions. Approved.', '2026-03-11T16:00:00+05:30'),
  -- Ravi restaurant closure — rejected by Neha
  ('44440000-0000-0000-0000-000000000003', '11110000-0000-0000-0000-000000000007', 'aaaa0000-0000-0000-0000-000000000101', 0.80, 0.00, 0.40, 'reject', 'No matching trigger event found. Text-only evidence without photo or geo corroboration. High fraud score (0.80). Insufficient evidence to support claim. Rejected.', '2026-03-15T10:00:00+05:30'),
  -- Demo Worker rain — approved by Demo Admin
  ('44440000-0000-0000-0000-000000000004', '11110000-0000-0000-0000-000000000008', 'aaaa0000-0000-0000-0000-000000000202', 0.08, 0.94, 0.91, 'approve', 'Auto-triggered rain claim with strong photo and GPS evidence. EXIF timestamp aligns with shift window. Heavy rain threshold confirmed via IMD data (72mm). Approved for recommended payout.', '2026-03-10T15:30:00+05:30')
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 13. Audit Events (key lifecycle events)
-- ────────────────────────────────────────────────────────────
INSERT INTO public.audit_events (id, actor_profile_id, entity_type, entity_id, action_type, event_payload) VALUES
  ('55550000-0000-0000-0000-000000000001', 'aaaa0000-0000-0000-0000-000000000001', 'claim', '11110000-0000-0000-0000-000000000001', 'claim_submitted',  '{"claim_mode": "trigger_auto", "trigger_code": "RAIN_HEAVY"}'::jsonb),
  ('55550000-0000-0000-0000-000000000002', 'aaaa0000-0000-0000-0000-000000000101', 'claim', '11110000-0000-0000-0000-000000000001', 'claim_reviewed',   '{"decision": "approve", "fraud_score": 0.06}'::jsonb),
  ('55550000-0000-0000-0000-000000000003', 'aaaa0000-0000-0000-0000-000000000003', 'claim', '11110000-0000-0000-0000-000000000003', 'claim_submitted',  '{"claim_mode": "trigger_auto", "trigger_code": "AQI_SEVERE"}'::jsonb),
  ('55550000-0000-0000-0000-000000000004', 'aaaa0000-0000-0000-0000-000000000102', 'claim', '11110000-0000-0000-0000-000000000003', 'claim_reviewed',   '{"decision": "approve", "fraud_score": 0.04}'::jsonb),
  ('55550000-0000-0000-0000-000000000005', 'aaaa0000-0000-0000-0000-000000000002', 'claim', '11110000-0000-0000-0000-000000000002', 'claim_submitted',  '{"claim_mode": "manual", "reason": "extreme_rainfall"}'::jsonb),
  ('55550000-0000-0000-0000-000000000006', 'aaaa0000-0000-0000-0000-000000000004', 'claim', '11110000-0000-0000-0000-000000000004', 'claim_submitted',  '{"claim_mode": "manual", "reason": "heat_wave"}'::jsonb),
  ('55550000-0000-0000-0000-000000000007', 'aaaa0000-0000-0000-0000-000000000001', 'claim', '11110000-0000-0000-0000-000000000007', 'claim_submitted',  '{"claim_mode": "manual", "reason": "restaurant_closure"}'::jsonb),
  ('55550000-0000-0000-0000-000000000008', 'aaaa0000-0000-0000-0000-000000000101', 'claim', '11110000-0000-0000-0000-000000000007', 'claim_reviewed',   '{"decision": "reject", "fraud_score": 0.80}'::jsonb),
  ('55550000-0000-0000-0000-000000000009', 'aaaa0000-0000-0000-0000-000000000201', 'claim', '11110000-0000-0000-0000-000000000008', 'claim_submitted',  '{"claim_mode": "trigger_auto", "trigger_code": "RAIN_HEAVY"}'::jsonb),
  ('55550000-0000-0000-0000-000000000010', 'aaaa0000-0000-0000-0000-000000000202', 'claim', '11110000-0000-0000-0000-000000000008', 'claim_reviewed',   '{"decision": "approve", "fraud_score": 0.08}'::jsonb),
  ('55550000-0000-0000-0000-000000000011', 'aaaa0000-0000-0000-0000-000000000201', 'claim', '11110000-0000-0000-0000-000000000009', 'claim_submitted',  '{"claim_mode": "manual", "reason": "moderate_rain"}'::jsonb)
ON CONFLICT (id) DO NOTHING;


-- ============================================================
-- Seed Complete.
-- 7 workers (incl. demo), 3 admins (incl. demo), 8 zones,
-- 12 triggers, 9 claims, 11 evidence records,
-- 9 payout recommendations, 4 reviews, 12 audit events,
-- 56 daily stats, 10 order events.
-- ============================================================

-- Force PostgREST to reload its schema cache.
-- This prevents "Database error querying schema" after running DDL/seed.
NOTIFY pgrst, 'reload schema';
