"""
Create DEMO9 synthetic auth users via Supabase Admin API.

This script is intended for the DEMO9 recovery flow after running:
  backend/sql/helpers/08c_fix_demo9_auth_users.sql (pass 1)

It creates 9 worker users with email_confirm=True (Auto Confirm equivalent)
and can verify password logins afterward.

Usage:
  python scripts/create_demo9_auth_users.py --apply
  python scripts/create_demo9_auth_users.py --apply --password "Covara#2026!"
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv


@dataclass(frozen=True)
class DemoUser:
    email: str
    full_name: str
    phone: str


DEMO_USERS: list[DemoUser] = [
    DemoUser("demo.auto01@synthetic.covara.dev", "DEMO9 AUTO01", "+919900000001"),
    DemoUser("demo.auto02@synthetic.covara.dev", "DEMO9 AUTO02", "+919900000002"),
    DemoUser("demo.auto03@synthetic.covara.dev", "DEMO9 AUTO03", "+919900000003"),
    DemoUser("demo.review01@synthetic.covara.dev", "DEMO9 REVIEW01", "+919900000004"),
    DemoUser("demo.review02@synthetic.covara.dev", "DEMO9 REVIEW02", "+919900000005"),
    DemoUser("demo.review03@synthetic.covara.dev", "DEMO9 REVIEW03", "+919900000006"),
    DemoUser("demo.fraud01@synthetic.covara.dev", "DEMO9 FRAUD01", "+919900000007"),
    DemoUser("demo.fraud02@synthetic.covara.dev", "DEMO9 FRAUD02", "+919900000008"),
    DemoUser("demo.fraud03@synthetic.covara.dev", "DEMO9 FRAUD03", "+919900000009"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create DEMO9 auth users (email_confirm=True)")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Without this flag the script runs in dry-run mode.")
    parser.add_argument("--password", default="Covara#2026!", help="Password to set for all DEMO9 users.")
    parser.add_argument("--skip-verify", action="store_true", help="Skip password-login verification after creation.")
    return parser.parse_args()


def _load_env() -> tuple[str, str, str]:
    root_env = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(root_env)

    supa_url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supa_url or not anon_key or not service_key:
        raise RuntimeError("Missing SUPABASE URL/ANON/SERVICE ROLE key in environment.")
    return supa_url, anon_key, service_key


def _create_users(
    client: httpx.Client,
    supa_url: str,
    service_key: str,
    password: str,
) -> tuple[int, int, list[str]]:
    created = 0
    already_exists = 0
    errors: list[str] = []

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    for user in DEMO_USERS:
        resp = client.post(
            f"{supa_url}/auth/v1/admin/users",
            headers=headers,
            json={
                "email": user.email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {
                    "role": "worker",
                    "full_name": user.full_name,
                    "phone": user.phone,
                    "seed_batch": "demo9",
                },
            },
        )

        if resp.status_code in (200, 201):
            created += 1
            print(f"[created] {user.email}")
            continue

        body = resp.text.lower()
        if resp.status_code in (400, 422) and ("already" in body or "registered" in body or "exists" in body):
            already_exists += 1
            print(f"[exists]  {user.email}")
            continue

        short_body = resp.text.replace("\n", " ")
        if len(short_body) > 220:
            short_body = short_body[:220] + "..."
        errors.append(f"{user.email}: http={resp.status_code} body={short_body}")
        print(f"[error]   {user.email} -> http {resp.status_code}")

    return created, already_exists, errors


def _verify_logins(
    client: httpx.Client,
    supa_url: str,
    anon_key: str,
    password: str,
) -> tuple[int, list[str]]:
    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Content-Type": "application/json",
    }
    ok = 0
    failures: list[str] = []

    for user in DEMO_USERS:
        resp = client.post(
            f"{supa_url}/auth/v1/token?grant_type=password",
            headers=headers,
            json={"email": user.email, "password": password},
        )
        if resp.status_code == 200:
            ok += 1
            print(f"[login-ok]   {user.email}")
            continue

        body = resp.text.replace("\n", " ")
        if len(body) > 180:
            body = body[:180] + "..."
        failures.append(f"{user.email}: http={resp.status_code} body={body}")
        print(f"[login-fail] {user.email} -> http {resp.status_code}")

    return ok, failures


def main() -> int:
    args = parse_args()

    try:
        supa_url, anon_key, service_key = _load_env()
    except Exception as exc:
        print(f"[fatal] {exc}")
        return 1

    print(f"[info] mode={'apply' if args.apply else 'dry-run'} users={len(DEMO_USERS)}")
    if not args.apply:
        for user in DEMO_USERS:
            print(f"[dry-run] would create {user.email} with email_confirm=True")
        print("[hint] Re-run with --apply to execute.")
        return 0

    with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), http2=False) as client:
        created, existed, errors = _create_users(client, supa_url, service_key, args.password)
        print(f"[result] created={created} existed={existed} errors={len(errors)}")

        if errors:
            for line in errors:
                print(f"[create-error] {line}")

        if args.skip_verify:
            return 0 if not errors else 2

        ok_count, failures = _verify_logins(client, supa_url, anon_key, args.password)
        print(f"[verify] login_ok={ok_count}/{len(DEMO_USERS)} failures={len(failures)}")
        if failures:
            for line in failures:
                print(f"[verify-fail] {line}")

        if errors or failures:
            return 2

    print("[done] DEMO9 users are created with Auto Confirm and login-ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
