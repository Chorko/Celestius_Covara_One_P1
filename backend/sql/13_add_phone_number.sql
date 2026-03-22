-- ============================================================
-- Migration 13: Add phone_number column to worker_profiles
-- Run this in the Supabase SQL Editor AFTER migrations 01-12
-- ============================================================

-- 1. Add the column (nullable, no disruption to existing rows)
ALTER TABLE worker_profiles
ADD COLUMN IF NOT EXISTS phone_number TEXT;

-- 2. Add a comment for clarity
COMMENT ON COLUMN worker_profiles.phone_number IS 'Indian mobile number (+91XXXXXXXXXX). Used for WhatsApp/SMS notifications and KYC verification.';
