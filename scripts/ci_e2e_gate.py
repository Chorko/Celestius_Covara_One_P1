"""CI E2E gate: validate runtime health, auth boundaries, and critical API contract.

This script is intentionally strict for CI and should fail fast when core runtime
behavior regresses.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, cast

import httpx


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _get_json(client: httpx.Client, url: str, expected_status: int = 200) -> dict[str, Any]:
    resp = client.get(url)
    _assert(resp.status_code == expected_status, f"{url} -> HTTP {resp.status_code}, expected {expected_status}")
    payload = resp.json()
    _assert(isinstance(payload, dict), f"{url} did not return JSON object")
    return payload


def _assert_auth_guard(client: httpx.Client, base_url: str, path: str) -> None:
    resp = client.get(f"{base_url}{path}")
    _assert(
        resp.status_code in {401, 403},
        f"{path} must enforce auth (expected 401/403, got {resp.status_code})",
    )


def run(base_url: str, timeout_seconds: float) -> None:
    base = base_url.rstrip("/")

    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        # Runtime and docs surfaces.
        root = _get_json(client, f"{base}/")
        _assert(root.get("service") == "covara-one-api", "Root service name mismatch")

        health = _get_json(client, f"{base}/health")
        _assert("status" in health, "/health missing status")
        _assert("config_ok" in health, "/health missing config_ok")
        _assert(bool(health.get("config_ok")) is True, "/health config_ok is false")

        ready = _get_json(client, f"{base}/ready")
        _assert(ready.get("status") in {"ready", "degraded"}, "/ready status must be ready|degraded")
        checks_raw = ready.get("checks")
        _assert(isinstance(checks_raw, dict), "/ready missing checks map")
        checks = cast(dict[str, Any], checks_raw)
        _assert("config_ok" in checks, "/ready checks missing config_ok")
        _assert(bool(checks.get("config_ok")) is True, "/ready checks.config_ok is false")

        docs_resp = client.get(f"{base}/docs")
        _assert(docs_resp.status_code == 200, f"/docs -> HTTP {docs_resp.status_code}")

        openapi = _get_json(client, f"{base}/openapi.json")
        paths_raw = openapi.get("paths")
        _assert(isinstance(paths_raw, dict), "/openapi.json missing paths object")
        paths = cast(dict[str, Any], paths_raw)

        required_paths = {
            "/health",
            "/ready",
            "/claims",
            "/claims/{claim_id}/assign",
            "/claims/{claim_id}/review",
            "/payouts/webhooks/{provider_key}",
            "/events/outbox/status",
            "/events/outbox/dead-letter/requeue",
            "/events/consumers/status",
            "/ops/status",
            "/ops/slo",
            "/ops/version-governance",
            "/ops/version-governance/activate",
            "/policies/quote",
            "/triggers/library",
        }
        missing = sorted(path for path in required_paths if path not in paths)
        _assert(not missing, f"OpenAPI missing required paths: {', '.join(missing)}")

        trigger_lib = _get_json(client, f"{base}/triggers/library")
        _assert(int(trigger_lib.get("count", 0)) > 0, "/triggers/library returned zero triggers")

        # Protected endpoints must not be open to anonymous callers.
        _assert_auth_guard(client, base, "/claims")
        _assert_auth_guard(client, base, "/analytics/summary")
        _assert_auth_guard(client, base, "/ops/status")
        _assert_auth_guard(client, base, "/ops/slo")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CI end-to-end runtime/API gate")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    args = parser.parse_args()

    try:
        run(base_url=args.base_url, timeout_seconds=args.timeout_seconds)
    except Exception as exc:
        print(f"FAIL ci e2e gate: {exc}")
        sys.exit(1)

    print("PASS ci e2e gate")
