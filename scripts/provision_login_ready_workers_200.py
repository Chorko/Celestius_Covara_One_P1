"""
Provision 200 login-ready synthetic worker auth users via Supabase Admin API.

Why this exists:
- Direct SQL inserts into auth.users/auth.identities can break on newer
  Supabase Auth schema versions.
- This script uses the supported Admin API path for durable user creation.

Usage:
  python scripts/provision_login_ready_workers_200.py --apply

Recommended recovery flow for existing broken synthetic auth rows:
  1) Run backend/sql/19a_login_ready_workers_auth_cleanup.sql
  2) Run this script with --apply
  3) Run backend/sql/19_login_ready_workers_200.sql
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

PASSWORD = "Covara#2026!"
WORKER_COUNT = 200

FIRST_NAMES = [
    "Aarav", "Vihaan", "Ishaan", "Reyansh", "Aditya", "Arjun", "Kabir", "Rohan", "Aman", "Nikhil",
    "Karan", "Varun", "Siddharth", "Akash", "Rahul", "Ritesh", "Manish", "Yash", "Sanjay", "Pranav",
    "Ananya", "Aditi", "Kavya", "Neha", "Pooja", "Riya", "Ira", "Meera", "Sana", "Naina",
]

LAST_NAMES = [
    "Sharma", "Patel", "Khan", "Yadav", "Verma", "Nair", "Iyer", "Reddy", "Singh", "Das",
    "Gupta", "Mishra", "Jain", "Chopra", "Bose", "Kulkarni", "Mehta", "Pillai", "Rao", "Tiwari",
]


@dataclass(frozen=True)
class WorkerAuthSeed:
    worker_idx: int
    worker_id: str
    email: str
    full_name: str


def _seed_uuid(seed: str) -> str:
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return f"{digest[0:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


def _build_workers(count: int = WORKER_COUNT) -> list[WorkerAuthSeed]:
    workers: list[WorkerAuthSeed] = []
    for idx in range(1, count + 1):
        first_name = FIRST_NAMES[(idx - 1) % len(FIRST_NAMES)]
        last_name = LAST_NAMES[(idx * 3 - 1) % len(LAST_NAMES)]
        workers.append(
            WorkerAuthSeed(
                worker_idx=idx,
                worker_id=_seed_uuid(f"covara19-worker-auth-{idx}"),
                email=f"worker{idx:03d}@synthetic.covara.dev",
                full_name=f"{first_name} {last_name}",
            )
        )
    return workers


def _with_retry(fn, attempts: int = 3):
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # pragma: no cover - network/runtime retries
            last_exc = exc
            if attempt < attempts:
                time.sleep(0.4 * attempt)
    assert last_exc is not None
    raise last_exc


def _create_service_client(url: str, service_role_key: str) -> Client:
    http_client = httpx.Client(
        timeout=httpx.Timeout(20.0, connect=8.0),
        http2=False,
    )
    options = SyncClientOptions(
        auto_refresh_token=False,
        persist_session=False,
        postgrest_client_timeout=20,
        storage_client_timeout=20,
        function_client_timeout=20,
        httpx_client=http_client,
    )
    return create_client(url, service_role_key, options=options)


def _verify_password_logins(url: str, anon_key: str, workers: list[WorkerAuthSeed]) -> tuple[int, list[str]]:
    ok = 0
    failures: list[str] = []

    endpoint = f"{url}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
    }

    with httpx.Client(timeout=httpx.Timeout(20.0, connect=8.0), http2=False) as client:
        for worker in workers:
            try:
                resp = client.post(
                    endpoint,
                    headers=headers,
                    json={"email": worker.email, "password": PASSWORD},
                )
            except Exception as exc:  # pragma: no cover - network/runtime condition
                failures.append(f"{worker.email}: request_error={exc}")
                continue

            if resp.status_code == 200:
                ok += 1
            else:
                body = resp.text.replace("\n", " ")
                if len(body) > 180:
                    body = body[:180] + "..."
                failures.append(f"{worker.email}: http={resp.status_code} body={body}")

    return ok, failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provision 200 login-ready synthetic auth users via Supabase Admin API.")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Without this flag, script runs in dry-run mode.")
    return parser.parse_args()


def main() -> int:
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    args = parse_args()
    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    anon_key = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not anon_key or not service_role_key:
        print("[fatal] Missing SUPABASE URL/ANON/SERVICE_ROLE_KEY in .env")
        return 1

    workers = _build_workers()
    print(f"[info] target workers: {len(workers)}")
    print(f"[info] mode: {'apply' if args.apply else 'dry-run'}")

    if not args.apply:
        for worker in workers[:10]:
            print(f"[dry-run] would ensure {worker.email} ({worker.worker_id})")
        print("[dry-run] ...")
        print("[hint] Re-run with --apply to provision auth users.")
        return 0

    sb = _create_service_client(url, service_role_key)

    created = 0
    already_exists = 0
    errors: list[str] = []

    for worker in workers:
        payload = {
            "id": worker.worker_id,
            "email": worker.email,
            "password": PASSWORD,
            "email_confirm": True,
            "user_metadata": {
                "full_name": worker.full_name,
                "seed_batch": "19_login_ready_workers_200",
            },
        }

        try:
            _with_retry(lambda p=payload: sb.auth.admin.create_user(p))
            created += 1
        except Exception as exc:
            msg = str(exc)
            lowered = msg.lower()
            if "already" in lowered and ("registered" in lowered or "exists" in lowered):
                already_exists += 1
            else:
                errors.append(f"{worker.email}: {msg}")

        # Keep request pressure moderate for free-tier projects.
        time.sleep(0.02)

    print(f"[result] created={created} already_exists={already_exists} errors={len(errors)}")
    if errors:
        for line in errors[:25]:
            print(f"[error] {line}")
        if len(errors) > 25:
            print(f"[error] ... and {len(errors) - 25} more")

    print("[verify] checking password login for all synthetic workers...")
    ok_count, failures = _verify_password_logins(url, anon_key, workers)
    print(f"[verify] successful_logins={ok_count}/{len(workers)} failures={len(failures)}")
    if failures:
        for line in failures[:25]:
            print(f"[verify-fail] {line}")
        if len(failures) > 25:
            print(f"[verify-fail] ... and {len(failures) - 25} more")

    if errors or failures:
        return 2

    print("[done] synthetic auth users are login-ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
