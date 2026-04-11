const required = [
  "EXPO_PUBLIC_API_BASE_URL",
  "EXPO_PUBLIC_SUPABASE_URL",
  "EXPO_PUBLIC_SUPABASE_ANON_KEY",
  "EXPO_PUBLIC_DEVICE_CONTEXT_HMAC_SECRET",
];

const missing = required.filter((name) => {
  const value = process.env[name];
  return !value || value.trim().length === 0;
});

if (missing.length > 0) {
  console.error("Missing required mobile environment variables:");
  for (const name of missing) {
    console.error(`- ${name}`);
  }
  process.exit(1);
}

console.log("Mobile environment validation passed.");
