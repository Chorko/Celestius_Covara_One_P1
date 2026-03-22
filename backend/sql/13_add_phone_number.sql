-- ============================================================
-- Migration 13: Add phone_number column to worker_profiles
-- Run this in the Supabase SQL Editor AFTER migrations 01-12
-- ============================================================

-- 1. Add the column (nullable, no disruption to existing rows)
ALTER TABLE worker_profiles
ADD COLUMN IF NOT EXISTS phone_number TEXT;

-- 2. Seed random 10-digit Indian mobile numbers for existing workers
-- Indian mobile numbers start with 6/7/8/9
UPDATE worker_profiles
SET phone_number = '+91' || (
  (ARRAY['6','7','8','9'])[floor(random()*4+1)::int]
  || lpad(floor(random()*1000000000)::text, 9, '0')
)
WHERE phone_number IS NULL;

-- 3. Add a comment for clarity
COMMENT ON COLUMN worker_profiles.phone_number IS 'Indian mobile number (+91XXXXXXXXXX). Used for WhatsApp/SMS notifications and KYC verification.';
