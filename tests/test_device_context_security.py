"""
Tests for signed mobile device-context verification.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import time

from backend.app.services.device_context_security import (
    compute_hmac_signature,
    verify_signed_device_context,
)


class TestDeviceContextSecurity:

    def test_absent_context_is_accepted_for_legacy_clients(self):
        result = verify_signed_device_context(
            raw_context=None,
            signature=None,
            timestamp=None,
            secret="test-secret",
        )

        assert result.verified is True
        assert result.reason == "absent"
        assert result.context == {}

    def test_signature_without_context_is_rejected(self):
        result = verify_signed_device_context(
            raw_context=None,
            signature="abc123",
            timestamp=str(int(time.time())),
            secret="test-secret",
        )

        assert result.verified is False
        assert result.reason == "signature_without_context"

    def test_invalid_context_json_is_rejected(self):
        result = verify_signed_device_context(
            raw_context="{bad-json",
            signature="abc123",
            timestamp=str(int(time.time())),
            secret="test-secret",
        )

        assert result.verified is False
        assert result.reason == "invalid_context_json"

    def test_valid_signature_passes(self):
        payload = {
            "is_rooted": False,
            "mock_location_detected": False,
            "developer_mode_active": False,
            "hardware_id": "dev-001",
        }
        raw_context = json.dumps(payload, separators=(",", ":"))
        timestamp = str(int(time.time()))
        secret = "test-secret"
        signature = compute_hmac_signature(raw_context, timestamp, secret)

        result = verify_signed_device_context(
            raw_context=raw_context,
            signature=signature,
            timestamp=timestamp,
            secret=secret,
            key_id="v1",
        )

        assert result.verified is True
        assert result.reason == "verified"
        # Alias mapping is applied for anti-spoofing engine compatibility.
        assert result.context["mock_location_enabled"] is False
        assert result.context["developer_mode"] is False
        assert result.context["hardware_id"] == "dev-001"

    def test_signature_mismatch_is_rejected(self):
        raw_context = json.dumps({"is_rooted": False})
        timestamp = str(int(time.time()))

        result = verify_signed_device_context(
            raw_context=raw_context,
            signature="0" * 64,
            timestamp=timestamp,
            secret="test-secret",
        )

        assert result.verified is False
        assert result.reason == "signature_mismatch"

    def test_stale_timestamp_is_rejected(self):
        raw_context = json.dumps({"is_rooted": False})
        old_timestamp = str(int(time.time()) - 3600)
        secret = "test-secret"
        signature = compute_hmac_signature(raw_context, old_timestamp, secret)

        result = verify_signed_device_context(
            raw_context=raw_context,
            signature=signature,
            timestamp=old_timestamp,
            secret=secret,
            max_skew_seconds=60,
        )

        assert result.verified is False
        assert result.reason == "stale_timestamp"
