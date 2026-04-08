export interface DeviceContextPayload {
  schema_version: string;
  nonce: string;
  os_platform: "android" | "ios";
  device_model: string;
  hardware_id: string;
  is_rooted: boolean;
  developer_mode_active: boolean;
  mock_location_detected: boolean;
  malicious_packages_found: string[];
  vpn_active: boolean;
  has_accelerometer: boolean;
  has_gyroscope: boolean;
  app_version?: string;
  app_build_number?: string;
  integrity_verdict?: string;
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
  developer_mode_active: boolean;
  mock_location_detected: boolean;
  malicious_packages_found: string[];
  has_accelerometer: boolean;
  has_gyroscope: boolean;
  integrity_verdict: string;
}
