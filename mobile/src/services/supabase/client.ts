import AsyncStorage from "@react-native-async-storage/async-storage";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { getMobileEnv } from "../../config/env";

let supabase: SupabaseClient | null = null;

export function getSupabaseClient(): SupabaseClient {
  if (supabase) {
    return supabase;
  }

  const env = getMobileEnv();
  supabase = createClient(env.supabaseUrl, env.supabaseAnonKey, {
    auth: {
      storage: AsyncStorage,
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: false,
    },
  });

  return supabase;
}

export async function getActiveAccessToken(): Promise<string | null> {
  const client = getSupabaseClient();
  const { data, error } = await client.auth.getSession();

  if (error) {
    return null;
  }

  return data.session?.access_token ?? null;
}
