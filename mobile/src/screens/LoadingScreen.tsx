import React from "react";
import { ActivityIndicator, SafeAreaView, StyleSheet, Text, View } from "react-native";
import { AppCard } from "../components/ui/AppCard";
import { BrandMark } from "../components/ui/BrandMark";
import { theme } from "../theme/tokens";

interface LoadingScreenProps {
  label?: string;
}

const LOAD_STEPS = [
  "Verifying session token",
  "Syncing worker profile",
  "Preparing secure claim stack",
] as const;

export function LoadingScreen({ label = "Loading session" }: LoadingScreenProps) {
  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <View style={styles.bgOrbA} />
        <View style={styles.bgOrbB} />

        <AppCard elevated style={styles.card}>
          <View style={styles.headerRow}>
            <View style={styles.logoWrap}>
              <BrandMark size={72} />
            </View>
            <View style={styles.headerCopyWrap}>
              <Text style={styles.title}>Covara Worker</Text>
              <Text style={styles.subtitle}>Session bootstrap in progress</Text>
            </View>
          </View>

          <View style={styles.loadingRow}>
            <ActivityIndicator size="large" color={theme.colors.accent} />
            <Text style={styles.label}>{label}</Text>
          </View>

          <View style={styles.stepList}>
            {LOAD_STEPS.map((step, index) => (
              <View key={step} style={styles.stepRow}>
                <Text style={styles.stepIndex}>{index + 1}</Text>
                <Text style={styles.stepText}>{step}</Text>
              </View>
            ))}
          </View>

          <Text style={styles.footer}>Please keep this screen open until initialization completes.</Text>
        </AppCard>
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
    alignItems: "center",
    padding: theme.spacing.lg,
    overflow: "hidden",
  },
  bgOrbA: {
    position: "absolute",
    width: 220,
    height: 220,
    borderRadius: 999,
    backgroundColor: "rgba(43, 120, 212, 0.18)",
    top: -40,
    right: -50,
  },
  bgOrbB: {
    position: "absolute",
    width: 180,
    height: 180,
    borderRadius: 999,
    backgroundColor: "rgba(55, 166, 114, 0.18)",
    bottom: -40,
    left: -40,
  },
  card: {
    width: "100%",
    maxWidth: 360,
    gap: theme.spacing.sm,
    borderColor: theme.colors.borderStrong,
    backgroundColor: theme.colors.backgroundAlt,
    paddingVertical: theme.spacing.md,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.sm,
  },
  headerCopyWrap: {
    flex: 1,
    gap: 2,
  },
  logoWrap: {
    width: 72,
    height: 72,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  title: {
    color: theme.colors.textPrimary,
    fontSize: 21,
    fontWeight: "800",
    letterSpacing: 0.2,
  },
  subtitle: {
    color: theme.colors.textMuted,
    fontSize: 13,
    lineHeight: 18,
  },
  loadingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.sm,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  label: {
    color: theme.colors.textPrimary,
    fontSize: 14,
    fontWeight: "700",
  },
  stepList: {
    gap: 8,
  },
  stepRow: {
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
  stepIndex: {
    width: 20,
    height: 20,
    borderRadius: 999,
    textAlign: "center",
    textAlignVertical: "center",
    backgroundColor: theme.colors.surfaceStrong,
    color: theme.colors.accent,
    fontSize: 12,
    fontWeight: "800",
    overflow: "hidden",
  },
  stepText: {
    flex: 1,
    color: theme.colors.textMuted,
    fontSize: 13,
    lineHeight: 18,
  },
  footer: {
    color: theme.colors.textSoft,
    fontSize: 12,
    lineHeight: 16,
  },
});
