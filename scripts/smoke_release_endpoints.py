"""Smoke-check release-critical backend endpoints against a running deployment."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import httpx


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _check_health(payload: dict[str, Any], allow_degraded: bool) -> None:
    _expect("status" in payload, "Health payload missing 'status'.")
    _expect("config_ok" in payload, "Health payload missing 'config_ok'.")
    if not allow_degraded:
        _expect(payload.get("status") == "ok", f"Health status is {payload.get('status')}, expected ok.")
        _expect(bool(payload.get("config_ok")) is True, "Health config_ok must be true.")


def _check_ready(payload: dict[str, Any], allow_degraded: bool) -> None:
    _expect("status" in payload, "Readiness payload missing 'status'.")
    _expect(isinstance(payload.get("checks"), dict), "Readiness payload missing checks map.")
    if not allow_degraded:
        _expect(payload.get("status") == "ready", f"Readiness status is {payload.get('status')}, expected ready.")
        checks = payload.get("checks") or {}
        failed = [name for name, value in checks.items() if not bool(value)]
        _expect(not failed, f"Readiness checks failing: {', '.join(failed)}")


def _check_ops_status(payload: dict[str, Any]) -> None:
    _expect("runtime" in payload, "Ops status payload missing runtime section.")
    _expect("event_bus" in payload, "Ops status payload missing event_bus section.")
    _expect("review_queue" in payload, "Ops status payload missing review_queue section.")
    _expect("payouts" in payload, "Ops status payload missing payouts section.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Release smoke checks for backend health/readiness/ops")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL for backend API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--allow-degraded",
        action="store_true",
        help="Do not fail when health/readiness status is degraded.",
    )
    parser.add_argument(
        "--ops-admin-bearer-token",
        default="",
        help="Optional bearer token for authenticated /ops/status validation.",
    )
    parser.add_argument(
        "--require-ops-status",
        action="store_true",
        help="Fail if /ops/status cannot be validated (requires admin token in most envs).",
    )

    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    try:
        with httpx.Client(timeout=args.timeout_seconds) as client:
            endpoints = {
                "/health": _check_health,
                "/ready": _check_ready,
            }

            for endpoint, validator in endpoints.items():
                url = f"{base}{endpoint}"
                response = client.get(url)
                _expect(response.status_code == 200, f"{endpoint} returned HTTP {response.status_code}")

                payload = response.json()
                _expect(isinstance(payload, dict), f"{endpoint} did not return a JSON object")
                validator(payload, args.allow_degraded)
                print(f"PASS {endpoint}")

            ops_headers = None
            token = (args.ops_admin_bearer_token or "").strip()
            if token:
                ops_headers = {"Authorization": f"Bearer {token}"}

            ops_url = f"{base}/ops/status"
            ops_response = client.get(ops_url, headers=ops_headers)

            if ops_response.status_code == 200:
                ops_payload = ops_response.json()
                _expect(isinstance(ops_payload, dict), "/ops/status did not return a JSON object")
                _check_ops_status(ops_payload)
                print("PASS /ops/status")
            elif ops_response.status_code in (401, 403):
                if token:
                    _expect(
                        False,
                        f"/ops/status returned HTTP {ops_response.status_code} even with provided admin token",
                    )
                if args.require_ops_status:
                    _expect(
                        False,
                        f"/ops/status returned HTTP {ops_response.status_code}; provide --ops-admin-bearer-token",
                    )
                print(
                    f"SKIP /ops/status (HTTP {ops_response.status_code} - admin auth required)"
                )
            else:
                _expect(False, f"/ops/status returned HTTP {ops_response.status_code}")

    except Exception as exc:
        print(f"FAIL release smoke checks: {exc}")
        return 1

    print("PASS release smoke checks completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
