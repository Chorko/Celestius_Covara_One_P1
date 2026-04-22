# Covara Worker Mobile

This package contains the mobile app implementation for signed claim
submission and role-aware session gating.

## Current scope in this commit

- React Native Expo app scaffold.
- Supabase-backed session bootstrap with role normalization (`worker` / `insurer_admin`).
- Auth gate, onboarding-required, and KYC-pending screens wired in navigator.
- Signed device-context pipeline compatible with backend contract.
- Claim submission service that sends signed telemetry headers to `POST /claims`.
- Worker claim screen with live location capture plus evidence-photo
  attach/upload to `claim-evidence`.
- Uploaded `evidence_url` now flows through backend EXIF +
  Gemini/SynthID + C2PA fraud checks.
- Admin overview screen for insurer-admin session visibility.

## Prerequisites

- Node.js 20+
- Expo CLI (optional, `npx expo` works)
- Android Studio emulator and/or iOS simulator

## Setup

1. Copy `.env.example` to `.env` and fill values.
2. Install dependencies.
3. Start app.

```bash
cd mobile
npm install
npm run start
```

### No-hassle direct launch (demo mode)

To open directly without pasting a token every time, enable auto-login in `.env`:

```env
EXPO_PUBLIC_AUTO_LOGIN_ENABLED=true
EXPO_PUBLIC_AUTO_LOGIN_PROFILE=worker
EXPO_PUBLIC_AUTO_LOGIN_WORKER_EMAIL=worker@demo.com
EXPO_PUBLIC_AUTO_LOGIN_WORKER_PASSWORD=demo1234
EXPO_PUBLIC_AUTO_LOGIN_ADMIN_EMAIL=admin@demo.com
EXPO_PUBLIC_AUTO_LOGIN_ADMIN_PASSWORD=demo1234
EXPO_PUBLIC_DEFAULT_BEARER_TOKEN=
```

- If `EXPO_PUBLIC_DEFAULT_BEARER_TOKEN` is set, the app uses that token first.
- Otherwise it signs in with profile credentials selected by
  `EXPO_PUBLIC_AUTO_LOGIN_PROFILE` (`worker` or `admin`).
- `EXPO_PUBLIC_AUTO_LOGIN_EMAIL` and `EXPO_PUBLIC_AUTO_LOGIN_PASSWORD`
  remain as a legacy fallback if profile-specific values are not set.
- Restart Metro after changing these values so Expo picks up updated env vars.

## Build and Share (Your Own Expo Account)

Use your own Expo/EAS account and project for download links.

```bash
cd mobile
npx expo login
npx eas login
npx eas-cli@latest whoami
npx eas-cli@latest build --platform android --profile preview \
  --non-interactive --no-wait
npx eas-cli@latest build --platform android --profile production \
  --non-interactive --no-wait
npx eas-cli@latest build --platform ios --profile production
```

Build output URLs can then be mapped into website env vars for `/download` and `/download/go`.

Current verified local config:

- owner: `chorkos-organization`
- slug: `covara-one`
- projectId: `fdc7c955-29ee-4124-9ab2-3d4076983a8e`

Check recent build states:

```bash
cd mobile
npx eas-cli@latest build:list --limit 10 --json
```

If the shell prompt already ends in `.../mobile`, do not run `cd mobile` again.

## Install Android APK (Android Studio)

Use the built APK directly with Android Studio or `adb`.

1. Get the latest finished Android build metadata:

```bash
cd mobile
npx eas-cli@latest build:list --platform android --status finished --limit 1 --json
```

1. Copy `artifacts.buildUrl` from the JSON output and download the APK
  locally.
2. Start your emulator from Android Studio Device Manager.
3. Install the APK by dragging it onto the emulator window.

Optional package verification:

```powershell
adb shell pm list packages | findstr com.covara.worker
```

If you need ad-hoc helper scripts, keep them under
`../TEMP_WILL_BE_DELETED/` instead of `mobile/scripts/`.

## Security notes

- Header/signature behavior follows
  [docs/MOBILE_DEVICE_CONTEXT_CONTRACT.md](../docs/MOBILE_DEVICE_CONTEXT_CONTRACT.md).
- Backend verifier is
  [backend/app/services/device_context_security.py](../backend/app/services/device_context_security.py).
- This kickoff uses client-side HMAC key from env to prove integration path;
  move toward short-lived key rotation and attestation in later phases.

## Known limitations in kickoff

- Root/jailbreak and advanced emulator checks are placeholders until native
  bridges are added.
- Full mobile parity with web worker pages (`/worker/rewards`, `/worker/pricing`,
  richer dashboard analytics) is not complete yet.
- Offline queueing is not complete yet.
- UI is functional and security-first; broader navigation depth is still planned.

## April 2026 Repo Update Addendum

### Newly implemented in current repo

- Expo kickoff app now submits claims with signed device-context headers.
- Device-context contract v2 alignment includes key-id and nonce semantics.
- Backend verifier path is integrated for signature and replay checks.
- TypeScript diagnostics were hardened through local tsconfig settings.

### Planned and next tranche

- Add stronger native attestation checks for rooted or emulated environments.
- Introduce short-lived signing key rotation patterns.
- Build full auth UX and robust offline queueing for unstable networks.
- Expand worker flows beyond kickoff claim submission.
