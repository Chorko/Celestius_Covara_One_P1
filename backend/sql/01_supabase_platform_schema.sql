-- DEVTrails Supabase starter schema (corrected)
-- Uses Supabase Auth users as the identity root.
-- Idempotent enough for clean reruns in Supabase SQL Editor.

create extension if not exists pgcrypto;

create table if not exists public.reference_sources (
    ref_id text primary key,
    source_name text not null,
    source_type text not null,
    what_it_provides text not null,
    use_in_project text not null,
    link text not null
);

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    role text not null check (role in ('worker','insurer_admin')),
    full_name text not null,
    email text unique,
    phone text,
    created_at timestamptz not null default now()
);

create table if not exists public.worker_profiles (
    profile_id uuid primary key references public.profiles(id) on delete cascade,
    platform_name text not null,
    city text not null,
    preferred_zone_id uuid,
    vehicle_type text,
    avg_hourly_income_inr numeric(10,2) not null,
    bank_verified boolean not null default false,
    trust_score numeric(4,2),
    gps_consent boolean not null default false
);

create table if not exists public.insurer_profiles (
    profile_id uuid primary key references public.profiles(id) on delete cascade,
    company_name text not null,
    job_title text
);

create table if not exists public.zones (
    id uuid primary key default gen_random_uuid(),
    city text not null,
    zone_name text not null,
    center_lat numeric(9,6),
    center_lng numeric(9,6),
    polygon_geojson jsonb
);

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'worker_profiles_preferred_zone_fk'
    ) then
        alter table public.worker_profiles
        add constraint worker_profiles_preferred_zone_fk
        foreign key (preferred_zone_id) references public.zones(id);
    end if;
end $$;

create table if not exists public.worker_shifts (
    id uuid primary key default gen_random_uuid(),
    worker_profile_id uuid not null references public.worker_profiles(profile_id) on delete cascade,
    shift_date date not null,
    shift_start timestamptz not null,
    shift_end timestamptz not null,
    zone_id uuid not null references public.zones(id),
    created_at timestamptz not null default now()
);

create table if not exists public.platform_worker_daily_stats (
    id uuid primary key default gen_random_uuid(),
    worker_profile_id uuid not null references public.worker_profiles(profile_id) on delete cascade,
    stat_date date not null,
    active_hours numeric(5,2) not null,
    completed_orders integer not null default 0,
    accepted_orders integer not null default 0,
    cancelled_orders integer not null default 0,
    gross_earnings_inr numeric(10,2) not null default 0,
    platform_login_minutes integer,
    gps_consistency_score numeric(4,2),
    unique(worker_profile_id, stat_date)
);

create table if not exists public.platform_order_events (
    id uuid primary key default gen_random_uuid(),
    worker_profile_id uuid not null references public.worker_profiles(profile_id) on delete cascade,
    platform_order_id text not null,
    assigned_at timestamptz,
    picked_up_at timestamptz,
    delivered_at timestamptz,
    order_status text not null,
    pickup_zone_id uuid references public.zones(id),
    drop_zone_id uuid references public.zones(id),
    distance_km numeric(6,2),
    payout_inr numeric(10,2),
    created_at timestamptz not null default now(),
    unique(platform_order_id)
);

create table if not exists public.trigger_events (
    id uuid primary key default gen_random_uuid(),
    city text not null,
    zone_id uuid references public.zones(id),
    trigger_family text not null,
    trigger_code text not null,
    source_ref_id text references public.reference_sources(ref_id),
    observed_value numeric(10,2),
    official_threshold_label text,
    product_threshold_value text,
    severity_band text not null check (severity_band in ('watch','claim','escalation')),
    source_type text not null check (source_type in ('public_source','internal_operational','mock')),
    started_at timestamptz not null,
    ended_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists public.manual_claims (
    id uuid primary key default gen_random_uuid(),
    worker_profile_id uuid not null references public.worker_profiles(profile_id) on delete cascade,
    trigger_event_id uuid references public.trigger_events(id),
    claim_mode text not null check (claim_mode in ('manual','trigger_auto')),
    claim_reason text not null,
    stated_lat numeric(9,6),
    stated_lng numeric(9,6),
    claimed_at timestamptz not null default now(),
    shift_id uuid references public.worker_shifts(id),
    claim_status text not null check (claim_status in ('submitted','held','approved','rejected','paid'))
);

create table if not exists public.claim_evidence (
    id uuid primary key default gen_random_uuid(),
    claim_id uuid not null references public.manual_claims(id) on delete cascade,
    evidence_type text not null check (evidence_type in ('photo','video','text','geo')),
    storage_path text,
    captured_at timestamptz,
    exif_lat numeric(9,6),
    exif_lng numeric(9,6),
    exif_timestamp timestamptz,
    integrity_score numeric(4,2),
    created_at timestamptz not null default now()
);

create table if not exists public.claim_reviews (
    id uuid primary key default gen_random_uuid(),
    claim_id uuid not null references public.manual_claims(id) on delete cascade,
    reviewer_profile_id uuid not null references public.insurer_profiles(profile_id) on delete cascade,
    fraud_score numeric(4,2),
    geo_confidence_score numeric(4,2),
    evidence_completeness_score numeric(4,2),
    decision text not null check (decision in ('approve','hold','escalate','reject')),
    decision_reason text,
    reviewed_at timestamptz not null default now()
);

create table if not exists public.payout_recommendations (
    id uuid primary key default gen_random_uuid(),
    claim_id uuid not null references public.manual_claims(id) on delete cascade,
    covered_weekly_income_b numeric(10,2) not null,
    claim_probability_p numeric(6,4) not null,
    severity_score_s numeric(6,4) not null,
    exposure_score_e numeric(6,4) not null,
    confidence_score_c numeric(6,4) not null,
    fraud_holdback_fh numeric(6,4) not null,
    outlier_uplift_u numeric(6,4) not null default 1.0,
    payout_cap numeric(10,2) not null,
    expected_payout numeric(10,2) not null,
    gross_premium numeric(10,2) not null,
    recommended_payout numeric(10,2) not null,
    explanation_json jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.audit_events (
    id uuid primary key default gen_random_uuid(),
    actor_profile_id uuid references public.profiles(id) on delete set null,
    entity_type text not null,
    entity_id text,
    action_type text not null,
    event_payload jsonb,
    created_at timestamptz not null default now()
);

insert into public.reference_sources(ref_id, source_name, source_type, what_it_provides, use_in_project, link) values
('R1','CPCB National Air Quality Index','official','AQI category bands and interpretation','AQI trigger thresholds and README reference layer','https://www.cpcb.nic.in/national-air-quality-index/'),
('R2','OGD Real-Time Air Quality Index dataset','official','Machine-readable AQI observations by location','AQI ingestion / trigger feed design','https://www.data.gov.in/catalog/real-time-air-quality-index'),
('R3','IMD Heavy Rainfall Warning Services','official','Heavy / very heavy rainfall categories','Rain trigger anchors and escalation logic','https://mausam.imd.gov.in/imd_latest/contents/pdf/pubbrochures/Heavy%20Rainfall%20Warning%20Services.pdf'),
('R4','IMD Heat Wave Warning Services','official','Heat-wave and severe heat guidance','Heat trigger anchors and escalation logic','https://mausam.imd.gov.in/imd_latest/contents/pdf/pubbrochures/Heat%20Wave%20Warning%20Services.pdf'),
('R5','NDMA Heat Wave guidance','official','National heat-wave preparedness framing','Secondary support for heat thresholds','https://ndma.gov.in/Natural-Hazards/Heat-Wave'),
('R6','NITI Aayog - India''s booming gig and platform economy','policy','Gig/platform worker context','Worker-profile schema context','https://www.niti.gov.in/sites/default/files/2022-06/India%27s-booming-gig-and-platform-economy_English.pdf'),
('R7','Breiman (2001) Random Forests','academic','Baseline model reference','Claim probability baseline justification','https://www.stat.berkeley.edu/~breiman/randomforest2001.pdf'),
('R8','Chen & Guestrin (2016) XGBoost','academic','Benchmark model reference','Future benchmark justification','https://arxiv.org/abs/1603.02754'),
('R9','Loss Data Analytics - Premium Foundations','actuarial','Premium principle and actuarial framing','Pricing/payout README reference block','https://openacttexts.github.io/Loss-Data-Analytics/ChapPremiumFoundations.html'),
('R10','Mikosch - Non-Life Insurance Mathematics','actuarial','Non-life insurance mathematical framing','Pricing/payout README reference block','https://link.springer.com/book/10.1007/978-3-642-20548-3')
on conflict (ref_id) do nothing;

comment on table public.platform_worker_daily_stats is 'Synthetic or future platform-API-like daily worker metrics for pricing and claims context.';
comment on table public.platform_order_events is 'Synthetic or future platform-API-like order events for route, payout, and timeline context.';
comment on table public.trigger_events is 'Normalized public and internal disruption events.';
comment on table public.manual_claims is 'Manual or auto-routed claim intake records.';
comment on table public.payout_recommendations is 'Formula outputs: B, p, S, E, C, FH, U, Cap, expected payout, premium, recommended payout.';

-- ── PostgREST schema access grants ──────────────────────────────────────────
-- Without these, PostgREST returns "Database error querying schema".

GRANT USAGE ON SCHEMA public TO anon, authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE
  ON ALL TABLES IN SCHEMA public TO authenticated;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO anon;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO authenticated;

-- Reload PostgREST schema cache after all DDL.
NOTIFY pgrst, 'reload schema';
