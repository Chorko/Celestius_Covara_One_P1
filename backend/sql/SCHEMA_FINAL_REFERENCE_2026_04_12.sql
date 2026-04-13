-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.audit_events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  actor_profile_id uuid,
  entity_type text NOT NULL,
  entity_id text,
  action_type text NOT NULL,
  event_payload jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT audit_events_pkey PRIMARY KEY (id),
  CONSTRAINT audit_events_actor_profile_id_fkey FOREIGN KEY (actor_profile_id) REFERENCES public.profiles(id)
);
CREATE TABLE public.claim_evidence (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  claim_id uuid NOT NULL,
  evidence_type text NOT NULL CHECK (evidence_type = ANY (ARRAY['photo'::text, 'video'::text, 'text'::text, 'geo'::text])),
  storage_path text,
  captured_at timestamp with time zone,
  exif_lat numeric,
  exif_lng numeric,
  exif_timestamp timestamp with time zone,
  integrity_score numeric,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT claim_evidence_pkey PRIMARY KEY (id),
  CONSTRAINT claim_evidence_claim_id_fkey FOREIGN KEY (claim_id) REFERENCES public.manual_claims(id)
);
CREATE TABLE public.claim_reviews (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  claim_id uuid NOT NULL,
  reviewer_profile_id uuid NOT NULL,
  fraud_score numeric,
  geo_confidence_score numeric,
  evidence_completeness_score numeric,
  decision text NOT NULL CHECK (decision = ANY (ARRAY['approve'::text, 'hold'::text, 'escalate'::text, 'reject'::text, 'flag_post_approval'::text, 'downgrade_trust'::text])),
  decision_reason text,
  reviewed_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT claim_reviews_pkey PRIMARY KEY (id),
  CONSTRAINT claim_reviews_claim_id_fkey FOREIGN KEY (claim_id) REFERENCES public.manual_claims(id),
  CONSTRAINT claim_reviews_reviewer_profile_id_fkey FOREIGN KEY (reviewer_profile_id) REFERENCES public.insurer_profiles(profile_id)
);
CREATE TABLE public.coins_ledger (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL,
  activity text NOT NULL,
  coins integer NOT NULL,
  description text,
  reference_id text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT coins_ledger_pkey PRIMARY KEY (id),
  CONSTRAINT coins_ledger_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.profiles(id)
);
CREATE TABLE public.disruption_events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  event_id text NOT NULL UNIQUE,
  zone_id uuid,
  trigger_family text NOT NULL,
  window_start timestamp with time zone NOT NULL,
  window_end timestamp with time zone,
  validated boolean NOT NULL DEFAULT false,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT disruption_events_pkey PRIMARY KEY (id),
  CONSTRAINT disruption_events_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id)
);
CREATE TABLE public.event_consumer_ledger (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  consumer_name text NOT NULL,
  event_id uuid NOT NULL,
  event_type text NOT NULL,
  event_key text,
  status text NOT NULL DEFAULT 'processing'::text CHECK (status = ANY (ARRAY['processing'::text, 'succeeded'::text, 'failed'::text, 'dead_letter'::text])),
  attempt_count integer NOT NULL DEFAULT 1,
  first_seen_at timestamp with time zone NOT NULL DEFAULT now(),
  last_attempt_at timestamp with time zone NOT NULL DEFAULT now(),
  processed_at timestamp with time zone,
  last_error text,
  result_payload jsonb,
  dead_lettered_at timestamp with time zone,
  CONSTRAINT event_consumer_ledger_pkey PRIMARY KEY (id)
);
CREATE TABLE public.event_outbox (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL UNIQUE,
  event_type text NOT NULL,
  event_key text,
  event_source text NOT NULL,
  event_payload jsonb NOT NULL,
  status text NOT NULL DEFAULT 'pending'::text CHECK (status = ANY (ARRAY['pending'::text, 'failed'::text, 'processed'::text, 'dead_letter'::text])),
  retry_count integer NOT NULL DEFAULT 0,
  last_error text,
  available_at timestamp with time zone NOT NULL DEFAULT now(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  processed_at timestamp with time zone,
  dead_lettered_at timestamp with time zone,
  CONSTRAINT event_outbox_pkey PRIMARY KEY (id)
);
CREATE TABLE public.insurer_profiles (
  profile_id uuid NOT NULL,
  company_name text NOT NULL,
  job_title text,
  CONSTRAINT insurer_profiles_pkey PRIMARY KEY (profile_id),
  CONSTRAINT insurer_profiles_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.profiles(id)
);
CREATE TABLE public.kyc_verification_events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  provider text NOT NULL DEFAULT 'sandbox'::text,
  verification_type text NOT NULL CHECK (verification_type = ANY (ARRAY['otp_send'::text, 'otp_verify'::text, 'aadhaar_initiate'::text, 'aadhaar_verify'::text, 'bank_verify'::text, 'pan_verify'::text])),
  actor_profile_id uuid,
  subject_ref text,
  reference_id text,
  provider_status_code integer,
  success boolean NOT NULL DEFAULT false,
  verified boolean,
  request_meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  risk_flags jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT kyc_verification_events_pkey PRIMARY KEY (id),
  CONSTRAINT kyc_verification_events_actor_profile_id_fkey FOREIGN KEY (actor_profile_id) REFERENCES public.profiles(id)
);
CREATE TABLE public.manual_claims (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  worker_profile_id uuid NOT NULL,
  trigger_event_id uuid,
  claim_mode text NOT NULL CHECK (claim_mode = ANY (ARRAY['manual'::text, 'trigger_auto'::text])),
  claim_reason text NOT NULL,
  stated_lat numeric,
  stated_lng numeric,
  claimed_at timestamp with time zone NOT NULL DEFAULT now(),
  shift_id uuid,
  claim_status text NOT NULL CHECK (claim_status = ANY (ARRAY['submitted'::text, 'auto_approved'::text, 'soft_hold_verification'::text, 'fraud_escalated_review'::text, 'approved'::text, 'rejected'::text, 'paid'::text, 'post_approval_flagged'::text])),
  assigned_reviewer_profile_id uuid,
  assignment_state text DEFAULT 'unassigned'::text CHECK (assignment_state = ANY (ARRAY['unassigned'::text, 'assigned'::text, 'in_review'::text, 'escalated'::text, 'resolved'::text])),
  assigned_at timestamp with time zone,
  review_due_at timestamp with time zone,
  first_reviewed_at timestamp with time zone,
  last_reviewed_at timestamp with time zone,
  escalated_at timestamp with time zone,
  escalation_reason text,
  CONSTRAINT manual_claims_pkey PRIMARY KEY (id),
  CONSTRAINT manual_claims_worker_profile_id_fkey FOREIGN KEY (worker_profile_id) REFERENCES public.worker_profiles(profile_id),
  CONSTRAINT manual_claims_trigger_event_id_fkey FOREIGN KEY (trigger_event_id) REFERENCES public.trigger_events(id),
  CONSTRAINT manual_claims_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.worker_shifts(id),
  CONSTRAINT manual_claims_assigned_reviewer_profile_id_fkey FOREIGN KEY (assigned_reviewer_profile_id) REFERENCES public.insurer_profiles(profile_id)
);
CREATE TABLE public.payout_recommendations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  claim_id uuid NOT NULL,
  covered_weekly_income_b numeric NOT NULL,
  claim_probability_p numeric NOT NULL,
  severity_score_s numeric NOT NULL,
  exposure_score_e numeric NOT NULL,
  confidence_score_c numeric NOT NULL,
  fraud_holdback_fh numeric NOT NULL,
  outlier_uplift_u numeric NOT NULL DEFAULT 1.0,
  payout_cap numeric NOT NULL,
  expected_payout numeric NOT NULL,
  gross_premium numeric NOT NULL,
  recommended_payout numeric NOT NULL,
  explanation_json jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT payout_recommendations_pkey PRIMARY KEY (id),
  CONSTRAINT payout_recommendations_claim_id_fkey FOREIGN KEY (claim_id) REFERENCES public.manual_claims(id)
);
CREATE TABLE public.payout_requests (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  claim_id uuid NOT NULL UNIQUE,
  worker_profile_id uuid NOT NULL,
  amount numeric NOT NULL CHECK (amount > 0::numeric),
  currency text NOT NULL DEFAULT 'INR'::text,
  payout_method text NOT NULL DEFAULT 'upi'::text,
  provider text NOT NULL DEFAULT 'mock'::text,
  provider_payout_id text,
  idempotency_key text NOT NULL UNIQUE,
  status text NOT NULL DEFAULT 'initiated'::text CHECK (status = ANY (ARRAY['initiated'::text, 'submitted'::text, 'processing'::text, 'paid'::text, 'failed'::text, 'manual_review'::text])),
  failure_reason text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT payout_requests_pkey PRIMARY KEY (id),
  CONSTRAINT payout_requests_claim_id_fkey FOREIGN KEY (claim_id) REFERENCES public.manual_claims(id),
  CONSTRAINT payout_requests_worker_profile_id_fkey FOREIGN KEY (worker_profile_id) REFERENCES public.worker_profiles(profile_id)
);
CREATE TABLE public.payout_settlement_events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  payout_request_id uuid NOT NULL,
  provider text NOT NULL,
  provider_event_id text NOT NULL,
  event_type text NOT NULL,
  event_time timestamp with time zone,
  payload jsonb NOT NULL,
  signature_valid boolean,
  processed_at timestamp with time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT payout_settlement_events_pkey PRIMARY KEY (id),
  CONSTRAINT payout_settlement_events_payout_request_id_fkey FOREIGN KEY (payout_request_id) REFERENCES public.payout_requests(id)
);
CREATE TABLE public.payout_status_transitions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  payout_request_id uuid NOT NULL,
  from_status text,
  to_status text NOT NULL,
  reason text,
  actor_profile_id uuid,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT payout_status_transitions_pkey PRIMARY KEY (id),
  CONSTRAINT payout_status_transitions_payout_request_id_fkey FOREIGN KEY (payout_request_id) REFERENCES public.payout_requests(id),
  CONSTRAINT payout_status_transitions_actor_profile_id_fkey FOREIGN KEY (actor_profile_id) REFERENCES public.profiles(id)
);
CREATE TABLE public.platform_order_events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  worker_profile_id uuid NOT NULL,
  platform_order_id text NOT NULL UNIQUE,
  assigned_at timestamp with time zone,
  picked_up_at timestamp with time zone,
  delivered_at timestamp with time zone,
  order_status text NOT NULL,
  pickup_zone_id uuid,
  drop_zone_id uuid,
  distance_km numeric,
  payout_inr numeric,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT platform_order_events_pkey PRIMARY KEY (id),
  CONSTRAINT platform_order_events_worker_profile_id_fkey FOREIGN KEY (worker_profile_id) REFERENCES public.worker_profiles(profile_id),
  CONSTRAINT platform_order_events_pickup_zone_id_fkey FOREIGN KEY (pickup_zone_id) REFERENCES public.zones(id),
  CONSTRAINT platform_order_events_drop_zone_id_fkey FOREIGN KEY (drop_zone_id) REFERENCES public.zones(id)
);
CREATE TABLE public.platform_worker_daily_stats (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  worker_profile_id uuid NOT NULL,
  stat_date date NOT NULL,
  active_hours numeric NOT NULL,
  completed_orders integer NOT NULL DEFAULT 0,
  accepted_orders integer NOT NULL DEFAULT 0,
  cancelled_orders integer NOT NULL DEFAULT 0,
  gross_earnings_inr numeric NOT NULL DEFAULT 0,
  platform_login_minutes integer,
  gps_consistency_score numeric,
  CONSTRAINT platform_worker_daily_stats_pkey PRIMARY KEY (id),
  CONSTRAINT platform_worker_daily_stats_worker_profile_id_fkey FOREIGN KEY (worker_profile_id) REFERENCES public.worker_profiles(profile_id)
);
CREATE TABLE public.policies (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  policy_id text NOT NULL UNIQUE,
  worker_profile_id uuid NOT NULL,
  zone_id uuid,
  plan_type text NOT NULL CHECK (plan_type = ANY (ARRAY['essential'::text, 'plus'::text])),
  coverage_amount numeric NOT NULL,
  premium_amount numeric NOT NULL,
  status text NOT NULL CHECK (status = ANY (ARRAY['active'::text, 'expired'::text, 'cancelled'::text])),
  activated_at timestamp with time zone NOT NULL DEFAULT now(),
  valid_until timestamp with time zone NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT policies_pkey PRIMARY KEY (id),
  CONSTRAINT policies_worker_profile_id_fkey FOREIGN KEY (worker_profile_id) REFERENCES public.worker_profiles(profile_id),
  CONSTRAINT policies_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id)
);
CREATE TABLE public.profiles (
  id uuid NOT NULL,
  role text NOT NULL CHECK (role = ANY (ARRAY['worker'::text, 'insurer_admin'::text])),
  full_name text NOT NULL,
  email text UNIQUE,
  phone text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT profiles_pkey PRIMARY KEY (id),
  CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);
CREATE TABLE public.reference_sources (
  ref_id text NOT NULL,
  source_name text NOT NULL,
  source_type text NOT NULL,
  what_it_provides text NOT NULL,
  use_in_project text NOT NULL,
  link text NOT NULL,
  CONSTRAINT reference_sources_pkey PRIMARY KEY (ref_id)
);
CREATE TABLE public.trigger_events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  city text NOT NULL,
  zone_id uuid,
  trigger_family text NOT NULL,
  trigger_code text NOT NULL,
  source_ref_id text,
  observed_value numeric,
  official_threshold_label text,
  product_threshold_value text,
  severity_band text NOT NULL CHECK (severity_band = ANY (ARRAY['watch'::text, 'claim'::text, 'escalation'::text])),
  source_type text NOT NULL CHECK (source_type = ANY (ARRAY['public_source'::text, 'internal_operational'::text, 'mock'::text])),
  started_at timestamp with time zone NOT NULL,
  ended_at timestamp with time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT trigger_events_pkey PRIMARY KEY (id),
  CONSTRAINT trigger_events_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id),
  CONSTRAINT trigger_events_source_ref_id_fkey FOREIGN KEY (source_ref_id) REFERENCES public.reference_sources(ref_id)
);
CREATE TABLE public.validated_regional_incidents (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  zone_id uuid NOT NULL,
  trigger_family text NOT NULL,
  incident_start timestamp with time zone NOT NULL,
  incident_end timestamp with time zone,
  validation_source text NOT NULL CHECK (validation_source = ANY (ARRAY['trusted_workers'::text, 'admin'::text, 'news_feed'::text, 'public_api'::text])),
  confirming_worker_count integer NOT NULL DEFAULT 0,
  cluster_spike_detected boolean NOT NULL DEFAULT false,
  validated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT validated_regional_incidents_pkey PRIMARY KEY (id),
  CONSTRAINT validated_regional_incidents_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id)
);
CREATE TABLE public.worker_profiles (
  profile_id uuid NOT NULL,
  platform_name text NOT NULL,
  city text NOT NULL,
  preferred_zone_id uuid,
  vehicle_type text,
  avg_hourly_income_inr numeric NOT NULL,
  bank_verified boolean NOT NULL DEFAULT false,
  trust_score numeric,
  gps_consent boolean NOT NULL DEFAULT false,
  phone_number text,
  CONSTRAINT worker_profiles_pkey PRIMARY KEY (profile_id),
  CONSTRAINT worker_profiles_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.profiles(id),
  CONSTRAINT worker_profiles_preferred_zone_fk FOREIGN KEY (preferred_zone_id) REFERENCES public.zones(id)
);
CREATE TABLE public.worker_shifts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  worker_profile_id uuid NOT NULL,
  shift_date date NOT NULL,
  shift_start timestamp with time zone NOT NULL,
  shift_end timestamp with time zone NOT NULL,
  zone_id uuid NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT worker_shifts_pkey PRIMARY KEY (id),
  CONSTRAINT worker_shifts_worker_profile_id_fkey FOREIGN KEY (worker_profile_id) REFERENCES public.worker_profiles(profile_id),
  CONSTRAINT worker_shifts_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id)
);
CREATE TABLE public.zone_monthly_thresholds (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  zone_id uuid NOT NULL,
  year_month text NOT NULL CHECK (year_month ~ '^\d{4}-\d{2}$'::text),
  metric text NOT NULL CHECK (metric = ANY (ARRAY['aqi'::text, 'pm25'::text, 'pm10'::text, 'rainfall_mm_24h'::text, 'temp_c'::text])),
  observed_mean numeric,
  observed_stddev numeric,
  observed_p25 numeric,
  observed_p50 numeric,
  observed_p75 numeric,
  observed_p90 numeric,
  observed_p99 numeric,
  sample_count integer,
  watch_threshold numeric NOT NULL,
  claim_threshold numeric NOT NULL,
  extreme_threshold numeric NOT NULL,
  data_source text DEFAULT 'dynamic'::text,
  computed_at timestamp with time zone NOT NULL DEFAULT now(),
  expires_at timestamp with time zone,
  CONSTRAINT zone_monthly_thresholds_pkey PRIMARY KEY (id),
  CONSTRAINT zone_monthly_thresholds_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id)
);
CREATE TABLE public.zones (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  city text NOT NULL,
  zone_name text NOT NULL,
  center_lat numeric,
  center_lng numeric,
  polygon_geojson jsonb,
  pincode text,
  state text,
  zone_type text CHECK (zone_type = ANY (ARRAY['urban_core'::text, 'mixed'::text, 'peri_urban'::text])),
  tier text CHECK (tier = ANY (ARRAY['metro'::text, 'tier1'::text, 'tier2'::text, 'tier3'::text])),
  CONSTRAINT zones_pkey PRIMARY KEY (id)
);
