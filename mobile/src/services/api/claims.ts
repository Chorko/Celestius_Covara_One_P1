import { getMobileEnv } from "../../config/env";
import {
  ClaimSubmissionError,
  type SubmitClaimPayload,
  type SubmitClaimResult,
} from "../../types/claims";
import { postJson, HttpRequestError } from "./http";
import { buildSignedDeviceContext } from "../security/deviceContext";

export interface SubmitSignedClaimInput extends SubmitClaimPayload {
  accessToken: string;
  requestId?: string;
}

function trimTrailingSlash(input: string): string {
  return input.endsWith("/") ? input.slice(0, -1) : input;
}

function mapErrorMessage(status: number, detail: string): string {
  if (status === 400 && detail.startsWith("Invalid signed device context:")) {
    return "Device security validation failed. Please refresh location and retry.";
  }

  if (
    status === 400 &&
    (detail.includes("Place is required") || detail.includes("Pincode is required"))
  ) {
    return "Select place and enter a valid 6-digit PIN code before submitting.";
  }

  if (status === 401) {
    return "Session expired. Sign in again and retry claim submission.";
  }

  if (status === 409) {
    return "A similar claim already exists for this event.";
  }

  if (status === 429) {
    return "Rate limit reached. Wait a moment before retrying.";
  }

  return detail;
}

export async function submitSignedClaim(
  input: SubmitSignedClaimInput,
): Promise<SubmitClaimResult> {
  const env = getMobileEnv();
  const signedContext = await buildSignedDeviceContext();

  const headers: Record<string, string> = {
    Authorization: `Bearer ${input.accessToken}`,
    "Content-Type": "application/json",
    "X-Device-Context": signedContext.rawContext,
    "X-Device-Context-Signature": signedContext.signature,
    "X-Device-Context-Timestamp": signedContext.timestamp,
  };

  if (signedContext.keyId) {
    headers["X-Device-Context-Key-Id"] = signedContext.keyId;
  }

  if (input.requestId) {
    headers["X-Request-ID"] = input.requestId;
  }

  const payload: SubmitClaimPayload = {
    claim_reason: input.claim_reason,
    place: input.place,
    pincode: input.pincode,
    city: input.city,
    plan: input.plan ?? "essential",
    stated_lat: input.stated_lat,
    stated_lng: input.stated_lng,
    trigger_event_id: input.trigger_event_id,
    shift_id: input.shift_id,
    evidence_url: input.evidence_url,
  };

  try {
    return await postJson<SubmitClaimResult>(
      `${trimTrailingSlash(env.apiBaseUrl)}/claims/`,
      payload,
      headers,
    );
  } catch (error) {
    if (error instanceof HttpRequestError) {
      throw new ClaimSubmissionError(
        mapErrorMessage(error.status, error.detail),
        error.status,
        error.detail,
      );
    }

    throw error;
  }
}
