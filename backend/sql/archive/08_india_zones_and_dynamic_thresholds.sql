-- ══════════════════════════════════════════════════════════════════════
-- Covara One — SQL Migration 08: India Zones (65 zones / 15 cities)
--                              + Dynamic Monthly Thresholds Table
-- ══════════════════════════════════════════════════════════════════════
-- Run AFTER 07_rls_fix_and_pincodes.sql.
-- Safe to re-run (ON CONFLICT DO NOTHING / ADD COLUMN IF NOT EXISTS).
--
-- Contents:
--   §1  Schema Extensions on zones table
--   §2  zone_monthly_thresholds table + RLS
--   §3  65 Indian zones (15 cities, 3-8 zones each)
--   §4  RLS & Grants for new table
--   §5  PostgREST reload
-- ══════════════════════════════════════════════════════════════════════


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §1  SCHEMA EXTENSIONS on public.zones                           │
-- └──────────────────────────────────────────────────────────────────┘

-- pincode: 6-digit India Post PIN code for the zone
ALTER TABLE public.zones ADD COLUMN IF NOT EXISTS pincode TEXT;
COMMENT ON COLUMN public.zones.pincode IS
  '6-digit India Post PIN code (e.g. 400053 for Andheri-W, Mumbai).';

-- state: ISO 3166-2 IN state/UT code (MH, DL, KA, TG, TN, WB, GJ, ...)
-- Full list: https://en.wikipedia.org/wiki/States_and_union_territories_of_India
ALTER TABLE public.zones ADD COLUMN IF NOT EXISTS state TEXT;
COMMENT ON COLUMN public.zones.state IS
  'Indian state/UT code: MH=Maharashtra, DL=Delhi, KA=Karnataka, TG=Telangana, '
  'TN=Tamil Nadu, WB=West Bengal, GJ=Gujarat, RJ=Rajasthan, UP=Uttar Pradesh, '
  'MH=Maharashtra, MP=Madhya Pradesh, CH=Chandigarh, KL=Kerala, PB=Punjab, HR=Haryana.';

-- zone_type: affects AQI/rain threshold adjustments
ALTER TABLE public.zones ADD COLUMN IF NOT EXISTS zone_type TEXT
  CHECK (zone_type IN ('urban_core', 'mixed', 'peri_urban'));
COMMENT ON COLUMN public.zones.zone_type IS
  'Zone type for threshold calibration: '
  'urban_core=covered areas, good drainage, shelter options (+25 AQI tolerance). '
  'mixed=standard residential-commercial (baseline). '
  'peri_urban=exposed roads, poor drainage, no shelter (-25 AQI tolerance).';

-- tier: city tier classification for pricing and coverage decisions
ALTER TABLE public.zones ADD COLUMN IF NOT EXISTS tier TEXT
  CHECK (tier IN ('metro', 'tier1', 'tier2', 'tier3'));
COMMENT ON COLUMN public.zones.tier IS
  'City tier: metro=8 major metros. tier1=major commercial hubs. '
  'tier2=secondary cities. tier3=smaller towns.';


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §2  zone_monthly_thresholds TABLE                               │
-- └──────────────────────────────────────────────────────────────────┘
-- Stores dynamically computed trigger thresholds per zone per month.
-- Populated by the dynamic_threshold_engine.py service (runs monthly).
--
-- Threshold derivation formula:
--   watch   = observed_p50 * 1.40   (40% above monthly median)
--   claim   = observed_p75 * 1.30   (30% above 75th percentile)
--   extreme = observed_p90 * 1.20   (20% above 90th percentile)
-- Clamped to CPCB absolute minimums.
--
-- If no row exists for current month → fall back to zone_aqi_thresholds.py static map.

CREATE TABLE IF NOT EXISTS public.zone_monthly_thresholds (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id         uuid        NOT NULL REFERENCES public.zones(id) ON DELETE CASCADE,
    year_month      text        NOT NULL CHECK (year_month ~ '^\d{4}-\d{2}$'), -- 'YYYY-MM'
    metric          text        NOT NULL CHECK (
                                  metric IN ('aqi', 'pm25', 'pm10', 'rainfall_mm_24h', 'temp_c')
                                ),
    -- Observed distribution stats from historical API data (30 days)
    observed_mean   numeric(8,2),
    observed_stddev numeric(8,2),
    observed_p25    numeric(8,2),
    observed_p50    numeric(8,2),   -- monthly median
    observed_p75    numeric(8,2),   -- 75th percentile
    observed_p90    numeric(8,2),   -- 90th percentile
    observed_p99    numeric(8,2),   -- 99th percentile (safety valve)
    sample_count    integer,        -- # of data points used
    -- Derived trigger thresholds (clamped to CPCB minimums)
    watch_threshold   numeric(8,2)  NOT NULL,
    claim_threshold   numeric(8,2)  NOT NULL,
    extreme_threshold numeric(8,2)  NOT NULL,
    -- Metadata
    data_source     text            DEFAULT 'dynamic',  -- 'dynamic', 'static_fallback', 'manual_override'
    computed_at     timestamptz     NOT NULL DEFAULT now(),
    expires_at      timestamptz,    -- set by application on insert
    -- Uniqueness: one threshold set per zone per month per metric
    UNIQUE (zone_id, year_month, metric)
);

COMMENT ON TABLE public.zone_monthly_thresholds IS
  'Monthly dynamic trigger thresholds computed from 30-day rolling AQI/rain data. '
  'Populated by dynamic_threshold_engine.py. Falls back to static map if missing.';

-- Index for fast lookups by zone + current month
CREATE INDEX IF NOT EXISTS idx_zone_thresholds_lookup
  ON public.zone_monthly_thresholds (zone_id, year_month, metric);

-- Index for expiry cleanup jobs
CREATE INDEX IF NOT EXISTS idx_zone_thresholds_expires
  ON public.zone_monthly_thresholds (expires_at);


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §3  COMPREHENSIVE INDIA ZONES (65 zones / 15 cities)            │
-- └──────────────────────────────────────────────────────────────────┘
-- Deterministic UUIDs: b7a1c2d3-e4f5-5678-abcd-2000000000XX
-- Pincodes: verified via India Post / postal.co.in
-- Coordinates: verified via Google Maps / OpenStreetMap
--
-- City coverage:
--   Metro   (5): Mumbai, Delhi, Bangalore, Hyderabad, Chennai
--   Metro   (1): Kolkata
--   Tier 1  (3): Pune, Ahmedabad, Surat
--   Tier 2  (6): Jaipur, Lucknow, Nagpur, Indore, Bhopal, Chandigarh
--   Coastal (2): Kochi, Vizag (Visakhapatnam)
-- ──────────────────────────────────────────────────────────────────

INSERT INTO public.zones
  (id, city, zone_name, center_lat, center_lng, pincode, state, zone_type, tier)
VALUES

-- ── MUMBAI (Maharashtra) — 8 zones ──────────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000001','Mumbai','Andheri-W',       19.136400, 72.829600,'400058','MH','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000002','Mumbai','Bandra-Kurla',    19.059600, 72.865600,'400051','MH','urban_core', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000003','Mumbai','Dadar',           19.018200, 72.843400,'400014','MH','urban_core', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000004','Mumbai','Powai',           19.117300, 72.905800,'400076','MH','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000005','Mumbai','Borivali',        19.228300, 72.858800,'400066','MH','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000006','Mumbai','Lower-Parel',     18.993900, 72.829200,'400013','MH','urban_core', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000007','Mumbai','Thane-West',      19.213700, 72.978500,'400601','MH','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000008','Mumbai','Navi-Mumbai-Vashi',19.076300,73.009900,'400703','MH','mixed',      'metro'),

-- ── DELHI (Delhi UT) — 8 zones ───────────────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000011','Delhi','Connaught-Place',  28.631500, 77.216700,'110001','DL','urban_core', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000012','Delhi','Saket',            28.524400, 77.206600,'110017','DL','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000013','Delhi','Lajpat-Nagar',     28.566900, 77.243200,'110024','DL','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000014','Delhi','Karol-Bagh',       28.651900, 77.190000,'110005','DL','urban_core', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000015','Delhi','Dwarka-Sec10',     28.581700, 77.045600,'110075','DL','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000016','Delhi','Rohini',           28.699700, 77.132600,'110085','DL','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000017','Delhi','Noida-Sec18',      28.570100, 77.321300,'201301','UP','urban_core', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000018','Delhi','Gurugram-Cyber',   28.494100, 77.090100,'122002','HR','urban_core', 'metro'),

-- ── BANGALORE (Karnataka) — 7 zones ─────────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000021','Bangalore','Koramangala',   12.935200, 77.624500,'560034','KA','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000022','Bangalore','Indiranagar',   12.978400, 77.640800,'560038','KA','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000023','Bangalore','HSR-Layout',    12.912000, 77.642300,'560102','KA','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000024','Bangalore','Whitefield',    12.969700, 77.749800,'560066','KA','peri_urban', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000025','Bangalore','Electronic-City',12.844000,77.665500,'560100','KA','peri_urban', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000026','Bangalore','Marathahalli',  12.956400, 77.701200,'560037','KA','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000027','Bangalore','Jayanagar',     12.930800, 77.582700,'560011','KA','mixed',      'metro'),

-- ── HYDERABAD (Telangana) — 6 zones ─────────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000031','Hyderabad','Madhapur',     17.448600, 78.390800,'500081','TG','urban_core', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000032','Hyderabad','Gachibowli',   17.440100, 78.348900,'500032','TG','urban_core', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000033','Hyderabad','Banjara-Hills',17.413900, 78.448000,'500034','TG','urban_core', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000034','Hyderabad','Kukatpally',   17.484400, 78.395200,'500072','TG','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000035','Hyderabad','Secunderabad',  17.443800, 78.498600,'500003','TG','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000036','Hyderabad','LB-Nagar',     17.347200, 78.552900,'500074','TG','peri_urban', 'metro'),

-- ── CHENNAI (Tamil Nadu) — 6 zones ──────────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000041','Chennai','T-Nagar',        13.040100, 80.233600,'600017','TN','urban_core', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000042','Chennai','Anna-Nagar',     13.085600, 80.209800,'600040','TN','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000043','Chennai','Velachery',      12.977800, 80.220000,'600042','TN','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000044','Chennai','OMR-Sholinganallur',12.900600,80.227300,'600119','TN','peri_urban','metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000045','Chennai','Nungambakkam',   13.060700, 80.243200,'600034','TN','urban_core', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000046','Chennai','Perambur',       13.116100, 80.238800,'600011','TN','mixed',      'metro'),

-- ── KOLKATA (West Bengal) — 5 zones ─────────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000051','Kolkata','Park-Street',    22.553200, 88.351800,'700016','WB','urban_core', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000052','Kolkata','Salt-Lake-Sec5', 22.578900, 88.418400,'700064','WB','urban_core', 'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000053','Kolkata','New-Town',       22.593300, 88.468400,'700156','WB','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000054','Kolkata','Howrah',         22.588100, 88.312300,'711101','WB','mixed',      'metro'),
('b7a1c2d3-e4f5-5678-abcd-200000000055','Kolkata','Jadavpur',       22.497300, 88.370600,'700032','WB','peri_urban', 'metro'),

-- ── PUNE (Maharashtra) — 5 zones ────────────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000061','Pune','Koregaon-Park',    18.536700, 73.894400,'411001','MH','mixed',      'tier1'),
('b7a1c2d3-e4f5-5678-abcd-200000000062','Pune','Kothrud',           18.507100, 73.810200,'411038','MH','mixed',      'tier1'),
('b7a1c2d3-e4f5-5678-abcd-200000000063','Pune','Hinjawadi',         18.591600, 73.738500,'411057','MH','peri_urban', 'tier1'),
('b7a1c2d3-e4f5-5678-abcd-200000000064','Pune','Viman-Nagar',       18.567800, 73.914500,'411014','MH','mixed',      'tier1'),
('b7a1c2d3-e4f5-5678-abcd-200000000065','Pune','Hadapsar',          18.502300, 73.942900,'411028','MH','peri_urban', 'tier1'),

-- ── AHMEDABAD (Gujarat) — 4 zones ───────────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000071','Ahmedabad','Navrangpura',  23.030300, 72.560300,'380009','GJ','urban_core', 'tier1'),
('b7a1c2d3-e4f5-5678-abcd-200000000072','Ahmedabad','Satellite',    23.016100, 72.529400,'380015','GJ','mixed',      'tier1'),
('b7a1c2d3-e4f5-5678-abcd-200000000073','Ahmedabad','Bopal',        23.041200, 72.455400,'380058','GJ','peri_urban', 'tier1'),
('b7a1c2d3-e4f5-5678-abcd-200000000074','Ahmedabad','Prahlad-Nagar',23.007800, 72.504300,'380015','GJ','urban_core', 'tier1'),

-- ── SURAT (Gujarat) — 3 zones ───────────────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000081','Surat','Adajan',           21.205100, 72.802800,'395009','GJ','mixed',      'tier1'),
('b7a1c2d3-e4f5-5678-abcd-200000000082','Surat','Vesu',             21.163500, 72.785200,'395007','GJ','mixed',      'tier1'),
('b7a1c2d3-e4f5-5678-abcd-200000000083','Surat','Udhna',            21.164700, 72.840900,'394210','GJ','peri_urban', 'tier1'),

-- ── JAIPUR (Rajasthan) — 3 zones ────────────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000091','Jaipur','Malviya-Nagar',   26.850000, 75.804100,'302017','RJ','mixed',      'tier2'),
('b7a1c2d3-e4f5-5678-abcd-200000000092','Jaipur','Vaishali-Nagar',  26.912400, 75.738200,'302021','RJ','mixed',      'tier2'),
('b7a1c2d3-e4f5-5678-abcd-200000000093','Jaipur','Civil-Lines',     26.904400, 75.812300,'302006','RJ','urban_core', 'tier2'),

-- ── LUCKNOW (Uttar Pradesh) — 3 zones ───────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000101','Lucknow','Hazratganj',     26.848700, 80.944000,'226001','UP','urban_core', 'tier2'),
('b7a1c2d3-e4f5-5678-abcd-200000000102','Lucknow','Gomti-Nagar',    26.839200, 81.002700,'226010','UP','mixed',      'tier2'),
('b7a1c2d3-e4f5-5678-abcd-200000000103','Lucknow','Indira-Nagar',   26.873800, 81.010100,'226016','UP','mixed',      'tier2'),

-- ── NAGPUR (Maharashtra) — 2 zones ──────────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000111','Nagpur','Dharampeth',      21.137400, 79.063500,'440010','MH','urban_core', 'tier2'),
('b7a1c2d3-e4f5-5678-abcd-200000000112','Nagpur','Sitabuldi',       21.152200, 79.079800,'440012','MH','urban_core', 'tier2'),

-- ── INDORE (Madhya Pradesh) — 2 zones ───────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000121','Indore','Palasia',         22.724100, 75.872900,'452001','MP','urban_core', 'tier2'),
('b7a1c2d3-e4f5-5678-abcd-200000000122','Indore','Vijay-Nagar',     22.756700, 75.840300,'452010','MP','mixed',      'tier2'),

-- ── CHANDIGARH (UT) — 2 zones ───────────────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000131','Chandigarh','Sector-17',   30.741800, 76.778600,'160017','CH','urban_core', 'tier2'),
('b7a1c2d3-e4f5-5678-abcd-200000000132','Chandigarh','Sector-35',   30.724800, 76.760100,'160022','CH','mixed',      'tier2'),

-- ── KOCHI (Kerala) — 3 zones ────────────────────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000141','Kochi','Ernakulam-South',   9.966200, 76.285700,'682016','KL','urban_core', 'tier2'),
('b7a1c2d3-e4f5-5678-abcd-200000000142','Kochi','Edapally',          10.012900,76.311100,'682024','KL','mixed',      'tier2'),
('b7a1c2d3-e4f5-5678-abcd-200000000143','Kochi','Kakkanad',          10.004400,76.341900,'682030','KL','peri_urban', 'tier2'),

-- ── VISAKHAPATNAM (Andhra Pradesh) — 2 zones ────────────────────────
('b7a1c2d3-e4f5-5678-abcd-200000000151','Visakhapatnam','Dwaraka-Nagar',17.729900,83.318500,'530016','AP','urban_core','tier2'),
('b7a1c2d3-e4f5-5678-abcd-200000000152','Visakhapatnam','Gajuwaka',    17.681200,83.212900,'530026','AP','peri_urban','tier2')

ON CONFLICT (id) DO UPDATE SET
  pincode    = EXCLUDED.pincode,
  state      = EXCLUDED.state,
  zone_type  = EXCLUDED.zone_type,
  tier       = EXCLUDED.tier,
  center_lat = EXCLUDED.center_lat,
  center_lng = EXCLUDED.center_lng;
-- NOTE: ON CONFLICT DO UPDATE so re-runs also refresh pincode/state/zone_type
-- for any of the 8 originally seeded zones (UUIDs b7a1c2d3-...-1-8 are different).


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §4  Update original 8 seed zones with new columns              │
-- └──────────────────────────────────────────────────────────────────┘
-- The original zones from 06_synthetic_seed.sql have IDs ending in 00000001-8.
-- Set their new columns since those rows already exist.

UPDATE public.zones SET pincode='400058', state='MH', zone_type='mixed',      tier='metro' WHERE id='b7a1c2d3-e4f5-5678-abcd-100000000001';
UPDATE public.zones SET pincode='400051', state='MH', zone_type='urban_core', tier='metro' WHERE id='b7a1c2d3-e4f5-5678-abcd-100000000002';
UPDATE public.zones SET pincode='110001', state='DL', zone_type='urban_core', tier='metro' WHERE id='b7a1c2d3-e4f5-5678-abcd-100000000003';
UPDATE public.zones SET pincode='110017', state='DL', zone_type='mixed',      tier='metro' WHERE id='b7a1c2d3-e4f5-5678-abcd-100000000004';
UPDATE public.zones SET pincode='560034', state='KA', zone_type='mixed',      tier='metro' WHERE id='b7a1c2d3-e4f5-5678-abcd-100000000005';
UPDATE public.zones SET pincode='560038', state='KA', zone_type='mixed',      tier='metro' WHERE id='b7a1c2d3-e4f5-5678-abcd-100000000006';
UPDATE public.zones SET pincode='500081', state='TG', zone_type='urban_core', tier='metro' WHERE id='b7a1c2d3-e4f5-5678-abcd-100000000007';
UPDATE public.zones SET pincode='500032', state='TG', zone_type='urban_core', tier='metro' WHERE id='b7a1c2d3-e4f5-5678-abcd-100000000008';


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §5  RLS + GRANTS for zone_monthly_thresholds                    │
-- └──────────────────────────────────────────────────────────────────┘

ALTER TABLE public.zone_monthly_thresholds ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "ThresholdTable: Read all authenticated" ON public.zone_monthly_thresholds;
DROP POLICY IF EXISTS "ThresholdTable: Service role bypass"    ON public.zone_monthly_thresholds;

-- Any authenticated user can read thresholds (needed for app logic)
CREATE POLICY "ThresholdTable: Read all authenticated"
  ON public.zone_monthly_thresholds FOR SELECT TO authenticated
  USING (true);

-- Only service role writes (threshold engine runs server-side)
CREATE POLICY "ThresholdTable: Service role bypass"
  ON public.zone_monthly_thresholds FOR ALL TO service_role
  USING (true) WITH CHECK (true);

GRANT SELECT ON public.zone_monthly_thresholds TO authenticated;
GRANT ALL    ON public.zone_monthly_thresholds TO service_role;

-- ══════════════════════════════════════════════════════════════════════
-- PostgREST schema reload
-- ══════════════════════════════════════════════════════════════════════
NOTIFY pgrst, 'reload schema';

-- ══════════════════════════════════════════════════════════════════════
-- Migration 08 complete.
-- Next step: run dynamic_threshold_engine.py to populate
-- zone_monthly_thresholds for the current month.
-- ══════════════════════════════════════════════════════════════════════
