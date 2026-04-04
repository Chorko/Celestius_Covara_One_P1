"""
Covara One — Payment Gateway Mock Service

In a production environment, this would integrate with RazorpayX or Cashfree Payouts.
For this hackathon, we simulate network latency and return mock success transaction IDs
for UPI payouts to riders.
"""

import asyncio
import uuid
import logging
from datetime import datetime

logger = logging.getLogger("covara.payment_mock")

async def mock_upi_payout(profile_id: str, amount: float, upi_id: str) -> dict:
    """
    Simulates a UPI payout via RazorpayX or Cashfree.
    """
    logger.info(f"Initiating mock payout of ₹{amount} to {upi_id} for {profile_id}")
    
    # Simulate network latency
    await asyncio.sleep(0.5)
    
    transaction_id = f"pay_{uuid.uuid4().hex[:14]}"
    now = datetime.utcnow().isoformat() + "Z"
    
    status = "processed"
    if "fail" in upi_id.lower():
        status = "failed"
        
    return {
        "status": status,
        "transaction_id": transaction_id,
        "amount": amount,
        "currency": "INR",
        "beneficiary": upi_id,
        "processed_at": now,
        "gateway": "mock_razorpay",
    }
