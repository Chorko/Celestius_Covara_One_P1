"""
Covara One — Auth Dependencies & Role Gating

Provides FastAPI dependencies for:
- Extracting authenticated user from Supabase JWT (via Authorization header)
- Role-based access control (worker vs insurer_admin)

The frontend sends the Supabase access token in the Authorization header.
The backend verifies it against Supabase Auth and loads the user's profile/role.
"""

from fastapi import Depends, HTTPException, Request, status
from supabase import Client
from backend.app.supabase_client import get_supabase_admin, get_supabase_anon


async def get_current_user(request: Request) -> dict:
    """Extract and verify the authenticated user from the Supabase JWT.

    Expects: Authorization: Bearer <supabase_access_token>

    Returns a dict with at minimum:
        - id: str (auth.users UUID)
        - email: str
        - role: str ('worker' or 'insurer_admin') from profiles table
        - profile: dict (full profile row)
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Expected: Bearer <token>",
        )

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty access token.",
        )

    sb_anon: Client = get_supabase_anon()

    # Verify the JWT with Supabase Auth
    try:
        user_response = sb_anon.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
            )
        auth_user = user_response.user
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {exc}",
        )

    # Load the user's profile (role + metadata) from the profiles table
    # Profile lookup must use service-role client. The anon client is not bound
    # to the bearer token session in this backend context, so RLS can hide rows.
    sb_admin: Client = get_supabase_admin()
    profile_resp = (
        sb_admin.table("profiles")
        .select("*")
        .eq("id", str(auth_user.id))
        .maybe_single()
        .execute()
    )

    profile = getattr(profile_resp, "data", None) if profile_resp else None
    if not profile:
        # User exists in auth but has no profile yet — likely mid-onboarding
        return {
            "id": str(auth_user.id),
            "email": auth_user.email,
            "role": None,
            "profile": None,
            "needs_onboarding": True,
        }

    return {
        "id": str(auth_user.id),
        "email": auth_user.email,
        "role": profile.get("role"),
        "profile": profile,
        "needs_onboarding": False,
    }


def require_role(required_role: str):
    """Factory for role-gated dependencies.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("insurer_admin"))])
        def admin_endpoint(): ...
    """

    async def _check_role(user: dict = Depends(get_current_user)):
        if user.get("role") != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires role '{required_role}'. "
                f"Your role: '{user.get('role')}'.",
            )
        return user

    return _check_role


# Convenience shortcuts
require_worker = require_role("worker")
require_insurer_admin = require_role("insurer_admin")
