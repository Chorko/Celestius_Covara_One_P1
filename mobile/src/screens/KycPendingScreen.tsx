import React from "react";
import { SafeAreaView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import type { KycSnapshot } from "../store/userStore";
import { theme } from "../theme/tokens";

interface KycPendingScreenProps {
  kyc: KycSnapshot | null;
  onRefresh: () => void;
  onSignOut: () => void;
}

function statusLabel(isDone: boolean): string {
  return isDone ? "Verified" : "Pending";
}

export function KycPendingScreen({ kyc, onRefresh, onSignOut }: KycPendingScreenProps) {
  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <Text style={styles.title}>KYC Verification Required</Text>
        <Text style={styles.copy}>
          Worker claims are unlocked after Aadhaar and bank verification. Finish KYC steps, then refresh
          this session.
        </Text>

        <View style={styles.card}>
          <Text style={styles.row}>Aadhaar: {statusLabel(Boolean(kyc?.aadhaarVerified))}</Text>
          <Text style={styles.row}>Bank: {statusLabel(Boolean(kyc?.bankVerified))}</Text>
          <Text style={styles.row}>Phone: {statusLabel(Boolean(kyc?.phoneVerified))}</Text>
          <Text style={styles.row}>Face: {statusLabel(Boolean(kyc?.faceVerified))}</Text>
        </View>

        <TouchableOpacity style={styles.primaryButton} onPress={onRefresh}>
          <Text style={styles.primaryText}>Refresh KYC status</Text>
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
  row: {
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
