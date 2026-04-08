export interface MobileEnv {
  apiBaseUrl: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
  deviceContextHmacSecret: string;
  deviceContextKeyId?: string;
  deviceContextSchemaVersion: string;
}

function readOptional(name: string): string | undefined {
  const value = process.env[name];
  if (!value) {
    return undefined;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function readRequired(name: string): string {
  const value = readOptional(name);
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }

  return value;
}

export function getMobileEnv(): MobileEnv {
  return {
    apiBaseUrl: readRequired("EXPO_PUBLIC_API_BASE_URL"),
    supabaseUrl: readRequired("EXPO_PUBLIC_SUPABASE_URL"),
    supabaseAnonKey: readRequired("EXPO_PUBLIC_SUPABASE_ANON_KEY"),
    deviceContextHmacSecret: readRequired("EXPO_PUBLIC_DEVICE_CONTEXT_HMAC_SECRET"),
    deviceContextKeyId: readOptional("EXPO_PUBLIC_DEVICE_CONTEXT_KEY_ID"),
    deviceContextSchemaVersion:
      readOptional("EXPO_PUBLIC_DEVICE_CONTEXT_SCHEMA_VERSION") ?? "2.0",
  };
}
