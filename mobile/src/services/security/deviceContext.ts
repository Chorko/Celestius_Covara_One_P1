import { Platform } from "react-native";
import * as Application from "expo-application";
import * as Device from "expo-device";
import * as Location from "expo-location";
import * as Network from "expo-network";
import { getMobileEnv } from "../../config/env";
import type {
  DeviceContextPayload,
  SignedDeviceContext,
} from "../../types/deviceContext";
import { collectIntegritySignals } from "./integrity";
import { signDeviceContext } from "./signing";

function generateNonce(): string {
  const maybeCrypto = globalThis.crypto as
    | { randomUUID?: () => string }
    | undefined;

  if (maybeCrypto?.randomUUID) {
    return maybeCrypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;
}

async function resolveHardwareId(): Promise<string> {
  const appApi = Application as {
    androidId?: string | null;
    getAndroidIdAsync?: () => Promise<string | null>;
    getIosIdForVendorAsync?: () => Promise<string | null>;
  };

  if (Platform.OS === "android") {
    if (typeof appApi.getAndroidIdAsync === "function") {
      const id = await appApi.getAndroidIdAsync();
      if (id) {
        return id;
      }
    }

    if (appApi.androidId) {
      return appApi.androidId;
    }
  }

  if (Platform.OS === "ios" && typeof appApi.getIosIdForVendorAsync === "function") {
    const id = await appApi.getIosIdForVendorAsync();
    if (id) {
      return id;
    }
  }

  return `${Device.osName ?? "unknown-os"}-${Device.modelName ?? "unknown-device"}`;
}

async function resolveLocationScope(): Promise<"none" | "foreground" | "background"> {
  const fg = await Location.getForegroundPermissionsAsync();
  if (!fg.granted) {
    return "none";
  }

  const bg = await Location.getBackgroundPermissionsAsync();
  return bg.granted ? "background" : "foreground";
}

function currentTimestamp(): string {
  return Math.floor(Date.now() / 1000).toString();
}

export async function buildSignedDeviceContext(): Promise<SignedDeviceContext> {
  const env = getMobileEnv();
  const signals = await collectIntegritySignals();
  const locationScope = await resolveLocationScope();
  const networkState = await Network.getNetworkStateAsync();
  const hardwareId = await resolveHardwareId();

  const payload: DeviceContextPayload = {
    schema_version: env.deviceContextSchemaVersion,
    nonce: generateNonce(),
    os_platform: Platform.OS === "ios" ? "ios" : "android",
    device_model: Device.modelName ?? "unknown-device",
    hardware_id: hardwareId,
    is_rooted: signals.is_rooted,
    is_emulator: signals.is_emulator,
    debugger_attached: signals.debugger_detected,
    developer_mode_active: signals.developer_mode_active,
    mock_location_detected: signals.mock_location_detected,
    mock_location_source: signals.mock_location_source,
    malicious_packages_found: signals.malicious_packages_found,
    vpn_active: String(networkState.type).toLowerCase() === "vpn",
    has_accelerometer: signals.has_accelerometer,
    has_gyroscope: signals.has_gyroscope,
    app_version: Application.nativeApplicationVersion ?? undefined,
    app_build_number: Application.nativeBuildVersion ?? undefined,
    integrity_verdict: signals.integrity_verdict,
    signal_confidence: signals.signal_confidence,
    collection_method: signals.collection_method,
    collection_warnings: signals.collection_warnings,
    unsupported_checks: signals.unsupported_checks,
    attestation_provider: signals.attestation_provider,
    attestation_verdict: signals.attestation_verdict,
    attestation_token_present: signals.attestation_token_present,
    location_permission_scope: locationScope,
    precise_location_enabled: locationScope !== "none",
  };

  const rawContext = JSON.stringify(payload);
  const timestamp = currentTimestamp();
  const signature = signDeviceContext(rawContext, timestamp, env.deviceContextHmacSecret);

  return {
    rawContext,
    signature,
    timestamp,
    keyId: env.deviceContextKeyId,
    payload,
  };
}
