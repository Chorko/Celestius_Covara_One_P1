import importlib
from typing import Any

import pytest


_BASE_ENV: dict[str, str] = {
    "APP_ENV": "development",
    "STRICT_ENV_VALIDATION": "false",
    "SUPABASE_URL": "",
    "SUPABASE_ANON_KEY": "",
    "SUPABASE_SERVICE_ROLE_KEY": "",
    "NEXT_PUBLIC_SUPABASE_URL": "",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY": "",
    "DEVICE_CONTEXT_HMAC_SECRET": "",
    "PAYOUT_PROVIDER": "simulated_gateway",
    "PAYOUT_PROVIDER_API_BASE_URL": "",
    "PAYOUT_PROVIDER_API_KEY": "",
    "PAYOUT_PROVIDER_WEBHOOK_SECRET": "",
    "EVENT_BUS_BACKEND": "inmemory",
    "KAFKA_BOOTSTRAP_SERVERS": "",
}


def _reload_settings_module(monkeypatch: pytest.MonkeyPatch, **overrides: Any):
    env_values = dict(_BASE_ENV)
    for key, value in overrides.items():
        env_values[key] = str(value)

    for key, value in env_values.items():
        monkeypatch.setenv(key, value)

    import backend.app.config as config_module

    return importlib.reload(config_module)


def test_non_strict_validation_requires_only_core_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    config_module = _reload_settings_module(
        monkeypatch,
        APP_ENV="test",
        STRICT_ENV_VALIDATION="false",
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_ANON_KEY="anon",
        SUPABASE_SERVICE_ROLE_KEY="service-role",
    )

    settings = config_module.Settings()
    assert settings.is_strict_env_validation_enabled() is False
    assert settings.validate() == []


def test_strict_validation_requires_device_secret_and_non_default_webhook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_module = _reload_settings_module(
        monkeypatch,
        APP_ENV="production",
        STRICT_ENV_VALIDATION="true",
        SUPABASE_URL="https://prod.supabase.co",
        SUPABASE_ANON_KEY="anon",
        SUPABASE_SERVICE_ROLE_KEY="service-role",
        PAYOUT_PROVIDER_WEBHOOK_SECRET="dev-payout-webhook-secret",
    )

    settings = config_module.Settings()
    missing = settings.validate()

    assert "DEVICE_CONTEXT_HMAC_SECRET" in missing
    assert any(
        "PAYOUT_PROVIDER_WEBHOOK_SECRET" in value and "non-default" in value
        for value in missing
    )


def test_strict_validation_requires_kafka_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    config_module = _reload_settings_module(
        monkeypatch,
        APP_ENV="production",
        STRICT_ENV_VALIDATION="true",
        SUPABASE_URL="https://prod.supabase.co",
        SUPABASE_ANON_KEY="anon",
        SUPABASE_SERVICE_ROLE_KEY="service-role",
        DEVICE_CONTEXT_HMAC_SECRET="device-secret",
        PAYOUT_PROVIDER_WEBHOOK_SECRET="prod-webhook-secret",
        EVENT_BUS_BACKEND="kafka",
    )

    settings = config_module.Settings()
    missing = settings.validate()

    assert any("KAFKA_BOOTSTRAP_SERVERS" in value for value in missing)


def test_strict_validation_requires_http_provider_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_module = _reload_settings_module(
        monkeypatch,
        APP_ENV="production",
        STRICT_ENV_VALIDATION="true",
        SUPABASE_URL="https://prod.supabase.co",
        SUPABASE_ANON_KEY="anon",
        SUPABASE_SERVICE_ROLE_KEY="service-role",
        DEVICE_CONTEXT_HMAC_SECRET="device-secret",
        PAYOUT_PROVIDER="http_gateway",
        PAYOUT_PROVIDER_WEBHOOK_SECRET="prod-webhook-secret",
    )

    settings = config_module.Settings()
    missing = settings.validate()

    assert any("PAYOUT_PROVIDER_API_BASE_URL" in value for value in missing)
    assert any("PAYOUT_PROVIDER_API_KEY" in value for value in missing)


def test_payout_provider_http_missing_credentials_raises_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reload_settings_module(
        monkeypatch,
        APP_ENV="production",
        STRICT_ENV_VALIDATION="true",
        SUPABASE_URL="https://prod.supabase.co",
        SUPABASE_ANON_KEY="anon",
        SUPABASE_SERVICE_ROLE_KEY="service-role",
        DEVICE_CONTEXT_HMAC_SECRET="device-secret",
        PAYOUT_PROVIDER="http_gateway",
        PAYOUT_PROVIDER_WEBHOOK_SECRET="prod-webhook-secret",
    )

    import backend.app.services.payout_provider as payout_provider

    payout_provider = importlib.reload(payout_provider)

    with pytest.raises(RuntimeError):
        payout_provider.get_payout_provider("http_gateway")


def test_payout_provider_http_missing_credentials_falls_back_when_not_strict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reload_settings_module(
        monkeypatch,
        APP_ENV="test",
        STRICT_ENV_VALIDATION="false",
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_ANON_KEY="anon",
        SUPABASE_SERVICE_ROLE_KEY="service-role",
        PAYOUT_PROVIDER="http_gateway",
        PAYOUT_PROVIDER_WEBHOOK_SECRET="test-webhook-secret",
    )

    import backend.app.services.payout_provider as payout_provider

    payout_provider = importlib.reload(payout_provider)
    adapter = payout_provider.get_payout_provider("http_gateway")

    assert isinstance(adapter, payout_provider.SimulatedGatewayProviderAdapter)
