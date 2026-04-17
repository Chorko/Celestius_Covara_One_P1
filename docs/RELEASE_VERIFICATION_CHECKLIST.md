# Release Verification Checklist (One Pass)

This checklist verifies migration, runtime, and CI readiness in one sequence.
Use it after schema or claim-pipeline changes,
especially migration 22 and RPC hotfix updates.

## 1) Local Preflight

Run from repo root:

```powershell
d:/Celestius_DEVTrails_P1/.venv/Scripts/python.exe scripts/validate_sql_migrations.py
```

Pass condition:
- Guardrails pass with latest migration equal to 24.

## 2) Database Governance Verification

Run in Supabase SQL editor (or `psql`) against the target environment:

```sql
select
  exists (
    select 1 from pg_proc where proname = 'resolve_active_rule_version_id'
  ) as has_rule_resolver,
  exists (
    select 1 from pg_proc where proname = 'resolve_active_model_version_id'
  ) as has_model_resolver,
  exists (
    select 1 from pg_indexes where schemaname = 'public' and indexname = 'uq_rule_versions_single_active'
  ) as has_rule_single_active_index,
  exists (
    select 1 from pg_indexes where schemaname = 'public' and indexname = 'uq_model_versions_single_active'
  ) as has_model_single_active_index;

select 'rule' as kind, count(*) as active_rows
from public.rule_versions
where is_active = true and status in ('active', 'canary')
union all
select 'model' as kind, count(*) as active_rows
from public.model_versions
where is_active = true and status in ('active', 'canary');

select
  count(*) filter (where rule_version_id is null) as claims_missing_rule_version,
  count(*) filter (where model_version_id is null) as claims_missing_model_version
from public.manual_claims;
```

Pass condition:
- All booleans are `true`.
- `active_rows` is exactly `1` for both `rule` and `model`.
- Missing version counts in `manual_claims` are `0`
  (or a documented expected legacy exception).

## 3) RPC Contract Verification

Run this SQL:

```sql
select
  pg_get_function_identity_arguments(p.oid) as args,
  p.prosecdef as security_definer,
  (
    exists (
      select 1
      from unnest(coalesce(p.proconfig, array[]::text[])) as cfg
      where lower(cfg) in ('search_path=public, pg_temp', 'search_path=public,pg_temp')
    )
    or pg_get_functiondef(p.oid) ~* 'set\\s+search_path\\s*(=|to)\\s*public\\s*,\\s*pg_temp'
  ) as has_safe_search_path
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public'
  and p.proname = 'persist_claim_with_outbox'
  and pg_get_function_identity_arguments(p.oid) =
    (
      'p_claim jsonb, p_payout jsonb, p_event_type text, p_event_key text, '
      || 'p_event_source text, p_event_payload jsonb'
    );
```

Pass condition:
- Function exists with `jsonb,jsonb,text,text,text,jsonb` arguments.
- `security_definer = true`.
- Safe search path check is `true`.

## 4) Backend Behavioral Verification

Run focused tests:

```powershell
d:/Celestius_DEVTrails_P1/.venv/Scripts/python.exe -m pytest `
  tests/test_version_governance.py `
  tests/test_claim_pipeline.py `
  tests/test_claims_review_workflow.py `
  tests/test_openapi_contract.py -q
```

Pass condition:
- All tests pass, including review decision trust-adjustment assertions and the OpenAPI review response contract check.

## 5) Runtime Smoke Verification

Run against deployed/staging API:

```powershell
d:/Celestius_DEVTrails_P1/.venv/Scripts/python.exe `
  scripts/smoke_release_endpoints.py `
  --base-url https://covara-backend.onrender.com
```

Optional strict ops check (admin token required):

```powershell
$env:OPS_ADMIN_BEARER_TOKEN = "<admin_jwt>"
d:/Celestius_DEVTrails_P1/.venv/Scripts/python.exe `
  scripts/smoke_release_endpoints.py `
  --base-url https://covara-backend.onrender.com `
  --ops-admin-bearer-token $env:OPS_ADMIN_BEARER_TOKEN `
  --require-ops-status
```

Evaluator note:
- Sharing the public backend base URL is safe.
- Do not share any secrets, tokens, or environment files.

Pass condition:
- Public evaluator run: `/health` and `/ready` pass.
- `SKIP /ops/status (HTTP 401/403 - admin auth required)` is acceptable
  for evaluator/public checks.
- Internal release gate: run the strict ops check command and require
  `/ops/status` to pass.
- Status is not degraded for release acceptance.

## 6) CI Parity Verification

Confirm CI includes and passes these gates:
- Backend tests.
- Frontend env/lint/type/build.
- Mobile env/type checks.
- OpenAPI drift checks.
- SQL migration guardrails.
- Deployment manifest tests.
- E2E/API flow gate.

Pass condition:
- All required checks green on the release branch.

## 7) Release Decision Rule

Release is approved only when all sections above pass.
If any section fails:
- Stop release.
- Fix root cause.
- Re-run this checklist from section 1.

## 8) Fast Failure Triage

- Resolver/index checks fail: re-run migration
  `22_rule_model_version_governance.sql` in target DB.
- RPC contract mismatch: apply `02_rpc_postrun_hotfix_2026_04_12.sql`.
- Missing claim version IDs: run migration 22 backfill block and re-check counts.
- Runtime smoke fail: follow rollback and diagnostics in `docs/DEPLOYMENT_RELEASE_RUNBOOK.md`.
