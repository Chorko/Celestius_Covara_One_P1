import React from "react";
import { SafeAreaView, ScrollView, StyleSheet, Text, View } from "react-native";
import { AppButton } from "../components/ui/AppButton";
import { AppCard } from "../components/ui/AppCard";
import type { Profile } from "../store/userStore";
import { theme } from "../theme/tokens";

interface AdminOverviewScreenProps {
  profile: Profile | null;
  onRefresh: () => void;
  onSignOut: () => void;
}

export function AdminOverviewScreen({
  profile,
  onRefresh,
  onSignOut,
}: AdminOverviewScreenProps) {
  const fullName = profile?.full_name ?? "Unknown";
  const email = profile?.email ?? "Unknown";
  const role = profile?.role ?? "insurer_admin";
  const hasCompleteProfile = Boolean(profile?.full_name && profile?.email);

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        <AppCard elevated style={styles.heroCard}>
          <View style={styles.heroTopRow}>
            <Text style={styles.eyebrow}>Control Access</Text>
            <Text
              style={[
                styles.stateChip,
                hasCompleteProfile ? styles.stateChipReady : styles.stateChipLimited,
              ]}
            >
              {hasCompleteProfile ? "Profile synced" : "Limited profile"}
            </Text>
          </View>
          <Text style={styles.title}>Insurer admin launcher</Text>
          <Text style={styles.copy}>
            Mobile is optimized for quick identity checks and secure launch into your full web operations
            workspace.
          </Text>
        </AppCard>

        <AppCard elevated style={styles.card}>
          <Text style={styles.sectionTitle}>Session identity</Text>

          <View style={styles.infoRow}>
            <Text style={styles.label}>Name</Text>
            <Text style={styles.value}>{fullName}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.label}>Email</Text>
            <Text style={styles.value}>{email}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.label}>Role</Text>
            <Text style={styles.value}>{role}</Text>
          </View>
        </AppCard>

        <AppCard elevated style={styles.card}>
          <Text style={styles.sectionTitle}>Ops launch guidance</Text>
          <View style={styles.launchRow}>
            <View style={[styles.dot, styles.dotDone]} />
            <Text style={styles.launchCopy}>Auth session active on this device</Text>
          </View>
          <View style={styles.launchRow}>
            <View style={[styles.dot, styles.dotPending]} />
            <Text style={styles.launchCopy}>Use web for full incident, payout, and policy controls</Text>
          </View>
          <View style={styles.launchRow}>
            <View style={[styles.dot, styles.dotPending]} />
            <Text style={styles.launchCopy}>Refresh session here after role or policy updates</Text>
          </View>

          <AppButton label="Refresh profile" onPress={onRefresh} variant="primary" />
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
  stateChip: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
    fontSize: theme.typography.caption,
    fontWeight: "700",
  },
  stateChipReady: {
    color: "#CFE7D8",
    borderColor: "rgba(55, 166, 114, 0.45)",
    backgroundColor: "rgba(55, 166, 114, 0.16)",
  },
  stateChipLimited: {
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
  infoRow: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surfaceElevated,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 2,
  },
  label: {
    color: theme.colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.45,
  },
  value: {
    color: theme.colors.textPrimary,
    fontSize: 15,
    fontWeight: "700",
  },
  launchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surfaceElevated,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  dot: {
    width: 9,
    height: 9,
    borderRadius: 999,
  },
  dotDone: {
    backgroundColor: theme.colors.success,
  },
  dotPending: {
    backgroundColor: theme.colors.accentBlue,
  },
  launchCopy: {
    flex: 1,
    color: theme.colors.textMuted,
    fontSize: 13,
    lineHeight: 18,
  },
});
