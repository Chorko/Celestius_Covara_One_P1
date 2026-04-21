export interface MobileEnv {
  apiBaseUrl: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
  deviceContextHmacSecret: string;
  deviceContextKeyId?: string;
  deviceContextSchemaVersion: string;
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

  return {
    apiBaseUrl: apiBaseUrl.trim(),
    supabaseUrl: supabaseUrl.trim(),
    supabaseAnonKey: supabaseAnonKey.trim(),
    deviceContextHmacSecret: deviceContextHmacSecret.trim(),
    deviceContextKeyId: deviceContextKeyId?.trim() || undefined,
    deviceContextSchemaVersion: deviceContextSchemaVersion.trim(),
  };
}

