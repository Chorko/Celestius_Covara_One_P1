-- ============================================================
-- 24_trust_score_history.sql
-- Covara One - Worker trust score lifecycle history
--
-- Why:
--   Persist every trust-score mutation with actor/reason metadata so
--   reviewers and workers can audit trust changes across claims.
-- ============================================================

create table if not exists public.trust_score_history (
    id uuid primary key default gen_random_uuid(),
    worker_profile_id uuid not null references public.worker_profiles(profile_id) on delete cascade,
    claim_id uuid references public.manual_claims(id) on delete set null,
    event_type text not null,
    severity text,
    previous_trust_score numeric(4,2) not null,
    delta numeric(5,2) not null,
    new_trust_score numeric(4,2) not null,
    reason text,
    actor_profile_id uuid references public.profiles(id) on delete set null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint trust_score_history_score_bounds_chk check (
      previous_trust_score >= 0.00 and previous_trust_score <= 1.00
      and new_trust_score >= 0.00 and new_trust_score <= 1.00
    )
);

create index if not exists idx_trust_score_history_worker_created
  on public.trust_score_history(worker_profile_id, created_at desc);

create index if not exists idx_trust_score_history_claim
  on public.trust_score_history(claim_id)
  where claim_id is not null;

create index if not exists idx_trust_score_history_event_type
  on public.trust_score_history(event_type, created_at desc);

alter table public.trust_score_history enable row level security;

drop policy if exists "TrustHistory: Workers can read own" on public.trust_score_history;
drop policy if exists "TrustHistory: Admins can read all" on public.trust_score_history;
drop policy if exists "TrustHistory: Service manage" on public.trust_score_history;

create policy "TrustHistory: Workers can read own"
  on public.trust_score_history
  for select to authenticated
  using (worker_profile_id = auth.uid());

create policy "TrustHistory: Admins can read all"
  on public.trust_score_history
  for select to authenticated
  using (public.current_user_role() = 'insurer_admin');

create policy "TrustHistory: Service manage"
  on public.trust_score_history
  for all to service_role
  using (true)
  with check (true);

grant select on public.trust_score_history to authenticated;
grant all on public.trust_score_history to service_role;

notify pgrst, 'reload schema';
