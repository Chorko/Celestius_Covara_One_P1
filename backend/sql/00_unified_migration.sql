-- ══════════════════════════════════════════════════════════════════════
-- DEVTrails — Unified Migration (v00)
-- ══════════════════════════════════════════════════════════════════════
-- Copy-paste ready. Fully idempotent — safe on fresh OR existing DBs.
-- Consolidates migrations 01–13 into a single script.
--
-- Contents:
--   §1  Core Schema (tables, constraints)
--   §2  Auth Trigger (handle_new_user)
--   §3  Helper Functions + RLS Policies
--   §4  Storage Policies
--   §5  Extensions (disruption_events, validated_regional_incidents,
--       claim state expansion, phone_number column)
--   §6  Grants + PostgREST cache reload
--   §7  Synthetic Seed Data
-- ══════════════════════════════════════════════════════════════════════


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §1  CORE SCHEMA                                                 │
-- └──────────────────────────────────────────────────────────────────┘

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
    claim_status text not null check (claim_status in (
      'submitted','held','approved','rejected','paid',
      'auto_approved','soft_hold_verification','fraud_escalated_review','post_approval_flagged'
    ))
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
    decision text not null check (decision in ('approve','hold','escalate','reject','flag_post_approval','downgrade_trust')),
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

-- Reference source data
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


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §2  AUTH TRIGGER                                                │
-- └──────────────────────────────────────────────────────────────────┘

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, full_name, email, phone, role)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1)),
    new.email,
    new.raw_user_meta_data->>'phone',
    'worker'
  )
  on conflict (id) do nothing;

  insert into public.worker_profiles (
    profile_id, platform_name, city, avg_hourly_income_inr
  )
  values (new.id, 'Pending Assignment', 'Pending Local', 0)
  on conflict (profile_id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §3  HELPER FUNCTIONS + RLS POLICIES                             │
-- └──────────────────────────────────────────────────────────────────┘

create or replace function public.current_user_role()
returns text
language sql
security definer
set search_path = public
stable
as $$
  select role from public.profiles where id = auth.uid();
$$;

-- Enable RLS on all tables
alter table public.profiles enable row level security;
alter table public.worker_profiles enable row level security;
alter table public.insurer_profiles enable row level security;
alter table public.manual_claims enable row level security;
alter table public.claim_evidence enable row level security;
alter table public.claim_reviews enable row level security;
alter table public.payout_recommendations enable row level security;
alter table public.trigger_events enable row level security;
alter table public.zones enable row level security;

-- Drop all policies first (idempotent)
drop policy if exists "Profiles: Users can read own" on public.profiles;
drop policy if exists "Profiles: Admins can read all" on public.profiles;
drop policy if exists "WorkerProfiles: Workers can read own" on public.worker_profiles;
drop policy if exists "WorkerProfiles: Admins can read all" on public.worker_profiles;
drop policy if exists "InsurerProfiles: Admins can read all" on public.insurer_profiles;
drop policy if exists "Claims: Workers can read own" on public.manual_claims;
drop policy if exists "Claims: Workers can insert own" on public.manual_claims;
drop policy if exists "Claims: Admins can read all" on public.manual_claims;
drop policy if exists "Claims: Admins can update all" on public.manual_claims;
drop policy if exists "Evidence: Workers can read own" on public.claim_evidence;
drop policy if exists "Evidence: Workers can insert own" on public.claim_evidence;
drop policy if exists "Evidence: Admins can read all" on public.claim_evidence;
drop policy if exists "Reviews: Admins can read all" on public.claim_reviews;
drop policy if exists "Reviews: Admins can insert" on public.claim_reviews;
drop policy if exists "Payouts: Workers can read own" on public.payout_recommendations;
drop policy if exists "Payouts: Admins can read all" on public.payout_recommendations;
drop policy if exists "Triggers: Read access for all authenticated" on public.trigger_events;
drop policy if exists "Zones: Read access for all authenticated" on public.zones;

-- Create policies
create policy "Profiles: Users can read own" on public.profiles for select to authenticated using (id = auth.uid());
create policy "Profiles: Admins can read all" on public.profiles for select to authenticated using (public.current_user_role() = 'insurer_admin');

create policy "WorkerProfiles: Workers can read own" on public.worker_profiles for select to authenticated using (profile_id = auth.uid());
create policy "WorkerProfiles: Admins can read all" on public.worker_profiles for select to authenticated using (public.current_user_role() = 'insurer_admin');

create policy "InsurerProfiles: Admins can read all" on public.insurer_profiles for select to authenticated using (public.current_user_role() = 'insurer_admin');

create policy "Claims: Workers can read own" on public.manual_claims for select to authenticated using (worker_profile_id = auth.uid());
create policy "Claims: Workers can insert own" on public.manual_claims for insert to authenticated with check (worker_profile_id = auth.uid());
create policy "Claims: Admins can read all" on public.manual_claims for select to authenticated using (public.current_user_role() = 'insurer_admin');
create policy "Claims: Admins can update all" on public.manual_claims for update to authenticated using (public.current_user_role() = 'insurer_admin');

create policy "Evidence: Workers can read own" on public.claim_evidence for select to authenticated using (claim_id in (select id from public.manual_claims where worker_profile_id = auth.uid()));
create policy "Evidence: Workers can insert own" on public.claim_evidence for insert to authenticated with check (claim_id in (select id from public.manual_claims where worker_profile_id = auth.uid()));
create policy "Evidence: Admins can read all" on public.claim_evidence for select to authenticated using (public.current_user_role() = 'insurer_admin');

create policy "Reviews: Admins can read all" on public.claim_reviews for select to authenticated using (public.current_user_role() = 'insurer_admin');
create policy "Reviews: Admins can insert" on public.claim_reviews for insert to authenticated with check (public.current_user_role() = 'insurer_admin' and reviewer_profile_id = auth.uid());

create policy "Payouts: Workers can read own" on public.payout_recommendations for select to authenticated using (claim_id in (select id from public.manual_claims where worker_profile_id = auth.uid()));
create policy "Payouts: Admins can read all" on public.payout_recommendations for select to authenticated using (public.current_user_role() = 'insurer_admin');

create policy "Triggers: Read access for all authenticated" on public.trigger_events for select to authenticated using (true);
create policy "Zones: Read access for all authenticated" on public.zones for select to authenticated using (true);


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §4  STORAGE POLICIES                                            │
-- └──────────────────────────────────────────────────────────────────┘

insert into storage.buckets (id, name, public)
values ('claim-evidence', 'claim-evidence', true)
on conflict (id) do nothing;

drop policy if exists "Authenticated users can upload evidence" on storage.objects;
drop policy if exists "Authenticated users can view evidence" on storage.objects;

create policy "Authenticated users can upload evidence"
on storage.objects for insert to authenticated
with check (bucket_id = 'claim-evidence');

create policy "Authenticated users can view evidence"
on storage.objects for select to authenticated
using (bucket_id = 'claim-evidence');


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §5  EXTENSIONS                                                  │
-- └──────────────────────────────────────────────────────────────────┘

-- §5.1 Disruption Events
create table if not exists public.disruption_events (
    id            uuid primary key default gen_random_uuid(),
    event_id      text unique not null,
    zone_id       uuid references public.zones(id),
    trigger_family text not null,
    window_start  timestamptz not null,
    window_end    timestamptz,
    validated     boolean not null default false,
    created_at    timestamptz not null default now()
);

comment on table public.disruption_events is
  'Unique disruption event identity for idempotent payout execution. '
  'event_id = hash(zone_id + trigger_family + window_start).';

alter table public.disruption_events enable row level security;

drop policy if exists "disruption_events_select_authenticated" on public.disruption_events;
drop policy if exists "disruption_events_manage_service" on public.disruption_events;
-- Also drop old permissive policy name from 10_payout_safety.sql
drop policy if exists "disruption_events_read_authenticated" on public.disruption_events;

create policy "disruption_events_select_authenticated"
  on public.disruption_events for select to authenticated
  using (
    current_user_role() = 'insurer_admin'
    or zone_id = (
      select preferred_zone_id from public.worker_profiles where profile_id = auth.uid()
    )
  );

create policy "disruption_events_manage_service"
  on public.disruption_events for all to service_role
  using (true) with check (true);

grant select on public.disruption_events to authenticated;
grant all   on public.disruption_events to service_role;

-- §5.2 Worker-Event Uniqueness
create unique index if not exists idx_unique_worker_event
    on public.manual_claims(worker_profile_id, trigger_event_id)
    where claim_status in ('approved', 'paid', 'auto_approved');

-- §5.3 Claim State Machine Expansion (idempotent)
alter table public.manual_claims
  drop constraint if exists manual_claims_claim_status_check;

-- Migrate legacy data (no-ops on fresh DBs)
update public.manual_claims set claim_status = 'soft_hold_verification' where claim_status = 'held';
update public.manual_claims set claim_status = 'auto_approved' where claim_status = 'approved' and claim_mode = 'trigger_auto';

alter table public.manual_claims
  add constraint manual_claims_claim_status_check
  check (claim_status in (
    'submitted', 'auto_approved', 'soft_hold_verification',
    'fraud_escalated_review', 'approved', 'rejected', 'paid',
    'post_approval_flagged'
  ));

comment on constraint manual_claims_claim_status_check on public.manual_claims is
  'Expanded 8-state claim lifecycle with soft-hold and post-approval flagging.';

-- §5.4 Review Decision Expansion
alter table public.claim_reviews
  drop constraint if exists claim_reviews_decision_check;

alter table public.claim_reviews
  add constraint claim_reviews_decision_check
  check (decision in (
    'approve', 'hold', 'escalate', 'reject',
    'flag_post_approval', 'downgrade_trust'
  ));

-- §5.5 Validated Regional Incidents
create table if not exists public.validated_regional_incidents (
    id                       uuid primary key default gen_random_uuid(),
    zone_id                  uuid not null references public.zones(id),
    trigger_family           text not null,
    incident_start           timestamptz not null,
    incident_end             timestamptz,
    validation_source        text not null check (
      validation_source in ('trusted_workers', 'admin', 'news_feed', 'public_api')
    ),
    confirming_worker_count  integer not null default 0,
    cluster_spike_detected   boolean not null default false,
    validated_at             timestamptz not null default now(),
    unique(zone_id, trigger_family, incident_start)
);

comment on table public.validated_regional_incidents is
  'Cache of validated regional incidents for fast-lane claim processing.';

alter table public.validated_regional_incidents enable row level security;

drop policy if exists "validated_incidents_select_authenticated" on public.validated_regional_incidents;
drop policy if exists "validated_incidents_manage_service" on public.validated_regional_incidents;
-- Also drop old permissive policy name from 12_region_validation_cache.sql
drop policy if exists "validated_incidents_read_authenticated" on public.validated_regional_incidents;

create policy "validated_incidents_select_authenticated"
  on public.validated_regional_incidents for select to authenticated
  using (
    current_user_role() = 'insurer_admin'
    or zone_id = (
      select preferred_zone_id from public.worker_profiles where profile_id = auth.uid()
    )
  );

create policy "validated_incidents_manage_service"
  on public.validated_regional_incidents for all to service_role
  using (true) with check (true);

grant select on public.validated_regional_incidents to authenticated;
grant all   on public.validated_regional_incidents to service_role;

-- §5.6 Worker Phone Numbers
alter table public.worker_profiles
  add column if not exists phone_number text;


-- ┌──────────────────────────────────────────────────────────────────┐
-- │  §6  GRANTS + PostgREST CACHE RELOAD                            │
-- └──────────────────────────────────────────────────────────────────┘

GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO anon;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO authenticated;

NOTIFY pgrst, 'reload schema';


-- ══════════════════════════════════════════════════════════════════════
-- §7  SYNTHETIC SEED DATA
-- All INSERTs use ON CONFLICT DO NOTHING for idempotent re-runs.
-- ══════════════════════════════════════════════════════════════════════

-- See 06_synthetic_seed.sql for the full seed data.
-- The seed is intentionally NOT duplicated here because the user has
-- already executed it. Running the seed data a second time is harmless
-- (ON CONFLICT DO NOTHING) but unnecessary.
--
-- If you need a fresh environment, run this file first, then run
-- 06_synthetic_seed.sql to populate demo data.

-- ══════════════════════════════════════════════════════════════════════
-- Migration Complete.
-- ══════════════════════════════════════════════════════════════════════
