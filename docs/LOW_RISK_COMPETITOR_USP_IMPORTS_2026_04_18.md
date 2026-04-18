# Low-Risk Competitor USP Imports (2026-04-18)

## Objective
Copy competitor USP patterns that can be implemented in Covara One without changing the current parametric model or payout logic.

## Selection Criteria
- No change to trigger families, payout formula, or fraud score semantics.
- Additive reliability/trust/ops capability only.
- Integrates into existing modules already present in Covara.

## Imported Now (Implemented)

### 1) Carbon-style observability export for external monitoring
Competitor signal:
- Carbon repeatedly emphasizes Prometheus-style monitoring and metrics endpoints.

What we implemented in Covara:
- Added Prometheus exposition rendering for existing in-memory metrics.
- Added admin-protected endpoint for Prometheus scraping.

Covara touchpoints:
- `backend/app/services/observability.py`
- `backend/app/routers/ops.py`
- `tests/test_observability.py`
- `tests/test_ops_router.py`

Endpoint:
- `GET /ops/metrics/prometheus` (insurer-admin guarded)

Why this is no-model-impact:
- No changes to claim scoring, trigger evaluation, payout recommendation, or approval routing.
- Only exposes operational telemetry already being collected.

Validation:
- Targeted tests passed:
  - `tests/test_observability.py`
  - `tests/test_ops_router.py`

## Implemented This Pass (No Model Change)

### 2) Trust-Stamped payout event envelope
Competitor inspiration:
- SPAM signal layering
- Code Mavens payment integrity framing

Current Covara base already available:
- Payout workflow has webhook signature handling and status-transition ledger.
- Anti-spoofing already computes `device_trust_tier`, `signal_confidence`, `attestation_verdict`.

Low-risk import implemented:
- Added a compact `trust_stamp` object into payout initiation/settlement/audit payloads and claim detail surfaces.

Suggested fields:
- `device_trust_tier`
- `signal_confidence`
- `attestation_verdict`
- `fraud_score_band`
- `version_governance.rule_version`
- `version_governance.model_version`

Covara touchpoints:
- `backend/app/services/payout_workflow.py`
- `backend/app/routers/claims.py`

Why this is no-model-impact:
- Uses already computed outputs; no recalculation logic change.
- Improves auditability and explanation only.

Validation:
- Covered in payout workflow regression tests and claim-detail response wiring.

### 3) SLO signal severity mapping for reviewer operations
Competitor inspiration:
- Carbon operational readiness framing (monitoring + operator actionability)

Current Covara base already available:
- Ops router already emits SLO breach checks and runbook links.

Low-risk import implemented:
- Added severity level (`info`, `warning`, `critical`) and `owner` per SLO signal.
- Added monotonic breach-age tracking to avoid alert flapping in dashboards.

Covara touchpoints:
- `backend/app/routers/ops.py`
- `backend/app/services/observability.py`

Why this is no-model-impact:
- Operational governance metadata only.

Validation:
- Covered in ops router tests and observability unit tests.

## What We Should Not Copy (For This Constraint)
- Full architecture sprawl or multi-service decomposition for optics.
- Any USP that requires replacing parametric eligibility logic.
- Unverified attestation claims without concrete implementation evidence.

## Priority Order
1. Done: Prometheus ops metrics exposition
2. Done: Trust-stamped payout envelope
3. Done: SLO severity + breach-age controls

## Expected Outcome
These imports raise enterprise confidence (ops visibility + audit explainability) while preserving Covara's current product model and adjudication math.
