export type ClaimPlan = "essential" | "plus";

export interface SubmitClaimPayload {
  claim_reason: string;
  plan?: ClaimPlan;
  stated_lat?: number;
  stated_lng?: number;
  trigger_event_id?: string;
  shift_id?: string;
  evidence_url?: string;
}

export interface SubmitClaimResult {
  status: string;
  claim: {
    id: string;
    claim_status: string;
    claim_reason: string;
    claimed_at: string;
  };
  pipeline?: Record<string, unknown>;
}

export class ClaimSubmissionError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(message);
    this.name = "ClaimSubmissionError";
  }
}
