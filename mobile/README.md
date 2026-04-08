# Covara Worker Mobile (Implementation Start)

This package is the mobile implementation kickoff for signed claim submission.

## Current scope in this commit

- React Native Expo app scaffold.
- Signed device-context pipeline compatible with backend contract.
- Claim submission service that sends signed telemetry headers to `POST /claims`.
- Minimal worker-facing screen to submit a signed claim.

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

## Security notes

- Header/signature behavior follows [docs/MOBILE_DEVICE_CONTEXT_CONTRACT.md](../docs/MOBILE_DEVICE_CONTEXT_CONTRACT.md).
- Backend verifier is [backend/app/services/device_context_security.py](../backend/app/services/device_context_security.py).
- This kickoff uses client-side HMAC key from env to prove integration path; move toward short-lived key rotation and attestation in later phases.

## Known limitations in kickoff

- Root/jailbreak and advanced emulator checks are placeholders until native bridges are added.
- Full auth screens and offline queueing are not complete yet.
- UI is functional but intentionally minimal while core security path is being wired first.
