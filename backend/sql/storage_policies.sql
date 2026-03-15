-- DEVTrails Storage Security Policies
-- Secures the 'claim-evidence' bucket to prevent anonymous spam and unauthorized access.

-- 1. Ensure the bucket exists and is configured
INSERT INTO storage.buckets (id, name, public) 
VALUES ('claim-evidence', 'claim-evidence', true)
ON CONFLICT (id) DO NOTHING;

-- 2. Restrict Uploads (INSERT) to authenticated users only
-- Only registered workers (or admins) can upload files to this bucket.
CREATE POLICY "Authenticated users can upload evidence" ON storage.objects
FOR INSERT TO authenticated
WITH CHECK (bucket_id = 'claim-evidence');

-- 3. Restrict Reads (SELECT) to authenticated users only
-- Prevents random internet users from enumerating or viewing evidence.
CREATE POLICY "Authenticated users can view evidence" ON storage.objects
FOR SELECT TO authenticated
USING (bucket_id = 'claim-evidence');

-- Note: The frontend uses unguessable UUID-based file paths 
-- (e.g. {user_id}-{timestamp}.jpg) as an additional layer of security.
