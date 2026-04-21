import React from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TouchableOpacity,
  type StyleProp,
  type TextStyle,
  type ViewStyle,
} from "react-native";
import { theme } from "../../theme/tokens";

type AppButtonVariant = "primary" | "outline" | "neutral" | "danger";

interface AppButtonProps {
  label: string;
  onPress: () => void;
  variant?: AppButtonVariant;
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
}

export function AppButton({
  label,
  onPress,
  variant = "primary",
  disabled = false,
  loading = false,
  style,
  textStyle,
}: AppButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <TouchableOpacity
      activeOpacity={0.82}
      onPress={onPress}
      disabled={isDisabled}
      style={[
        styles.button,
        variant === "primary" ? styles.primaryButton : undefined,
        variant === "outline" ? styles.outlineButton : undefined,
        variant === "neutral" ? styles.neutralButton : undefined,
        variant === "danger" ? styles.dangerButton : undefined,
        isDisabled ? styles.disabledButton : undefined,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator size="small" color={variant === "primary" ? "#FFFFFF" : theme.colors.textPrimary} />
      ) : (
        <Text
          style={[
            styles.label,
            variant === "primary" ? styles.primaryLabel : undefined,
            variant === "outline" ? styles.outlineLabel : undefined,
            variant === "neutral" ? styles.neutralLabel : undefined,
            variant === "danger" ? styles.dangerLabel : undefined,
            textStyle,
          ]}
        >
          {label}
        </Text>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: 52,
    borderRadius: theme.radius.md,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: theme.spacing.lg,
    borderWidth: 1,
  },
  label: {
    fontSize: 15,
    fontWeight: "700",
    letterSpacing: 0.25,
  },
  primaryButton: {
    backgroundColor: theme.colors.accent,
    borderColor: theme.colors.accentStrong,
    shadowColor: "#23A778",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.28,
    shadowRadius: 14,
    elevation: 6,
  },
  primaryLabel: {
    color: "#FFFFFF",
  },
  outlineButton: {
    backgroundColor: theme.colors.surfaceElevated,
    borderColor: theme.colors.accentStrong,
  },
  outlineLabel: {
    color: theme.colors.textPrimary,
  },
  neutralButton: {
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.borderStrong,
  },
  neutralLabel: {
    color: theme.colors.textPrimary,
  },
  dangerButton: {
    backgroundColor: "rgba(229, 110, 110, 0.18)",
    borderColor: theme.colors.danger,
  },
  dangerLabel: {
    color: "#FFD8D8",
  },
  disabledButton: {
    opacity: 0.58,
  },
});
