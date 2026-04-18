"""
Covara One — Twilio Service

Handles two completely separate Twilio products:

1. Twilio Verify     → OTP via SMS for phone verification & step-up auth
2. Twilio WhatsApp   → Worker notifications (claim alerts, payout status)

Both use the same Account SID + Auth Token from .env.
"""

from __future__ import annotations
import logging
from ..config import settings

logger = logging.getLogger("covara.twilio")

_mock_verify_overrides: set[str] = set()


def _normalize_phone(phone_number: str) -> str:
    return (phone_number or "").strip()


def _is_non_production_env() -> bool:
    return (settings.app_env or "development").strip().lower() not in {"production", "staging"}


def _is_twilio_trial_restriction_error(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code == 21608:
        return True

    message = str(exc).lower()
    if "21608" in message:
        return True
    return "trial" in message and "unverified" in message


def _get_client():
    """Create a Twilio REST client. Returns None if credentials missing."""
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.warning("Twilio credentials not configured — using mock mode")
        return None
    try:
        from twilio.rest import Client
        return Client(settings.twilio_account_sid, settings.twilio_auth_token)
    except ImportError:
        logger.error("twilio package not installed. Run: pip install twilio")
        return None


# ── OTP (Twilio Verify) ─────────────────────────────────────────────


def send_otp(phone_number: str) -> dict:
    """
    Send an OTP to the worker's phone via Twilio Verify (SMS).

    phone_number must be E.164 format: +919876543210

    Returns:
        {"success": True, "status": "pending", "mock": False}
        {"success": False, "error": "...", "mock": False}
        {"success": True, "status": "pending", "mock": True, "otp": "123456"}  ← dev mode
    """
    client = _get_client()
    service_sid = settings.twilio_verify_service_sid

    # ── MOCK MODE: no Twilio config ──
    if not client or not service_sid:
        mock_otp = "123456"
        logger.info(f"[MOCK] OTP for {phone_number}: {mock_otp}")
        return {
            "success": True,
            "status": "pending",
            "mock": True,
            "otp": mock_otp,
            "note": "Twilio not configured — use code 123456 in development",
        }

    try:
        verification = (
            client.verify.v2
            .services(service_sid)
            .verifications
            .create(to=phone_number, channel="sms")
        )
        _mock_verify_overrides.discard(_normalize_phone(phone_number))
        return {
            "success": True,
            "status": verification.status,  # "pending"
            "mock": False,
        }
    except Exception as e:
        if _is_non_production_env() and _is_twilio_trial_restriction_error(e):
            normalized_phone = _normalize_phone(phone_number)
            _mock_verify_overrides.add(normalized_phone)
            logger.warning(
                "Twilio trial restriction for %s; using mock OTP fallback in %s",
                phone_number,
                settings.app_env,
            )
            return {
                "success": True,
                "status": "pending",
                "mock": True,
                "otp": "123456",
                "note": "Twilio trial restriction detected — using mock OTP 123456",
            }

        logger.error(f"Twilio Verify send_otp failed for {phone_number}: {e}")
        return {"success": False, "error": str(e), "mock": False}


def verify_otp(phone_number: str, code: str) -> dict:
    """
    Check an OTP code entered by the worker.

    Returns:
        {"success": True,  "verified": True,  "status": "approved"}
        {"success": True,  "verified": False, "status": "pending"}
        {"success": False, "error": "..."}
    """
    client = _get_client()
    service_sid = settings.twilio_verify_service_sid

    normalized_phone = _normalize_phone(phone_number)

    # ── MOCK MODE ──
    if not client or not service_sid or normalized_phone in _mock_verify_overrides:
        is_valid = code == "123456"
        return {
            "success": True,
            "verified": is_valid,
            "status": "approved" if is_valid else "pending",
            "mock": True,
        }

    try:
        check = (
            client.verify.v2
            .services(service_sid)
            .verification_checks
            .create(to=phone_number, code=code)
        )
        return {
            "success": True,
            "verified": check.status == "approved",
            "status": check.status,
            "mock": False,
        }
    except Exception as e:
        logger.error(f"Twilio Verify check failed for {phone_number}: {e}")
        return {"success": False, "error": str(e), "mock": False}


# ── WhatsApp Notifications (Twilio Messaging) ────────────────────────

# Pre-built message templates for common worker events
MESSAGE_TEMPLATES = {
    "trigger_alert": (
        "⚠️ *Covara One Alert*\n\n"
        "{trigger_type} detected in your zone ({zone}).\n"
        "Your coverage is active. Stay safe! 🛡️"
    ),
    "claim_auto_approved": (
        "✅ *Claim Auto-Approved*\n\n"
        "Your claim for {trigger_type} has been automatically approved.\n"
        "Payout: *₹{amount}*\n"
        "Expected transfer: within 24 hours.\n\n"
        "Claim ID: {claim_id}"
    ),
    "claim_needs_review": (
        "🔍 *Claim Under Review*\n\n"
        "Your claim (ID: {claim_id}) is being reviewed by our team.\n"
        "We'll notify you within 4 hours."
    ),
    "claim_rejected": (
        "❌ *Claim Not Approved*\n\n"
        "Claim ID: {claim_id}\n"
        "Reason: {reason}\n\n"
        "Questions? Contact support@covara.one"
    ),
    "payout_sent": (
        "💰 *Payout Initiated*\n\n"
        "Amount: *₹{amount}*\n"
        "To: {bank_last4}\n"
        "Reference: {ref_id}\n\n"
        "Funds arrive in 24hrs. Thank you for being with Covara One! 🙏"
    ),
    "policy_renewal": (
        "🔔 *Policy Renewal Reminder*\n\n"
        "Your {plan} plan renews in *{days} days*.\n"
        "Premium: ₹{amount}/week\n\n"
        "You're covered. No action needed."
    ),
    "kyc_approved": (
        "✅ *KYC Verified*\n\n"
        "Your identity has been verified.\n"
        "You can now file claims up to ₹{limit}.\n\n"
        "Welcome to Covara One! 🎉"
    ),
}


def send_whatsapp(phone_number: str, message: str) -> dict:
    """
    Send a WhatsApp message to a worker via Twilio WhatsApp Sandbox.

    phone_number: E.164 format (+919876543210) — worker must have
                  joined sandbox by texting 'join blow-potatoes' to
                  +14155238886 first.

    Returns:
        {"success": True,  "sid": "SM...", "mock": False}
        {"success": False, "error": "...", "mock": False}
        {"success": True,  "mock": True}  ← dev mode
    """
    client = _get_client()
    from_number = settings.twilio_whatsapp_from

    # ── MOCK MODE ──
    if not client or not from_number:
        logger.info(f"[MOCK] WhatsApp to {phone_number}: {message[:80]}...")
        return {"success": True, "mock": True, "logged_message": message}

    try:
        msg = client.messages.create(
            from_=from_number,
            to=f"whatsapp:{phone_number}",
            body=message,
        )
        return {"success": True, "sid": msg.sid, "status": msg.status, "mock": False}
    except Exception as e:
        logger.error(f"Twilio WhatsApp send failed to {phone_number}: {e}")
        return {"success": False, "error": str(e), "mock": False}


def send_whatsapp_template(
    phone_number: str, template_key: str, **kwargs
) -> dict:
    """
    Send a pre-built template message.

    Example:
        send_whatsapp_template(
            "+919876543210",
            "claim_auto_approved",
            trigger_type="Heavy Rain",
            amount="2250",
            claim_id="CLM-0042"
        )
    """
    template = MESSAGE_TEMPLATES.get(template_key)
    if not template:
        return {"success": False, "error": f"Unknown template: {template_key}"}
    try:
        message = template.format(**kwargs)
    except KeyError as e:
        return {"success": False, "error": f"Missing template variable: {e}"}
    return send_whatsapp(phone_number, message)
