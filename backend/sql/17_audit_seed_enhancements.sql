-- ============================================================
-- 17_audit_seed_enhancements.sql
-- Covara One — Audit-Driven Seed Enhancements
--
-- Run AFTER 06_synthetic_seed.sql (or 08_fix_demo_auth_users.sql)
-- This version first verifies which workers actually exist
-- in the database and only inserts for those workers.
--
-- Safe to re-run (uses ON CONFLICT / upserts).
-- ============================================================

-- ────────────────────────────────────────────────────────────
-- 0. Resolve target workers dynamically
--
-- This script historically referenced fixed synthetic UUIDs
-- (aaaa...). After running 08_fix_demo_auth_users.sql, demo users
-- can have new auth/profile IDs. We map up to 7 worker "slots"
-- to whichever worker_profiles currently exist.
-- ────────────────────────────────────────────────────────────
CREATE TEMP TABLE IF NOT EXISTS tmp_audit_seed_workers (
  slot integer PRIMARY KEY,
  worker_profile_id uuid NOT NULL,
  zone_id uuid
) ON COMMIT DROP;

TRUNCATE tmp_audit_seed_workers;

WITH worker_candidates AS (
  SELECT
    wp.profile_id AS worker_profile_id,
    COALESCE(
      wp.preferred_zone_id,
      (
        SELECT z.id
        FROM public.zones z
        WHERE lower(z.city) = lower(COALESCE(wp.city, ''))
        ORDER BY z.zone_name
        LIMIT 1
      ),
      (
        SELECT z2.id
        FROM public.zones z2
        ORDER BY z2.zone_name
        LIMIT 1
      )
    ) AS zone_id,
    CASE lower(COALESCE(p.email, ''))
      WHEN 'ravi.kumar@demo.devtrails.in' THEN 1
      WHEN 'priya.sharma@demo.devtrails.in' THEN 2
      WHEN 'arun.patel@demo.devtrails.in' THEN 3
      WHEN 'meena.devi@demo.devtrails.in' THEN 4
      WHEN 'suresh.yadav@demo.devtrails.in' THEN 5
      WHEN 'fatima.khan@demo.devtrails.in' THEN 6
      WHEN 'worker@demo.com' THEN 7
      ELSE 100
    END AS preferred_slot
  FROM public.worker_profiles wp
  LEFT JOIN public.profiles p ON p.id = wp.profile_id
),
seeded_slots AS (
  SELECT preferred_slot AS slot, worker_profile_id, zone_id
  FROM (
    SELECT
      wc.*,
      row_number() OVER (
        PARTITION BY wc.preferred_slot
        ORDER BY wc.worker_profile_id
      ) AS rn
    FROM worker_candidates wc
    WHERE wc.preferred_slot BETWEEN 1 AND 7
  ) ranked
  WHERE rn = 1
),
fallback_pool AS (
  SELECT
    wc.worker_profile_id,
    wc.zone_id,
    row_number() OVER (
      ORDER BY wc.preferred_slot, wc.worker_profile_id
    ) AS rn
  FROM worker_candidates wc
  WHERE wc.worker_profile_id NOT IN (
    SELECT ss.worker_profile_id FROM seeded_slots ss
  )
),
missing_slots AS (
  SELECT
    gs AS slot,
    row_number() OVER (ORDER BY gs) AS rn
  FROM generate_series(1, 7) gs
  WHERE gs NOT IN (SELECT ss.slot FROM seeded_slots ss)
)
INSERT INTO tmp_audit_seed_workers (slot, worker_profile_id, zone_id)
SELECT ss.slot, ss.worker_profile_id, ss.zone_id
FROM seeded_slots ss
UNION ALL
SELECT ms.slot, fp.worker_profile_id, fp.zone_id
FROM missing_slots ms
JOIN fallback_pool fp ON fp.rn = ms.rn;


-- ────────────────────────────────────────────────────────────
-- 1. Policies for resolved worker slots
-- ────────────────────────────────────────────────────────────
INSERT INTO public.policies (id, policy_id, worker_profile_id, zone_id, plan_type, coverage_amount, premium_amount, status, activated_at, valid_until)
SELECT
  v.id,
  v.policy_id,
  sw.worker_profile_id,
  COALESCE(sw.zone_id, v.fallback_zone_id),
  v.plan_type,
  v.coverage_amount,
  v.premium_amount,
  v.status,
  v.activated_at,
  v.valid_until
FROM (VALUES
  (1::integer, '77770000-0000-0000-0000-000000000001'::uuid, 'COV-PLUS-RAVI-001',   'plus',      4500.00::numeric, 42.00::numeric, 'active', '2026-03-01T00:00:00+05:30'::timestamptz, '2026-06-30T23:59:59+05:30'::timestamptz, 'b7a1c2d3-e4f5-5678-abcd-100000000001'::uuid),
  (2::integer, '77770000-0000-0000-0000-000000000002'::uuid, 'COV-ESS-PRIYA-001',   'essential', 3000.00::numeric, 28.00::numeric, 'active', '2026-03-01T00:00:00+05:30'::timestamptz, '2026-06-30T23:59:59+05:30'::timestamptz, 'b7a1c2d3-e4f5-5678-abcd-100000000002'::uuid),
  (3::integer, '77770000-0000-0000-0000-000000000003'::uuid, 'COV-PLUS-ARUN-001',   'plus',      4500.00::numeric, 42.00::numeric, 'active', '2026-03-01T00:00:00+05:30'::timestamptz, '2026-06-30T23:59:59+05:30'::timestamptz, 'b7a1c2d3-e4f5-5678-abcd-100000000003'::uuid),
  (4::integer, '77770000-0000-0000-0000-000000000004'::uuid, 'COV-ESS-MEENA-001',   'essential', 3000.00::numeric, 28.00::numeric, 'active', '2026-03-01T00:00:00+05:30'::timestamptz, '2026-06-30T23:59:59+05:30'::timestamptz, 'b7a1c2d3-e4f5-5678-abcd-100000000004'::uuid),
  (5::integer, '77770000-0000-0000-0000-000000000005'::uuid, 'COV-PLUS-SURESH-001', 'plus',      4500.00::numeric, 42.00::numeric, 'active', '2026-03-01T00:00:00+05:30'::timestamptz, '2026-06-30T23:59:59+05:30'::timestamptz, 'b7a1c2d3-e4f5-5678-abcd-100000000005'::uuid),
  (6::integer, '77770000-0000-0000-0000-000000000006'::uuid, 'COV-ESS-FATIMA-001',  'essential', 3000.00::numeric, 28.00::numeric, 'active', '2026-03-01T00:00:00+05:30'::timestamptz, '2026-06-30T23:59:59+05:30'::timestamptz, 'b7a1c2d3-e4f5-5678-abcd-100000000007'::uuid),
  (7::integer, '77770000-0000-0000-0000-000000000007'::uuid, 'COV-ESS-DEMO-001',    'essential', 3000.00::numeric, 28.00::numeric, 'active', '2026-03-01T00:00:00+05:30'::timestamptz, '2026-06-30T23:59:59+05:30'::timestamptz, 'b7a1c2d3-e4f5-5678-abcd-100000000001'::uuid)
) AS v(slot, id, policy_id, plan_type, coverage_amount, premium_amount, status, activated_at, valid_until, fallback_zone_id)
JOIN tmp_audit_seed_workers sw ON sw.slot = v.slot
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 2. Fraud Ring Claims (DBSCAN cluster data)
-- 6 claims at nearly identical Mumbai Andheri-W coordinates
-- within a 4-minute window — produces a DBSCAN cluster.
-- Only inserts for workers that actually exist.
-- ────────────────────────────────────────────────────────────

-- Trigger event for the fraud ring to exploit
INSERT INTO public.trigger_events (id, city, zone_id, trigger_family, trigger_code, source_ref_id, observed_value, official_threshold_label, product_threshold_value, severity_band, source_type, started_at, ended_at) VALUES
  ('ffff0000-0000-0000-0000-000000000020', 'Mumbai', 'b7a1c2d3-e4f5-5678-abcd-100000000001', 'rain', 'RAIN_HEAVY', 'R3', 88.0, 'IMD heavy rainfall (64.5 mm/24h)', '64.5 mm', 'claim', 'public_source', '2026-03-16T14:00:00+05:30', '2026-03-16T22:00:00+05:30')
ON CONFLICT (id) DO NOTHING;

-- Fraud ring claims — only inserted for existing workers
INSERT INTO public.manual_claims (id, worker_profile_id, trigger_event_id, claim_mode, claim_reason, stated_lat, stated_lng, claimed_at, claim_status)
SELECT
  v.id,
  sw.worker_profile_id,
  v.trigger_event_id,
  v.claim_mode,
  v.claim_reason,
  v.stated_lat,
  v.stated_lng,
  v.claimed_at,
  v.claim_status
FROM (VALUES
  (1::integer, '11110000-0000-0000-0000-000000000021'::uuid, 'ffff0000-0000-0000-0000-000000000020'::uuid, 'manual',
   'Heavy rain in Andheri. Roads flooded. Cannot deliver.', 19.13642::numeric, 72.82958::numeric, '2026-03-16T15:01:00+05:30'::timestamptz, 'rejected'),
  (2::integer, '11110000-0000-0000-0000-000000000022'::uuid, 'ffff0000-0000-0000-0000-000000000020'::uuid, 'manual',
   'Severe waterlogging in Andheri West. Stuck at home.', 19.13645::numeric, 72.82961::numeric, '2026-03-16T15:01:30+05:30'::timestamptz, 'rejected'),
  (3::integer, '11110000-0000-0000-0000-000000000023'::uuid, 'ffff0000-0000-0000-0000-000000000020'::uuid, 'manual',
   'Rain flooding in Andheri area. Lost shift earnings.', 19.13648::numeric, 72.82955::numeric, '2026-03-16T15:02:00+05:30'::timestamptz, 'rejected'),
  (4::integer, '11110000-0000-0000-0000-000000000024'::uuid, 'ffff0000-0000-0000-0000-000000000020'::uuid, 'manual',
   'Cannot work due to heavy rain flooding.', 19.13640::numeric, 72.82963::numeric, '2026-03-16T15:02:30+05:30'::timestamptz, 'rejected'),
  (5::integer, '11110000-0000-0000-0000-000000000025'::uuid, 'ffff0000-0000-0000-0000-000000000020'::uuid, 'manual',
   'Massive flooding near Link Road Andheri. Zero orders.', 19.13644::numeric, 72.82960::numeric, '2026-03-16T15:03:00+05:30'::timestamptz, 'rejected'),
  (6::integer, '11110000-0000-0000-0000-000000000026'::uuid, 'ffff0000-0000-0000-0000-000000000020'::uuid, 'manual',
   'Heavy rain causing complete work stoppage in Andheri.', 19.13646::numeric, 72.82957::numeric, '2026-03-16T15:03:30+05:30'::timestamptz, 'rejected')
) AS v(slot, id, trigger_event_id, claim_mode, claim_reason, stated_lat, stated_lng, claimed_at, claim_status)
JOIN tmp_audit_seed_workers sw ON sw.slot = v.slot
ON CONFLICT (id) DO NOTHING;

-- Audit events for fraud ring (no FK to worker_profiles, always safe)
INSERT INTO public.audit_events (id, actor_profile_id, entity_type, entity_id, action_type, event_payload) VALUES
  ('55550000-0000-0000-0000-000000000020', NULL, 'claim', '11110000-0000-0000-0000-000000000021', 'fraud_cluster_detected', '{"cluster_id": "RING-MUM-20260316-001", "cluster_size": 6, "detection_method": "DBSCAN", "eps": 0.005, "min_samples": 3, "decision": "batch_hold"}'::jsonb),
  ('55550000-0000-0000-0000-000000000021', NULL, 'claim', '11110000-0000-0000-0000-000000000022', 'fraud_cluster_detected', '{"cluster_id": "RING-MUM-20260316-001", "cluster_size": 6, "detection_method": "DBSCAN"}'::jsonb),
  ('55550000-0000-0000-0000-000000000022', NULL, 'claim', '11110000-0000-0000-0000-000000000023', 'fraud_cluster_detected', '{"cluster_id": "RING-MUM-20260316-001", "cluster_size": 6, "detection_method": "DBSCAN"}'::jsonb),
  ('55550000-0000-0000-0000-000000000023', NULL, 'claim', '11110000-0000-0000-0000-000000000024', 'fraud_cluster_detected', '{"cluster_id": "RING-MUM-20260316-001", "cluster_size": 6, "detection_method": "DBSCAN"}'::jsonb),
  ('55550000-0000-0000-0000-000000000024', NULL, 'claim', '11110000-0000-0000-0000-000000000025', 'fraud_cluster_detected', '{"cluster_id": "RING-MUM-20260316-001", "cluster_size": 6, "detection_method": "DBSCAN"}'::jsonb),
  ('55550000-0000-0000-0000-000000000025', NULL, 'claim', '11110000-0000-0000-0000-000000000026', 'fraud_cluster_detected', '{"cluster_id": "RING-MUM-20260316-001", "cluster_size": 6, "detection_method": "DBSCAN"}'::jsonb)
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 3. Active Triggers (ended_at IS NULL)
-- No FK to worker_profiles, always safe.
-- ────────────────────────────────────────────────────────────
INSERT INTO public.trigger_events (id, city, zone_id, trigger_family, trigger_code, source_ref_id, observed_value, official_threshold_label, product_threshold_value, severity_band, source_type, started_at, ended_at) VALUES
  ('ffff0000-0000-0000-0000-000000000030', 'Delhi', 'b7a1c2d3-e4f5-5678-abcd-100000000003', 'aqi', 'AQI_SEVERE', 'R1', 355.0, 'CPCB Very Poor AQI (301-400)', '301+', 'claim', 'public_source', now() - interval '2 hours', NULL),
  ('ffff0000-0000-0000-0000-000000000031', 'Mumbai', 'b7a1c2d3-e4f5-5678-abcd-100000000001', 'rain', 'RAIN_HEAVY', 'R3', 74.0, 'IMD heavy rainfall (64.5 mm/24h)', '64.5 mm', 'claim', 'public_source', now() - interval '3 hours', NULL),
  ('ffff0000-0000-0000-0000-000000000032', 'Bangalore', 'b7a1c2d3-e4f5-5678-abcd-100000000005', 'traffic', 'TRAFFIC_SEVERE', NULL, 52.0, NULL, '40%+ delay', 'watch', 'internal_operational', now() - interval '1 hour', NULL)
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 4. Validated Regional Incidents
-- ────────────────────────────────────────────────────────────
INSERT INTO public.validated_regional_incidents (id, zone_id, trigger_family, incident_start, incident_end, validation_source, confirming_worker_count, cluster_spike_detected) VALUES
  ('88880000-0000-0000-0000-000000000001', 'b7a1c2d3-e4f5-5678-abcd-100000000001', 'rain',    '2026-03-10T07:00:00+05:30', '2026-03-10T15:00:00+05:30', 'trusted_workers', 4, false),
  ('88880000-0000-0000-0000-000000000002', 'b7a1c2d3-e4f5-5678-abcd-100000000003', 'aqi',     '2026-03-11T06:30:00+05:30', '2026-03-11T18:30:00+05:30', 'public_api', 0, false),
  ('88880000-0000-0000-0000-000000000003', 'b7a1c2d3-e4f5-5678-abcd-100000000004', 'heat',    '2026-03-12T07:00:00+05:30', '2026-03-12T17:00:00+05:30', 'admin', 0, false),
  ('88880000-0000-0000-0000-000000000004', 'b7a1c2d3-e4f5-5678-abcd-100000000005', 'traffic', '2026-03-13T06:30:00+05:30', '2026-03-13T12:30:00+05:30', 'news_feed', 0, false),
  ('88880000-0000-0000-0000-000000000005', 'b7a1c2d3-e4f5-5678-abcd-100000000001', 'rain',    '2026-03-16T15:01:00+05:30', '2026-03-16T15:04:00+05:30', 'trusted_workers', 1, true)
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 5. Coins Ledger Entries (Rewards Demo)
--    Uses resolved worker slots to support recreated demo IDs.
-- ────────────────────────────────────────────────────────────
INSERT INTO public.coins_ledger (id, profile_id, activity, coins, description, reference_id)
SELECT
  v.id,
  sw.worker_profile_id,
  v.activity,
  v.coins,
  v.description,
  v.reference_id
FROM (VALUES
  (1::integer, '99990000-0000-0000-0000-000000000001'::uuid, 'signup_bonus',  50, 'Welcome bonus for signing up', NULL::text),
  (1::integer, '99990000-0000-0000-0000-000000000002'::uuid, 'claim_approved', 25, 'Reward for approved claim',    NULL::text),
  (1::integer, '99990000-0000-0000-0000-000000000003'::uuid, 'weekly_active',  10, 'Active rider bonus (week 10)',  NULL::text),
  (2::integer, '99990000-0000-0000-0000-000000000004'::uuid, 'signup_bonus',  50, 'Welcome bonus for signing up', NULL::text),
  (3::integer, '99990000-0000-0000-0000-000000000005'::uuid, 'signup_bonus',  50, 'Welcome bonus for signing up', NULL::text),
  (3::integer, '99990000-0000-0000-0000-000000000006'::uuid, 'claim_approved', 25, 'Reward for approved claim',    NULL::text),
  (4::integer, '99990000-0000-0000-0000-000000000007'::uuid, 'signup_bonus',  50, 'Welcome bonus for signing up', NULL::text),
  (5::integer, '99990000-0000-0000-0000-000000000008'::uuid, 'signup_bonus',  50, 'Welcome bonus for signing up', NULL::text),
  (5::integer, '99990000-0000-0000-0000-000000000009'::uuid, 'claim_approved', 25, 'Reward for approved claim',    NULL::text),
  (5::integer, '99990000-0000-0000-0000-000000000010'::uuid, 'fraud_penalty', -50, 'Coins deducted for fraud',     NULL::text),
  (6::integer, '99990000-0000-0000-0000-000000000011'::uuid, 'signup_bonus',  50, 'Welcome bonus for signing up', NULL::text),
  (7::integer, '99990000-0000-0000-0000-000000000012'::uuid, 'signup_bonus',  50, 'Welcome bonus for signing up', NULL::text),
  (7::integer, '99990000-0000-0000-0000-000000000013'::uuid, 'claim_approved', 25, 'Reward for approved claim',    NULL::text),
  (7::integer, '99990000-0000-0000-0000-000000000014'::uuid, 'weekly_active',  10, 'Active rider bonus (week 10)',  NULL::text),
  (7::integer, '99990000-0000-0000-0000-000000000015'::uuid, 'weekly_active',  10, 'Active rider bonus (week 11)',  NULL::text)
) AS v(slot, id, activity, coins, description, reference_id)
JOIN tmp_audit_seed_workers sw ON sw.slot = v.slot
ON CONFLICT (id) DO NOTHING;


-- ────────────────────────────────────────────────────────────
-- 6. Zone Monthly Thresholds (Dynamic Threshold Engine)
-- No FK to worker_profiles, always safe.
-- ────────────────────────────────────────────────────────────
INSERT INTO public.zone_monthly_thresholds (id, zone_id, year_month, metric, observed_mean, observed_stddev, observed_p25, observed_p50, observed_p75, observed_p90, observed_p99, sample_count, watch_threshold, claim_threshold, extreme_threshold, data_source) VALUES
  ('aaa00000-0000-0000-0000-000000000001', 'b7a1c2d3-e4f5-5678-abcd-100000000001', '2026-03', 'rainfall_mm_24h', 35.0, 28.5, 12.0, 28.0, 52.0, 72.0, 130.0, 30, 48.0, 64.5, 115.6, 'dynamic'),
  ('aaa00000-0000-0000-0000-000000000002', 'b7a1c2d3-e4f5-5678-abcd-100000000002', '2026-03', 'rainfall_mm_24h', 32.0, 25.0, 10.0, 25.0, 48.0, 68.0, 125.0, 30, 48.0, 64.5, 115.6, 'dynamic'),
  ('aaa00000-0000-0000-0000-000000000003', 'b7a1c2d3-e4f5-5678-abcd-100000000003', '2026-03', 'aqi',             210.0, 85.0, 120.0, 185.0, 260.0, 340.0, 420.0, 30, 201.0, 301.0, 401.0, 'dynamic'),
  ('aaa00000-0000-0000-0000-000000000004', 'b7a1c2d3-e4f5-5678-abcd-100000000004', '2026-03', 'temp_c',          38.5, 5.2, 32.0, 38.0, 42.0, 45.0, 48.0, 30, 42.0, 45.0, 47.0, 'dynamic'),
  ('aaa00000-0000-0000-0000-000000000005', 'b7a1c2d3-e4f5-5678-abcd-100000000005', '2026-03', 'pm25',            45.0, 20.0, 25.0, 40.0, 55.0, 80.0, 120.0, 30, 60.0, 100.0, 150.0, 'dynamic'),
  ('aaa00000-0000-0000-0000-000000000006', 'b7a1c2d3-e4f5-5678-abcd-100000000006', '2026-03', 'rainfall_mm_24h', 18.0, 15.0, 5.0, 12.0, 28.0, 45.0, 75.0, 30, 48.0, 64.5, 115.6, 'dynamic'),
  ('aaa00000-0000-0000-0000-000000000007', 'b7a1c2d3-e4f5-5678-abcd-100000000007', '2026-03', 'aqi',             155.0, 65.0, 80.0, 130.0, 200.0, 310.0, 420.0, 30, 201.0, 301.0, 401.0, 'dynamic'),
  ('aaa00000-0000-0000-0000-000000000008', 'b7a1c2d3-e4f5-5678-abcd-100000000008', '2026-03', 'temp_c',          36.0, 4.5, 30.0, 35.0, 40.0, 44.0, 47.0, 30, 42.0, 45.0, 47.0, 'dynamic')
ON CONFLICT (id) DO NOTHING;


-- ============================================================
-- Seed complete. Rows inserted only where FK targets exist.
-- ============================================================
