import React, { useCallback, useEffect, useState } from "react";
import { StatusBar } from "react-native";
import { fetchAuthMe, fetchWorkerProfile, type MobileRole } from "../services/api/session";
import { HttpRequestError } from "../services/api/http";
import { getMobileEnv } from "../config/env";
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

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isResolvingSession, setIsResolvingSession] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const hydrateSession = useCallback(
    async (tokenOverride?: string): Promise<void> => {
      setIsResolvingSession(true);
      setAuthError(null);

      try {
        const env = getMobileEnv();
        let token = tokenOverride?.trim() || (await getActiveAccessToken());
        let tokenHint = "Sign in with your email and password.";

        if (!token && env.autoLoginEnabled) {
          if (env.defaultBearerToken) {
            token = env.defaultBearerToken;
          } else {
            const profileEmail =
              env.autoLoginProfile === "admin"
                ? env.autoLoginAdminEmail
                : env.autoLoginWorkerEmail;
            const profilePassword =
              env.autoLoginProfile === "admin"
                ? env.autoLoginAdminPassword
                : env.autoLoginWorkerPassword;
            const resolvedEmail = profileEmail || env.autoLoginEmail;
            const resolvedPassword = profilePassword || env.autoLoginPassword;

            if (!resolvedEmail || !resolvedPassword) {
              tokenHint =
                "Auto login is enabled but credentials are missing. Sign in with your email and password.";
            } else {
            const { data, error } = await getSupabaseClient().auth.signInWithPassword({
                email: resolvedEmail,
                password: resolvedPassword,
            });

            if (error) {
              tokenHint = `Auto login failed: ${error.message}. Sign in with your email and password.`;
            } else {
              token = data.session?.access_token ?? null;
            }
            }
          }
        }

        if (!token) {
          setSessionSnapshot({
            user: null,
            profile: null,
            role: null,
            needsOnboarding: false,
            accessToken: null,
          });
          setKyc(null);
          setAuthError(
            "No active Supabase session found on this device. " +
            tokenHint
          );
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
    }
  }

  async function signInWithEmailPassword(): Promise<void> {
    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail || !password) {
      setAuthError("Enter both email and password.");
      return;
    }

    setIsResolvingSession(true);
    setAuthError(null);

    try {
      const { data, error } = await getSupabaseClient().auth.signInWithPassword({
        email: normalizedEmail,
        password,
      });

      if (error) {
        setAuthError(`Sign-in failed: ${error.message}`);
        return;
      }

      const signedInToken = data.session?.access_token;
      if (!signedInToken) {
        setAuthError("Sign-in succeeded but no session token was returned.");
        return;
      }

      await hydrateSession(signedInToken);
    } catch (error) {
      if (error instanceof Error) {
        setAuthError(error.message);
      } else {
        setAuthError("Sign-in failed.");
      }
    } finally {
      setIsResolvingSession(false);
    }
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
          email={email}
          password={password}
          errorMessage={authError}
          loading={isResolvingSession}
          onChangeEmail={setEmail}
          onChangePassword={setPassword}
          onSignIn={() => {
            void signInWithEmailPassword();
          }}
          onTrySupabaseSession={() => {
            void hydrateSession();
          }}
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
