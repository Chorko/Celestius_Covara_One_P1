import type { IntegritySignals } from "../../types/deviceContext";
import * as Application from "expo-application";
import * as Device from "expo-device";
import * as Location from "expo-location";

import { getAttestationProvider } from "./attestation";

function safeLower(value: unknown): string {
  return String(value ?? "").trim().toLowerCase();
}

function detectEmulator(device: {
  isDevice?: boolean;
  modelName?: string | null;
  productName?: string | null;
  manufacturer?: string | null;
  osBuildFingerprint?: string | null;
}): boolean {
  const markers = [
    "emulator",
    "simulator",
    "sdk_gphone",
    "generic",
    "vbox",
    "genymotion",
    "x86",
    "goldfish",
    "ranchu",
  ];

  const fingerprint = [
    safeLower(device.modelName),
    safeLower(device.productName),
    safeLower(device.manufacturer),
    safeLower(device.osBuildFingerprint),
  ].join("|");

  const markerMatched = markers.some((m) => fingerprint.includes(m));
  return device.isDevice === false || markerMatched;
}

function detectRootHint(device: {
  osBuildFingerprint?: string | null;
  productName?: string | null;
  modelName?: string | null;
}): boolean {
  const fingerprint = [
    safeLower(device.osBuildFingerprint),
    safeLower(device.productName),
    safeLower(device.modelName),
  ].join("|");

  const rootedMarkers = [
    "test-keys",
    "magisk",
    "su",
    "lineage",
    "xposed",
  ];

  return rootedMarkers.some((m) => fingerprint.includes(m));
}

function detectDebuggerHeuristic(): boolean {
  const globals = globalThis as {
    __REMOTEDEV__?: unknown;
    __DEV__?: boolean;
    nativeCallSyncHook?: unknown;
  };

  if (Boolean(globals.__REMOTEDEV__)) {
    return true;
  }

  // Dev builds in RN often run with interactive debugging tooling.
  return Boolean(globals.__DEV__);
}

async function detectMockLocation(): Promise<{
  detected: boolean;
  source: "location_object" | "provider_status" | "none";
  warning?: string;
}> {
  try {
    const fg = await Location.getForegroundPermissionsAsync();
    if (!fg.granted) {
      return {
        detected: false,
        source: "none",
        warning: "location_permission_not_granted",
      };
    }

    const lastKnown = await Location.getLastKnownPositionAsync({});
    const mockedFromLocation = Boolean((lastKnown as { mocked?: boolean } | null)?.mocked);
    if (mockedFromLocation) {
      return { detected: true, source: "location_object" };
    }

    const provider = await Location.getProviderStatusAsync();
    const mockedFromProvider = Boolean((provider as { mocked?: boolean }).mocked);
    if (mockedFromProvider) {
      return { detected: true, source: "provider_status" };
    }

    return { detected: false, source: "none" };
  } catch {
    return {
      detected: false,
      source: "none",
      warning: "mock_location_detection_failed",
    };
  }
}

function classifySignalConfidence(params: {
  isRooted: boolean;
  isEmulator: boolean;
  debuggerDetected: boolean;
  mockLocationDetected: boolean;
  unsupportedCheckCount: number;
}): IntegritySignals["signal_confidence"] {
  const {
    isRooted,
    isEmulator,
    debuggerDetected,
    mockLocationDetected,
    unsupportedCheckCount,
  } = params;

  let score = 1.0;
  if (isRooted) score -= 0.35;
  if (isEmulator) score -= 0.25;
  if (debuggerDetected) score -= 0.15;
  if (mockLocationDetected) score -= 0.2;

  score -= Math.min(0.25, unsupportedCheckCount * 0.08);

  if (score >= 0.75) return "high";
  if (score >= 0.5) return "medium";
  return "low";
}

function classifyIntegrityVerdict(params: {
  isRooted: boolean;
  isEmulator: boolean;
  debuggerDetected: boolean;
  mockLocationDetected: boolean;
  signalConfidence: IntegritySignals["signal_confidence"];
  attestationVerdict: IntegritySignals["attestation_verdict"];
}): IntegritySignals["integrity_verdict"] {
  if (
    params.isRooted
    || params.debuggerDetected
    || params.attestationVerdict === "failed"
  ) {
    return "high_risk";
  }

  if (
    params.isEmulator
    || params.mockLocationDetected
    || params.signalConfidence === "low"
  ) {
    return "weak";
  }

  if (params.signalConfidence === "medium") {
    return "moderate";
  }

  return "strong";
}

export async function collectIntegritySignals(): Promise<IntegritySignals> {
  const unsupportedChecks = [
    "runtime_package_scanning_not_available_in_expo_managed",
    "kernel_level_root_detection_not_available_in_expo_managed",
  ];

  const collectionWarnings: string[] = [];

  try {
    const attestation = await getAttestationProvider().collect();
    collectionWarnings.push(...attestation.warnings);

    const deviceLike = Device as {
      isDevice?: boolean;
      modelName?: string | null;
      productName?: string | null;
      manufacturer?: string | null;
      osBuildFingerprint?: string | null;
    };

    const isEmulator = detectEmulator(deviceLike);
    const isRooted = detectRootHint(deviceLike);
    const debuggerDetected = detectDebuggerHeuristic();

    const mockLocation = await detectMockLocation();
    if (mockLocation.warning) {
      collectionWarnings.push(mockLocation.warning);
    }

    const signalConfidence = classifySignalConfidence({
      isRooted,
      isEmulator,
      debuggerDetected,
      mockLocationDetected: mockLocation.detected,
      unsupportedCheckCount: unsupportedChecks.length,
    });

    const attestationVerdict = attestation.verdict;
    const integrityVerdict = classifyIntegrityVerdict({
      isRooted,
      isEmulator,
      debuggerDetected,
      mockLocationDetected: mockLocation.detected,
      signalConfidence,
      attestationVerdict,
    });

    const inferredSensorPresence = !isEmulator;
    if (!inferredSensorPresence) {
      collectionWarnings.push("sensor_presence_inferred_false_on_emulator_runtime");
    }

    if (Application.nativeBuildVersion == null) {
      collectionWarnings.push("native_build_version_unavailable");
    }

    const collectionMethod: IntegritySignals["collection_method"] =
      attestationVerdict === "passed" || attestationVerdict === "failed"
        ? "mixed"
        : "heuristic";

    return {
      is_rooted: isRooted,
      is_emulator: isEmulator,
      debugger_detected: debuggerDetected,
      developer_mode_active: Boolean((globalThis as { __DEV__?: boolean }).__DEV__),
      mock_location_detected: mockLocation.detected,
      mock_location_source: mockLocation.source,
      malicious_packages_found: [],
      has_accelerometer: inferredSensorPresence,
      has_gyroscope: inferredSensorPresence,
      integrity_verdict: integrityVerdict,
      signal_confidence: signalConfidence,
      collection_method: collectionMethod,
      collection_warnings: collectionWarnings,
      unsupported_checks: unsupportedChecks,
      attestation_provider: attestation.provider,
      attestation_verdict: attestation.verdict,
      attestation_token_present: attestation.tokenPresent,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown_error";
    collectionWarnings.push(`integrity_collection_error:${message}`);

    // Fail-safe return: do not fabricate confidence when collection fails.
    return {
      is_rooted: false,
      is_emulator: false,
      debugger_detected: false,
      developer_mode_active: false,
      mock_location_detected: false,
      mock_location_source: "none",
      malicious_packages_found: [],
      has_accelerometer: false,
      has_gyroscope: false,
      integrity_verdict: "weak",
      signal_confidence: "low",
      collection_method: "heuristic",
      collection_warnings: collectionWarnings,
      unsupported_checks: unsupportedChecks,
      attestation_provider: "none",
      attestation_verdict: "error",
      attestation_token_present: false,
    };
  }
}
