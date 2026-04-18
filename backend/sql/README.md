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
  Includes governance-aware version-id persistence when RuleOps/ModelOps
  columns/functions are present, while remaining compatible with older
  schemas that do not yet include migration 22 columns.

1. `06_synthetic_seed.sql`
  Demo baseline seed set (public tables).
  Requires deterministic auth users to already exist.

1. Companion script: `scripts/create_seed06_auth_users.py`
  Provisions deterministic auth users required by `06_synthetic_seed.sql`
  via Supabase Admin API (safe, no direct SQL writes to auth tables).
  Run with: `python scripts/create_seed06_auth_users.py --apply`

1. `16_synthetic_seed_200.sql`
  Additional large synthetic data pack for trigger/claim/payout stress.

1. `backend/sql/helpers/19a_login_ready_workers_auth_cleanup.sql` (recovery-only)
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

1. `20_security_schema_sync.sql`
  Idempotent security/schema sync patch for already-provisioned environments
  (R11 reference source backfill, storage bucket privacy hardening,
  positive payout amount constraint, worker trust default,
  `manual_claims.updated_at` trigger/index).

1. `21_3month_history_seed.sql` (optional but recommended for demos)
  Extends synthetic worker history to 90 days in
  `platform_worker_daily_stats` and adds historical `coins_ledger`
  activity so analytics/rewards dashboards have realistic trailing-window
  depth.

1. `22_rule_model_version_governance.sql`
  Adds `rule_versions` / `model_versions` registries, rollout metadata
  (full/canary/cohort), and persists version IDs on claim + review
  decision paths for replayable governance.

1. `23_current_user_role_rls_hardening.sql`
  Restores `public.current_user_role()` as `SECURITY DEFINER` with
  stable `search_path`, preventing RLS policy recursion in environments
  where the helper function drifted.

1. `24_trust_score_history.sql`
  Adds durable trust score lifecycle history (`trust_score_history`) with
  worker/admin read policies and service-role write access for auditable
  trust changes tied to claim decisions.

1. `backend/sql/helpers/08_fix_demo_auth_users.sql` (repair helper)
  Recovery helper for hard auth corruption.
  First try script-first recovery:
  `python scripts/recover_demo_auth_without_sql.py --mode full --apply`.
  If Auth still returns 500, run this SQL helper and rerun the recovery script.

1. `backend/sql/helpers/24_backfill_worker_profile_realism.sql` (data-quality helper)
  Backfills missing worker `phone`, `preferred_zone_id`, `vehicle_type`,
  and `trust_score`, normalizes placeholder `Pending Local` /
  `Pending Assignment` fields, and ensures active policies have `zone_id`
  so worker/admin dashboards avoid null-looking seeded records.

## Recommended Run Order (fresh environment)

```text
# Required
backend/sql/00_unified_migration.sql
python scripts/create_seed06_auth_users.py --apply
backend/sql/01_enterprise_alignment_patch_2026_04_12.sql
backend/sql/06_synthetic_seed.sql

# Optional scale seed (claims/payout stress only)
backend/sql/16_synthetic_seed_200.sql

# Required for 200 login-ready synthetic workers
python scripts/provision_login_ready_workers_200.py --apply
backend/sql/19_login_ready_workers_200.sql

# Optional but recommended dashboard data-quality normalization
backend/sql/helpers/24_backfill_worker_profile_realism.sql

# Recommended schema/data hardening
backend/sql/20_security_schema_sync.sql

# Recommended analytics/rewards depth (90-day trailing history)
backend/sql/21_3month_history_seed.sql

# Recommended governance hardening (RuleOps / ModelOps)
backend/sql/22_rule_model_version_governance.sql

# Recommended auth-policy recursion hardening
backend/sql/23_current_user_role_rls_hardening.sql

# Recommended trust lifecycle auditability
backend/sql/24_trust_score_history.sql

# Optional RPC repair (only if needed)
backend/sql/02_rpc_postrun_hotfix_2026_04_12.sql
```

## Recovery Flow (if synthetic auth logins return 500)

```text
backend/sql/helpers/19a_login_ready_workers_auth_cleanup.sql
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

`backend/sql/helpers/` contains operational recovery helpers that are run
manually when needed. They are intentionally outside the strict top-level
`NN_description.sql` migration sequence validated by
`scripts/validate_sql_migrations.py`.

## Final Schema Reference

`backend/sql/reference/SCHEMA_FINAL_REFERENCE_2026_04_12.sql` stores the final live
schema snapshot used as structural reference during this cleanup.
