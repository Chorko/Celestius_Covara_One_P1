"""
DEVTrails — Supabase Client Initialization

Two clients are provided:
- supabase_anon: uses anon key — safe for operations that respect RLS.
- supabase_admin: uses service role key — bypasses RLS for backend-only
  operations like seeding data, admin queries, and server-side claim processing.

IMPORTANT: supabase_admin must NEVER be exposed to the frontend.
"""

from supabase import create_client, Client
from backend.app.config import settings


def _create_client(key: str) -> Client:
    """Create a Supabase client with the given key."""
    if not settings.supabase_url or not key:
        raise RuntimeError(
            "Supabase URL or key not configured. "
            "Check .env file and SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY."
        )
    return create_client(settings.supabase_url, key)


def get_supabase_anon() -> Client:
    """Return a Supabase client using the anon/publishable key (RLS-aware)."""
    return _create_client(settings.supabase_anon_key)


def get_supabase_admin() -> Client:
    """Return a Supabase client using the service role key (bypasses RLS).
    Use only in backend services — never expose to frontend."""
    return _create_client(settings.supabase_service_role_key)
