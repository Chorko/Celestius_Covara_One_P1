# Backend - API Layer & Service Orchestration

> The backend orchestrates the insurance logic. It should be easy to read, easy to demo, and segmented cleanly enough that an evaluator can follow the flow without reverse-engineering the code.

---

## Engineering Snapshot (2026-04-05)

- Added reliability schema path with migrations `10` to `13` (rewards ledger, durable outbox, transactional claim+outbox persistence RPC, and consumer dead-letter status support).
- Introduced broker-agnostic event bus package (`backend/app/services/event_bus/`) with in-memory + Kafka adapters, outbox relay service, and consumer idempotency helpers.
- Added admin operations router `backend/app/routers/events.py` with outbox and consumer status/dead-letter/requeue endpoints.
- Enabled background outbox relay loop and optional Kafka consumer loop in app lifespan, configured through `EVENT_*` environment flags.
- Hardened request layer with signed mobile device-context verification, rate limits (`slowapi`), and explicit OWASP security headers.
- Added focused reliability tests for consumers, outbox ops, Kafka consumer runner, and events-router consumer endpoints.

---

## Implementation Status

| Component | Status |
|-----------|--------|
| Service architecture definition | ✅ Implemented |
| FastAPI app with routers | ✅ Implemented |
| Auth endpoints (login, signup, profile) | ✅ Implemented |
| Claims endpoints (submit, list, detail, review, flag) | ✅ Implemented |
| Policies endpoints (quote with plan, activate with plan) | ✅ Implemented |
| Triggers endpoints (live feed, inject) | ✅ Implemented |
| Workers endpoints (profile, stats) | ✅ Implemented |
| Zones endpoints (list, detail, cities) | ✅ Implemented |
| Analytics endpoint (admin KPIs) | ✅ Implemented |
| Ingest endpoints (weather, AQI, traffic, scan-all-zones) | ✅ Implemented |
| 8-stage claim pipeline | ✅ Implemented |
| IRDAI pricing engine (₹28/₹42 weekly fixed plans) | ✅ Implemented |
| Fraud scoring engine (5-layer Ghost Shift Detector) | ✅ Implemented |
| TomTom route plausibility in Layer 2 | ✅ Implemented |
| Manual claim verifier | ✅ Implemented |
| Gemini AI claim narrative | ✅ Implemented |
| EXIF evidence extraction (forensic) | ✅ Implemented |
| Anti-spoofing verification | ✅ Implemented |
| Image forensics & AI detection | ✅ Implemented |
| Region controls & behavioral identity | ✅ Implemented |
| Region validation cache (fast-lane) | ✅ Implemented |
| Payout safety (event-ID, worker-event uniqueness) | ✅ Implemented |
| Claim state machine (8 states, soft hold) | ✅ Implemented |
| Post-approval fraud controls | ✅ Implemented |
| Supabase SQL schema (14 tables, unified migration) | ✅ Implemented |
| Row-Level Security policies | ✅ Implemented |
| CLI seed system | ✅ Implemented |
| KYC service (Postman Mock — PAN, Bank Verify) | ✅ Implemented |
| Twilio WhatsApp + OTP (7 templates) | ✅ Implemented |
| OpenWeather live data (weather + temp triggers) | ✅ Live |
| CPCB AQI live data (data.gov.in, 511 stations) | ✅ Live |
| TomTom Traffic Flow + Routing | ✅ Live |
| ApiProviderPool (round-robin + LRU cache) | ✅ Implemented |
| Docker multi-stage build | ✅ Implemented |
| GitHub Actions CI/CD (3-job pipeline) | ✅ Implemented |
| Automated test suite (65 smoke validations, 100% pass) | ✅ Implemented |
| Redis caching layer (`fastapi-cache2`) | ✅ Implemented (TTL decorators on `/triggers/live`, `/analytics/summary`, `/zones/`, `/policies/quote`) |
| ML live inference | ✅ Implemented (`get_claim_probability()` — lazy-loads `severity_rf.joblib`, falls back to p=0.15 if model missing) |
| DBSCAN cluster intelligence (Layer 4) | ✅ Implemented (`sklearn.cluster.DBSCAN` on lat/lng/timestamp batch) |
| Simulation & mock-data endpoints | ✅ Implemented (`/simulate/claim-scenario`, `/simulate/mock-data/generate`) |
| Payment gateway service | ✅ Implemented (provider adapter workflow with `http_gateway` / Stripe Test Mode + `simulated_gateway` + `mock_fallback`) |
| Gamification & Rewards engine | ✅ Implemented (`coins_ledger` + 5 endpoints + auto-claim integration) |
| Rule/model version governance | ✅ Implemented (`rule_versions` + `model_versions`, rollout controls, persisted version IDs on claim decisions) |
| Rate Limiting & OWASP Headers | ✅ Implemented (`slowapi` + explicit CORS + 6 security headers) |
---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Framework | Python (FastAPI) | Transparent REST endpoint design, automatic OpenAPI docs, strong data-science ecosystem integration |
| Database | Supabase (PostgreSQL) | Managed PostgreSQL with built-in Auth, Storage, RLS, and real-time capabilities |
| Auth | Supabase Auth | Google OAuth + email/password, JWT tokens, auth triggers for profile bootstrap |
| AI | Google Gemini | Claim narrative generation for admin-assisted review |
| HTTP Client | httpx | Async HTTP for evidence fetching and external calls |

---

## Quick Start

```bash
# From the repo root:
pip install -r requirements.txt

# Set environment variables (see .env.example)
cp .env.example .env  # fill in your keys
uvicorn backend.app.main:app --reload --port 8000

# Or with Docker:
docker compose up --build
```

Then open:
- http://localhost:8000/docs (Swagger UI — all endpoints)
- http://localhost:8000/health
- **Live deployment**: https://covara-backend.onrender.com/docs

---

## Service Architecture

```mermaid
flowchart TD
    subgraph "API Gateway"
        AUTH["Auth &<br/>Onboarding"]
    end

    subgraph "Core Services"
        PS["Policy<br/>Service"]
        PR["Pricing<br/>Service"]
        TM["Trigger<br/>Monitor"]
        CO["Claim<br/>Orchestrator"]
        FS["Fraud Scoring<br/>Service"]
        PO["Payout<br/>Service"]
        AS["Analytics<br/>Service"]
    end

    subgraph "Data Layer"
        DB[("Supabase<br/>PostgreSQL")]
    end

    subgraph "External"
        GM["Gemini AI"]
        EX["Integrations<br/>(Weather, AQI, etc.)"]
    end

    AUTH --> PS
    PS --> PR
    EX --> TM
    TM --> CO
    CO --> FS
    FS --> PO
    CO --> AS
    CO --> GM
    PS & PR & CO & FS & PO & AS --> DB
    RC[("Redis")] --> CO
    RC --> TM
    RC --> AS

    style AUTH fill:#4a9eff,color:#fff
    style CO fill:#e74c3c,color:#fff
    style FS fill:#9b59b6,color:#fff
    style PO fill:#2ecc71,color:#fff
```

---

## Endpoint Inventory

### Auth Endpoints

| Method | Endpoint | Purpose | Status |
|--------|----------|---------|--------|
| `POST` | `/auth/signup` | Register new user (worker or insurer) | ✅ Implemented |
| `POST` | `/auth/login` | Email/password login | ✅ Implemented |
| `GET` | `/auth/profile` | Get current user profile + role | ✅ Implemented |

### Worker Endpoints

| Method | Endpoint | Purpose | Status |
|--------|----------|---------|--------|
| `GET` | `/workers/profile` | Get worker profile with zone info | ✅ Implemented |
| `GET` | `/workers/stats` | Get worker earnings stats (14-day chart) | ✅ Implemented |

### Policy Endpoints

| Method | Endpoint | Purpose | Status |
|--------|----------|---------|--------|
| `GET` | `/policies/quote` | Generate weekly premium quote (plan-aware: essential/plus) | ✅ Implemented |
| `POST` | `/policies/activate` | Activate weekly policy with plan selection | ✅ Implemented |

### Trigger & Claim Endpoints

| Method | Endpoint | Purpose | Status |
|--------|----------|---------|--------|
| `GET` | `/triggers/live` | Current active trigger events | ✅ Implemented |
| `POST` | `/triggers/inject` | Inject mock trigger event (admin) | ✅ Implemented |
| `POST` | `/claims` | Submit manual claim with evidence + plan | ✅ Implemented |
| `GET` | `/claims` | List claims (worker=own, admin=all) | ✅ Implemented |
| `GET` | `/claims/{id}` | Get claim detail, evidence, payout | ✅ Implemented |
| `POST` | `/claims/{id}/review` | Admin review action on claim | ✅ Implemented |
| `POST` | `/claims/{id}/flag` | Post-approval fraud flag + trust downgrade | ✅ Implemented |

### Rewards & Gamification Endpoints

| Method | Endpoint | Purpose | Status |
|--------|----------|---------|--------|
| `GET` | `/rewards/balance` | Get worker coin balance & options | ✅ Implemented |
| `GET` | `/rewards/history` | List recent coin transactions | ✅ Implemented |
| `POST` | `/rewards/check-in` | Weekly 10-coin login bonus | ✅ Implemented |
| `POST` | `/rewards/redeem/discount` | Redeem 100 coins for ₹5 off | ✅ Implemented |
| `POST` | `/rewards/redeem/free-week`| Redeem 500 coins for free week | ✅ Implemented |

### Zone & Analytics Endpoints

| Method | Endpoint | Purpose | Status |
|--------|----------|---------|--------|
| `GET` | `/zones` | List zones, optionally by city (cached 1hr) | ✅ Implemented |
| `GET` | `/zones/{id}` | Zone detail with polygon | ✅ Implemented |
| `GET` | `/zones/cities/list` | Distinct cities with zones | ✅ Implemented |
| `GET` | `/analytics/summary` | Admin KPI metrics (cached 2min) | ✅ Implemented |

### Simulation & Dev Endpoints

| Method | Endpoint | Purpose | Status |
|--------|----------|---------|--------|
| `POST` | `/simulate/claim-scenario` | Simulate a full 8-stage claim pipeline run without persisting to DB | ✅ Implemented |
| `POST` | `/simulate/mock-data/generate` | Regenerate synthetic seed data into the DB | ✅ Implemented |

---

## Core Services (backend/app/services/)

| Module | File | Responsibility |
|--------|------|---------------|
| **Claim Pipeline** | `claim_pipeline.py` | 8-stage orchestration: validation → severity → parametric band → anti-spoofing + fraud → decision |
| **Severity Scoring** | `severity.py` | Compute severity score S from trigger data |
| **Pricing Engine** | `pricing.py` | Compute B (covered income), E (exposure), C (confidence), premiums and payouts |
| **Fraud Engine** | `fraud_engine.py` | 5-layer Ghost Shift Detector with signal confidence hierarchy, 5-band decisions (`auto_approve`, `needs_review`, `hold_for_fraud`, `batch_hold`, `reject_spoof_risk`), and ML feature vector output |
| **Anti-Spoofing** | `anti_spoofing.py` | Layer 3: EXIF vs GPS cross-check, timestamp freshness, VPN/datacenter IP detection, device continuity, impossible travel velocity, emulator/root detection |
| **Image Forensics** | `image_forensics.py` | Evidence integrity: EXIF completeness, software/editor detection, timestamp chain-of-custody, GPS precision, camera-device consistency, AI detection stub (Gemini SynthID) |
| **Region Controls** | `region_controls.py` | Behavioral identity: zone affinity, pre-trigger presence, dynamic trust penalties, zone volume monitoring, mass-claim throttling |
| **Region Validation Cache** | `region_validation_cache.py` | Fast-lane eligibility checks, cluster spike liquidity protection, post-approval trust score penalties |
| **Manual Verifier** | `manual_claim_verifier.py` | Evidence completeness and geo confidence for manual claims |
| **Evidence Processing** | `evidence.py` | EXIF metadata extraction (forensic-grade: 10+ fields including Software, DateTimeDigitized, ModifyDate, Make, GPS precision) |
| **Gemini Analysis** | `gemini_analysis.py` | AI-generated claim narrative for admin review |

---

## Database Schema (backend/sql/)

| File | Contents |
|------|----------|
| `00_unified_migration.sql` | **Single-file schema** — all 14+2 tables, RLS, auth triggers, storage policies, grants (idempotent) |
| `06_synthetic_seed.sql` | 62KB seed: demo users, zones, trigger events, claims |

> The schema is fully consolidated. Run `00_unified_migration.sql` in Supabase SQL Editor to bootstrap a fresh project.

---

## New Services (Phase 2)

| Module | File | Responsibility |
|--------|------|---------------|
| **KYC Service** | `kyc_service.py` | Postman Mock for PAN/Bank verify. Switchable to Sandbox.co.in. 3-tier progressive KYC ladder. |
| **Twilio Service** | `twilio_service.py` | WhatsApp + OTP. 7 notification templates. Mock fallback. |
| **Trigger Evaluator** | `trigger_evaluator.py` | Threshold evaluation bridge for all 15+ trigger families. |
| **Zone Coordinates** | `zone_coordinates.py` | Zone-to-coordinate mapping for batch scanning. |
| **Auto Claim Engine** | `auto_claim_engine.py` | Zero-touch claim initiation from verified trigger events. Includes valid DBSCAN queries. |
| **Rewards Engine** | `rewards_engine.py` | Gamification layer: award coins, fetch balance, handle redemptions, log to `coins_ledger`. |
| **Payout Provider Layer** | `payout_provider.py`, `payout_workflow.py` | Provider abstraction, durable payout requests, webhook verification, idempotent settlement ingestion, and payout transition ledger. |
| **ML Training** | `ml_training.py` | RandomForestClassifier training script. Reads `joined_training_data_seed.csv`, exports `ml/model_artifacts/severity_rf.joblib`. |



## April 2026 Repo Update Addendum

### Newly implemented in current repo

- Review workflow is live with assignment endpoints, queue filters,
  SLA classification, and ownership-aware review actions.
- Payout workflow is live with provider adapters, durable request tracking,
  webhook verification, settlement transitions, and idempotent ingestion.
- Event reliability includes outbox status APIs, dead-letter APIs, relay loop,
  and consumer idempotency ledger.
- Kafka consumer mode is implemented with explicit offset management,
  malformed payload guards, and event_id integrity checks.
- Claims route now verifies signed device context headers when provided,
  with backward-compatible behavior when headers are absent.
- OpenAPI generation script and contract tests are in place to detect route drift.
- Rule/model version registry and rollout controls are now exposed via
    `/ops/version-governance` and `/ops/version-governance/activate`, with
    version IDs persisted in claim + review records.
- Ops SLO surfacing now includes breach-aware thresholds and recommended
    runbook actions via `/ops/status` and `/ops/slo`.

### Planned and next tranche

- Harden observability with richer metrics and alerting around relay/consumer lag.
- Expand consumer workers for additional side effects beyond initial handlers.
- Add deeper payout reconciliation and provider failover strategy.
- Progress from optional Kafka mode toward environment-specific defaults.
- Continue strict production validation for integrations and secrets.

### Deployment Updates (April 12, 2026)

- Backend deployed to **Render** as Docker Web Service (`covara-backend.onrender.com`).
- **Stripe Test Mode** integrated via `PayoutProviderAdapter` with 61 webhook events.
- **Postman Mock** KYC server replaces Sandbox.co.in for reliable development.
- Webhook: `POST /payouts/webhooks/http_gateway` with `whsec_*` signature verification.
- Strict env validation enforced in production (`APP_ENV=production`).
- Full webhook event catalog: [docs/STRIPE_WEBHOOK_EVENTS.md](../docs/STRIPE_WEBHOOK_EVENTS.md).



