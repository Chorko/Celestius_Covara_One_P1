import React from "react";
import { SafeAreaView, ScrollView, StyleSheet, Text, View } from "react-native";
import { AppButton } from "../components/ui/AppButton";
import { AppCard } from "../components/ui/AppCard";
import type { KycSnapshot } from "../store/userStore";
import { theme } from "../theme/tokens";

interface KycPendingScreenProps {
  kyc: KycSnapshot | null;
  onRefresh: () => void;
  onSignOut: () => void;
}

const KYC_STEPS = [
  {
    key: "aadhaarVerified",
    label: "Aadhaar identity",
    detail: "Primary identity verification through approved Aadhaar flow.",
  },
  {
    key: "bankVerified",
    label: "Bank account",
    detail: "Payout destination account linked and verified.",
  },
  {
    key: "phoneVerified",
    label: "Phone ownership",
    detail: "OTP-authenticated mobile number for secure notifications.",
  },
  {
    key: "faceVerified",
    label: "Face match",
    detail: "Liveness + face verification completed for anti-spoof controls.",
  },
] as const;

type KycStepKey = (typeof KYC_STEPS)[number]["key"];

function stepDone(kyc: KycSnapshot | null, key: KycStepKey): boolean {
  return Boolean(kyc?.[key]);
}

export function KycPendingScreen({ kyc, onRefresh, onSignOut }: KycPendingScreenProps) {
  const completedCount = KYC_STEPS.filter((step) => stepDone(kyc, step.key)).length;
  const totalCount = KYC_STEPS.length;
  const progress = Math.round((completedCount / totalCount) * 100);
  const ready = completedCount === totalCount;

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        <AppCard elevated style={styles.heroCard}>
          <View style={styles.heroTopRow}>
            <Text style={styles.badge}>Access Gate</Text>
            <Text style={[styles.stateChip, ready ? styles.stateChipReady : styles.stateChipPending]}>
              {ready ? "Ready for claims" : "KYC pending"}
            </Text>
          </View>

          <Text style={styles.title}>Complete worker verification stack</Text>
          <Text style={styles.copy}>
            Claims unlock after all mandatory verification checks pass. Keep this screen open and refresh once
            each step is done on web.
          </Text>

          <View style={styles.progressMetaRow}>
            <Text style={styles.progressLabel}>Completion</Text>
            <Text style={styles.progressValue}>
              {completedCount}/{totalCount} steps
            </Text>
          </View>
          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: `${progress}%` }]} />
          </View>
          <Text style={styles.progressHint}>{progress}% verification complete</Text>
        </AppCard>

        <AppCard elevated style={styles.stepCard}>
          <Text style={styles.sectionTitle}>Verification checklist</Text>
          {KYC_STEPS.map((step) => {
            const done = stepDone(kyc, step.key);
            return (
              <View key={step.key} style={styles.stepRow}>
                <View style={[styles.stepDot, done ? styles.stepDotDone : styles.stepDotPending]} />
                <View style={styles.stepCopyWrap}>
                  <Text style={styles.stepLabel}>{step.label}</Text>
                  <Text style={styles.stepDetail}>{step.detail}</Text>
                </View>
                <Text style={[styles.stepState, done ? styles.stepStateDone : styles.stepStatePending]}>
                  {done ? "Verified" : "Pending"}
                </Text>
              </View>
            );
          })}
        </AppCard>

        <AppCard elevated style={styles.actionCard}>
          <Text style={styles.sectionTitle}>Next action</Text>
          <Text style={styles.actionCopy}>
            {ready
              ? "All checks are complete. Refresh to enter claim workflow."
              : "Finish pending checks in the web portal, then refresh to re-sync this session."}
          </Text>
          <AppButton label="Refresh KYC status" onPress={onRefresh} variant="primary" />
          <AppButton label="Sign out" onPress={onSignOut} variant="neutral" />
        </AppCard>
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
    flexGrow: 1,
    padding: theme.spacing.lg,
    gap: theme.spacing.md,
  },
  heroCard: {
    borderColor: theme.colors.borderStrong,
    backgroundColor: theme.colors.backgroundAlt,
    gap: theme.spacing.sm,
  },
  heroTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  badge: {
    color: theme.colors.accent,
    fontSize: theme.typography.caption,
    fontWeight: "800",
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },
  stateChip: {
    fontSize: theme.typography.caption,
    fontWeight: "700",
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  stateChipReady: {
    color: "#CFF2DE",
    backgroundColor: "rgba(73, 188, 129, 0.18)",
    borderColor: "rgba(73, 188, 129, 0.5)",
  },
  stateChipPending: {
    color: "#F9D8A3",
    backgroundColor: "rgba(240, 182, 91, 0.18)",
    borderColor: "rgba(240, 182, 91, 0.45)",
  },
  title: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.section,
    fontWeight: "800",
    lineHeight: 26,
  },
  copy: {
    color: theme.colors.textMuted,
    fontSize: 15,
    lineHeight: 22,
  },
  progressMetaRow: {
    marginTop: 4,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  progressLabel: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.caption,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  progressValue: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.label,
    fontWeight: "700",
  },
  progressTrack: {
    height: 10,
    borderRadius: 999,
    backgroundColor: theme.colors.surfaceStrong,
    borderWidth: 1,
    borderColor: theme.colors.border,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: theme.colors.accent,
  },
  progressHint: {
    color: theme.colors.textSoft,
    fontSize: theme.typography.caption,
  },
  stepCard: {
    borderColor: theme.colors.borderStrong,
    backgroundColor: theme.colors.surface,
    gap: theme.spacing.xs,
  },
  sectionTitle: {
    color: theme.colors.textPrimary,
    fontSize: 17,
    fontWeight: "800",
    letterSpacing: 0.2,
  },
  stepRow: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surfaceElevated,
    padding: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  stepDot: {
    width: 10,
    height: 10,
    borderRadius: 999,
  },
  stepDotDone: {
    backgroundColor: theme.colors.success,
  },
  stepDotPending: {
    backgroundColor: theme.colors.warning,
  },
  stepCopyWrap: {
    flex: 1,
    gap: 2,
  },
  stepLabel: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.body,
    fontWeight: "700",
  },
  stepDetail: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.caption,
    lineHeight: 16,
  },
  stepState: {
    fontSize: theme.typography.caption,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  stepStateDone: {
    color: theme.colors.success,
  },
  stepStatePending: {
    color: theme.colors.warning,
  },
  actionCard: {
    borderColor: theme.colors.borderStrong,
    backgroundColor: theme.colors.surface,
    gap: theme.spacing.sm,
  },
  actionCopy: {
    color: theme.colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
  },
});
