export interface DeviceContextPayload {
  schema_version: string;
  nonce: string;
  os_platform: "android" | "ios";
  device_model: string;
  hardware_id: string;
  is_rooted: boolean;
  is_emulator?: boolean;
  debugger_attached?: boolean;
  developer_mode_active: boolean;
  mock_location_detected: boolean;
  mock_location_source?: "location_object" | "provider_status" | "none";
  malicious_packages_found: string[];
  vpn_active: boolean;
  has_accelerometer: boolean;
  has_gyroscope: boolean;
  app_version?: string;
  app_build_number?: string;
  integrity_verdict?: "strong" | "moderate" | "weak" | "high_risk";
  signal_confidence?: "high" | "medium" | "low";
  collection_method?: "heuristic" | "attestation" | "mixed";
  collection_warnings?: string[];
  unsupported_checks?: string[];
  attestation_provider?: string;
  attestation_verdict?:
    | "passed"
    | "failed"
    | "not_configured"
    | "not_available"
    | "error";
  attestation_token_present?: boolean;
  location_permission_scope?: "none" | "foreground" | "background";
  precise_location_enabled?: boolean;
}

export interface SignedDeviceContext {
  rawContext: string;
  signature: string;
  timestamp: string;
  keyId?: string;
  payload: DeviceContextPayload;
}

export interface IntegritySignals {
  is_rooted: boolean;
  is_emulator: boolean;
  debugger_detected: boolean;
  developer_mode_active: boolean;
  mock_location_detected: boolean;
  mock_location_source: "location_object" | "provider_status" | "none";
  malicious_packages_found: string[];
  has_accelerometer: boolean;
  has_gyroscope: boolean;
  integrity_verdict: "strong" | "moderate" | "weak" | "high_risk";
  signal_confidence: "high" | "medium" | "low";
  collection_method: "heuristic" | "attestation" | "mixed";
  collection_warnings: string[];
  unsupported_checks: string[];
  attestation_provider: string;
  attestation_verdict:
    | "passed"
    | "failed"
    | "not_configured"
    | "not_available"
    | "error";
  attestation_token_present: boolean;
}
