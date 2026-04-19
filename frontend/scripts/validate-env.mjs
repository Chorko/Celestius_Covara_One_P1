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

const optionalUrlVars = [
  "NEXT_PUBLIC_MOBILE_DOWNLOAD_ANDROID_URL",
  "NEXT_PUBLIC_MOBILE_DOWNLOAD_IOS_URL",
  "NEXT_PUBLIC_MOBILE_DOWNLOAD_WEB_URL",
  "NEXT_PUBLIC_MOBILE_DOWNLOAD_FALLBACK_URL",
];

for (const name of optionalUrlVars) {
  const raw = process.env[name];
  if (!raw) {
    continue;
  }

  const value = raw.trim();
  if (!value) {
    continue;
  }

  try {
    new URL(value);
  } catch {
    console.error(`${name} must be a valid absolute URL when provided.`);
    process.exit(1);
  }
}

console.log("Frontend environment validation passed.");
