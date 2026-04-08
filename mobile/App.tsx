import React, { useState } from "react";
import {
  Alert,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import * as Location from "expo-location";
import { submitSignedClaim } from "./src/services/api/claims";
import {
  getActiveAccessToken,
  getSupabaseClient,
} from "./src/services/supabase/client";
import { ClaimSubmissionError, type ClaimPlan } from "./src/types/claims";

export default function App() {
  const [reason, setReason] = useState("");
  const [plan, setPlan] = useState<ClaimPlan>("essential");
  const [lat, setLat] = useState<number | undefined>();
  const [lng, setLng] = useState<number | undefined>();
  const [manualToken, setManualToken] = useState("");
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

  async function resolveAccessToken(): Promise<string | null> {
    const sessionToken = await getActiveAccessToken();
    if (sessionToken) {
      return sessionToken;
    }

    if (manualToken.trim().length > 0) {
      return manualToken.trim();
    }

    return null;
  }

  async function submit(): Promise<void> {
    if (!reason.trim()) {
      Alert.alert("Claim reason required", "Please add the disruption reason.");
      return;
    }

    setSubmitting(true);
    setResult("Submitting...");

    try {
      // Creates the client early to surface env configuration issues quickly.
      getSupabaseClient();

      const accessToken = await resolveAccessToken();
      if (!accessToken) {
        throw new Error("No access token available. Sign in or paste a test token.");
      }

      const response = await submitSignedClaim({
        accessToken,
        claim_reason: reason.trim(),
        plan,
        stated_lat: lat,
        stated_lng: lng,
      });

      setResult(`Submitted claim ${response.claim.id} with status ${response.claim.claim_status}`);
      setReason("");
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
      <StatusBar barStyle="light-content" />
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Covara Worker Mobile</Text>
        <Text style={styles.subtitle}>Signed device-context claim submission kickoff</Text>

        <View style={styles.card}>
          <Text style={styles.label}>Disruption reason</Text>
          <TextInput
            style={[styles.input, styles.multiline]}
            multiline
            numberOfLines={4}
            placeholder="e.g. heavy flooding blocked delivery route"
            placeholderTextColor="#8D95A8"
            value={reason}
            onChangeText={setReason}
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

          <Text style={styles.label}>Optional access token override</Text>
          <TextInput
            style={styles.input}
            placeholder="Paste bearer token if no active Supabase session"
            placeholderTextColor="#8D95A8"
            value={manualToken}
            onChangeText={setManualToken}
            autoCapitalize="none"
            autoCorrect={false}
          />

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
    backgroundColor: "#09131F",
  },
  container: {
    padding: 20,
    gap: 14,
  },
  title: {
    color: "#F5F7FA",
    fontSize: 26,
    fontWeight: "700",
  },
  subtitle: {
    color: "#B0B8C9",
    fontSize: 14,
    marginBottom: 10,
  },
  card: {
    backgroundColor: "#13233A",
    borderColor: "#29415F",
    borderWidth: 1,
    borderRadius: 14,
    padding: 14,
    gap: 10,
  },
  label: {
    color: "#D9E2F2",
    fontWeight: "600",
    fontSize: 13,
  },
  input: {
    borderWidth: 1,
    borderColor: "#2E4D73",
    backgroundColor: "#0E1A2B",
    color: "#F5F7FA",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  multiline: {
    minHeight: 96,
    textAlignVertical: "top",
  },
  row: {
    flexDirection: "row",
    gap: 8,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#3E5474",
    backgroundColor: "#102038",
  },
  chipActive: {
    backgroundColor: "#1D4F8B",
    borderColor: "#3E82CC",
  },
  chipText: {
    color: "#E7ECF4",
    fontSize: 12,
    fontWeight: "600",
  },
  secondaryButton: {
    borderColor: "#4B6383",
    borderWidth: 1,
    borderRadius: 10,
    paddingVertical: 11,
    alignItems: "center",
    backgroundColor: "#0F2135",
  },
  secondaryButtonText: {
    color: "#CFDAEA",
    fontWeight: "600",
  },
  primaryButton: {
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
    backgroundColor: "#2F74C0",
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontWeight: "700",
  },
  result: {
    color: "#C7D3E6",
    fontSize: 12,
  },
});
