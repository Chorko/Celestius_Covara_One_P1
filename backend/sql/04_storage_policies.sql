-- DEVTrails Storage Security Policies (corrected + rerunnable)
-- Note: For fastest demo unblocking, this keeps the bucket public.
-- You can harden later by making the bucket private and switching to signed/server retrieval.

insert into storage.buckets (id, name, public)
values ('claim-evidence', 'claim-evidence', true)
on conflict (id) do nothing;

drop policy if exists "Authenticated users can upload evidence" on storage.objects;
drop policy if exists "Authenticated users can view evidence" on storage.objects;

create policy "Authenticated users can upload evidence"
on storage.objects
for insert
to authenticated
with check (bucket_id = 'claim-evidence');

create policy "Authenticated users can view evidence"
on storage.objects
for select
to authenticated
using (bucket_id = 'claim-evidence');
