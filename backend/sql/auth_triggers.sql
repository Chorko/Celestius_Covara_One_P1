-- DEVTrails Auth User Trigger
-- Ensures any new user (e.g. from Google OAuth) automatically receives a profile mapping.
-- STRICTLY defaults to 'worker' to prevent privilege escalation.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
BEGIN
  -- 1. Create base profile, hardcoding role to 'worker' for safety
  INSERT INTO public.profiles (id, full_name, email, phone, role)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)),
    NEW.email,
    NEW.raw_user_meta_data->>'phone',
    'worker' -- Secure backend-controlled default
  );
  
  -- 2. Scaffold a default worker_profile to prevent downstream foreign key/UI crashes
  INSERT INTO public.worker_profiles (profile_id, platform_name, city, active_status)
  VALUES (
    NEW.id,
    'Pending Assignment',
    'Pending Local',
    'active'
  );
  
  RETURN NEW;
END;
$$;

-- Drop trigger if it exists to allow idempotent re-runs
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Bind trigger to auth.users insertions
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();
