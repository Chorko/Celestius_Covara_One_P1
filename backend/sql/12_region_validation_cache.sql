-- ══════════════════════════════════════════════════════════════════════
-- DEVTrails — Region Validation Cache / Fast-Lane (Gap §4.3)
-- ══════════════════════════════════════════════════════════════════════
-- Purpose:
--   Cache validated regional incidents so that claims in the same
--   zone/trigger/window can skip repeated manual review.
--   Individual fraud checks are NEVER bypassed by fast-lane.
--
--   Liquidity protection: if an extreme spike of same-zone claims
--   appears, the platform switches to cluster-level validation,
--   protecting the liquidity pool before mass payouts are executed.
-- ══════════════════════════════════════════════════════════════════════

create table if not exists public.validated_regional_incidents (
    id uuid primary key default gen_random_uuid(),
    zone_id uuid not null references public.zones(id),
    trigger_family text not null,
    incident_start timestamptz not null,
    incident_end timestamptz,
    -- How the incident was validated:
    -- 'trusted_workers' = 3+ high-trust workers confirm same trigger
    -- 'admin'           = insurer admin confirms via dashboard
    -- 'news_feed'       = external news API corroboration
    -- 'public_api'      = official gov/weather data confirms
    validation_source text not null check (
        validation_source in ('trusted_workers', 'admin', 'news_feed', 'public_api')
    ),
    -- How many workers confirmed this incident
    confirming_worker_count integer not null default 0,
    -- Cluster spike flag: if set, fast-lane auto-release is paused
    cluster_spike_detected boolean not null default false,
    validated_at timestamptz not null default now(),
    unique(zone_id, trigger_family, incident_start)
);

comment on table public.validated_regional_incidents is
  'Cache of validated regional incidents for fast-lane claim processing. '
  'Fast-lane reduces manual review but never bypasses individual fraud checks.';

comment on column public.validated_regional_incidents.cluster_spike_detected is
  'If true, fast-lane auto-release is paused and cluster-level validation '
  'is required to protect the liquidity pool.';

-- Grant access
grant select, insert, update, delete
  on public.validated_regional_incidents to authenticated;
grant select on public.validated_regional_incidents to anon;

-- Reload PostgREST schema cache
notify pgrst, 'reload schema';
