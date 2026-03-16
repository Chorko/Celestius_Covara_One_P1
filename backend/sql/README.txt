DEVTrails SQL Fix Pack

Run in this order inside Supabase SQL Editor:

1) 01_supabase_platform_schema.sql
2) 02_auth_triggers.sql
3) 03_rls_policies.sql
4) Create the Storage bucket named claim-evidence if it does not already exist
5) 04_storage_policies.sql

Only use 05_rls_rollback.sql if you need to undo the RLS policies.

Notes:
- The original schema failed because PostgreSQL does not support: ADD CONSTRAINT IF NOT EXISTS
- The original auth trigger failed because it referenced a missing column: active_status
- The original auth trigger also omitted the required non-null column: avg_hourly_income_inr
- The corrected RLS and storage files are rerunnable because they drop existing policies before recreating them.
