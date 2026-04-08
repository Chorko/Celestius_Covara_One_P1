import type { IntegritySignals } from "../../types/deviceContext";

export async function collectIntegritySignals(): Promise<IntegritySignals> {
  // Placeholder defaults for kickoff. Native anti-tamper bridges will replace this.
  return {
    is_rooted: false,
    developer_mode_active: false,
    mock_location_detected: false,
    malicious_packages_found: [],
    has_accelerometer: true,
    has_gyroscope: true,
    integrity_verdict: "unknown",
  };
}
