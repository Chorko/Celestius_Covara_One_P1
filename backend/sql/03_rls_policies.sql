-- DEVTrails RLS patch (corrected + rerunnable)

create or replace function public.current_user_role()
returns text
language sql
security definer
set search_path = public
stable
as $$
  select role from public.profiles where id = auth.uid();
$$;

alter table public.profiles enable row level security;
alter table public.worker_profiles enable row level security;
alter table public.insurer_profiles enable row level security;
alter table public.manual_claims enable row level security;
alter table public.claim_evidence enable row level security;
alter table public.claim_reviews enable row level security;
alter table public.payout_recommendations enable row level security;
alter table public.trigger_events enable row level security;
alter table public.zones enable row level security;

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

create policy "Profiles: Users can read own"
on public.profiles
for select
to authenticated
using (id = auth.uid());

create policy "Profiles: Admins can read all"
on public.profiles
for select
to authenticated
using (public.current_user_role() = 'insurer_admin');

create policy "WorkerProfiles: Workers can read own"
on public.worker_profiles
for select
to authenticated
using (profile_id = auth.uid());

create policy "WorkerProfiles: Admins can read all"
on public.worker_profiles
for select
to authenticated
using (public.current_user_role() = 'insurer_admin');

create policy "InsurerProfiles: Admins can read all"
on public.insurer_profiles
for select
to authenticated
using (public.current_user_role() = 'insurer_admin');

create policy "Claims: Workers can read own"
on public.manual_claims
for select
to authenticated
using (worker_profile_id = auth.uid());

create policy "Claims: Workers can insert own"
on public.manual_claims
for insert
to authenticated
with check (worker_profile_id = auth.uid());

create policy "Claims: Admins can read all"
on public.manual_claims
for select
to authenticated
using (public.current_user_role() = 'insurer_admin');

create policy "Claims: Admins can update all"
on public.manual_claims
for update
to authenticated
using (public.current_user_role() = 'insurer_admin');

create policy "Evidence: Workers can read own"
on public.claim_evidence
for select
to authenticated
using (
  claim_id in (
    select id from public.manual_claims where worker_profile_id = auth.uid()
  )
);

create policy "Evidence: Workers can insert own"
on public.claim_evidence
for insert
to authenticated
with check (
  claim_id in (
    select id from public.manual_claims where worker_profile_id = auth.uid()
  )
);

create policy "Evidence: Admins can read all"
on public.claim_evidence
for select
to authenticated
using (public.current_user_role() = 'insurer_admin');

create policy "Reviews: Admins can read all"
on public.claim_reviews
for select
to authenticated
using (public.current_user_role() = 'insurer_admin');

create policy "Reviews: Admins can insert"
on public.claim_reviews
for insert
to authenticated
with check (
  public.current_user_role() = 'insurer_admin'
  and reviewer_profile_id = auth.uid()
);

create policy "Payouts: Workers can read own"
on public.payout_recommendations
for select
to authenticated
using (
  claim_id in (
    select id from public.manual_claims where worker_profile_id = auth.uid()
  )
);

create policy "Payouts: Admins can read all"
on public.payout_recommendations
for select
to authenticated
using (public.current_user_role() = 'insurer_admin');

create policy "Triggers: Read access for all authenticated"
on public.trigger_events
for select
to authenticated
using (true);

create policy "Zones: Read access for all authenticated"
on public.zones
for select
to authenticated
using (true);
