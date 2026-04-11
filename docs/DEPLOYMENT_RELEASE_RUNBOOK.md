# Deployment Release Runbook

This runbook defines the minimum release-safety flow
for staging and production-like deployments.

## 1. Pre-release Gates

All checks below are blocking in CI:

1. Backend pytest suite.
2. Frontend environment validation, lint, type-check, and build.
3. Mobile environment validation and type-check.
4. OpenAPI drift check against runtime app schema.
5. SQL migration naming and ordering safety check.
6. Deployment manifest guardrail tests.
7. Docker Compose render sanity check.

## 2. Environment Validation Rules

Backend strict validation behavior:

1. Set APP_ENV=production and STRICT_ENV_VALIDATION=true for staging/prod.
2. In strict mode, startup fails when critical config is missing.
3. In strict mode, PAYOUT_PROVIDER=http_gateway requires:
   - PAYOUT_PROVIDER_API_BASE_URL
   - PAYOUT_PROVIDER_API_KEY
4. In strict mode, PAYOUT_PROVIDER_WEBHOOK_SECRET must not be the dev default.
5. In strict mode with EVENT_BUS_BACKEND=kafka, KAFKA_BOOTSTRAP_SERVERS is required.

Frontend and mobile now have explicit env validation scripts:

1. frontend/scripts/validate-env.mjs
2. mobile/scripts/validate-env.mjs

## 3. Compose Release-Sanity

Validate compose wiring before startup:

PowerShell:

python scripts/validate_sql_migrations.py
docker compose --env-file .env.example config

Start local release-like stack:

PowerShell:

docker compose up --build

Backend readiness now points to /ready and frontend depends on backend health.

## 4. Kubernetes Apply Order

Apply in this order:

1. k8s/covara-configmap.yaml
2. k8s/covara-secrets.template.yaml (copy and replace values before apply)
3. k8s/redis-deployment.yaml
4. k8s/backend-deployment.yaml
5. k8s/frontend-deployment.yaml
6. k8s/ingress.yaml

Important:

1. ingress.yaml expects TLS secret name covara-tls.
2. backend readiness probe is /ready, liveness is /health.
3. frontend liveness/readiness probe is /.

## 5. Staging Prerequisite Checklist

Before running any `kubectl apply`, confirm all required staging inputs exist.

Cluster and access:

1. `kubectl config current-context` returns the intended staging context.
2. `kubectl get namespace` succeeds for the target namespace.
3. The target namespace is agreed and created (manifests do not hardcode `metadata.namespace`).

Ingress and TLS:

1. Replace `covara.local` in `k8s/ingress.yaml` with the real staging host.
2. DNS for the staging host resolves to the ingress controller.
3. TLS secret `covara-tls` exists in the target namespace (or update ingress to the real secret name).

Images and pull access:

1. `k8s/backend-deployment.yaml` and `k8s/frontend-deployment.yaml` image fields point to pullable staging images.
2. If registry auth is required, image pull secrets are configured for the namespace/service accounts.

Application secrets/config:

1. Create a non-template `covara-secrets` from `k8s/covara-secrets.template.yaml`.
2. Required values for strict mode are present and non-default:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `DEVICE_CONTEXT_HMAC_SECRET`
   - `PAYOUT_PROVIDER_WEBHOOK_SECRET` (must not be dev default)
3. If `PAYOUT_PROVIDER=http_gateway`, also set:
   - `PAYOUT_PROVIDER_API_BASE_URL`
   - `PAYOUT_PROVIDER_API_KEY`

Optional event bus dependencies:

1. If `EVENT_BUS_BACKEND=kafka`, set `KAFKA_BOOTSTRAP_SERVERS` and validate broker reachability.

## 6. Post-deploy Smoke Checks

Run release smoke checks against deployed backend:

PowerShell:

python scripts/smoke_release_endpoints.py --base-url https://your-backend-host

Default checks:

1. GET /health
2. GET /ready
3. GET /ops/status

Use --allow-degraded only for diagnostics, not for release acceptance.

## 7. Rollback Drill (Staging)

Run one rollback drill after a successful staging rollout:

1. Capture deployment revisions:
   - `kubectl rollout history deployment/covara-backend`
   - `kubectl rollout history deployment/covara-frontend`
2. Trigger a controlled rollout change (for example, deploy a new image tag).
3. Wait for rollout complete:
   - `kubectl rollout status deployment/covara-backend`
   - `kubectl rollout status deployment/covara-frontend`
4. Execute rollback:
   - `kubectl rollout undo deployment/covara-backend`
   - `kubectl rollout undo deployment/covara-frontend`
5. Wait for rollback rollout complete and re-run smoke checks.
6. Record:
   - revision restored
   - smoke-check status after rollback
   - any manual intervention required

## 8. Rollback Guidance

If smoke checks fail after rollout:

1. Stop traffic expansion.
2. Roll back to previous deployment revision.
3. Re-run smoke checks on rolled-back version.
4. Review /ops/status and structured logs for root cause.
5. Open follow-up fix PR and re-run CI gates before retry.

Suggested Kubernetes rollback command:

kubectl rollout undo deployment/covara-backend
kubectl rollout undo deployment/covara-frontend

## 9. Known External Blockers

1. Real payout provider live credential validation remains blocked
   until production provider secrets/endpoints are supplied.
2. Centralized telemetry sink and alert-routing infrastructure remain
   future work (current observability baseline is in-process).
