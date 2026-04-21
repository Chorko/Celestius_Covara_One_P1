import React, { useMemo, useState } from "react";
import {
  Alert,
  Image,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import * as Location from "expo-location";
import { AppButton } from "../components/ui/AppButton";
import { AppCard } from "../components/ui/AppCard";
import { BrandMark } from "../components/ui/BrandMark";
import { submitSignedClaim } from "../services/api/claims";
import { getSupabaseClient } from "../services/supabase/client";
import { ClaimSubmissionError, type ClaimPlan } from "../types/claims";
import { theme } from "../theme/tokens";

const QUICK_REASON_TEMPLATES = [
  "Flooding blocked delivery route",
  "Heat stress prevented safe operations",
  "AQI spike made outdoor work unsafe",
  "Platform outage prevented deliveries",
];

type ReadinessLane = "fast" | "review" | "high_risk";

interface ReadinessCheck {
  id: string;
  label: string;
  passed: boolean;
}

interface ReadinessSnapshot {
  score: number;
  lane: ReadinessLane;
  laneLabel: string;
  checks: ReadinessCheck[];
}

interface SubmissionInsight {
  decision: string | null;
  fraudScore: number | null;
  fraudConfidence: number | null;
  reviewPriority: string | null;
  reviewSlaMinutes: number | null;
  riskTier: string | null;
  reasonCodes: string[];
  requiredChallenges: string[];
  throttleMode: string | null;
}

interface EvidenceImage {
  uri: string;
  fileName: string;
  mimeType: string;
}

function inferImageExtension(mimeType: string, fallbackName: string): string {
  const normalizedMime = mimeType.toLowerCase();
  if (normalizedMime.includes("png")) {
    return "png";
  }
  if (normalizedMime.includes("webp")) {
    return "webp";
  }
  if (normalizedMime.includes("heic")) {
    return "heic";
  }

  const fallbackMatch = fallbackName.toLowerCase().match(/\.([a-z0-9]+)(?:\?.*)?$/);
  if (fallbackMatch?.[1]) {
    return fallbackMatch[1];
  }

  return "jpg";
}

function sanitizeUploadPrefix(rawValue: string | null | undefined): string {
  const normalized = String(rawValue || "worker")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

  return normalized || "worker";
}

async function uploadEvidenceImage(
  image: EvidenceImage,
  workerLabel: string | null | undefined,
): Promise<string> {
  const extension = inferImageExtension(image.mimeType, image.fileName || image.uri);
  const fileName = `${sanitizeUploadPrefix(workerLabel)}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}.${extension}`;

  const fileResponse = await fetch(image.uri);
  if (!fileResponse.ok) {
    throw new Error("Selected evidence image could not be read from device storage.");
  }

  const fileBlob = await fileResponse.blob();
  const supabase = getSupabaseClient();
  const { data, error } = await supabase.storage
    .from("claim-evidence")
    .upload(fileName, fileBlob, {
      contentType: image.mimeType || "image/jpeg",
      upsert: false,
    });

  if (error) {
    throw new Error(`Evidence upload failed: ${error.message}`);
  }

  const storedPath = data?.path || fileName;
  const { data: publicData } = supabase.storage
    .from("claim-evidence")
    .getPublicUrl(storedPath);

  if (!publicData?.publicUrl) {
    throw new Error("Evidence upload succeeded but public URL could not be resolved.");
  }

  return publicData.publicUrl;
}

function evaluateReadiness(params: {
  reason: string;
  place: string;
  pincode: string;
  lat?: number;
  lng?: number;
  hasEvidence: boolean;
}): ReadinessSnapshot {
  const checks: ReadinessCheck[] = [
    {
      id: "reason",
      label: "Detailed reason (18+ chars)",
      passed: params.reason.trim().length >= 18,
    },
    {
      id: "place",
      label: "Place or zone captured",
      passed: params.place.trim().length >= 3,
    },
    {
      id: "pincode",
      label: "Valid 6-digit PIN code",
      passed: /^\d{6}$/.test(params.pincode.trim()),
    },
    {
      id: "location",
      label: "Live location captured",
      passed: typeof params.lat === "number" && typeof params.lng === "number",
    },
    {
      id: "evidence",
      label: "Evidence photo attached",
      passed: params.hasEvidence,
    },
  ];

  const passedCount = checks.filter((check) => check.passed).length;
  const score = Math.round((passedCount / checks.length) * 100);

  if (score >= 80) {
    return {
      score,
      lane: "fast",
      laneLabel: "Fast lane ready",
      checks,
    };
  }

  if (score >= 60) {
    return {
      score,
      lane: "review",
      laneLabel: "Likely review lane",
      checks,
    };
  }

  return {
    score,
    lane: "high_risk",
    laneLabel: "High review risk",
    checks,
  };
}

function formatLocationLabel(lat?: number, lng?: number): string {
  if (typeof lat !== "number" || typeof lng !== "number") {
    return "Capture location";
  }

  return `Location ${lat.toFixed(4)}, ${lng.toFixed(4)}`;
}

function toRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object") {
    return {};
  }

  return value as Record<string, unknown>;
}

function toNumberOrNull(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((entry): entry is string => typeof entry === "string")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

function humanizeCode(value: string): string {
  const normalized = value.replace(/_/g, " ").replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "Unknown";
  }

  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function formatDecision(value: string | null): string {
  return value ? humanizeCode(value) : "Decision pending";
}

function formatPriority(value: string | null): string {
  return value ? value.toUpperCase() : "N/A";
}

function formatSla(minutes: number | null): string {
  if (minutes === null) {
    return "N/A";
  }

  if (minutes < 60) {
    return `${minutes} min`;
  }

  const hours = Math.round((minutes / 60) * 10) / 10;
  return `${hours} h`;
}

function parseSubmissionInsight(
  pipeline?: Record<string, unknown>,
): SubmissionInsight | null {
  if (!pipeline) {
    return null;
  }

  const review = toRecord(pipeline.review);
  const fraud = toRecord(pipeline.fraud_analysis);
  const riskActionPack = toRecord(fraud.risk_action_pack);
  const reviewThrottle = toRecord(review.throttle_strategy);
  const packThrottle = toRecord(riskActionPack.throttle_strategy);
  const throttle =
    Object.keys(reviewThrottle).length > 0 ? reviewThrottle : packThrottle;

  const decision =
    typeof review.decision_action === "string"
      ? review.decision_action
      : typeof review.decision === "string"
        ? review.decision
        : null;

  const reasonCodes = toStringArray(review.decision_reason_codes);
  const challengeCodes = toStringArray(review.required_challenges);
  const fallbackChallenges = toStringArray(riskActionPack.required_challenges);

  const finalReasonCodes =
    reasonCodes.length > 0
      ? reasonCodes
      : toStringArray(
          toRecord(fraud.decision_explainability).decision_reason_codes,
        );

  const finalChallenges =
    challengeCodes.length > 0 ? challengeCodes : fallbackChallenges;

  return {
    decision,
    fraudScore: toNumberOrNull(fraud.fraud_score),
    fraudConfidence: toNumberOrNull(review.fraud_confidence),
    reviewPriority:
      typeof review.review_priority === "string"
        ? review.review_priority
        : typeof riskActionPack.review_priority === "string"
          ? riskActionPack.review_priority
          : null,
    reviewSlaMinutes:
      toNumberOrNull(review.review_sla_minutes) ??
      toNumberOrNull(riskActionPack.review_sla_minutes),
    riskTier:
      typeof riskActionPack.risk_tier === "string"
        ? riskActionPack.risk_tier
        : null,
    reasonCodes: finalReasonCodes,
    requiredChallenges: finalChallenges,
    throttleMode:
      typeof throttle.mode === "string" ? throttle.mode : null,
  };
}

interface WorkerClaimScreenProps {
  accessToken: string;
  displayName: string | null | undefined;
  onRefreshSession: () => void;
  onSignOut: () => void;
}

export function WorkerClaimScreen({
  accessToken,
  displayName,
  onRefreshSession,
  onSignOut,
}: WorkerClaimScreenProps) {
  const [reason, setReason] = useState("");
  const [place, setPlace] = useState("");
  const [pincode, setPincode] = useState("");
  const [plan, setPlan] = useState<ClaimPlan>("essential");
  const [lat, setLat] = useState<number | undefined>();
  const [lng, setLng] = useState<number | undefined>();
  const [locationCapturedAt, setLocationCapturedAt] = useState<string | null>(
    null,
  );
  const [evidenceImage, setEvidenceImage] = useState<EvidenceImage | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<string>("Idle");
  const [submissionInsight, setSubmissionInsight] = useState<SubmissionInsight | null>(
    null,
  );

  const readiness = useMemo(
    () =>
      evaluateReadiness({
        reason,
        place,
        pincode,
        lat,
        lng,
        hasEvidence: Boolean(evidenceImage),
      }),
    [reason, place, pincode, lat, lng, evidenceImage],
  );

  const resultTone = useMemo(() => {
    const text = result.toLowerCase();
    if (text.startsWith("submitted")) {
      return "success";
    }
    if (text.startsWith("failed")) {
      return "danger";
    }
    return "neutral";
  }, [result]);

  function applyReasonTemplate(template: string): void {
    setReason((prev) => {
      const trimmed = prev.trim();
      if (!trimmed) {
        return template;
      }
      if (trimmed.toLowerCase().includes(template.toLowerCase())) {
        return prev;
      }
      return `${trimmed}. ${template}`;
    });
  }

  async function getLocation(): Promise<void> {
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (!permission.granted) {
        Alert.alert("Location denied", "Location permission is optional but strongly recommended.");
        setResult("Location missing. Claims without live coordinates are reviewed more strictly.");
        return;
      }

      const current = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });
      setLat(current.coords.latitude);
      setLng(current.coords.longitude);
      setLocationCapturedAt(new Date().toLocaleTimeString());
      setResult("Location captured and attached to claim context.");
    } catch (error) {
      if (error instanceof Error) {
        setResult(`Location capture failed: ${error.message}`);
      } else {
        setResult("Location capture failed due to an unknown error.");
      }
    }
  }

  async function pickEvidencePhoto(): Promise<void> {
    try {
      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        Alert.alert(
          "Permission required",
          "Please allow photo library access to attach evidence.",
        );
        return;
      }

      const pickerResult = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        quality: 0.8,
        allowsEditing: false,
        exif: false,
      });

      if (pickerResult.canceled || pickerResult.assets.length === 0) {
        return;
      }

      const asset = pickerResult.assets[0];
      if (!asset.uri) {
        throw new Error("Selected evidence image is missing a local URI.");
      }

      const mimeType = asset.mimeType || "image/jpeg";
      const extension = inferImageExtension(mimeType, asset.uri);
      const fileName = asset.fileName || `evidence-${Date.now()}.${extension}`;

      setEvidenceImage({
        uri: asset.uri,
        fileName,
        mimeType,
      });

      setResult("Evidence photo attached. Image forensics checks will run for this claim.");
    } catch (error) {
      if (error instanceof Error) {
        setResult(`Evidence selection failed: ${error.message}`);
      } else {
        setResult("Evidence selection failed due to an unknown error.");
      }
    }
  }

  async function submit(): Promise<void> {
    if (!reason.trim()) {
      Alert.alert("Claim reason required", "Please add the disruption reason.");
      return;
    }

    if (reason.trim().length < 12) {
      Alert.alert("Reason too short", "Add more detail so the review engine can classify disruption evidence reliably.");
      return;
    }

    if (!place.trim()) {
      Alert.alert("Place required", "Please enter the place/zone name.");
      return;
    }

    if (!/^\d{6}$/.test(pincode.trim())) {
      Alert.alert("Invalid PIN code", "Please enter a valid 6-digit PIN code.");
      return;
    }

    setSubmitting(true);
    setResult("Submitting...");

    try {
      // Creates the client early to surface env configuration issues quickly.
      getSupabaseClient();

      let evidenceUrl: string | undefined;
      if (evidenceImage) {
        setResult("Uploading evidence photo...");
        evidenceUrl = await uploadEvidenceImage(evidenceImage, displayName);
      }

      const response = await submitSignedClaim({
        accessToken,
        claim_reason: reason.trim(),
        place: place.trim(),
        pincode: pincode.trim(),
        plan,
        stated_lat: lat,
        stated_lng: lng,
        evidence_url: evidenceUrl,
      });

      setSubmissionInsight(parseSubmissionInsight(response.pipeline));

      setResult(`Submitted claim ${response.claim.id} with status ${response.claim.claim_status}`);
      setReason("");
      setPlace("");
      setPincode("");
      setLat(undefined);
      setLng(undefined);
      setLocationCapturedAt(null);
      setEvidenceImage(null);
    } catch (error) {
      if (error instanceof ClaimSubmissionError) {
        setResult(`Failed (${error.status}): ${error.detail}`);
      } else if (error instanceof Error) {
        setResult(`Failed: ${error.message}`);
      } else {
        setResult("Failed due to unknown error.");
      }
      setSubmissionInsight(null);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.topHeader}>
          <View style={styles.topHeaderLeft}>
            <BrandMark size={46} />
            <View style={styles.topHeaderCopy}>
              <Text style={styles.title}>Worker Claims Console</Text>
              <Text style={styles.subtitle}>Signed device-context claim submission for verified workers.</Text>
            </View>
          </View>
        </View>

        <AppCard elevated style={styles.heroCard}>
          <Text style={styles.heroTitle}>Claim Integrity Command Deck</Text>
          <Text style={styles.heroCopy}>
            Higher readiness lowers fraud review friction. Submit with richer context for faster routing.
          </Text>

          <View style={styles.readinessHeader}>
            <View>
              <Text style={styles.readinessLabel}>Readiness score</Text>
              <Text style={styles.readinessScore}>{readiness.score}%</Text>
            </View>
            <View
              style={[
                styles.lanePill,
                readiness.lane === "fast"
                  ? styles.laneFast
                  : readiness.lane === "review"
                    ? styles.laneReview
                    : styles.laneHighRisk,
              ]}
            >
              <Text style={styles.laneText}>{readiness.laneLabel}</Text>
            </View>
          </View>

          <View style={styles.progressTrack}>
            <View
              style={[
                styles.progressFill,
                { width: `${readiness.score}%` },
                readiness.lane === "fast"
                  ? styles.progressFast
                  : readiness.lane === "review"
                    ? styles.progressReview
                    : styles.progressHighRisk,
              ]}
            />
          </View>
        </AppCard>

        <AppCard elevated style={styles.banner}>
          <Text style={styles.bannerText}>Signed in as {displayName ?? "worker"}</Text>
          <View style={styles.bannerActions}>
            <AppButton
              label="Refresh"
              onPress={onRefreshSession}
              variant="neutral"
              style={styles.smallActionButton}
              textStyle={styles.smallActionText}
            />
            <AppButton
              label="Sign out"
              onPress={onSignOut}
              variant="danger"
              style={styles.smallActionButton}
              textStyle={styles.smallActionText}
            />
          </View>
        </AppCard>

        <AppCard elevated style={styles.card}>
          <Text style={styles.sectionTitle}>Quick reason templates</Text>
          <View style={styles.templateRow}>
            {QUICK_REASON_TEMPLATES.map((template) => (
              <TouchableOpacity
                key={template}
                style={styles.templateChip}
                onPress={() => {
                  applyReasonTemplate(template);
                }}
              >
                <Text style={styles.templateText}>{template}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.label}>Disruption reason</Text>
          <TextInput
            style={[styles.input, styles.multiline]}
            multiline
            numberOfLines={4}
            placeholder="e.g. heavy flooding blocked delivery route"
            placeholderTextColor="#8EA79B"
            value={reason}
            onChangeText={setReason}
          />

          <Text style={styles.label}>Place / Zone</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g. Andheri-W"
            placeholderTextColor="#8EA79B"
            value={place}
            onChangeText={setPlace}
          />

          <Text style={styles.label}>PIN code</Text>
          <TextInput
            style={styles.input}
            placeholder="6-digit PIN code"
            placeholderTextColor="#8EA79B"
            value={pincode}
            onChangeText={setPincode}
            keyboardType="number-pad"
            maxLength={6}
          />

          <Text style={styles.label}>Plan</Text>
          <View style={styles.row}>
            <TouchableOpacity
              style={[styles.chip, plan === "essential" ? styles.chipActive : undefined]}
              onPress={() => setPlan("essential")}
            >
              <Text style={styles.chipText}>Essential</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.chip, plan === "plus" ? styles.chipActive : undefined]}
              onPress={() => setPlan("plus")}
            >
              <Text style={styles.chipText}>Plus</Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.planHint}>
            Essential favors core disruption cover. Plus supports higher weekly protection limits.
          </Text>

          <AppButton
            label={formatLocationLabel(lat, lng)}
            onPress={getLocation}
            variant="outline"
          />
          {locationCapturedAt ? (
            <Text style={styles.locationStamp}>Captured at {locationCapturedAt}</Text>
          ) : (
            <Text style={styles.locationStamp}>Location not captured yet.</Text>
          )}

          <Text style={styles.label}>Evidence photo</Text>
          <AppButton
            label={evidenceImage ? "Change evidence photo" : "Attach evidence photo"}
            onPress={pickEvidencePhoto}
            variant="outline"
          />
          {evidenceImage ? (
            <View style={styles.evidencePreviewCard}>
              <Image
                source={{ uri: evidenceImage.uri }}
                style={styles.evidencePreviewImage}
              />
              <View style={styles.evidencePreviewMeta}>
                <Text style={styles.evidenceFileName} numberOfLines={1}>
                  {evidenceImage.fileName}
                </Text>
                <Text style={styles.evidenceFileMeta} numberOfLines={1}>
                  {evidenceImage.mimeType}
                </Text>
                <TouchableOpacity
                  onPress={() => setEvidenceImage(null)}
                  style={styles.evidenceRemoveChip}
                >
                  <Text style={styles.evidenceRemoveText}>Remove photo</Text>
                </TouchableOpacity>
              </View>
            </View>
          ) : (
            <Text style={styles.locationStamp}>
              Attach a clear disruption photo to enable EXIF + AI forensics checks.
            </Text>
          )}

          <View style={styles.checklistCard}>
            <Text style={styles.sectionTitle}>Pre-submit checks</Text>
            {readiness.checks.map((check) => (
              <View key={check.id} style={styles.checkRow}>
                <Text style={styles.checkLabel}>{check.label}</Text>
                <View
                  style={[
                    styles.checkPill,
                    check.passed ? styles.checkPillPass : styles.checkPillPending,
                  ]}
                >
                  <Text style={styles.checkPillText}>{check.passed ? "OK" : "WAIT"}</Text>
                </View>
              </View>
            ))}
          </View>

          <AppButton
            label={submitting ? "Submitting..." : "Submit claim"}
            onPress={submit}
            loading={submitting}
            disabled={submitting}
            variant="primary"
          />

          <Text
            style={[
              styles.result,
              resultTone === "success"
                ? styles.resultSuccess
                : resultTone === "danger"
                  ? styles.resultDanger
                  : styles.resultNeutral,
            ]}
          >
            {result}
          </Text>
        </AppCard>

        {submissionInsight ? (
          <AppCard elevated style={styles.intelCard}>
            <View style={styles.intelHeader}>
              <Text style={styles.intelTitle}>Fraud routing intelligence</Text>
              <View style={styles.intelTierChip}>
                <Text style={styles.intelTierText}>
                  {submissionInsight.riskTier
                    ? humanizeCode(submissionInsight.riskTier)
                    : "Unknown"}
                </Text>
              </View>
            </View>

            <Text style={styles.intelDecision}>
              {formatDecision(submissionInsight.decision)}
            </Text>

            <View style={styles.metricGrid}>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Fraud score</Text>
                <Text style={styles.metricValue}>
                  {submissionInsight.fraudScore !== null
                    ? submissionInsight.fraudScore.toFixed(2)
                    : "--"}
                </Text>
              </View>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Confidence</Text>
                <Text style={styles.metricValue}>
                  {submissionInsight.fraudConfidence !== null
                    ? submissionInsight.fraudConfidence.toFixed(2)
                    : "--"}
                </Text>
              </View>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Review SLA</Text>
                <Text style={styles.metricValue}>
                  {formatSla(submissionInsight.reviewSlaMinutes)}
                </Text>
              </View>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Priority</Text>
                <Text style={styles.metricValue}>
                  {formatPriority(submissionInsight.reviewPriority)}
                </Text>
              </View>
            </View>

            {submissionInsight.reasonCodes.length > 0 ? (
              <View style={styles.insightBlock}>
                <Text style={styles.insightLabel}>Decision reasons</Text>
                <View style={styles.insightChipRow}>
                  {submissionInsight.reasonCodes.slice(0, 6).map((code) => (
                    <View key={code} style={styles.infoChip}>
                      <Text style={styles.infoChipText}>{humanizeCode(code)}</Text>
                    </View>
                  ))}
                </View>
              </View>
            ) : null}

            {submissionInsight.requiredChallenges.length > 0 ? (
              <View style={styles.insightBlock}>
                <Text style={styles.insightLabel}>Required challenge steps</Text>
                <View style={styles.insightChipRow}>
                  {submissionInsight.requiredChallenges.map((challenge) => (
                    <View key={challenge} style={styles.challengeChip}>
                      <Text style={styles.challengeChipText}>
                        {humanizeCode(challenge)}
                      </Text>
                    </View>
                  ))}
                </View>
              </View>
            ) : null}

            {submissionInsight.throttleMode ? (
              <Text style={styles.throttleText}>
                Zone control: {humanizeCode(submissionInsight.throttleMode)}
              </Text>
            ) : null}
          </AppCard>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  container: {
    padding: theme.spacing.lg,
    gap: theme.spacing.md,
    paddingBottom: theme.spacing.xl,
  },
  topHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  topHeaderLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  topHeaderCopy: {
    flex: 1,
    gap: 2,
  },
  title: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.title,
    fontWeight: "800",
  },
  subtitle: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.subtitle,
  },
  heroCard: {
    borderColor: theme.colors.accentBlue,
    backgroundColor: theme.colors.backgroundAlt,
    gap: theme.spacing.sm,
  },
  heroTitle: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.section,
    fontWeight: "800",
  },
  heroCopy: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.body,
    lineHeight: 20,
  },
  readinessHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: theme.spacing.sm,
  },
  readinessLabel: {
    color: theme.colors.textSoft,
    fontSize: theme.typography.caption,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  readinessScore: {
    color: theme.colors.textPrimary,
    fontSize: 36,
    fontWeight: "900",
    lineHeight: 42,
  },
  lanePill: {
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
  },
  laneFast: {
    backgroundColor: "rgba(73, 188, 129, 0.16)",
    borderColor: theme.colors.success,
  },
  laneReview: {
    backgroundColor: "rgba(240, 182, 91, 0.16)",
    borderColor: theme.colors.warning,
  },
  laneHighRisk: {
    backgroundColor: "rgba(217, 101, 101, 0.16)",
    borderColor: theme.colors.danger,
  },
  laneText: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.caption,
    fontWeight: "700",
  },
  progressTrack: {
    height: 10,
    borderRadius: 999,
    overflow: "hidden",
    backgroundColor: theme.colors.surfaceStrong,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  progressFill: {
    height: "100%",
  },
  progressFast: {
    backgroundColor: theme.colors.success,
  },
  progressReview: {
    backgroundColor: theme.colors.warning,
  },
  progressHighRisk: {
    backgroundColor: theme.colors.danger,
  },
  banner: {
    borderColor: theme.colors.borderStrong,
    backgroundColor: theme.colors.surface,
    gap: theme.spacing.sm,
  },
  bannerText: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.body,
    fontWeight: "700",
  },
  bannerActions: {
    flexDirection: "row",
    gap: theme.spacing.sm,
  },
  smallActionButton: {
    flex: 1,
    minHeight: 40,
  },
  smallActionText: {
    fontSize: theme.typography.caption,
  },
  card: {
    borderColor: theme.colors.borderStrong,
    backgroundColor: theme.colors.surface,
    gap: theme.spacing.sm,
  },
  intelCard: {
    borderColor: theme.colors.accentBlue,
    backgroundColor: theme.colors.backgroundAlt,
    gap: theme.spacing.sm,
  },
  sectionTitle: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.label,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0.45,
  },
  templateRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.xs,
  },
  templateChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.colors.accentBlue,
    backgroundColor: "rgba(43, 120, 212, 0.15)",
    paddingHorizontal: 10,
    paddingVertical: 6,
    maxWidth: "100%",
  },
  templateText: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.caption,
    fontWeight: "600",
  },
  label: {
    color: theme.colors.textPrimary,
    fontWeight: "600",
    fontSize: theme.typography.label,
  },
  input: {
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    backgroundColor: theme.colors.surfaceElevated,
    color: theme.colors.textPrimary,
    borderRadius: theme.radius.sm,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  multiline: {
    minHeight: 96,
    textAlignVertical: "top",
  },
  row: {
    flexDirection: "row",
    gap: theme.spacing.sm,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    backgroundColor: theme.colors.chipIdle,
  },
  chipActive: {
    backgroundColor: theme.colors.chipActive,
    borderColor: theme.colors.accent,
  },
  chipText: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.caption,
    fontWeight: "600",
  },
  planHint: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.caption,
    lineHeight: 18,
  },
  locationStamp: {
    color: theme.colors.textSoft,
    fontSize: theme.typography.caption,
    marginTop: -2,
  },
  evidencePreviewCard: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surfaceElevated,
    padding: theme.spacing.xs,
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.sm,
  },
  evidencePreviewImage: {
    width: 74,
    height: 74,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
  },
  evidencePreviewMeta: {
    flex: 1,
    gap: 4,
  },
  evidenceFileName: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.caption,
    fontWeight: "700",
  },
  evidenceFileMeta: {
    color: theme.colors.textSoft,
    fontSize: 11,
  },
  evidenceRemoveChip: {
    alignSelf: "flex-start",
    borderWidth: 1,
    borderColor: theme.colors.danger,
    borderRadius: 999,
    backgroundColor: "rgba(217, 101, 101, 0.15)",
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  evidenceRemoveText: {
    color: theme.colors.textPrimary,
    fontSize: 11,
    fontWeight: "700",
  },
  checklistCard: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    padding: theme.spacing.sm,
    backgroundColor: theme.colors.surfaceElevated,
    gap: theme.spacing.xs,
  },
  checkRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: theme.spacing.sm,
  },
  checkLabel: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.caption,
    flexShrink: 1,
    lineHeight: 17,
  },
  checkPill: {
    minWidth: 50,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderWidth: 1,
  },
  checkPillPass: {
    backgroundColor: "rgba(73, 188, 129, 0.18)",
    borderColor: theme.colors.success,
  },
  checkPillPending: {
    backgroundColor: "rgba(240, 182, 91, 0.15)",
    borderColor: theme.colors.warning,
  },
  checkPillText: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.caption,
    fontWeight: "800",
    letterSpacing: 0.35,
  },
  result: {
    fontSize: theme.typography.caption,
    lineHeight: 18,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  resultNeutral: {
    color: theme.colors.textMuted,
    borderColor: theme.colors.border,
    backgroundColor: theme.colors.surfaceElevated,
  },
  resultSuccess: {
    color: theme.colors.success,
    borderColor: theme.colors.success,
    backgroundColor: "rgba(73, 188, 129, 0.12)",
  },
  resultDanger: {
    color: theme.colors.danger,
    borderColor: theme.colors.danger,
    backgroundColor: "rgba(217, 101, 101, 0.12)",
  },
  intelHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: theme.spacing.sm,
  },
  intelTitle: {
    color: theme.colors.textPrimary,
    fontSize: 15,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  intelTierChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.colors.accentBlue,
    backgroundColor: "rgba(43, 120, 212, 0.16)",
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  intelTierText: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.caption,
    fontWeight: "700",
  },
  intelDecision: {
    color: theme.colors.textPrimary,
    fontSize: 17,
    fontWeight: "800",
    lineHeight: 24,
  },
  metricGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.xs,
  },
  metricCard: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.sm,
    backgroundColor: theme.colors.surface,
    paddingHorizontal: 10,
    paddingVertical: 8,
    minWidth: "48%",
    flexGrow: 1,
    gap: 2,
  },
  metricLabel: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.caption,
    textTransform: "uppercase",
    letterSpacing: 0.35,
    fontWeight: "700",
  },
  metricValue: {
    color: theme.colors.textPrimary,
    fontSize: 16,
    fontWeight: "800",
  },
  insightBlock: {
    gap: theme.spacing.xs,
  },
  insightLabel: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.caption,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  insightChipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.xs,
  },
  infoChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    backgroundColor: theme.colors.surface,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  infoChipText: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.caption,
    fontWeight: "600",
  },
  challengeChip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.colors.warning,
    backgroundColor: "rgba(240, 182, 91, 0.16)",
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  challengeChipText: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.caption,
    fontWeight: "700",
  },
  throttleText: {
    color: theme.colors.textSoft,
    fontSize: theme.typography.caption,
    lineHeight: 18,
  },
});
