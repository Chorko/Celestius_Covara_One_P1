"""
Covara One — Gemini Analysis Service

Provides AI narrative summaries for manual claims.
Called by the backend to translate raw data points into actionable insights
for the insurance administrator.

Never exposes Gemini key to frontend.
"""

import google.generativeai as genai
from backend.app.config import settings
import traceback

# Optional: configure globally if settings has the key
if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)


async def generate_claim_narrative(
    claim_record: dict, pipeline_result: dict, worker_context: dict
) -> str:
    """
    Calls the Gemini API using google-generativeai to explain the claim risk posture
    for the insurance administrator in one structured, clear paragraph.
    """
    if not settings.gemini_api_key:
        return (
            "AI analysis unavailable: GEMINI_API_KEY not configured on server."
        )

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")

        # Safely extract context for the prompt
        reason = claim_record.get("claim_reason", "Not provided")
        mode = claim_record.get("claim_mode", "unknown")
        review_data = pipeline_result.get("review", {})

        fraud_val = review_data.get("fraud_score", "N/A")
        geo_val = review_data.get("geo_confidence_score", "N/A")
        comp_val = review_data.get("evidence_completeness_score", "N/A")
        decision = review_data.get("decision", "N/A")
        reasons = review_data.get("decision_reason") or "None listed"

        prompt = f"""
You are an AI assistant for an insurance administrator managing parametric
income-protection for gig workers in India.

Based on the pipeline metadata below, provide a highly concise 2-3 sentence summary
for the administrator reviewing this `{mode}` claim. Do not make payout decisions;
your job is purely to interpret the pipeline math and stated cause for the human reviewer.
Always maintain a serious, professional, and neutral tone. Do not use conversational greetings.

Worker states reason for claim: "{reason}"

System Pipeline Output:
- Fraud Score: {fraud_val}
- Geo-Confidence Score: {geo_val}
- Evidence Completeness: {comp_val}
- Computed Decision: {decision}
- Hold/Reject Reasons: {reasons}

Format: Return just the final paragraph explaining if the evidence and system scores support the worker's narrative or contradict it.
"""
        # We run this synchronously inside an executor in production, but SDK's generate_content_async is supported.
        # However, for 100% safety with the current standard package:
        response = await model.generate_content_async(prompt)

        # Sanitize whitespace
        if response and response.text:
            return response.text.strip()
        return "AI analysis returned empty."

    except Exception as e:
        print(f"Gemini AI Error: {e}")
        traceback.print_exc()
        return "AI analysis failed: Safe fallback engaged. Please rely on manual system scores."
