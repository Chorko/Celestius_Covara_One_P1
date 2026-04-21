export interface MobileEnv {
  apiBaseUrl: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
  deviceContextHmacSecret: string;
  deviceContextKeyId?: string;
  deviceContextSchemaVersion: string;
}

declare const process: {
  env: Record<string, string | undefined>;
};

const DEFAULT_API_BASE_URL = "https://covara-backend.onrender.com";

const API_BASE_ENV_NAMES = ["EXPO_PUBLIC_API_BASE_URL", "API_BASE_URL"];
const SUPABASE_URL_ENV_NAMES = ["EXPO_PUBLIC_SUPABASE_URL", "SUPABASE_URL"];
const SUPABASE_ANON_ENV_NAMES = [
  "EXPO_PUBLIC_SUPABASE_ANON_KEY",
  "SUPABASE_ANON_KEY",
  "NEXT_PUBLIC_SUPABASE_ANON_KEY",
];
const DEVICE_HMAC_ENV_NAMES = [
  "EXPO_PUBLIC_DEVICE_CONTEXT_HMAC_SECRET",
  "DEVICE_CONTEXT_HMAC_SECRET",
];
const DEVICE_KEY_ID_ENV_NAMES = ["EXPO_PUBLIC_DEVICE_CONTEXT_KEY_ID", "DEVICE_CONTEXT_KEY_ID"];
const DEVICE_SCHEMA_ENV_NAMES = [
  "EXPO_PUBLIC_DEVICE_CONTEXT_SCHEMA_VERSION",
  "DEVICE_CONTEXT_SCHEMA_VERSION",
];

function readOptional(name: string): string | undefined {
  const value = process.env[name];
  if (!value) {
    return undefined;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function readAnyOptional(names: string[]): string | undefined {
  for (const name of names) {
    const value = readOptional(name);
    if (value) {
      return value;
    }
  }

  return undefined;
}

function readRequiredAny(names: string[], fallback?: string): string {
  const value = readAnyOptional(names);
  if (value) {
    return value;
  }

  if (fallback) {
    return fallback;
  }

  throw new Error(`Missing required environment variable (checked: ${names.join(", ")})`);
}

export function getMobileEnv(): MobileEnv {
  return {
    // API base falls back to the verified Render deployment so preview APKs keep working
    // even if EXPO_PUBLIC_API_BASE_URL was not injected in Expo project variables.
    apiBaseUrl: readRequiredAny(API_BASE_ENV_NAMES, DEFAULT_API_BASE_URL),
    supabaseUrl: readRequiredAny(SUPABASE_URL_ENV_NAMES),
    supabaseAnonKey: readRequiredAny(SUPABASE_ANON_ENV_NAMES),
    deviceContextHmacSecret: readRequiredAny(DEVICE_HMAC_ENV_NAMES),
    deviceContextKeyId: readAnyOptional(DEVICE_KEY_ID_ENV_NAMES),
    deviceContextSchemaVersion: readAnyOptional(DEVICE_SCHEMA_ENV_NAMES) ?? "2.0",
  };
}
