"""
Create deterministic Auth users required by backend/sql/06_synthetic_seed.sql.

Why this script exists:
- Direct SQL writes to auth.users/auth.identities can corrupt Supabase Auth.
- 06_synthetic_seed.sql expects fixed UUIDs for demo users.
- This script uses the Supabase Admin API (service-role) to provision those
  fixed IDs safely.

Usage:
  python scripts/create_seed06_auth_users.py --apply

Dry-run is default without --apply.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv


@dataclass(frozen=True)
class SeedAuthUser:
    user_id: str
    email: str
    password: str
    full_name: str
    role: str


SEED_USERS: list[SeedAuthUser] = [
    SeedAuthUser("aaaa0000-0000-0000-0000-000000000001", "ravi.kumar@demo.devtrails.in", "demopassword", "Ravi Kumar", "worker"),
    SeedAuthUser("aaaa0000-0000-0000-0000-000000000002", "priya.sharma@demo.devtrails.in", "demopassword", "Priya Sharma", "worker"),
    SeedAuthUser("aaaa0000-0000-0000-0000-000000000003", "arun.patel@demo.devtrails.in", "demopassword", "Arun Patel", "worker"),
    SeedAuthUser("aaaa0000-0000-0000-0000-000000000004", "meena.devi@demo.devtrails.in", "demopassword", "Meena Devi", "worker"),
    SeedAuthUser("aaaa0000-0000-0000-0000-000000000005", "suresh.yadav@demo.devtrails.in", "demopassword", "Suresh Yadav", "worker"),
    SeedAuthUser("aaaa0000-0000-0000-0000-000000000006", "fatima.khan@demo.devtrails.in", "demopassword", "Fatima Khan", "worker"),
    SeedAuthUser("aaaa0000-0000-0000-0000-000000000201", "worker@demo.com", "demo1234", "Demo Worker", "worker"),
    SeedAuthUser("aaaa0000-0000-0000-0000-000000000202", "admin@demo.com", "demo1234", "Demo Admin", "insurer_admin"),
    SeedAuthUser("aaaa0000-0000-0000-0000-000000000101", "neha.sharma@devtrails.insurance", "demopassword", "Neha Sharma", "insurer_admin"),
    SeedAuthUser("aaaa0000-0000-0000-0000-000000000102", "vijay.mehta@devtrails.insurance", "demopassword", "Vijay Mehta", "insurer_admin"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create deterministic auth users for 06_synthetic_seed.sql")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Without this flag, run in dry-run mode.")
    parser.add_argument("--skip-verify", action="store_true", help="Skip password-login verification after creation.")
    return parser.parse_args()


def load_env() -> tuple[str, str, str]:
    root_env = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(root_env)

    supabase_url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")

    if not supabase_url or not service_key or not anon_key:
        raise RuntimeError("Missing SUPABASE URL/SERVICE_ROLE_KEY/ANON_KEY in .env")

    return supabase_url, service_key, anon_key


def service_headers(service_key: str) -> dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def anon_headers(anon_key: str) -> dict[str, str]:
    return {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Content-Type": "application/json",
    }


def _json_body(resp: httpx.Response) -> dict[str, Any]:
    ctype = (resp.headers.get("content-type") or "").lower()
    if "application/json" not in ctype:
        return {}
    try:
        data = resp.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def get_user_by_id(client: httpx.Client, supabase_url: str, service_key: str, user_id: str) -> tuple[int, dict[str, Any], str]:
    resp = client.get(
        f"{supabase_url}/auth/v1/admin/users/{user_id}",
        headers=service_headers(service_key),
    )
    body = _json_body(resp)
    text = resp.text.replace("\n", " ")
    if len(text) > 300:
        text = text[:300] + "..."
    return resp.status_code, body, text


def login_probe(client: httpx.Client, supabase_url: str, anon_key: str, email: str, password: str) -> int:
    resp = client.post(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        headers=anon_headers(anon_key),
        json={"email": email, "password": password},
    )
    return resp.status_code


def sign_in_payload(client: httpx.Client, supabase_url: str, anon_key: str, email: str, password: str) -> tuple[int, dict[str, Any]]:
    resp = client.post(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        headers=anon_headers(anon_key),
        json={"email": email, "password": password},
    )
    return resp.status_code, _json_body(resp)


def password_candidates(spec: SeedAuthUser) -> list[str]:
    candidates = [
        spec.password,
        "demo1234",
        "demopassword",
        "DevTrails@123",
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for p in candidates:
        if p not in seen:
            ordered.append(p)
            seen.add(p)
    return ordered


def find_user_id_via_signin(client: httpx.Client, supabase_url: str, anon_key: str, spec: SeedAuthUser) -> str | None:
    for pwd in password_candidates(spec):
        status, body = sign_in_payload(client, supabase_url, anon_key, spec.email, pwd)
        if status == 200:
            user = body.get("user")
            if isinstance(user, dict):
                uid = user.get("id")
                if uid:
                    return str(uid)
        elif status >= 500:
            raise RuntimeError(
                f"Auth sign-in probe failed for {spec.email} with http={status}. "
                "Run supabase db query --file backend/sql/helpers/08_fix_demo_auth_users.sql --linked, then retry."
            )
    return None


def delete_user(client: httpx.Client, supabase_url: str, service_key: str, user_id: str) -> None:
    resp = client.delete(
        f"{supabase_url}/auth/v1/admin/users/{user_id}",
        headers=service_headers(service_key),
    )
    if resp.status_code in (404,):
        return
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"Failed deleting user {user_id}: http={resp.status_code} body={resp.text[:300]}")


def update_user(client: httpx.Client, supabase_url: str, service_key: str, spec: SeedAuthUser) -> None:
    payload = {
        "email": spec.email,
        "password": spec.password,
        "email_confirm": True,
        "user_metadata": {
            "full_name": spec.full_name,
            "role": spec.role,
            "seed_batch": "seed06",
        },
    }
    resp = client.put(
        f"{supabase_url}/auth/v1/admin/users/{spec.user_id}",
        headers=service_headers(service_key),
        json=payload,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed updating {spec.email}: http={resp.status_code} body={resp.text[:300]}")


def create_user(client: httpx.Client, supabase_url: str, service_key: str, spec: SeedAuthUser) -> tuple[bool, str]:
    payload = {
        "id": spec.user_id,
        "email": spec.email,
        "password": spec.password,
        "email_confirm": True,
        "user_metadata": {
            "full_name": spec.full_name,
            "role": spec.role,
            "seed_batch": "seed06",
        },
    }
    resp = client.post(
        f"{supabase_url}/auth/v1/admin/users",
        headers=service_headers(service_key),
        json=payload,
    )

    if resp.status_code in (200, 201):
        return True, "created"

    body_lower = resp.text.lower()
    if resp.status_code in (400, 409, 422) and (
        "already" in body_lower or "registered" in body_lower or "exists" in body_lower
    ):
        return False, "already_exists"

    if resp.status_code >= 500:
        return False, "server_error"

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed creating {spec.email}: http={resp.status_code} body={resp.text[:300]}")

    return False, "unknown"


def ensure_seed_users(
    client: httpx.Client,
    *,
    supabase_url: str,
    service_key: str,
    anon_key: str,
    apply: bool,
) -> tuple[int, int, int]:
    created = 0
    recreated = 0
    kept = 0

    for spec in SEED_USERS:
        status, body, raw = get_user_by_id(client, supabase_url, service_key, spec.user_id)

        if status == 200:
            user_obj = body.get("user")
            if not isinstance(user_obj, dict):
                user_obj = body if isinstance(body, dict) else {}
            existing_email = str(user_obj.get("email") or "").strip().lower()

            if existing_email != spec.email.lower():
                if not apply:
                    print(f"[dry-run] recreate {spec.email}: id occupied by {existing_email or 'unknown'}")
                    recreated += 1
                    continue
                delete_user(client, supabase_url, service_key, spec.user_id)
                ok, reason = create_user(client, supabase_url, service_key, spec)
                if not ok:
                    if reason == "already_exists":
                        alt_id = find_user_id_via_signin(client, supabase_url, anon_key, spec)
                        if not alt_id:
                            raise RuntimeError(
                                f"{spec.email} already exists with unknown ID. "
                                "Run supabase db query --file backend/sql/helpers/08_fix_demo_auth_users.sql --linked, then retry."
                            )
                        delete_user(client, supabase_url, service_key, alt_id)
                        ok, reason = create_user(client, supabase_url, service_key, spec)
                        if not ok:
                            raise RuntimeError(f"Failed recreating {spec.email} after cleanup: reason={reason}")
                    else:
                        raise RuntimeError(f"Failed creating {spec.email}: reason={reason}")
                print(f"[recreated] {spec.email} with deterministic id={spec.user_id}")
                recreated += 1
                continue

            login_status = login_probe(client, supabase_url, anon_key, spec.email, spec.password)
            if login_status == 200:
                print(f"[ok] {spec.email} already login-ready")
                kept += 1
                continue

            if login_status >= 500:
                raise RuntimeError(
                    f"Auth probe failed for {spec.email} with http={login_status}. "
                    "Run supabase db query --file backend/sql/helpers/08_fix_demo_auth_users.sql --linked, then rerun this script."
                )

            if not apply:
                print(f"[dry-run] update password/metadata for {spec.email}")
                recreated += 1
                continue

            update_user(client, supabase_url, service_key, spec)
            print(f"[updated] reset credentials for {spec.email}")
            recreated += 1
            continue

        if status == 404:
            if not apply:
                print(f"[dry-run] create {spec.email} with id={spec.user_id}")
                created += 1
                continue

            ok, reason = create_user(client, supabase_url, service_key, spec)
            if ok:
                print(f"[created] {spec.email}")
                created += 1
                continue

            if reason == "already_exists":
                alt_id = find_user_id_via_signin(client, supabase_url, anon_key, spec)
                if not alt_id:
                    raise RuntimeError(
                        f"{spec.email} already exists but could not resolve user ID via sign-in. "
                        "Run supabase db query --file backend/sql/helpers/08_fix_demo_auth_users.sql --linked, then retry."
                    )
                delete_user(client, supabase_url, service_key, alt_id)
                ok2, reason2 = create_user(client, supabase_url, service_key, spec)
                if not ok2:
                    raise RuntimeError(f"Failed creating deterministic user for {spec.email}: reason={reason2}")
                print(f"[recreated] {spec.email}: {alt_id} -> {spec.user_id}")
                recreated += 1
                continue

            if reason == "server_error":
                raise RuntimeError(
                    f"Auth API server error while creating {spec.email}. "
                    "Run backend/sql/helpers/08_fix_demo_auth_users.sql via supabase db query --linked, then retry."
                )

            raise RuntimeError(f"Unhandled create result for {spec.email}: reason={reason}")

        if status >= 500:
            if not apply:
                print(f"[dry-run] recover possibly-corrupt auth row for {spec.email} (id={spec.user_id})")
                recreated += 1
                continue

            # Best-effort self-heal: remove target ID row if present/corrupt, then create.
            delete_user(client, supabase_url, service_key, spec.user_id)
            ok, reason = create_user(client, supabase_url, service_key, spec)
            if ok:
                print(f"[recovered] {spec.email} with deterministic id={spec.user_id}")
                recreated += 1
                continue

            if reason == "already_exists":
                alt_id = find_user_id_via_signin(client, supabase_url, anon_key, spec)
                if not alt_id:
                    raise RuntimeError(
                        f"Could not recover {spec.email}: conflicting existing email and unresolved user id. "
                        "Run supabase db query --file backend/sql/helpers/08_fix_demo_auth_users.sql --linked, then retry."
                    )
                delete_user(client, supabase_url, service_key, alt_id)
                ok2, reason2 = create_user(client, supabase_url, service_key, spec)
                if not ok2:
                    raise RuntimeError(f"Recovery failed for {spec.email}: reason={reason2}")
                print(f"[recovered] {spec.email}: {alt_id} -> {spec.user_id}")
                recreated += 1
                continue

            raise RuntimeError(
                f"Could not recover auth user {spec.email} (http={status}, body={raw}). "
                "Run supabase db query --file backend/sql/helpers/08_fix_demo_auth_users.sql --linked, then retry."
            )

        raise RuntimeError(f"Unexpected admin get-user status for {spec.email}: http={status} body={raw}")

    return created, recreated, kept


def verify_seed_users(client: httpx.Client, supabase_url: str, service_key: str, anon_key: str) -> tuple[int, list[str]]:
    failures: list[str] = []
    ok = 0

    for spec in SEED_USERS:
        status, body, raw = get_user_by_id(client, supabase_url, service_key, spec.user_id)
        if status != 200:
            failures.append(f"missing auth user by id for {spec.email}: http={status} body={raw}")
            continue

        user_obj = body.get("user")
        if not isinstance(user_obj, dict):
            user_obj = body if isinstance(body, dict) else {}
        actual_email = str(user_obj.get("email") or "").strip().lower()
        if actual_email != spec.email.lower():
            failures.append(f"email mismatch for {spec.user_id}: expected {spec.email} got {actual_email or 'unknown'}")
            continue

        status = login_probe(client, supabase_url, anon_key, spec.email, spec.password)
        if status != 200:
            failures.append(f"login failed for {spec.email}: http={status}")
            continue

        ok += 1

    return ok, failures


def main() -> int:
    args = parse_args()

    try:
        supabase_url, service_key, anon_key = load_env()
    except Exception as exc:
        print(f"[fatal] {exc}")
        return 1

    print(f"[info] mode={'apply' if args.apply else 'dry-run'} users={len(SEED_USERS)}")

    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), http2=False) as client:
            created, recreated, kept = ensure_seed_users(
                client,
                supabase_url=supabase_url,
                service_key=service_key,
                anon_key=anon_key,
                apply=args.apply,
            )
            print(f"[result] created={created} recreated={recreated} kept={kept}")

            if args.skip_verify:
                if not args.apply:
                    print("[hint] run with --apply to execute changes")
                return 0

            ok, failures = verify_seed_users(client, supabase_url, service_key, anon_key)
            print(f"[verify] login_ok={ok}/{len(SEED_USERS)} failures={len(failures)}")
            for line in failures:
                print(f"[verify-fail] {line}")

            if failures:
                return 2

    except Exception as exc:
        print(f"[fatal] {exc}")
        return 2

    print("[done] 06_synthetic_seed auth users are deterministic and login-ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
