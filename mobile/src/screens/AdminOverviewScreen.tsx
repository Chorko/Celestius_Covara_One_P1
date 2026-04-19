import React from "react";
import { SafeAreaView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
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
  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <Text style={styles.title}>Insurer Admin Workspace</Text>
        <Text style={styles.copy}>
          This role is authenticated for admin capabilities. Mobile keeps this as a lightweight launcher
          while the full admin surface remains on web.
        </Text>

        <View style={styles.card}>
          <Text style={styles.label}>Name</Text>
          <Text style={styles.value}>{profile?.full_name ?? "Unknown"}</Text>
          <Text style={styles.label}>Email</Text>
          <Text style={styles.value}>{profile?.email ?? "Unknown"}</Text>
          <Text style={styles.label}>Role</Text>
          <Text style={styles.value}>{profile?.role ?? "insurer_admin"}</Text>
        </View>

        <TouchableOpacity style={styles.primaryButton} onPress={onRefresh}>
          <Text style={styles.primaryText}>Refresh profile</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.secondaryButton} onPress={onSignOut}>
          <Text style={styles.secondaryText}>Sign out</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  container: {
    flex: 1,
    justifyContent: "center",
    padding: theme.spacing.lg,
    gap: theme.spacing.md,
  },
  title: {
    color: theme.colors.textPrimary,
    fontSize: 24,
    fontWeight: "800",
  },
  copy: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.body,
    lineHeight: 20,
  },
  card: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    padding: theme.spacing.md,
    gap: theme.spacing.xs,
  },
  label: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.caption,
    fontWeight: "700",
    marginTop: 4,
  },
  value: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.body,
    fontWeight: "600",
  },
  primaryButton: {
    borderRadius: theme.radius.sm,
    paddingVertical: 12,
    alignItems: "center",
    backgroundColor: theme.colors.accent,
  },
  primaryText: {
    color: "#FFFFFF",
    fontWeight: "700",
  },
  secondaryButton: {
    borderRadius: theme.radius.sm,
    paddingVertical: 11,
    alignItems: "center",
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: theme.colors.surface,
  },
  secondaryText: {
    color: theme.colors.textPrimary,
    fontWeight: "700",
  },
});
