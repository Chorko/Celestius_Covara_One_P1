from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_ci_workflow_has_release_blocking_gates() -> None:
    ci = _read(".github/workflows/ci.yml").lower()
    assert "openapi contract drift check" in ci
    assert "sql migration safety check" in ci
    assert "deployment manifest guardrail tests" in ci
    assert "mobile type-check" in ci
    assert "docker compose render check" in ci


def test_compose_enforces_critical_env_and_ready_healthcheck() -> None:
    compose = _read("docker-compose.yml").lower()
    assert "strict_env_validation=${strict_env_validation:-true}" in compose
    assert "supabase_url=${supabase_url:?supabase_url is required}" in compose
    assert "supabase_anon_key=${supabase_anon_key:?supabase_anon_key is required}" in compose
    assert "supabase_service_role_key=${supabase_service_role_key:?supabase_service_role_key is required}" in compose
    assert "device_context_hmac_secret=${device_context_hmac_secret:?device_context_hmac_secret is required}" in compose
    assert "http://localhost:8000/ready" in compose


def test_backend_manifest_uses_ready_probe_and_config_sources() -> None:
    backend = _read("k8s/backend-deployment.yaml").lower()
    assert "path: /ready" in backend
    assert "startupprobe" in backend
    assert "configmapref" in backend
    assert "secretref" in backend


def test_frontend_manifest_has_valid_health_probes() -> None:
    frontend = _read("k8s/frontend-deployment.yaml").lower()
    assert "readinessprobe" in frontend
    assert "path: /" in frontend
    assert "/api/live" not in frontend


def test_ingress_has_tls_baseline() -> None:
    ingress = _read("k8s/ingress.yaml").lower()
    assert "tls:" in ingress
    assert "secretname: covara-tls" in ingress
    assert "ssl-redirect" in ingress


def test_k8s_has_config_and_secret_templates() -> None:
    config = _read("k8s/covara-configmap.yaml").lower()
    secrets = _read("k8s/covara-secrets.template.yaml").lower()
    assert "kind: configmap" in config
    assert "strict_env_validation" in config
    assert "kind: secret" in secrets
    assert "payout_provider_webhook_secret" in secrets
