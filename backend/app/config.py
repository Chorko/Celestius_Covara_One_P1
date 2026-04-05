"""
Covara One - Application Configuration
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
    supabase_url: str = os.getenv(
        "SUPABASE_URL", os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
    )
    supabase_anon_key: str = os.getenv(
        "SUPABASE_ANON_KEY", os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
    )
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Gemini (backend-only)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

    # External APIs (legacy single-key names - still supported)
    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    tomtom_api_key: str = os.getenv("TOMTOM_API_KEY", "")
    news_api_key: str = os.getenv("NEWS_API_KEY", "")

    # KYC - Sandbox.co.in
    sandbox_kyc_api_key: str = os.getenv("SANDBOX_KYC_API_KEY", "")

    # Twilio
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_verify_service_sid: str = os.getenv("TWILIO_VERIFY_SERVICE_SID", "")
    twilio_whatsapp_from: str = os.getenv("TWILIO_WHATSAPP_FROM", "")

    # Mobile device-context signing
    device_context_hmac_secret: str = os.getenv("DEVICE_CONTEXT_HMAC_SECRET", "")

    # Event bus abstraction and Kafka adapter settings
    event_bus_backend: str = os.getenv("EVENT_BUS_BACKEND", "inmemory")
    event_bus_topic_prefix: str = os.getenv("EVENT_BUS_TOPIC_PREFIX", "covara")
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
    kafka_client_id: str = os.getenv("KAFKA_CLIENT_ID", "covara-backend")
    kafka_security_protocol: str = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
    event_bus_publish_on_write: bool = (
        os.getenv("EVENT_BUS_PUBLISH_ON_WRITE", "true").strip().lower() == "true"
    )
    event_bus_inline_consumer_enabled: bool = (
        os.getenv("EVENT_BUS_INLINE_CONSUMER_ENABLED", "true").strip().lower()
        == "true"
    )
    event_outbox_relay_batch_size: int = int(
        os.getenv("EVENT_OUTBOX_RELAY_BATCH_SIZE", "100")
    )
    event_outbox_relay_enabled: bool = (
        os.getenv("EVENT_OUTBOX_RELAY_ENABLED", "true").strip().lower() == "true"
    )
    event_outbox_relay_interval_seconds: int = int(
        os.getenv("EVENT_OUTBOX_RELAY_INTERVAL_SECONDS", "15")
    )
    event_outbox_max_retries: int = int(
        os.getenv("EVENT_OUTBOX_MAX_RETRIES", "10")
    )
    event_consumer_enabled: bool = (
        os.getenv("EVENT_CONSUMER_ENABLED", "true").strip().lower() == "true"
    )
    event_consumer_group_id: str = os.getenv(
        "EVENT_CONSUMER_GROUP_ID", "covara-event-consumers"
    )
    event_consumer_auto_offset_reset: str = os.getenv(
        "EVENT_CONSUMER_AUTO_OFFSET_RESET", "latest"
    )
    event_consumer_poll_timeout_ms: int = int(
        os.getenv("EVENT_CONSUMER_POLL_TIMEOUT_MS", "1000")
    )
    event_consumer_max_records: int = int(
        os.getenv("EVENT_CONSUMER_MAX_RECORDS", "100")
    )
    event_consumer_max_attempts: int = int(
        os.getenv("EVENT_CONSUMER_MAX_ATTEMPTS", "5")
    )

    # -- Dynamic API Key Discovery --
    # Instead of hardcoding N key fields, we scan env vars at runtime.
    # Just add WEATHER_API_KEY_1, WEATHER_API_KEY_2, ... to .env
    # and the system auto-discovers them. Works for any N.

    @staticmethod
    def get_api_keys(prefix: str) -> dict[str, str]:
        """
        Auto-discover all API keys matching {PREFIX}_API_KEY_* from env vars.

        Example:
            get_api_keys("WEATHER") -> {"1": "abc123", "2": "def456"}

        This means you never need to touch config.py to add a new provider.
        Just add WEATHER_API_KEY_4=xxx to .env and it's discovered.
        """
        keys = {}
        prefix_pattern = f"{prefix}_API_KEY_"
        for env_name, env_value in os.environ.items():
            if env_name.startswith(prefix_pattern) and env_value:
                slot = env_name[len(prefix_pattern):]  # e.g. "1", "2", "myapi"
                keys[slot] = env_value
        return keys

    @staticmethod
    def get_api_key(prefix: str, slot: str) -> str:
        """Get a single API key by prefix and slot. Returns '' if not found."""
        return os.getenv(f"{prefix}_API_KEY_{slot}", "")

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

