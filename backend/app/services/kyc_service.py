"""
Covara One — KYC Service (Sandbox.co.in)

IRDAI-compliant progressive KYC using Sandbox.co.in APIs.

Tier 0: Google OAuth + Twilio Phone OTP  (done at registration)
Tier 1: Aadhaar OTP eKYC + Bank Account  (done at policy activation)
Tier 2: Face match + doc OCR             (done for high-risk claims)

API: https://api.sandbox.co.in
Auth: Bearer token using SANDBOX_KYC_API_KEY from .env

IRDAI compliance note:
  - Our premium range (₹20-50/week = ~₹1,040-2,600/year) qualifies
    for Simplified Due Diligence (SDD) under the micro-insurance
    relaxation for policies ≤ ₹10,000 annual premium.
  - Aadhaar OTP eKYC is UIDAI-backed and IRDAI-accepted.
  - PAN is NOT mandatory at our premium/payout level.
    (Required only for premiums >₹50,000 or payouts >₹1,00,000)
"""

from __future__ import annotations
import logging
import httpx
from ..config import settings

logger = logging.getLogger("covara.kyc")

SANDBOX_BASE_URL = "https://api.sandbox.co.in"


def _get_headers() -> dict:
    """Build auth headers for Sandbox.co.in API."""
    return {
        "Authorization": settings.sandbox_kyc_api_key,
        "x-api-key": settings.sandbox_kyc_api_key,
        "x-api-version": "1.0",
        "Content-Type": "application/json",
    }


def _mock_mode() -> bool:
    return not bool(settings.sandbox_kyc_api_key)


# ── TIER 1A: Aadhaar OTP eKYC ────────────────────────────────────────


async def aadhaar_generate_otp(aadhaar_number: str) -> dict:
    """
    Step 1: Generate OTP for Aadhaar eKYC.
    The OTP goes to the mobile number registered with UIDAI.

    Args:
        aadhaar_number: 12-digit Aadhaar number

    Returns:
        {"success": True,  "reference_id": "...", "message": "OTP sent"}
        {"success": False, "error": "..."}
    """
    if _mock_mode():
        logger.info(f"[MOCK] Aadhaar OTP generated for {aadhaar_number[-4:]}")
        return {
            "success": True,
            "reference_id": "MOCK_REF_12345",
            "message": "OTP sent to Aadhaar-linked mobile (MOCK)",
            "mock": True,
        }

    url = f"{SANDBOX_BASE_URL}/kyc/aadhaar/okyc/otp"
    payload = {"@entity": "in.co.sandbox.kyc.aadhaar.okyc.otp.request", "aadhaar_number": aadhaar_number}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = client.post(url, json=payload, headers=_get_headers())
            resp.raise_for_status()
            data = resp.json()
        return {
            "success": True,
            "reference_id": data.get("data", {}).get("reference_id"),
            "message": data.get("message", "OTP sent"),
            "mock": False,
        }
    except Exception as e:
        logger.error(f"Aadhaar OTP generation failed: {e}")
        return {"success": False, "error": str(e), "mock": False}


async def aadhaar_verify_otp(reference_id: str, otp: str, share_code: str = "1234") -> dict:
    """
    Step 2: Verify OTP and get Aadhaar details from UIDAI.

    Returns verified identity data:
    {
        "name": "Rajan Kumar",
        "dob": "1992-05-15",
        "gender": "M",
        "address": "...",
        "masked_aadhaar": "XXXX-XXXX-1234",
        "photo": "<base64>"
    }
    """
    if _mock_mode():
        if otp == "123456":
            return {
                "success": True,
                "verified": True,
                "identity": {
                    "name": "Test Worker",
                    "dob": "1995-01-01",
                    "gender": "M",
                    "address": "Mumbai, Maharashtra",
                    "masked_aadhaar": "XXXX-XXXX-9999",
                    "care_of": "S/O Test Father",
                },
                "mock": True,
            }
        return {"success": True, "verified": False, "error": "Invalid OTP (MOCK)", "mock": True}

    url = f"{SANDBOX_BASE_URL}/kyc/aadhaar/okyc/otp/verify"
    payload = {
        "@entity": "in.co.sandbox.kyc.aadhaar.okyc.request",
        "reference_id": reference_id,
        "otp": otp,
        "share_code": share_code,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = client.post(url, json=payload, headers=_get_headers())
            resp.raise_for_status()
            data = resp.json()
        kyc_data = data.get("data", {})
        return {
            "success": True,
            "verified": True,
            "identity": {
                "name": kyc_data.get("name"),
                "dob": kyc_data.get("date_of_birth"),
                "gender": kyc_data.get("gender"),
                "address": kyc_data.get("address", {}).get("country"),
                "masked_aadhaar": kyc_data.get("maskedAadhaarNumber"),
                "care_of": kyc_data.get("care_of"),
            },
            "mock": False,
        }
    except Exception as e:
        logger.error(f"Aadhaar OTP verify failed: {e}")
        return {"success": False, "error": str(e), "mock": False}


# ── TIER 1B: PAN Verification (optional, collected for record) ───────


async def verify_pan(pan_number: str) -> dict:
    """
    Verify PAN card against NSDL/Income Tax database.

    Note: PAN is NOT mandatory at our premium/payout level under IRDAI.
    We collect it optionally and verify for record-keeping.
    PAN becomes mandatory only for payouts > ₹1,00,000 (IRDAI AML rule).
    """
    if _mock_mode():
        return {
            "success": True,
            "verified": True,
            "name": "TEST WORKER",
            "pan_type": "individual",
            "status": "active",
            "mock": True,
        }

    url = f"{SANDBOX_BASE_URL}/pans/{pan_number}/verify"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = client.get(url, headers=_get_headers())
            resp.raise_for_status()
            data = resp.json()
        pan_data = data.get("data", {})
        return {
            "success": True,
            "verified": pan_data.get("registered_name") is not None,
            "name": pan_data.get("registered_name"),
            "pan_type": pan_data.get("type"),
            "status": pan_data.get("pan_status"),
            "mock": False,
        }
    except Exception as e:
        logger.error(f"PAN verify failed for {pan_number}: {e}")
        return {"success": False, "error": str(e), "mock": False}


# ── TIER 1B: Bank Account Verification (required for payout) ─────────


async def verify_bank_account(account_number: str, ifsc: str) -> dict:
    """
    Verify bank account ownership via penny-less verification.
    REQUIRED before any payout disbursement.

    Returns:
        {"success": True, "verified": True, "name_at_bank": "RAJAN KUMAR"}
        {"success": False, "error": "Account not found"}
    """
    if _mock_mode():
        return {
            "success": True,
            "verified": True,
            "name_at_bank": "TEST WORKER",
            "account_number": account_number,
            "ifsc": ifsc,
            "bank_name": "State Bank of India (MOCK)",
            "mock": True,
        }

    url = f"{SANDBOX_BASE_URL}/bank/{account_number}/verify"
    payload = {"ifsc": ifsc}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = client.post(url, json=payload, headers=_get_headers())
            resp.raise_for_status()
            data = resp.json()
        bank_data = data.get("data", {})
        return {
            "success": True,
            "verified": bank_data.get("account_exists", False),
            "name_at_bank": bank_data.get("name_at_bank"),
            "bank_name": bank_data.get("bank_name"),
            "account_number": account_number,
            "ifsc": ifsc,
            "mock": False,
        }
    except Exception as e:
        logger.error(f"Bank verify failed for {account_number}: {e}")
        return {"success": False, "error": str(e), "mock": False}


# ── KYC TIER HELPER ─────────────────────────────────────────────────


def compute_kyc_tier(worker_profile: dict) -> int:
    """
    Compute current KYC tier from worker profile fields.

    Tier 0: Google OAuth + phone verified
    Tier 1: Aadhaar verified + bank account verified
    Tier 2: Face/doc verified (for high-risk / high-value claims)
    """
    phone_verified = bool(worker_profile.get("phone_verified"))
    aadhaar_verified = bool(worker_profile.get("aadhaar_verified"))
    bank_verified = bool(worker_profile.get("bank_verified"))
    face_verified = bool(worker_profile.get("face_verified"))

    if face_verified and aadhaar_verified and bank_verified:
        return 2
    if aadhaar_verified and bank_verified:
        return 1
    if phone_verified:
        return 0
    return 0


KYC_TIER_LABELS = {
    0: "Basic (Phone Verified)",
    1: "Standard (Identity Verified)",
    2: "Enhanced (Full KYC)",
}

KYC_PAYOUT_LIMITS = {
    0: 0,        # Cannot receive payouts until Tier 1
    1: 50000,    # Up to ₹50,000 per claim
    2: 100000,   # Up to ₹1,00,000 per claim
}
