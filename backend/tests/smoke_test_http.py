"""
Covara One — HTTP Smoke Test

Hits all critical API endpoints and verifies they return expected
status codes. Run against local or production to catch config issues.

Usage:
    python backend/tests/smoke_test_http.py
    python backend/tests/smoke_test_http.py --base-url https://covara-backend.onrender.com
"""

import argparse
import json
import os
import sys
import time

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)


DEFAULT_BASE_URL = os.getenv("NEXT_PUBLIC_API_URL", "http://127.0.0.1:8000")

# ── Test definitions ──────────────────────────────────────────────────
# Each tuple: (method, path, expected_status, description)

SMOKE_TESTS = [
    # Health & readiness
    ("GET", "/health", 200, "Health check"),
    ("GET", "/ready", 200, "Readiness probe"),
    ("GET", "/", 200, "Root endpoint"),

    # OpenAPI
    ("GET", "/docs", 200, "OpenAPI Swagger UI"),
    ("GET", "/openapi.json", 200, "OpenAPI JSON spec"),

    # Triggers (public)
    ("GET", "/triggers/library", 200, "Trigger library"),
    ("GET", "/triggers/live", 200, "Live triggers"),
    ("GET", "/triggers/civic-news", 200, "NewsAPI civic news"),

    # Analytics (requires auth — 401/403 expected without token)
    ("GET", "/analytics/summary", [200, 401, 403], "Analytics summary"),

    # Claims (requires auth)
    ("GET", "/claims", [200, 401, 403], "Claims list"),
]


def run_smoke_tests(base_url: str) -> tuple[int, int, list[dict]]:
    """Run all smoke tests and return (passed, failed, results)."""
    passed = 0
    failed = 0
    results = []

    url = base_url.rstrip("/")
    print(f"\n{'='*65}")
    print(f"  Covara One — HTTP Smoke Test Suite")
    print(f"  Target: {url}")
    print(f"  Time:   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}\n")

    with httpx.Client(timeout=15, follow_redirects=True) as client:
        for method, path, expected, description in SMOKE_TESTS:
            full_url = f"{url}{path}"
            try:
                start = time.time()
                resp = client.request(method, full_url)
                elapsed_ms = round((time.time() - start) * 1000)

                expected_list = expected if isinstance(expected, list) else [expected]
                ok = resp.status_code in expected_list

                status_icon = "✅" if ok else "❌"
                if ok:
                    passed += 1
                else:
                    failed += 1

                result = {
                    "path": path,
                    "status": resp.status_code,
                    "expected": expected,
                    "ok": ok,
                    "ms": elapsed_ms,
                    "description": description,
                }
                results.append(result)

                print(
                    f"  {status_icon} [{resp.status_code}] {method:4s} {path:30s} "
                    f"({elapsed_ms:>4d}ms) — {description}"
                )

            except httpx.ConnectError:
                failed += 1
                results.append({"path": path, "status": "CONN_ERR", "ok": False})
                print(f"  ❌ [ERR] {method:4s} {path:30s} — CONNECTION REFUSED")

            except Exception as e:
                failed += 1
                results.append({"path": path, "status": str(e), "ok": False})
                print(f"  ❌ [ERR] {method:4s} {path:30s} — {e}")

    print(f"\n{'─'*65}")
    print(f"  Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed == 0:
        print(f"  🎉 All smoke tests passed!")
    else:
        print(f"  ⚠️  {failed} test(s) failed — investigate before demo")
    print(f"{'─'*65}\n")

    return passed, failed, results


def main():
    parser = argparse.ArgumentParser(description="Covara One HTTP Smoke Tests")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    passed, failed, results = run_smoke_tests(args.base_url)
    if args.json:
        print(json.dumps({"passed": passed, "failed": failed, "results": results}, indent=2))
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
