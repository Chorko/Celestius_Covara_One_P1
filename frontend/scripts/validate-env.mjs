const required = [
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_ANON_KEY",
];

const missing = required.filter((name) => {
  const value = process.env[name];
  return !value || value.trim().length === 0;
});

if (missing.length > 0) {
  console.error("Missing required frontend environment variables:");
  for (const name of missing) {
    console.error(`- ${name}`);
  }
  process.exit(1);
}

const apiUrl = process.env.NEXT_PUBLIC_API_URL;
if (apiUrl !== undefined && apiUrl.trim().length === 0) {
  console.error("NEXT_PUBLIC_API_URL is set but empty.");
  process.exit(1);
}

console.log("Frontend environment validation passed.");
