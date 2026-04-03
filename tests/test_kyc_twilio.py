"""
Tests for KYC service (mock mode) and Twilio service (mock mode).

These test the mock/fallback paths that work without live API credentials,
ensuring the code paths are exercised and the interfaces are correct.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from unittest.mock import patch
from backend.app.services.kyc_service import (
    aadhaar_generate_otp,
    aadhaar_verify_otp,
    verify_pan,
    verify_bank_account,
    compute_kyc_tier,
    KYC_TIER_LABELS,
    KYC_PAYOUT_LIMITS,
)
from backend.app.services.twilio_service import (
    send_otp,
    verify_otp,
    send_whatsapp,
    send_whatsapp_template,
    MESSAGE_TEMPLATES,
)


# ── KYC Tier Computation ─────────────────────────────────────────────

class TestKYCTiers:

    def test_tier_0_phone_only(self):
        profile = {"phone_verified": True}
        assert compute_kyc_tier(profile) == 0

    def test_tier_1_aadhaar_and_bank(self):
        profile = {"phone_verified": True, "aadhaar_verified": True, "bank_verified": True}
        assert compute_kyc_tier(profile) == 1

    def test_tier_2_full_kyc(self):
        profile = {
            "phone_verified": True,
            "aadhaar_verified": True,
            "bank_verified": True,
            "face_verified": True,
        }
        assert compute_kyc_tier(profile) == 2

    def test_tier_0_no_verification(self):
        assert compute_kyc_tier({}) == 0

    def test_payout_limits_increase_with_tier(self):
        assert KYC_PAYOUT_LIMITS[0] < KYC_PAYOUT_LIMITS[1] < KYC_PAYOUT_LIMITS[2]

    def test_all_tiers_have_labels(self):
        for tier in (0, 1, 2):
            assert tier in KYC_TIER_LABELS


# ── Twilio Mock Mode ─────────────────────────────────────────────────

class TestTwilioMock:
    """Tests force mock mode by patching _get_client to return None."""

    @patch("backend.app.services.twilio_service._get_client", return_value=None)
    def test_send_otp_mock(self, mock_client):
        result = send_otp("+919876543210")
        assert result["success"] is True
        assert result["status"] == "pending"
        assert result["mock"] is True

    @patch("backend.app.services.twilio_service._get_client", return_value=None)
    def test_verify_otp_mock_correct(self, mock_client):
        result = verify_otp("+919876543210", "123456")
        assert result["success"] is True
        assert result["verified"] is True

    @patch("backend.app.services.twilio_service._get_client", return_value=None)
    def test_verify_otp_mock_wrong_code(self, mock_client):
        result = verify_otp("+919876543210", "000000")
        assert result["success"] is True
        assert result["verified"] is False

    @patch("backend.app.services.twilio_service._get_client", return_value=None)
    def test_send_whatsapp_mock(self, mock_client):
        result = send_whatsapp("+919876543210", "Test message")
        assert result["success"] is True
        assert result["mock"] is True

    @patch("backend.app.services.twilio_service._get_client", return_value=None)
    def test_template_claim_approved(self, mock_client):
        result = send_whatsapp_template(
            "+919876543210",
            "claim_auto_approved",
            trigger_type="Heavy Rain",
            amount="2250",
            claim_id="CLM-0042",
        )
        assert result["success"] is True

    def test_template_unknown_key(self):
        result = send_whatsapp_template("+919876543210", "nonexistent_template")
        assert result["success"] is False
        assert "Unknown template" in result["error"]

    def test_all_templates_exist(self):
        expected = [
            "trigger_alert", "claim_auto_approved", "claim_needs_review",
            "claim_rejected", "payout_sent", "policy_renewal", "kyc_approved",
        ]
        for key in expected:
            assert key in MESSAGE_TEMPLATES, f"Missing template: {key}"


# ── KYC Mock Mode (use asyncio.run for compat) ───────────────────────

class TestKYCMock:
    """Force mock by patching _mock_mode to return True."""

    @patch("backend.app.services.kyc_service._mock_mode", return_value=True)
    def test_aadhaar_otp_mock(self, mock_fn):
        result = asyncio.run(aadhaar_generate_otp("999941057058"))
        assert result["success"] is True
        assert result.get("mock") is True
        assert result.get("reference_id") is not None

    @patch("backend.app.services.kyc_service._mock_mode", return_value=True)
    def test_aadhaar_verify_mock_correct(self, mock_fn):
        result = asyncio.run(aadhaar_verify_otp("MOCK_REF_12345", "123456"))
        assert result["success"] is True
        assert result["verified"] is True
        assert result["identity"]["name"] == "Test Worker"

    @patch("backend.app.services.kyc_service._mock_mode", return_value=True)
    def test_aadhaar_verify_mock_wrong_otp(self, mock_fn):
        result = asyncio.run(aadhaar_verify_otp("MOCK_REF_12345", "000000"))
        assert result["verified"] is False

    @patch("backend.app.services.kyc_service._mock_mode", return_value=True)
    def test_pan_verify_mock(self, mock_fn):
        result = asyncio.run(verify_pan("ABCDE1234F"))
        assert result["success"] is True
        assert result["verified"] is True

    @patch("backend.app.services.kyc_service._mock_mode", return_value=True)
    def test_bank_verify_mock(self, mock_fn):
        result = asyncio.run(verify_bank_account("1234567890", "SBIN0001234"))
        assert result["success"] is True
        assert result["verified"] is True
        assert result.get("name_at_bank") is not None
