# Covara SQL Runbook (Organized)

This folder is split into active scripts and archive scripts.

## Active Scripts (use these)

1. `00_unified_migration.sql`
  Base bootstrap schema, auth trigger, RLS baseline, storage policies,
  and grants.

1. `01_enterprise_alignment_patch_2026_04_12.sql`
  Aligns the base schema to the current production/final schema shape.
  Includes compatibility updates for claim workflow, payout tables, KYC
  audit table, rewards/index compatibility, event reliability glue, and
  policy/RLS hardening.

1. `02_rpc_postrun_hotfix_2026_04_12.sql` (optional)
  Run only if
  `public.persist_claim_with_outbox(jsonb,jsonb,text,text,text,jsonb)`
  is missing or mismatched in a post-run environment.

1. `06_synthetic_seed.sql`
  Demo baseline seed set.

1. `16_synthetic_seed_200.sql`
  Additional large synthetic data pack for trigger/claim/payout stress.

1. `19a_login_ready_workers_auth_cleanup.sql` (recovery-only)
  One-time cleanup for malformed synthetic auth rows created by legacy
  direct SQL inserts into Auth tables.

1. `19_login_ready_workers_200.sql`
  Public-data seed only
  (profiles/worker_profiles/policies/stats/claims/payouts/evidence).
  Requires synthetic auth users to already exist.
  Includes a credential output table.
  Worker login format:
  Email range: `worker001@synthetic.covara.dev` to
  `worker200@synthetic.covara.dev`
  Password: `Covara#2026!`

1. Companion script: `scripts/provision_login_ready_workers_200.py`
  Provisions 200 login-capable synthetic auth users via Supabase Admin API.
  Run with: `python scripts/provision_login_ready_workers_200.py --apply`

1. `08_fix_demo_auth_users.sql` (repair helper)
  Use only if demo logins return Supabase Auth 500 errors.
  Run cleanup SQL once, then run
  `python scripts/seed_test_users.py` and
  `python scripts/force_sync_users.py`.

## Recommended Run Order (fresh environment)

```text
# Required
backend/sql/00_unified_migration.sql
backend/sql/01_enterprise_alignment_patch_2026_04_12.sql
backend/sql/06_synthetic_seed.sql

# Optional scale seed (claims/payout stress only)
backend/sql/16_synthetic_seed_200.sql

# Required for 200 login-ready synthetic workers
python scripts/provision_login_ready_workers_200.py --apply
backend/sql/19_login_ready_workers_200.sql

# Optional RPC repair (only if needed)
backend/sql/02_rpc_postrun_hotfix_2026_04_12.sql
```

## Recovery Flow (if synthetic auth logins return 500)

```text
backend/sql/19a_login_ready_workers_auth_cleanup.sql
python scripts/provision_login_ready_workers_200.py --apply
backend/sql/19_login_ready_workers_200.sql
```

## Login-Ready Workforce Output

After auth provisioning plus `backend/sql/19_login_ready_workers_200.sql`,
the SQL script prints:

1. Worker count summary.
1. Claim-status distribution summary.
1. Payout/fraud calibration summary.
1. Credential table (`login_email`, `password`, `full_name`, city/platform)
  for all 200 workers.

## Archive Scripts (historical)

`backend/sql/archive/` contains legacy incremental migrations (`07` to `15`).
They remain for audit/history and rollback investigation, but are no longer
the primary run path.

## Final Schema Reference

`backend/sql/SCHEMA_FINAL_REFERENCE_2026_04_12.sql` stores the final live
schema snapshot used as structural reference during this cleanup.
