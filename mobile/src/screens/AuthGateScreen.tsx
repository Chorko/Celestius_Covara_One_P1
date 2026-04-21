import React from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { AppButton } from "../components/ui/AppButton";
import { AppCard } from "../components/ui/AppCard";
import { BrandMark } from "../components/ui/BrandMark";
import { theme } from "../theme/tokens";

const REQUIRED_EXPO_ENV_KEYS = [
  "EXPO_PUBLIC_API_BASE_URL",
  "EXPO_PUBLIC_SUPABASE_URL",
  "EXPO_PUBLIC_SUPABASE_ANON_KEY",
  "EXPO_PUBLIC_DEVICE_CONTEXT_HMAC_SECRET",
];

interface AuthGateScreenProps {
  manualToken: string;
  errorMessage: string | null;
  loading: boolean;
  onChangeManualToken: (value: string) => void;
  onTrySupabaseSession: () => void;
  onUseManualToken: () => void;
}

export function AuthGateScreen({
  manualToken,
  errorMessage,
  loading,
  onChangeManualToken,
  onTrySupabaseSession,
  onUseManualToken,
}: AuthGateScreenProps) {
  const hasToken = manualToken.trim().length > 0;
  const missingEnvDetected = Boolean(
    errorMessage &&
      errorMessage.toLowerCase().includes("missing required environment variable"),
  );

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.heroBlock}>
          <View style={styles.brandRow}>
            <View style={styles.logoWrap}>
              <BrandMark size={68} />
            </View>
            <View style={styles.brandCopy}>
              <Text style={styles.title}>Covara Worker</Text>
              <Text style={styles.subtitle}>Secure claims with session-first access and field verification.</Text>
            </View>
          </View>

          <View style={styles.badgeRow}>
            <View style={[styles.badgePill, styles.badgePillPrimary]}>
              <Text style={styles.badgeText}>Worker App</Text>
            </View>
            <View style={[styles.badgePill, styles.badgePillAlt]}>
              <Text style={styles.badgeText}>Token Ready</Text>
            </View>
            <View style={[styles.badgePill, styles.badgePillBlue]}>
              <Text style={styles.badgeText}>Expo Ready</Text>
            </View>
          </View>
        </View>

        <AppCard elevated style={styles.card}>
          <Text style={styles.heading}>Session Access</Text>
          <Text style={styles.copy}>
            Continue with your active Supabase session, or paste a bearer token for controlled test flows.
          </Text>

          {errorMessage ? (
            <View style={styles.errorPanel}>
              <Text style={styles.errorTitle}>Cannot continue</Text>
              <Text style={styles.error}>{errorMessage}</Text>

              {missingEnvDetected ? (
                <View style={styles.envHelpPanel}>
                  <Text style={styles.envHelpTitle}>Set these Expo variables:</Text>
                  {REQUIRED_EXPO_ENV_KEYS.map((keyName) => (
                    <Text key={keyName} style={styles.envHelpItem}>
                      - {keyName}
                    </Text>
                  ))}
                  <Text style={styles.envHelpHint}>
                    Source of truth: mobile/.env.example and Expo project environment settings.
                  </Text>
                </View>
              ) : null}
            </View>
          ) : null}

          <AppButton
            label={loading ? "Checking session..." : "Use active Supabase session"}
            onPress={onTrySupabaseSession}
            loading={loading}
            disabled={loading}
            variant="primary"
          />

          <View style={styles.separator} />

          <Text style={styles.label}>Manual token override</Text>
          <TextInput
            style={[styles.input, hasToken ? styles.inputActive : styles.inputIdle]}
            placeholder="Paste access token"
            placeholderTextColor={theme.colors.textSoft}
            value={manualToken}
            onChangeText={onChangeManualToken}
            autoCapitalize="none"
            autoCorrect={false}
          />

          <AppButton
            label="Continue with token"
            onPress={onUseManualToken}
            loading={loading}
            disabled={loading || !hasToken}
            variant="outline"
          />

          <Text style={styles.footnote}>
            Uses your current Covara Supabase flow. No database schema changes are applied.
          </Text>
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
    padding: theme.spacing.lg,
    gap: theme.spacing.md,
  },
  heroBlock: {
    backgroundColor: theme.colors.backgroundAlt,
    borderWidth: 1,
    borderColor: theme.colors.borderStrong,
    borderRadius: 22,
    padding: theme.spacing.md,
    gap: theme.spacing.sm,
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
  },
  logoWrap: {
    width: 68,
    height: 68,
    alignItems: "center",
    justifyContent: "center",
    elevation: 8,
    shadowColor: "#0F6FFF",
    shadowOffset: { width: 0, height: 5 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
  },
  brandCopy: {
    flex: 1,
  },
  title: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.hero,
    fontWeight: "800",
    letterSpacing: 0.25,
  },
  subtitle: {
    color: theme.colors.textMuted,
    fontSize: 15,
    lineHeight: 20,
    marginTop: 2,
  },
  badgeRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  badgePill: {
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  badgePillPrimary: {
    backgroundColor: "#295E4A",
    borderColor: "#3FA678",
  },
  badgePillAlt: {
    backgroundColor: "#1A4636",
    borderColor: "#2F6A54",
  },
  badgePillBlue: {
    backgroundColor: "#162F4D",
    borderColor: "#2B78D4",
  },
  badgeText: {
    color: "#CFEFE1",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.2,
  },
  card: {
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.borderStrong,
    borderRadius: 20,
    gap: 12,
  },
  heading: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.section,
    fontWeight: "700",
    letterSpacing: 0.2,
  },
  copy: {
    color: "#C0D4CA",
    fontSize: 15,
    lineHeight: 22,
  },
  separator: {
    height: 1,
    backgroundColor: theme.colors.border,
    marginVertical: 2,
  },
  label: {
    color: theme.colors.textPrimary,
    fontWeight: "700",
    fontSize: 15,
  },
  input: {
    borderWidth: 1,
    borderRadius: 14,
    backgroundColor: theme.colors.surfaceElevated,
    color: theme.colors.textPrimary,
    paddingHorizontal: 14,
    paddingVertical: 14,
    fontSize: 16,
  },
  inputIdle: {
    borderColor: theme.colors.border,
  },
  inputActive: {
    borderColor: theme.colors.accentStrong,
  },
  errorPanel: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(217, 101, 101, 0.65)",
    backgroundColor: "rgba(217, 101, 101, 0.16)",
    padding: 12,
    gap: 4,
  },
  errorTitle: {
    color: "#FFB6B6",
    fontSize: 12,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0.45,
  },
  error: {
    color: "#FFD6D6",
    fontSize: 14,
    fontWeight: "600",
    lineHeight: 20,
  },
  envHelpPanel: {
    marginTop: 6,
    borderTopWidth: 1,
    borderTopColor: "rgba(255, 214, 214, 0.35)",
    paddingTop: 8,
    gap: 2,
  },
  envHelpTitle: {
    color: "#FFD6D6",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.2,
  },
  envHelpItem: {
    color: "#FFE7E7",
    fontSize: 12,
    fontWeight: "600",
    lineHeight: 17,
  },
  envHelpHint: {
    color: "#FFCFCF",
    fontSize: 11,
    marginTop: 4,
    lineHeight: 16,
  },
  footnote: {
    marginTop: 2,
    color: theme.colors.textMuted,
    fontSize: theme.typography.caption,
    lineHeight: 17,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  secondaryButtonText: {
    color: theme.colors.textPrimary,
    fontWeight: "700",
    fontSize: 16,
  },
});
