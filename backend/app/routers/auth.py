"""
Covara One — Auth Router

Handles:
- POST /auth/signup — register new user (creates profile row)
- POST /auth/complete-onboarding — complete worker or insurer profile
- GET  /auth/me — return current user session + profile
- POST /auth/logout — sign out

Google OAuth is handled entirely by the frontend Supabase client.
The backend trusts the JWT issued by Supabase Auth.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from backend.app.dependencies import get_current_user
from backend.app.supabase_client import get_supabase_admin

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Request / Response Models ──────────────────────────────────────


class SignupRequest(BaseModel):
    """Used only for email/password signup fallback. Google OAuth users
    get their profile created on first /auth/me call if needed."""

    full_name: str
    role: str  # 'worker' or 'insurer_admin'
    email: EmailStr
    password: str


class OnboardingWorkerRequest(BaseModel):
    """Complete worker profile after Google OAuth signup."""

    full_name: str
    platform_name: str  # e.g. Swiggy, Zomato, Zepto
    city: str
    vehicle_type: str | None = None
    avg_hourly_income_inr: float
    gps_consent: bool = False


class OnboardingInsurerRequest(BaseModel):
    """Complete insurer/admin profile after Google OAuth signup."""

    full_name: str
    company_name: str
    job_title: str | None = None


class WorkerOnboardingUpsertRequest(BaseModel):
    """Upsert worker onboarding/profile fields after signup."""

    full_name: str
    phone: str | None = None
    platform_name: str
    city: str
    preferred_zone_id: str | None = None
    vehicle_type: str | None = None
    avg_hourly_income_inr: float
    gps_consent: bool = False
    bank_verified: bool = False


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Return the current authenticated user's profile and role.

    If the user has no profile yet (just signed up via Google OAuth),
    returns needs_onboarding=True so the frontend can redirect to
    the onboarding flow.
    """
    return user


@router.post("/complete-onboarding/worker")
async def complete_worker_onboarding(
    body: OnboardingWorkerRequest,
    user: dict = Depends(get_current_user),
):
    """Create profile + worker_profiles rows for a Google OAuth user
    who hasn't completed onboarding yet."""
    sb = get_supabase_admin()
    user_id = user["id"]

    # Check if profile already exists
    existing = (
        sb.table("profiles")
        .select("id")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if existing.data:  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile already exists. Use profile update endpoints instead.",
        )

    # Create profiles row
    sb.table("profiles").insert(
        {
            "id": user_id,
            "role": "worker",
            "full_name": body.full_name,
            "email": user["email"],
        }
    ).execute()

    # Create worker_profiles row
    sb.table("worker_profiles").insert(
        {
            "profile_id": user_id,
            "platform_name": body.platform_name,
            "city": body.city,
            "vehicle_type": body.vehicle_type,
            "avg_hourly_income_inr": body.avg_hourly_income_inr,
            "gps_consent": body.gps_consent,
        }
    ).execute()

    return {"status": "onboarding_complete", "role": "worker", "id": user_id}


@router.post("/complete-onboarding/insurer")
async def complete_insurer_onboarding(
    body: OnboardingInsurerRequest,
    user: dict = Depends(get_current_user),
):
    """Create profile + insurer_profiles rows for a Google OAuth user
    who registers as an insurer/admin."""
    sb = get_supabase_admin()
    user_id = user["id"]

    existing = (
        sb.table("profiles")
        .select("id")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if existing.data:  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile already exists.",
        )

    sb.table("profiles").insert(
        {
            "id": user_id,
            "role": "insurer_admin",
            "full_name": body.full_name,
            "email": user["email"],
        }
    ).execute()

    sb.table("insurer_profiles").insert(
        {
            "profile_id": user_id,
            "company_name": body.company_name,
            "job_title": body.job_title,
        }
    ).execute()

    return {
        "status": "onboarding_complete",
        "role": "insurer_admin",
        "id": user_id,
    }


@router.post("/onboarding/worker")
async def upsert_worker_onboarding(
    body: WorkerOnboardingUpsertRequest,
    user: dict = Depends(get_current_user),
):
    """Upsert worker-facing onboarding data for the authenticated user."""
    if user.get("role") == "insurer_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insurer admin accounts cannot be updated via worker onboarding.",
        )

    sb = get_supabase_admin()
    user_id = user["id"]

    sb.table("profiles").upsert(
        {
            "id": user_id,
            "role": "worker",
            "full_name": body.full_name,
            "email": user.get("email"),
            "phone": body.phone,
        },
        on_conflict="id",
    ).execute()

    existing_worker = (
        sb.table("worker_profiles")
        .select("profile_id")
        .eq("profile_id", user_id)
        .maybe_single()
        .execute()
    )

    worker_payload = {
        "profile_id": user_id,
        "platform_name": body.platform_name,
        "city": body.city,
        "preferred_zone_id": body.preferred_zone_id,
        "vehicle_type": body.vehicle_type,
        "avg_hourly_income_inr": body.avg_hourly_income_inr,
        "gps_consent": body.gps_consent,
        "bank_verified": body.bank_verified,
    }

    if existing_worker.data:  # type: ignore
        sb.table("worker_profiles").update(worker_payload).eq(
            "profile_id", user_id
        ).execute()
    else:
        sb.table("worker_profiles").insert(worker_payload).execute()

    return {
        "status": "onboarding_saved",
        "role": "worker",
        "id": user_id,
    }
