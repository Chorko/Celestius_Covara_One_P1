export interface MobileEnv {
  apiBaseUrl: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
  deviceContextHmacSecret: string;
  deviceContextKeyId?: string;
  deviceContextSchemaVersion: string;
  autoLoginEnabled: boolean;
  autoLoginProfile: "worker" | "admin";
  defaultBearerToken?: string;
  autoLoginEmail?: string;
  autoLoginPassword?: string;
  autoLoginWorkerEmail?: string;
  autoLoginWorkerPassword?: string;
  autoLoginAdminEmail?: string;
  autoLoginAdminPassword?: string;
}

/**
 * Expo / Metro inline-replaces **static** references like
 *   process.env.EXPO_PUBLIC_FOO
 * at bundle time.  Dynamic lookups such as process.env[name]
 * are NOT replaced and will always be undefined in the built APK.
 *
 * Therefore every variable must be read with a direct static
 * property access — no helper indirection.
 */
export function getMobileEnv(): MobileEnv {
  const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL ?? "";
  const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL ?? "";
  const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? "";
  const deviceContextHmacSecret = process.env.EXPO_PUBLIC_DEVICE_CONTEXT_HMAC_SECRET ?? "";
  const deviceContextKeyId = process.env.EXPO_PUBLIC_DEVICE_CONTEXT_KEY_ID ?? undefined;
  const deviceContextSchemaVersion = process.env.EXPO_PUBLIC_DEVICE_CONTEXT_SCHEMA_VERSION ?? "2.0";
  const autoLoginEnabledRaw = process.env.EXPO_PUBLIC_AUTO_LOGIN_ENABLED ?? "false";
  const autoLoginProfileRaw = process.env.EXPO_PUBLIC_AUTO_LOGIN_PROFILE ?? "worker";
  const defaultBearerToken = process.env.EXPO_PUBLIC_DEFAULT_BEARER_TOKEN ?? undefined;
  const autoLoginEmail = process.env.EXPO_PUBLIC_AUTO_LOGIN_EMAIL ?? undefined;
  const autoLoginPassword = process.env.EXPO_PUBLIC_AUTO_LOGIN_PASSWORD ?? undefined;
  const autoLoginWorkerEmail = process.env.EXPO_PUBLIC_AUTO_LOGIN_WORKER_EMAIL ?? undefined;
  const autoLoginWorkerPassword = process.env.EXPO_PUBLIC_AUTO_LOGIN_WORKER_PASSWORD ?? undefined;
  const autoLoginAdminEmail = process.env.EXPO_PUBLIC_AUTO_LOGIN_ADMIN_EMAIL ?? undefined;
  const autoLoginAdminPassword = process.env.EXPO_PUBLIC_AUTO_LOGIN_ADMIN_PASSWORD ?? undefined;

  const normalizedDefaultBearer = (defaultBearerToken ?? "").trim();
  const bearerDisabled = ["", "none", "null", "disabled", "off"].includes(
    normalizedDefaultBearer.toLowerCase(),
  );

  const missing: string[] = [];
  if (!apiBaseUrl.trim()) missing.push("EXPO_PUBLIC_API_BASE_URL");
  if (!supabaseUrl.trim()) missing.push("EXPO_PUBLIC_SUPABASE_URL");
  if (!supabaseAnonKey.trim()) missing.push("EXPO_PUBLIC_SUPABASE_ANON_KEY");
  if (!deviceContextHmacSecret.trim()) missing.push("EXPO_PUBLIC_DEVICE_CONTEXT_HMAC_SECRET");

  if (missing.length > 0) {
    throw new Error(
      `Missing required environment variable (checked: ${missing.join(", ")})\n\n` +
      `Set these Expo variables:\n${missing.map((n) => `- ${n}`).join("\n")}\n\n` +
      `Source of truth: mobile/.env.example and Expo project environment settings.`
    );
  }

  const autoLoginEnabled = ["1", "true", "yes", "on"].includes(
    autoLoginEnabledRaw.trim().toLowerCase(),
  );
  const autoLoginProfile =
    autoLoginProfileRaw.trim().toLowerCase() === "admin" ? "admin" : "worker";

  return {
    apiBaseUrl: apiBaseUrl.trim(),
    supabaseUrl: supabaseUrl.trim(),
    supabaseAnonKey: supabaseAnonKey.trim(),
    deviceContextHmacSecret: deviceContextHmacSecret.trim(),
    deviceContextKeyId: deviceContextKeyId?.trim() || undefined,
    deviceContextSchemaVersion: deviceContextSchemaVersion.trim(),
    autoLoginEnabled,
    autoLoginProfile,
    defaultBearerToken: bearerDisabled ? undefined : normalizedDefaultBearer,
    autoLoginEmail: autoLoginEmail?.trim() || undefined,
    autoLoginPassword: autoLoginPassword?.trim() || undefined,
    autoLoginWorkerEmail: autoLoginWorkerEmail?.trim() || undefined,
    autoLoginWorkerPassword: autoLoginWorkerPassword?.trim() || undefined,
    autoLoginAdminEmail: autoLoginAdminEmail?.trim() || undefined,
    autoLoginAdminPassword: autoLoginAdminPassword?.trim() || undefined,
  };
}

