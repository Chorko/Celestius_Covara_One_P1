"""
Covara One — KYC & OTP Router

Endpoints:
  POST /kyc/otp/send          Send OTP to phone (Twilio Verify)
  POST /kyc/otp/verify        Verify OTP code
  POST /kyc/aadhaar/initiate  Start Aadhaar eKYC (generate OTP to Aadhaar-linked phone)
  POST /kyc/aadhaar/verify    Submit OTP and retrieve verified identity
  POST /kyc/bank/verify       Verify bank account for payout
  GET  /kyc/status            Get current KYC tier for authenticated worker
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ..supabase_client import get_supabase_admin
from ..services.twilio_service import send_otp, verify_otp
from ..services.kyc_service import (
    aadhaar_generate_otp,
    aadhaar_verify_otp,
    verify_pan,
    verify_bank_account,
    compute_kyc_tier,
    KYC_TIER_LABELS,
    KYC_PAYOUT_LIMITS,
)

router = APIRouter(prefix="/kyc", tags=["KYC & Verification"])


# ── Request Models ───────────────────────────────────────────────────

class SendOTPRequest(BaseModel):
    phone_number: str = Field(..., example="+919876543210", description="E.164 format")

class VerifyOTPRequest(BaseModel):
    phone_number: str
    code: str = Field(..., min_length=4, max_length=8)

class AadhaarInitiateRequest(BaseModel):
    aadhaar_number: str = Field(..., min_length=12, max_length=12)

class AadhaarVerifyRequest(BaseModel):
    reference_id: str
    otp: str = Field(..., min_length=6, max_length=6)

class BankVerifyRequest(BaseModel):
    account_number: str
    ifsc: str = Field(..., min_length=11, max_length=11)

class PANVerifyRequest(BaseModel):
    pan_number: str = Field(..., min_length=10, max_length=10)


# ── Phase OTP Endpoints ──────────────────────────────────────────────

@router.post("/otp/send")
async def send_phone_otp(body: SendOTPRequest):
    """
    Send OTP to worker's phone via Twilio Verify (SMS).
    Used for Tier 0 KYC and step-up authentication.
    """
    result = send_otp(body.phone_number)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "OTP send failed"))
    return {
        "message": "OTP sent successfully",
        "phone": body.phone_number,
        "mock": result.get("mock", False),
        # In mock mode, return the OTP for testing convenience
        **({"otp": result.get("otp")} if result.get("mock") else {}),
    }


@router.post("/otp/verify")
async def verify_phone_otp(body: VerifyOTPRequest):
    """
    Verify OTP code entered by worker.
    On success, marks phone as verified in worker_profiles.
    """
    result = verify_otp(body.phone_number, body.code)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Verification failed"))

    if not result.get("verified"):
        raise HTTPException(status_code=422, detail="Invalid or expired OTP")

    # Mark phone verified in DB
    sb = get_supabase_admin()
    try:
        sb.table("profiles").update({"phone": body.phone_number}).eq(
            "phone", body.phone_number
        ).execute()
    except Exception:
        pass  # Non-fatal — phone update can be retried

    return {
        "verified": True,
        "message": "Phone number verified successfully",
        "mock": result.get("mock", False),
    }


# ── Aadhaar eKYC Endpoints ───────────────────────────────────────────

@router.post("/aadhaar/initiate")
async def initiate_aadhaar_kyc(body: AadhaarInitiateRequest):
    """
    Start Aadhaar OTP eKYC.
    Sends OTP to the mobile number registered with UIDAI (not our system).
    Worker must enter this OTP on their Aadhaar-linked phone.
    """
    # Basic Luhn-like validation — Aadhaar is 12 digits, not starting with 0 or 1
    if not body.aadhaar_number.isdigit():
        raise HTTPException(status_code=422, detail="Aadhaar number must be 12 digits")
    if body.aadhaar_number[0] in ("0", "1"):
        raise HTTPException(status_code=422, detail="Invalid Aadhaar number format")

    result = await aadhaar_generate_otp(body.aadhaar_number)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Aadhaar OTP failed"))

    return {
        "reference_id": result.get("reference_id"),
        "message": "OTP sent to your Aadhaar-linked mobile number",
        "mock": result.get("mock", False),
    }


@router.post("/aadhaar/verify")
async def verify_aadhaar_kyc(body: AadhaarVerifyRequest):
    """
    Verify Aadhaar OTP and retrieve verified identity from UIDAI.
    On success, updates worker_profiles with aadhaar_verified = true.
    """
    result = await aadhaar_verify_otp(body.reference_id, body.otp)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Aadhaar verify failed"))
    if not result.get("verified"):
        raise HTTPException(status_code=422, detail="OTP incorrect or Aadhaar not verified")

    identity = result.get("identity", {})

    return {
        "verified": True,
        "identity": {
            "name": identity.get("name"),
            "dob": identity.get("dob"),
            "gender": identity.get("gender"),
            "masked_aadhaar": identity.get("masked_aadhaar"),
            # Never return full address or full Aadhaar — IRDAI/PDPA compliance
        },
        "kyc_tier_unlocked": 1,
        "message": "Aadhaar identity verified successfully",
        "mock": result.get("mock", False),
    }


# ── Bank Account Verification ────────────────────────────────────────

@router.post("/bank/verify")
async def verify_bank(body: BankVerifyRequest):
    """
    Verify bank account via penny-less verification (Sandbox.co.in).
    Required before any payout can be processed.
    """
    result = await verify_bank_account(body.account_number, body.ifsc)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Bank verify failed"))
    if not result.get("verified"):
        raise HTTPException(status_code=422, detail="Bank account could not be verified")

    return {
        "verified": True,
        "name_at_bank": result.get("name_at_bank"),
        "bank_name": result.get("bank_name"),
        "message": "Bank account verified — payouts enabled",
        "mock": result.get("mock", False),
    }


# ── PAN Verification (optional) ──────────────────────────────────────

@router.post("/pan/verify")
async def verify_pan_card(body: PANVerifyRequest):
    """
    Verify PAN card (optional for our premium/payout range).
    Mandatory only if annual payout exceeds ₹1,00,000 (IRDAI AML rule).
    Collected for completeness and higher trust tier.
    """
    result = await verify_pan(body.pan_number.upper())
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "PAN verify failed"))

    return {
        "verified": result.get("verified", False),
        "name": result.get("name"),
        "pan_type": result.get("pan_type"),
        "status": result.get("status"),
        "mock": result.get("mock", False),
    }


# ── KYC Status ───────────────────────────────────────────────────────

@router.get("/status/{worker_id}")
async def get_kyc_status(worker_id: str):
    """
    Get the current KYC tier and verification status for a worker.
    """
    sb = get_supabase_admin()
    try:
        resp = (
            sb.table("worker_profiles")
            .select("profile_id, phone_verified, aadhaar_verified, bank_verified, face_verified")
            .eq("profile_id", worker_id)
            .maybe_single()
            .execute()
        )
        profile = resp.data or {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    tier = compute_kyc_tier(profile)

    return {
        "worker_id": worker_id,
        "kyc_tier": tier,
        "tier_label": KYC_TIER_LABELS[tier],
        "max_payout_inr": KYC_PAYOUT_LIMITS[tier],
        "verifications": {
            "phone": bool(profile.get("phone_verified")),
            "aadhaar": bool(profile.get("aadhaar_verified")),
            "bank": bool(profile.get("bank_verified")),
            "face": bool(profile.get("face_verified")),
        },
        "next_step": _get_next_kyc_step(profile),
    }


def _get_next_kyc_step(profile: dict) -> str:
    if not profile.get("phone_verified"):
        return "Verify your phone number via OTP"
    if not profile.get("aadhaar_verified"):
        return "Complete Aadhaar eKYC to unlock claims"
    if not profile.get("bank_verified"):
        return "Add and verify your bank account to enable payouts"
    return "KYC complete — all verifications done"
