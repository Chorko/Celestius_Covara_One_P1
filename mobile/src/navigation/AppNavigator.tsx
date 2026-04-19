import React, { useCallback, useEffect, useState } from "react";
import { StatusBar } from "react-native";
import { fetchAuthMe, fetchWorkerProfile, type MobileRole } from "../services/api/session";
import { HttpRequestError } from "../services/api/http";
import { getActiveAccessToken, getSupabaseClient } from "../services/supabase/client";
import {
  useUserStore,
  type KycSnapshot,
  type Profile,
  type UserRole,
} from "../store/userStore";
import { AdminOverviewScreen } from "../screens/AdminOverviewScreen";
import { AuthGateScreen } from "../screens/AuthGateScreen";
import { KycPendingScreen } from "../screens/KycPendingScreen";
import { LoadingScreen } from "../screens/LoadingScreen";
import { OnboardingRequiredScreen } from "../screens/OnboardingRequiredScreen";
import { WorkerClaimScreen } from "../screens/WorkerClaimScreen";

function toRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object") {
    return {};
  }
  return value as Record<string, unknown>;
}

function normalizeRole(role: MobileRole): UserRole {
  if (role === "worker" || role === "insurer_admin") {
    return role;
  }
  return null;
}

function buildProfile(rawProfile: unknown, fallbackId: string, fallbackEmail: string | null, role: UserRole): Profile {
  const record = toRecord(rawProfile);
  const fullName = typeof record.full_name === "string" ? record.full_name : null;
  const email = typeof record.email === "string" ? record.email : fallbackEmail;
  const phone = typeof record.phone === "string" ? record.phone : null;

  return {
    ...record,
    id: typeof record.id === "string" ? record.id : fallbackId,
    full_name: fullName,
    email,
    phone,
    role,
  };
}

function buildKyc(workerProfile: Record<string, unknown>): KycSnapshot {
  const aadhaarVerified = Boolean(workerProfile.aadhaar_verified);
  const bankVerified = Boolean(workerProfile.bank_verified);
  const phoneVerified = Boolean(workerProfile.phone_verified);
  const faceVerified = Boolean(workerProfile.face_verified);

  return {
    aadhaarVerified,
    bankVerified,
    phoneVerified,
    faceVerified,
    isComplete: aadhaarVerified && bankVerified,
  };
}

export function AppNavigator() {
  const {
    profile,
    role,
    needsOnboarding,
    accessToken,
    kyc,
    setSessionSnapshot,
    setKyc,
    logout,
  } = useUserStore();

  const [manualToken, setManualToken] = useState("");
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isResolvingSession, setIsResolvingSession] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const hydrateSession = useCallback(
    async (tokenOverride?: string): Promise<void> => {
      setIsResolvingSession(true);
      setAuthError(null);

      try {
        const token = tokenOverride?.trim() || (await getActiveAccessToken());

        if (!token) {
          setSessionSnapshot({
            user: null,
            profile: null,
            role: null,
            needsOnboarding: false,
            accessToken: null,
          });
          setKyc(null);
          return;
        }

        const authMe = await fetchAuthMe(token);
        const normalizedRole = normalizeRole(authMe.role);
        const resolvedProfile = buildProfile(
          authMe.profile,
          authMe.id,
          authMe.email,
          normalizedRole,
        );

        setSessionSnapshot({
          user: null,
          profile: resolvedProfile,
          role: normalizedRole,
          needsOnboarding: Boolean(authMe.needs_onboarding),
          accessToken: token,
        });

        if (normalizedRole === "worker" && !authMe.needs_onboarding) {
          const workerProfile = await fetchWorkerProfile(token);
          setKyc(buildKyc(workerProfile));
        } else {
          setKyc(null);
        }
      } catch (error) {
        setSessionSnapshot({
          user: null,
          profile: null,
          role: null,
          needsOnboarding: false,
          accessToken: null,
        });
        setKyc(null);

        if (error instanceof HttpRequestError) {
          if (error.status === 401) {
            setAuthError("Session expired. Please sign in again.");
          } else {
            setAuthError(`Unable to load session: ${error.detail}`);
          }
        } else if (error instanceof Error) {
          setAuthError(error.message);
        } else {
          setAuthError("Unable to load session.");
        }
      } finally {
        setIsResolvingSession(false);
        setIsBootstrapping(false);
      }
    },
    [setSessionSnapshot, setKyc],
  );

  useEffect(() => {
    void hydrateSession();
  }, [hydrateSession]);

  async function signOut(): Promise<void> {
    try {
      await getSupabaseClient().auth.signOut();
    } finally {
      logout();
      setAuthError(null);
      setManualToken("");
    }
  }

  function retryWithManualToken(): void {
    if (!manualToken.trim()) {
      setAuthError("Paste a bearer token before continuing.");
      return;
    }

    void hydrateSession(manualToken);
  }

  if (isBootstrapping) {
    return (
      <>
        <StatusBar barStyle="light-content" />
        <LoadingScreen />
      </>
    );
  }

  if (!accessToken) {
    return (
      <>
        <StatusBar barStyle="light-content" />
        <AuthGateScreen
          manualToken={manualToken}
          errorMessage={authError}
          loading={isResolvingSession}
          onChangeManualToken={setManualToken}
          onTrySupabaseSession={() => {
            void hydrateSession();
          }}
          onUseManualToken={retryWithManualToken}
        />
      </>
    );
  }

  if (needsOnboarding || !role) {
    return (
      <>
        <StatusBar barStyle="light-content" />
        <OnboardingRequiredScreen
          role={role}
          onRefresh={() => {
            void hydrateSession(accessToken);
          }}
          onSignOut={() => {
            void signOut();
          }}
        />
      </>
    );
  }

  if (role === "insurer_admin") {
    return (
      <>
        <StatusBar barStyle="light-content" />
        <AdminOverviewScreen
          profile={profile}
          onRefresh={() => {
            void hydrateSession(accessToken);
          }}
          onSignOut={() => {
            void signOut();
          }}
        />
      </>
    );
  }

  if (role === "worker" && !kyc?.isComplete) {
    return (
      <>
        <StatusBar barStyle="light-content" />
        <KycPendingScreen
          kyc={kyc}
          onRefresh={() => {
            void hydrateSession(accessToken);
          }}
          onSignOut={() => {
            void signOut();
          }}
        />
      </>
    );
  }

  return (
    <>
      <StatusBar barStyle="light-content" />
      <WorkerClaimScreen
        accessToken={accessToken}
        displayName={profile?.full_name}
        onRefreshSession={() => {
          void hydrateSession(accessToken);
        }}
        onSignOut={() => {
          void signOut();
        }}
      />
    </>
  );
}
