import React from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { theme } from "../theme/tokens";

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
  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Covara Mobile</Text>
        <Text style={styles.subtitle}>Role-aware mobile flow aligned with Covara architecture.</Text>

        <View style={styles.card}>
          <Text style={styles.heading}>Session Access</Text>
          <Text style={styles.copy}>
            Continue with your active Supabase session, or paste a bearer token for test flows.
          </Text>

          {errorMessage ? <Text style={styles.error}>{errorMessage}</Text> : null}

          <TouchableOpacity
            style={[styles.primaryButton, loading ? styles.buttonDisabled : undefined]}
            disabled={loading}
            onPress={onTrySupabaseSession}
          >
            <Text style={styles.primaryButtonText}>
              {loading ? "Checking session..." : "Use active Supabase session"}
            </Text>
          </TouchableOpacity>

          <Text style={styles.label}>Manual token override</Text>
          <TextInput
            style={styles.input}
            placeholder="Paste access token"
            placeholderTextColor="#8EA79B"
            value={manualToken}
            onChangeText={onChangeManualToken}
            autoCapitalize="none"
            autoCorrect={false}
          />

          <TouchableOpacity
            style={[styles.secondaryButton, loading ? styles.buttonDisabled : undefined]}
            disabled={loading}
            onPress={onUseManualToken}
          >
            <Text style={styles.secondaryButtonText}>Continue with token</Text>
          </TouchableOpacity>
        </View>
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
  title: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.title,
    fontWeight: "800",
    letterSpacing: 0.2,
  },
  subtitle: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.subtitle,
  },
  card: {
    backgroundColor: theme.colors.surface,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.md,
    gap: theme.spacing.sm,
  },
  heading: {
    color: theme.colors.textPrimary,
    fontSize: 18,
    fontWeight: "700",
  },
  copy: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.body,
    lineHeight: 20,
  },
  label: {
    color: theme.colors.textPrimary,
    fontWeight: "600",
    fontSize: theme.typography.label,
    marginTop: theme.spacing.xs,
  },
  input: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.sm,
    backgroundColor: theme.colors.surfaceElevated,
    color: theme.colors.textPrimary,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  primaryButton: {
    borderRadius: theme.radius.sm,
    paddingVertical: 12,
    alignItems: "center",
    backgroundColor: theme.colors.accent,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontWeight: "700",
    fontSize: 14,
  },
  secondaryButton: {
    borderRadius: theme.radius.sm,
    paddingVertical: 11,
    alignItems: "center",
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: theme.colors.surfaceElevated,
  },
  secondaryButtonText: {
    color: theme.colors.textPrimary,
    fontWeight: "700",
    fontSize: 14,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  error: {
    color: theme.colors.danger,
    fontSize: theme.typography.caption,
    fontWeight: "600",
  },
});
