import React, { useState } from "react";
import {
  Alert,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import * as Location from "expo-location";
import { submitSignedClaim } from "../services/api/claims";
import { getSupabaseClient } from "../services/supabase/client";
import { ClaimSubmissionError, type ClaimPlan } from "../types/claims";
import { theme } from "../theme/tokens";

interface WorkerClaimScreenProps {
  accessToken: string;
  displayName: string | null | undefined;
  onRefreshSession: () => void;
  onSignOut: () => void;
}

export function WorkerClaimScreen({
  accessToken,
  displayName,
  onRefreshSession,
  onSignOut,
}: WorkerClaimScreenProps) {
  const [reason, setReason] = useState("");
  const [place, setPlace] = useState("");
  const [pincode, setPincode] = useState("");
  const [plan, setPlan] = useState<ClaimPlan>("essential");
  const [lat, setLat] = useState<number | undefined>();
  const [lng, setLng] = useState<number | undefined>();
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<string>("Idle");

  async function getLocation(): Promise<void> {
    const permission = await Location.requestForegroundPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("Location denied", "Location permission is optional but recommended.");
      return;
    }

    const current = await Location.getCurrentPositionAsync({});
    setLat(current.coords.latitude);
    setLng(current.coords.longitude);
  }

  async function submit(): Promise<void> {
    if (!reason.trim()) {
      Alert.alert("Claim reason required", "Please add the disruption reason.");
      return;
    }

    if (!place.trim()) {
      Alert.alert("Place required", "Please enter the place/zone name.");
      return;
    }

    if (!/^\d{6}$/.test(pincode.trim())) {
      Alert.alert("Invalid PIN code", "Please enter a valid 6-digit PIN code.");
      return;
    }

    setSubmitting(true);
    setResult("Submitting...");

    try {
      // Creates the client early to surface env configuration issues quickly.
      getSupabaseClient();

      const response = await submitSignedClaim({
        accessToken,
        claim_reason: reason.trim(),
        place: place.trim(),
        pincode: pincode.trim(),
        plan,
        stated_lat: lat,
        stated_lng: lng,
      });

      setResult(`Submitted claim ${response.claim.id} with status ${response.claim.claim_status}`);
      setReason("");
      setPlace("");
      setPincode("");
    } catch (error) {
      if (error instanceof ClaimSubmissionError) {
        setResult(`Failed (${error.status}): ${error.detail}`);
      } else if (error instanceof Error) {
        setResult(`Failed: ${error.message}`);
      } else {
        setResult("Failed due to unknown error.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Worker Claims Console</Text>
        <Text style={styles.subtitle}>Signed device-context claim submission for verified workers.</Text>

        <View style={styles.banner}>
          <Text style={styles.bannerText}>Signed in as {displayName ?? "worker"}</Text>
          <View style={styles.bannerActions}>
            <TouchableOpacity style={styles.smallButton} onPress={onRefreshSession}>
              <Text style={styles.smallButtonText}>Refresh</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.smallButton} onPress={onSignOut}>
              <Text style={styles.smallButtonText}>Sign out</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.label}>Disruption reason</Text>
          <TextInput
            style={[styles.input, styles.multiline]}
            multiline
            numberOfLines={4}
            placeholder="e.g. heavy flooding blocked delivery route"
            placeholderTextColor="#8EA79B"
            value={reason}
            onChangeText={setReason}
          />

          <Text style={styles.label}>Place / Zone</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g. Andheri-W"
            placeholderTextColor="#8EA79B"
            value={place}
            onChangeText={setPlace}
          />

          <Text style={styles.label}>PIN code</Text>
          <TextInput
            style={styles.input}
            placeholder="6-digit PIN code"
            placeholderTextColor="#8EA79B"
            value={pincode}
            onChangeText={setPincode}
            keyboardType="number-pad"
            maxLength={6}
          />

          <Text style={styles.label}>Plan</Text>
          <View style={styles.row}>
            <TouchableOpacity
              style={[styles.chip, plan === "essential" ? styles.chipActive : undefined]}
              onPress={() => setPlan("essential")}
            >
              <Text style={styles.chipText}>Essential</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.chip, plan === "plus" ? styles.chipActive : undefined]}
              onPress={() => setPlan("plus")}
            >
              <Text style={styles.chipText}>Plus</Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity style={styles.secondaryButton} onPress={getLocation}>
            <Text style={styles.secondaryButtonText}>
              {lat && lng ? `Location: ${lat.toFixed(4)}, ${lng.toFixed(4)}` : "Capture location"}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.primaryButton, submitting ? styles.buttonDisabled : undefined]}
            disabled={submitting}
            onPress={submit}
          >
            <Text style={styles.primaryButtonText}>{submitting ? "Submitting..." : "Submit claim"}</Text>
          </TouchableOpacity>

          <Text style={styles.result}>{result}</Text>
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
  },
  subtitle: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.subtitle,
  },
  banner: {
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    borderWidth: 1,
    borderColor: theme.colors.border,
    padding: theme.spacing.md,
    gap: theme.spacing.sm,
  },
  bannerText: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.body,
    fontWeight: "700",
  },
  bannerActions: {
    flexDirection: "row",
    gap: theme.spacing.sm,
  },
  smallButton: {
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: theme.colors.surfaceElevated,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  smallButtonText: {
    color: theme.colors.textPrimary,
    fontWeight: "700",
    fontSize: theme.typography.caption,
  },
  card: {
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    gap: theme.spacing.sm,
  },
  label: {
    color: theme.colors.textPrimary,
    fontWeight: "600",
    fontSize: theme.typography.label,
  },
  input: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: theme.colors.surfaceElevated,
    color: theme.colors.textPrimary,
    borderRadius: theme.radius.sm,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  multiline: {
    minHeight: 96,
    textAlignVertical: "top",
  },
  row: {
    flexDirection: "row",
    gap: theme.spacing.sm,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: theme.colors.chipIdle,
  },
  chipActive: {
    backgroundColor: theme.colors.chipActive,
    borderColor: theme.colors.accent,
  },
  chipText: {
    color: theme.colors.textPrimary,
    fontSize: theme.typography.caption,
    fontWeight: "600",
  },
  secondaryButton: {
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: theme.radius.sm,
    paddingVertical: 11,
    alignItems: "center",
    backgroundColor: theme.colors.surfaceElevated,
  },
  secondaryButtonText: {
    color: theme.colors.textPrimary,
    fontWeight: "600",
  },
  primaryButton: {
    borderRadius: theme.radius.sm,
    paddingVertical: 12,
    alignItems: "center",
    backgroundColor: theme.colors.accentStrong,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontWeight: "700",
  },
  result: {
    color: theme.colors.textMuted,
    fontSize: theme.typography.caption,
  },
});
