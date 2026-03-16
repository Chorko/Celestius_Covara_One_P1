-- DEVTrails Auth User Trigger (corrected)
-- Defaults all new auth users to worker safely.

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
    profile_id,
    platform_name,
    city,
    avg_hourly_income_inr
  )
  values (
    new.id,
    'Pending Assignment',
    'Pending Local',
    0
  )
  on conflict (profile_id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();
