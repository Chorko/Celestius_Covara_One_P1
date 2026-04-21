# Mobile App Distribution and Website Linking

This runbook is the verified source of truth for building and publishing
mobile artifacts and wiring website download links.

## 1. Verified Expo project binding

The mobile app is currently configured to this Expo project:

- owner: `chorkos-organization`
- slug: `covara-one`
- projectId: `fdc7c955-29ee-4124-9ab2-3d4076983a8e`

Config lives in `mobile/app.json`.

## 2. One-time setup (local machine)

Run from `mobile/`:

```bash
npm install
npx expo login
npx eas login
```

Check auth:

```bash
npx eas-cli@latest whoami
```

Expected result: account includes `chorkos-organization`.

## 3. Build commands

### Android preview (APK, internal testing)

```bash
npx eas-cli@latest build --platform android --profile preview \
  --non-interactive --no-wait
```

### Android production (AAB, store upload)

```bash
npx eas-cli@latest build --platform android --profile production \
  --non-interactive --no-wait
```

### iOS production

```bash
npx eas-cli@latest build --platform ios --profile production
```

Note: iOS often requires interactive credential setup at least once.

## 4. Status and artifact checks

Run from `mobile/`:

```bash
npx eas-cli@latest build:list --limit 10 --json
```

To inspect one build:

```bash
npx eas-cli@latest build:view <build-id> --json
```

Important:

- `build:view` does not accept `--non-interactive`.
- If shell path already ends in `.../mobile`, do not run `cd mobile` again.

## 5. Required Expo dashboard environment variables

In Expo project environment variables, set these values at minimum:

- `EXPO_PUBLIC_SUPABASE_URL`
- `EXPO_PUBLIC_SUPABASE_ANON_KEY`
- `EXPO_PUBLIC_DEVICE_CONTEXT_HMAC_SECRET`

Recommended (runtime has a Render fallback if omitted, but explicit is preferred):

- `EXPO_PUBLIC_API_BASE_URL`

Optional (if used by app logic):

- `EXPO_PUBLIC_DEVICE_CONTEXT_KEY_ID`
- `EXPO_PUBLIC_DEVICE_CONTEXT_SCHEMA_VERSION`

## 6. Website download link variables

Set these frontend env vars in deployment:

- `NEXT_PUBLIC_MOBILE_DOWNLOAD_ANDROID_URL`
- `NEXT_PUBLIC_MOBILE_DOWNLOAD_IOS_URL`
- `NEXT_PUBLIC_MOBILE_DOWNLOAD_WEB_URL`
- `NEXT_PUBLIC_MOBILE_DOWNLOAD_FALLBACK_URL`

Recommended values:

- Android: Play Store listing URL (preferred) or internal install URL for testers
- iOS: TestFlight/App Store URL
- Web: project landing page URL
- Fallback: generic product/download page URL

Current values for this build (2026-04-20):

- `NEXT_PUBLIC_MOBILE_DOWNLOAD_ANDROID_URL=https://expo.dev/artifacts/eas/uJHrzKSycbBxoTVhNotdM2.apk`
- `NEXT_PUBLIC_MOBILE_DOWNLOAD_IOS_URL=` (leave empty until iOS/TestFlight URL is ready)
- `NEXT_PUBLIC_MOBILE_DOWNLOAD_WEB_URL=https://expo.dev/accounts/chorkos-organization/projects/covara-one/builds/e8b6a8e7-bb15-48f4-b962-35824fa79fbb`
- `NEXT_PUBLIC_MOBILE_DOWNLOAD_FALLBACK_URL=https://expo.dev/accounts/chorkos-organization/projects/covara-one/builds/e8b6a8e7-bb15-48f4-b962-35824fa79fbb`

## 7. Routes already wired

- `/download` -> platform chooser page
- `/download/go` -> smart redirect by user agent
- `/download/go?platform=android` -> force Android
- `/download/go?platform=ios` -> force iOS

## 8. Common failure modes and fixes

### `Compose Compiler requires Kotlin 1.9.25`

Fix is already applied in `mobile/app.json` via `expo-build-properties`.

### `expo-asset cannot be found`

Install and re-run export/build:

```bash
npx expo install expo-asset
npx expo export --platform android
```

### `ECONNRESET` during `build:list` or upload

Retry the same command. Network failures are transient and common on long
uploads.

## 9. Release verification checklist

Run from `mobile/`:

```bash
npm run validate:env
npm run typecheck
npx expo export --platform android
npx eas-cli@latest build --platform android --profile production \
  --non-interactive --no-wait
npx eas-cli@latest build:list --limit 5 --json
```

Ship only when latest production build status is `FINISHED` and artifact URL
is present.
