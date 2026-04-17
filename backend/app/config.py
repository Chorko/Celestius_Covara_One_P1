"""
Covara One - Application Configuration
Loads environment variables for Supabase, Gemini, and app settings.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


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
    sandbox_kyc_base_url: str = os.getenv("SANDBOX_KYC_BASE_URL", "https://api.sandbox.co.in")

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

    # Ops SLO thresholds (used by /ops/status and /ops/slo surfaces)
    ops_slo_outbox_dead_letter_max: int = int(
        os.getenv("OPS_SLO_OUTBOX_DEAD_LETTER_MAX", "0")
    )
    ops_slo_consumer_dead_letter_max: int = int(
        os.getenv("OPS_SLO_CONSUMER_DEAD_LETTER_MAX", "0")
    )
    ops_slo_review_overdue_max: int = int(
        os.getenv("OPS_SLO_REVIEW_OVERDUE_MAX", "10")
    )
    ops_slo_review_unassigned_max: int = int(
        os.getenv("OPS_SLO_REVIEW_UNASSIGNED_MAX", "20")
    )
    ops_slo_payout_failures_max: int = int(
        os.getenv("OPS_SLO_PAYOUT_FAILURES_MAX", "0")
    )
    ops_slo_payout_manual_review_max: int = int(
        os.getenv("OPS_SLO_PAYOUT_MANUAL_REVIEW_MAX", "25")
    )

    # Rule/model governance defaults (used when registry tables are unavailable)
    default_rule_version_key: str = os.getenv(
        "DEFAULT_RULE_VERSION_KEY", "ruleset_2026_04_12"
    )
    default_model_version_key: str = os.getenv(
        "DEFAULT_MODEL_VERSION_KEY", "fraud_model_heuristic_v1"
    )
    version_rollout_subject_salt: str = os.getenv(
        "VERSION_ROLLOUT_SUBJECT_SALT", "covara-rollout"
    )

    # Review workflow SLA controls
    review_sla_hours: int = int(os.getenv("REVIEW_SLA_HOURS", "24"))
    review_sla_due_soon_hours: int = int(
        os.getenv("REVIEW_SLA_DUE_SOON_HOURS", "4")
    )

    # Payout provider settings
    payout_provider_key: str = os.getenv("PAYOUT_PROVIDER", "simulated_gateway")
    payout_provider_api_base_url: str = os.getenv("PAYOUT_PROVIDER_API_BASE_URL", "")
    payout_provider_api_key: str = os.getenv("PAYOUT_PROVIDER_API_KEY", "")
    payout_provider_webhook_secret: str = os.getenv(
        "PAYOUT_PROVIDER_WEBHOOK_SECRET", "dev-payout-webhook-secret"
    )
    payout_provider_timeout_seconds: int = int(
        os.getenv("PAYOUT_PROVIDER_TIMEOUT_SECONDS", "10")
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
    strict_env_validation: str = os.getenv("STRICT_ENV_VALIDATION", "auto")
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

        def is_blank(value: str | None) -> bool:
            return not bool((value or "").strip())

        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_anon_key:
            missing.append("SUPABASE_ANON_KEY")
        if not self.supabase_service_role_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")

        strict_mode = self.is_strict_env_validation_enabled()
        if strict_mode:
            if is_blank(self.device_context_hmac_secret):
                missing.append("DEVICE_CONTEXT_HMAC_SECRET")

            provider_key = (self.payout_provider_key or "").strip().lower()
            http_provider_keys = {"http_gateway", "razorpayx", "cashfree", "provider_http"}
            if provider_key in http_provider_keys:
                if is_blank(self.payout_provider_api_base_url):
                    missing.append(
                        "PAYOUT_PROVIDER_API_BASE_URL (required for PAYOUT_PROVIDER=http_gateway)"
                    )
                if is_blank(self.payout_provider_api_key):
                    missing.append(
                        "PAYOUT_PROVIDER_API_KEY (required for PAYOUT_PROVIDER=http_gateway)"
                    )

            webhook_secret = (self.payout_provider_webhook_secret or "").strip()
            if not webhook_secret or webhook_secret == "dev-payout-webhook-secret":
                missing.append(
                    "PAYOUT_PROVIDER_WEBHOOK_SECRET (must be non-default in strict mode)"
                )

            if (self.event_bus_backend or "").strip().lower() == "kafka" and is_blank(
                self.kafka_bootstrap_servers
            ):
                missing.append(
                    "KAFKA_BOOTSTRAP_SERVERS (required for EVENT_BUS_BACKEND=kafka)"
                )

        return missing

    def is_strict_env_validation_enabled(self) -> bool:
        mode = (self.strict_env_validation or "auto").strip().lower()
        if mode in _TRUE_VALUES:
            return True
        if mode in _FALSE_VALUES:
            return False
        return (self.app_env or "").strip().lower() in {"production", "staging"}


settings = Settings()

