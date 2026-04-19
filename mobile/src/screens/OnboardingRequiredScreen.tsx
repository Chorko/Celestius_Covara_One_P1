import React from "react";
import { SafeAreaView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { theme } from "../theme/tokens";

interface OnboardingRequiredScreenProps {
  role: string | null;
  onRefresh: () => void;
  onSignOut: () => void;
}

export function OnboardingRequiredScreen({
  role,
  onRefresh,
  onSignOut,
}: OnboardingRequiredScreenProps) {
  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <Text style={styles.title}>Onboarding Incomplete</Text>
        <Text style={styles.copy}>
          Your account is authenticated but profile onboarding is still pending. Complete onboarding on
          web, then refresh here.
        </Text>
        <Text style={styles.badge}>Detected role: {role ?? "pending"}</Text>

        <TouchableOpacity style={styles.primaryButton} onPress={onRefresh}>
          <Text style={styles.primaryText}>Refresh session</Text>
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
  badge: {
    color: theme.colors.warning,
    fontSize: theme.typography.label,
    fontWeight: "700",
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
