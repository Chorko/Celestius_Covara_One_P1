"""
DEVTrails — Application Configuration
Loads environment variables for Supabase, Gemini, and app settings.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment."""

    # Supabase
    supabase_url: str = os.getenv("SUPABASE_URL", os.getenv("NEXT_PUBLIC_SUPABASE_URL", ""))
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", ""))
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Gemini (backend-only)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

    # External APIs (anti-spoofing & trigger validation)
    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    tomtom_api_key: str = os.getenv("TOMTOM_API_KEY", "")
    news_api_key: str = os.getenv("NEWS_API_KEY", "")

    # App
    app_env: str = os.getenv("APP_ENV", "development")
    cors_origins: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
        # Ensure we cover all bases for local e2e testing
        parsed = [o.strip() for o in origins.split(",")]
        parsed.extend(["http://localhost:3000", "http://127.0.0.1:3000"])
        object.__setattr__(self, "cors_origins", list(set(parsed)))

    def validate(self) -> list[str]:
        """Return list of missing critical config vars."""
        missing = []
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_anon_key:
            missing.append("SUPABASE_ANON_KEY")
        if not self.supabase_service_role_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        return missing


settings = Settings()
