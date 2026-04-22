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
  email: string;
  password: string;
  errorMessage: string | null;
  loading: boolean;
  onChangeEmail: (value: string) => void;
  onChangePassword: (value: string) => void;
  onSignIn: () => void;
  onTrySupabaseSession: () => void;
}

export function AuthGateScreen({
  email,
  password,
  errorMessage,
  loading,
  onChangeEmail,
  onChangePassword,
  onSignIn,
  onTrySupabaseSession,
}: AuthGateScreenProps) {
  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Covara Mobile</Text>
        <Text style={styles.subtitle}>Role-aware mobile flow aligned with Covara architecture.</Text>

        <View style={styles.card}>
          <Text style={styles.heading}>Sign In</Text>
          <Text style={styles.copy}>
            Use any valid demo account email and password to continue.
          </Text>

          {errorMessage ? <Text style={styles.error}>{errorMessage}</Text> : null}

          <Text style={styles.label}>Email</Text>
          <TextInput
            style={styles.input}
            placeholder="you@example.com"
            placeholderTextColor="#8EA79B"
            value={email}
            onChangeText={onChangeEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
          />

          <Text style={styles.label}>Password</Text>
          <TextInput
            style={styles.input}
            placeholder="Enter password"
            placeholderTextColor="#8EA79B"
            value={password}
            onChangeText={onChangePassword}
            autoCapitalize="none"
            autoCorrect={false}
            secureTextEntry
          />

          <TouchableOpacity
            style={[styles.primaryButton, loading ? styles.buttonDisabled : undefined]}
            disabled={loading}
            onPress={onSignIn}
          >
            <Text style={styles.primaryButtonText}>
              {loading ? "Signing in..." : "Continue"}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.secondaryButton, loading ? styles.buttonDisabled : undefined]}
            disabled={loading}
            onPress={onTrySupabaseSession}
          >
            <Text style={styles.secondaryButtonText}>Use active session</Text>
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
