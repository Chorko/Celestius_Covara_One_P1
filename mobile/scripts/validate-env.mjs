import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

function loadLocalEnvFile() {
  const currentFile = fileURLToPath(import.meta.url);
  const currentDir = path.dirname(currentFile);
  const envPath = path.resolve(currentDir, "..", ".env");

  if (!fs.existsSync(envPath)) {
    return;
  }

  const raw = fs.readFileSync(envPath, "utf8");
  const lines = raw.split(/\r?\n/);

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const eqIndex = trimmed.indexOf("=");
    if (eqIndex <= 0) {
      continue;
    }

    const key = trimmed.slice(0, eqIndex).trim();
    let value = trimmed.slice(eqIndex + 1).trim();

    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }

    if (!process.env[key]) {
      process.env[key] = value;
    }
  }
}

loadLocalEnvFile();

const required = [
  "EXPO_PUBLIC_SUPABASE_URL",
  "EXPO_PUBLIC_SUPABASE_ANON_KEY",
  "EXPO_PUBLIC_DEVICE_CONTEXT_HMAC_SECRET",
];

const recommended = ["EXPO_PUBLIC_API_BASE_URL"];

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

const missingRecommended = recommended.filter((name) => {
  const value = process.env[name];
  return !value || value.trim().length === 0;
});

if (missingRecommended.length > 0) {
  console.warn(
    "Warning: EXPO_PUBLIC_API_BASE_URL is not set. Falling back to the default Render backend URL.",
  );
  for (const name of missingRecommended) {
    console.warn(`- ${name}`);
  }
}

console.log("Mobile environment validation passed.");
