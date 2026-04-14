"""
Recover demo auth users without running SQL Editor scripts.

Why:
- Supabase SQL Editor sessions can time out on slow/unstable connections.
- This script uses Supabase Admin + PostgREST APIs directly.

Usage:
  python scripts/recover_demo_auth_without_sql.py --mode full --apply
  python scripts/recover_demo_auth_without_sql.py --mode cleanup --apply
  python scripts/recover_demo_auth_without_sql.py --mode sync --apply

Default is dry-run unless --apply is provided.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, timedelta
from typing import Any
from uuid import NAMESPACE_DNS, uuid5

import httpx
from dotenv import load_dotenv
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DEMO_EMAILS = {"worker@demo.com", "admin@demo.com"}
LEGACY_DEMO_IDS = {
    "aaaa0000-0000-0000-0000-000000000201",
    "aaaa0000-0000-0000-0000-000000000202",
}


def _user_id(user: Any) -> str | None:
    if user is None:
        return None
    if isinstance(user, dict):
        uid = user.get("id")
        return str(uid) if uid else None
    uid = getattr(user, "id", None)
    return str(uid) if uid else None


def _user_email(user: Any) -> str:
    if user is None:
        return ""
    if isinstance(user, dict):
        return str(user.get("email") or "")
    return str(getattr(user, "email", "") or "")


class Runner:
    def __init__(self, sb: Client, apply: bool):
        self.sb = sb
        self.apply = apply

    def _with_retry(self, fn, attempts: int = 3):
        last_err: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except Exception as err:  # pragma: no cover
                last_err = err
                if attempt < attempts:
                    time.sleep(0.7 * attempt)
        assert last_err is not None
        raise last_err

    def read(self, label: str, fn):
        print(f"[read] {label}")
        return self._with_retry(fn)

    def write(self, label: str, fn):
        if not self.apply:
            print(f"[dry-run] {label}")
            return None
        print(f"[write] {label}")
        return self._with_retry(fn)


def _det_uuid(name: str) -> str:
    return str(uuid5(NAMESPACE_DNS, f"covara:{name}"))


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE URL or SERVICE_ROLE_KEY missing in .env")

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
    return create_client(url, key, options=options)


def get_profile_id_by_email(run: Runner, email: str) -> str | None:
    resp = run.read(
        f"profile lookup by email {email}",
        lambda: run.sb.table("profiles").select("id").eq("email", email).limit(1).execute(),
    )
    rows = resp.data or []
    if rows and rows[0].get("id"):
        return str(rows[0]["id"])
    return None


def get_user_id_via_signin(run: Runner, email: str, passwords: list[str]) -> str | None:
    for password in passwords:
        try:
            result = run.read(
                f"sign-in probe for {email}",
                lambda e=email, p=password: run.sb.auth.sign_in_with_password({"email": e, "password": p}),
            )
            uid = _user_id(getattr(result, "user", None)) or _user_id(result)
            try:
                run.sb.auth.sign_out()
            except Exception:
                pass
            if uid:
                return uid
        except Exception:
            continue
    return None


def collect_demo_user_ids(run: Runner) -> list[str]:
    ids: set[str] = set(LEGACY_DEMO_IDS)
    for email in sorted(DEMO_EMAILS):
        profile_id = get_profile_id_by_email(run, email)
        if profile_id:
            ids.add(profile_id)

        signin_id = get_user_id_via_signin(run, email, ["demo1234", "DevTrails@123"])
        if signin_id:
            ids.add(signin_id)

    return sorted(ids)


def ensure_auth_user(run: Runner, *, email: str, password: str, full_name: str) -> str:
    existing_profile_id = get_profile_id_by_email(run, email)
    if existing_profile_id:
        print(f"[ok] profile exists for {email} ({existing_profile_id})")
        return existing_profile_id

    signin_id = get_user_id_via_signin(run, email, [password, "demo1234", "DevTrails@123"])
    if signin_id:
        print(f"[ok] auth sign-in probe succeeded for {email} ({signin_id})")
        return signin_id

    if not run.apply:
        fake_id = _det_uuid(f"dryrun:{email}")
        print(f"[dry-run] would create auth user {email} ({fake_id})")
        return fake_id

    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"full_name": full_name},
    }

    result = None
    try:
        print(f"[write] create auth user {email}")
        result = run._with_retry(lambda: run.sb.auth.admin.create_user(payload))
    except Exception as err:
        err_msg = str(err).lower()
        if "already" not in err_msg and "registered" not in err_msg:
            raise
        print(f"[info] auth user {email} already exists according to auth API")

    user_obj = getattr(result, "user", None)
    uid = _user_id(user_obj) or _user_id(result)
    if not uid:
        uid = get_profile_id_by_email(run, email)
    if not uid:
        uid = get_user_id_via_signin(run, email, [password, "demo1234", "DevTrails@123"])
    if not uid:
        raise RuntimeError(f"Failed to create/find auth user: {email}")

    print(f"[ok] ensured auth user: {email} ({uid})")
    return uid


def cleanup_demo_data(run: Runner, target_user_ids: list[str]):
    ids = sorted({uid for uid in target_user_ids if uid})
    if not ids:
        print("[skip] cleanup: no target user ids")
        return

    print(f"[info] cleanup target ids: {ids}")

    claim_ids: set[str] = set()
    q1 = run.read(
        "claims by worker ids",
        lambda: run.sb.table("manual_claims").select("id").in_("worker_profile_id", ids).execute(),
    )
    for row in q1.data or []:
        if row.get("id"):
            claim_ids.add(str(row["id"]))

    q2 = run.read(
        "claims by reviewer ids",
        lambda: run.sb.table("manual_claims").select("id").in_("assigned_reviewer_profile_id", ids).execute(),
    )
    for row in q2.data or []:
        if row.get("id"):
            claim_ids.add(str(row["id"]))

    payout_ids: set[str] = set()
    q3 = run.read(
        "payout requests by worker ids",
        lambda: run.sb.table("payout_requests").select("id").in_("worker_profile_id", ids).execute(),
    )
    for row in q3.data or []:
        if row.get("id"):
            payout_ids.add(str(row["id"]))

    if claim_ids:
        q4 = run.read(
            "payout requests by claim ids",
            lambda: run.sb.table("payout_requests").select("id").in_("claim_id", sorted(claim_ids)).execute(),
        )
        for row in q4.data or []:
            if row.get("id"):
                payout_ids.add(str(row["id"]))

    if payout_ids:
        run.write(
            "delete payout_settlement_events",
            lambda: run.sb.table("payout_settlement_events").delete().in_("payout_request_id", sorted(payout_ids)).execute(),
        )
        run.write(
            "delete payout_status_transitions",
            lambda: run.sb.table("payout_status_transitions").delete().in_("payout_request_id", sorted(payout_ids)).execute(),
        )
        run.write(
            "delete payout_requests",
            lambda: run.sb.table("payout_requests").delete().in_("id", sorted(payout_ids)).execute(),
        )

    if claim_ids:
        run.write(
            "delete payout_recommendations",
            lambda: run.sb.table("payout_recommendations").delete().in_("claim_id", sorted(claim_ids)).execute(),
        )
        run.write(
            "delete claim_evidence",
            lambda: run.sb.table("claim_evidence").delete().in_("claim_id", sorted(claim_ids)).execute(),
        )
        run.write(
            "delete claim_reviews by claim",
            lambda: run.sb.table("claim_reviews").delete().in_("claim_id", sorted(claim_ids)).execute(),
        )

    run.write(
        "delete claim_reviews by reviewer",
        lambda: run.sb.table("claim_reviews").delete().in_("reviewer_profile_id", ids).execute(),
    )

    if claim_ids:
        run.write(
            "delete manual_claims",
            lambda: run.sb.table("manual_claims").delete().in_("id", sorted(claim_ids)).execute(),
        )

    run.write("delete policies", lambda: run.sb.table("policies").delete().in_("worker_profile_id", ids).execute())
    run.write(
        "delete platform_order_events",
        lambda: run.sb.table("platform_order_events").delete().in_("worker_profile_id", ids).execute(),
    )
    run.write(
        "delete platform_worker_daily_stats",
        lambda: run.sb.table("platform_worker_daily_stats").delete().in_("worker_profile_id", ids).execute(),
    )
    run.write("delete worker_shifts", lambda: run.sb.table("worker_shifts").delete().in_("worker_profile_id", ids).execute())
    run.write("delete coins_ledger", lambda: run.sb.table("coins_ledger").delete().in_("profile_id", ids).execute())

    run.write(
        "null actor in audit_events",
        lambda: run.sb.table("audit_events").update({"actor_profile_id": None}).in_("actor_profile_id", ids).execute(),
    )
    run.write(
        "null actor in kyc_verification_events",
        lambda: run.sb.table("kyc_verification_events").update({"actor_profile_id": None}).in_("actor_profile_id", ids).execute(),
    )

    run.write("delete insurer_profiles", lambda: run.sb.table("insurer_profiles").delete().in_("profile_id", ids).execute())
    run.write("delete worker_profiles", lambda: run.sb.table("worker_profiles").delete().in_("profile_id", ids).execute())
    run.write("delete profiles by id", lambda: run.sb.table("profiles").delete().in_("id", ids).execute())

    for email in sorted(DEMO_EMAILS):
        run.write(
            f"delete profiles by email {email}",
            lambda e=email: run.sb.table("profiles").delete().eq("email", e).execute(),
        )

    for uid in ids:
        if not run.apply:
            print(f"[dry-run] delete auth user by id {uid}")
            continue
        try:
            print(f"[write] delete auth user by id {uid}")
            run._with_retry(lambda user_id=uid: run.sb.auth.admin.delete_user(user_id))
        except Exception as err:
            # Best-effort: if user does not exist or cannot be deleted, continue.
            print(f"[warn] auth delete skipped for {uid}: {err}")


def sync_seed_demo_data(run: Runner):
    worker_id = ensure_auth_user(
        run,
        email="worker@demo.com",
        password="demo1234",
        full_name="Demo Worker",
    )

    admin_id = ensure_auth_user(
        run,
        email="admin@demo.com",
        password="demo1234",
        full_name="Demo Admin",
    )

    zone_resp = run.read(
        "fetch Mumbai zones",
        lambda: run.sb.table("zones").select("id, city, zone_name, center_lat, center_lng").eq("city", "Mumbai").order("zone_name").limit(10).execute(),
    )
    zones = zone_resp.data or []
    if not zones:
        zone_resp = run.read(
            "fetch any zone",
            lambda: run.sb.table("zones").select("id, city, zone_name, center_lat, center_lng").order("zone_name").limit(1).execute(),
        )
        zones = zone_resp.data or []

    zone = zones[0] if zones else {}
    zone_id = zone.get("id")
    zone_lat = float(zone.get("center_lat") or 19.1364)
    zone_lng = float(zone.get("center_lng") or 72.8296)

    run.write(
        "upsert worker profile row",
        lambda: run.sb.table("profiles").upsert(
            {
                "id": worker_id,
                "role": "worker",
                "full_name": "Demo Worker",
                "email": "worker@demo.com",
                "phone": "+919999900001",
            },
            on_conflict="id",
        ).execute(),
    )

    run.write(
        "upsert admin profile row",
        lambda: run.sb.table("profiles").upsert(
            {
                "id": admin_id,
                "role": "insurer_admin",
                "full_name": "Demo Admin",
                "email": "admin@demo.com",
                "phone": "+919999900002",
            },
            on_conflict="id",
        ).execute(),
    )

    run.write(
        "delete insurer profile for worker",
        lambda: run.sb.table("insurer_profiles").delete().eq("profile_id", worker_id).execute(),
    )
    run.write(
        "delete worker profile for admin",
        lambda: run.sb.table("worker_profiles").delete().eq("profile_id", admin_id).execute(),
    )

    run.write(
        "upsert worker_profiles",
        lambda: run.sb.table("worker_profiles").upsert(
            {
                "profile_id": worker_id,
                "platform_name": "Swiggy",
                "city": "Mumbai",
                "preferred_zone_id": zone_id,
                "vehicle_type": "Bike",
                "avg_hourly_income_inr": 90.0,
                "bank_verified": True,
                "trust_score": 0.86,
                "gps_consent": True,
            },
            on_conflict="profile_id",
        ).execute(),
    )

    run.write(
        "upsert insurer_profiles",
        lambda: run.sb.table("insurer_profiles").upsert(
            {
                "profile_id": admin_id,
                "company_name": "DEVTrails Insurance Ops",
                "job_title": "Demo Administrator",
            },
            on_conflict="profile_id",
        ).execute(),
    )

    since = (date.today() - timedelta(days=13)).isoformat()
    run.write(
        "delete recent daily stats",
        lambda: run.sb.table("platform_worker_daily_stats").delete().eq("worker_profile_id", worker_id).gte("stat_date", since).execute(),
    )

    rows: list[dict[str, Any]] = []
    today = date.today()
    for idx in range(14):
        d = today - timedelta(days=(13 - idx))
        weekend = d.isoweekday() in (6, 7)
        completed = (12 + idx % 3) if weekend else (9 + idx % 4)
        rows.append(
            {
                "worker_profile_id": worker_id,
                "stat_date": d.isoformat(),
                "active_hours": 8.5 if weekend else 9.75,
                "completed_orders": completed,
                "accepted_orders": completed + 2,
                "cancelled_orders": 1,
                "gross_earnings_inr": float(completed * (116 + ((idx % 4) * 7))),
                "platform_login_minutes": 510 if weekend else 585,
                "gps_consistency_score": min(0.97, 0.84 + ((idx % 5) * 0.025)),
            }
        )

    run.write(
        "insert fresh daily stats",
        lambda: run.sb.table("platform_worker_daily_stats").upsert(rows, on_conflict="worker_profile_id,stat_date").execute(),
    )

    trigger_id = _det_uuid("demo-worker-trigger-auto-fast")
    claim_id = _det_uuid("demo-worker-claim-auto-fast")
    payout_id = _det_uuid("demo-worker-payout-auto-fast")

    if zone_id:
        run.write(
            "upsert trigger event",
            lambda: run.sb.table("trigger_events").upsert(
                {
                    "id": trigger_id,
                    "city": "Mumbai",
                    "zone_id": zone_id,
                    "trigger_family": "rain",
                    "trigger_code": "RAIN_HEAVY",
                    "observed_value": 77.0,
                    "severity_band": "claim",
                    "source_type": "mock",
                    "started_at": (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 26 * 3600))),
                    "ended_at": (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 24 * 3600))),
                },
                on_conflict="id",
            ).execute(),
        )

    run.write(
        "upsert demo claim",
        lambda: run.sb.table("manual_claims").upsert(
            {
                "id": claim_id,
                "worker_profile_id": worker_id,
                "trigger_event_id": trigger_id,
                "claim_mode": "trigger_auto",
                "assignment_state": "resolved",
                "claim_reason": "Auto-triggered demo claim after heavy rain disruption in Andheri-W.",
                "stated_lat": round(zone_lat + 0.0012, 6),
                "stated_lng": round(zone_lng - 0.0011, 6),
                "claimed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - (24 * 3600 + 55 * 60))),
                "claim_status": "auto_approved",
            },
            on_conflict="id",
        ).execute(),
    )

    run.write(
        "upsert payout recommendation",
        lambda: run.sb.table("payout_recommendations").upsert(
            {
                "id": payout_id,
                "claim_id": claim_id,
                "covered_weekly_income_b": 4120,
                "claim_probability_p": 0.15,
                "severity_score_s": 0.78,
                "exposure_score_e": 0.84,
                "confidence_score_c": 0.89,
                "fraud_holdback_fh": 0.08,
                "outlier_uplift_u": 1.00,
                "payout_cap": 3000,
                "expected_payout": 606,
                "gross_premium": 28,
                "recommended_payout": 1500,
                "explanation_json": {
                    "seed": "recover_demo_auth_without_sql",
                    "scenario": "auto_approved",
                },
            },
            on_conflict="id",
        ).execute(),
    )

    run.write(
        "upsert worker policy",
        lambda: run.sb.table("policies").upsert(
            {
                "policy_id": "POL-DEMO-WORKER-ESSENTIAL",
                "worker_profile_id": worker_id,
                "zone_id": zone_id,
                "plan_type": "essential",
                "coverage_amount": 3000,
                "premium_amount": 28,
                "status": "active",
                "activated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 2 * 24 * 3600)),
                "valid_until": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 5 * 24 * 3600)),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            on_conflict="policy_id",
        ).execute(),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover demo auth users without SQL Editor.")
    parser.add_argument("--mode", choices=["cleanup", "sync", "full"], default="full")
    parser.add_argument("--apply", action="store_true", help="Apply mutations. Without this flag, script runs in dry-run mode.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        sb = get_supabase_client()
    except Exception as err:
        print(f"[fatal] Supabase client init failed: {err}")
        return 1

    run = Runner(sb=sb, apply=args.apply)
    print(f"[info] mode={args.mode} apply={args.apply}")

    demo_user_ids = collect_demo_user_ids(run)

    try:
        if args.mode in {"cleanup", "full"}:
            cleanup_demo_data(run, demo_user_ids)
        if args.mode in {"sync", "full"}:
            sync_seed_demo_data(run)
    except Exception as err:
        print(f"[fatal] Recovery failed: {err}")
        return 2

    print("[done] Recovery workflow finished.")
    if not args.apply:
        print("[hint] Re-run with --apply to execute changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
