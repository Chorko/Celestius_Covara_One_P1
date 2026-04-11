import type { IntegritySignals } from "../../types/deviceContext";

export interface AttestationResult {
  provider: string;
  verdict: IntegritySignals["attestation_verdict"];
  tokenPresent: boolean;
  warnings: string[];
}

export interface AttestationProvider {
  collect(): Promise<AttestationResult>;
}

class NotConfiguredAttestationProvider implements AttestationProvider {
  async collect(): Promise<AttestationResult> {
    return {
      provider: "none",
      verdict: "not_configured",
      tokenPresent: false,
      warnings: [
        "attestation_provider_not_configured",
        "attestation_bridge_pending_provider_selection",
      ],
    };
  }
}

export function getAttestationProvider(): AttestationProvider {
  // Future integration point for Play Integrity / DeviceCheck / App Attest.
  return new NotConfiguredAttestationProvider();
}
