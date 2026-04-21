import React from "react";
import { SafeAreaView, ScrollView, StyleSheet, Text, View } from "react-native";
import { AppButton } from "../components/ui/AppButton";
import { AppCard } from "../components/ui/AppCard";
import { theme } from "../theme/tokens";

interface OnboardingRequiredScreenProps {
  role: string | null;
  onRefresh: () => void;
  onSignOut: () => void;
}

const ONBOARDING_FLOW = [
  {
    title: "Account authenticated",
    detail: "Sign-in and token exchange completed for this device.",
    done: true,
  },
  {
    title: "Web onboarding",
    detail: "Finish role-specific onboarding checklist on Covara web app.",
    done: false,
  },
  {
    title: "Policy unlock",
    detail: "Role workflows are enabled automatically after onboarding sync.",
    done: false,
  },
] as const;

export function OnboardingRequiredScreen({
  role,
  onRefresh,
  onSignOut,
}: OnboardingRequiredScreenProps) {
  const hasResolvedRole = Boolean(role);

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        <AppCard elevated style={styles.heroCard}>
          <View style={styles.heroTopRow}>
            <Text style={styles.eyebrow}>Account state</Text>
            <Text style={[styles.roleChip, hasResolvedRole ? styles.roleChipReady : styles.roleChipPending]}>
              {role ?? "Role pending"}
            </Text>
          </View>
          <Text style={styles.title}>Onboarding still in progress</Text>
          <Text style={styles.copy}>
            Authentication is complete, but your role workflow is blocked until web onboarding syncs.
            Keep this session active and refresh after completing the checklist.
          </Text>
        </AppCard>

        <AppCard elevated style={styles.card}>
          <Text style={styles.sectionTitle}>Activation timeline</Text>
          {ONBOARDING_FLOW.map((item) => (
            <View key={item.title} style={styles.timelineRow}>
              <View style={[styles.timelineDot, item.done ? styles.timelineDotDone : styles.timelineDotPending]} />
              <View style={styles.timelineCopyWrap}>
                <Text style={styles.timelineTitle}>{item.title}</Text>
                <Text style={styles.timelineCopy}>{item.detail}</Text>
              </View>
              <Text style={[styles.timelineState, item.done ? styles.timelineStateDone : styles.timelineStatePending]}>
                {item.done ? "Done" : "Pending"}
              </Text>
            </View>
          ))}
        </AppCard>

        <AppCard elevated style={styles.card}>
          <Text style={styles.sectionTitle}>What to do now</Text>
          <Text style={styles.cardCopy}>
            Open the Covara web portal, complete onboarding tasks for your assigned role, then return here and
            refresh the session.
          </Text>
          <AppButton label="Refresh session" onPress={onRefresh} variant="primary" />
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
    alignItems: "center",
    justifyContent: "space-between",
  },
  eyebrow: {
    color: theme.colors.accent,
    fontSize: theme.typography.caption,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  roleChip: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
    fontSize: theme.typography.caption,
    fontWeight: "700",
  },
  roleChipReady: {
    color: "#CFE7D8",
    borderColor: "rgba(55, 166, 114, 0.45)",
    backgroundColor: "rgba(55, 166, 114, 0.16)",
  },
  roleChipPending: {
    color: "#F5D8A8",
    borderColor: "rgba(240, 182, 91, 0.45)",
    backgroundColor: "rgba(240, 182, 91, 0.16)",
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
  card: {
    borderColor: theme.colors.borderStrong,
    backgroundColor: theme.colors.surface,
    gap: theme.spacing.sm,
  },
  sectionTitle: {
    color: theme.colors.textPrimary,
    fontSize: 17,
    fontWeight: "800",
    letterSpacing: 0.2,
  },
  timelineRow: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surfaceElevated,
    padding: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  timelineDot: {
    width: 10,
    height: 10,
    borderRadius: 999,
  },
  timelineDotDone: {
    backgroundColor: theme.colors.success,
  },
  timelineDotPending: {
    backgroundColor: theme.colors.warning,
  },
  timelineCopyWrap: {
    flex: 1,
    gap: 2,
  },
  timelineTitle: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.body,
    fontWeight: "700",
  },
  timelineCopy: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.caption,
    lineHeight: 16,
  },
  timelineState: {
    fontSize: theme.typography.caption,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  timelineStateDone: {
    color: theme.colors.success,
  },
  timelineStatePending: {
    color: theme.colors.warning,
  },
  cardCopy: {
    color: theme.colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
  },
});
