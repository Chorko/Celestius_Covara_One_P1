# DEVTrails 2026 - Parametric Income Protection for Gig Workers

## What this project is

This project is an AI-assisted parametric insurance platform for delivery workers. It protects **weekly income**, not health, life, vehicle repair, or accident damage. The system watches external disruption signals such as heavy rain, severe AQI, heat, outages, closures, and traffic disruption, then estimates whether a worker's earning ability was genuinely affected during a covered shift.

The idea is simple:
- the worker buys weekly coverage
- the system monitors public trigger conditions
- the platform matches the event to the worker's zone and shift
- a claim can be initiated automatically
- fraud checks run before payout
- the insurer dashboard tracks the full lifecycle

## Why this is aligned to the challenge

The challenge asks for:
- gig-worker income protection
- weekly pricing
- AI-powered risk assessment
- intelligent fraud detection
- parametric trigger automation
- payout processing
- analytics dashboards

This repository is structured so evaluators can understand the platform **without reading the code first**.

## Delivery persona and coverage boundary

**Chosen persona:** food delivery workers in disruption-prone urban zones

**Covered risk:** temporary loss of earning opportunity caused by external disruption

**Not covered:**
- health or hospitalization
- life insurance
- accident insurance
- vehicle repair
- personal theft unrelated to the disruption trigger

## End-to-end logic in one pass

1. Worker signs up and chooses a weekly policy.
2. Pricing service calculates a weekly premium using worker data, zone risk, and trust adjustment.
3. Trigger monitor ingests event signals such as rainfall, AQI, heat, closures, outages, and traffic disruption.
4. Claim engine checks whether the event overlaps the worker's shift and covered zone.
5. Fraud layer scores the claim using GPS consistency, prior claim history, duplicate-event patterns, and bank validation.
6. Approval engine decides instant payout, soft review, or hard hold.
7. Dashboards update worker-facing and insurer-facing metrics.

## Repository map

```text
/frontend
/backend
/caching
/data
/ml
/fraud
/claim-engine
/integrations
/docs
```

Each folder has its own README that explains:
- what goes in
- what comes out
- why the folder exists
- what service receives the output next

## High-level architecture views

This repo uses five visual views:
1. Unified overall architecture
2. Gig worker journey
3. Insurer operations
4. Trigger -> validation -> claim -> approval flow
5. Fraud detection pipeline

## Trigger library

The platform should expose around 15 triggers so the project looks operationally real, not shallow.

### Environmental
- heavy rain alert
- extreme rain claim threshold
- flood escalation
- severe AQI alert
- severe AQI claim threshold
- heatwave alert
- heatwave claim threshold

### Operational and civic
- local zone closure
- outage disruption
- abnormal traffic delay
- route inaccessibility
- platform demand collapse
- curfew or strike notice
- warehouse or pickup point blockage
- multi-trigger escalation event

## Data split

The dataset must stay split into two major entities.

### worker_data
Contains the worker-side facts:
- worker_id
- zone_id
- city
- shift window
- historical hourly income
- active days per week
- bank verification
- GPS consistency
- trust score
- prior claim rate

### trigger_data
Contains the event-side facts:
- trigger_id
- city
- zone_id
- timestamp start and end
- trigger type
- raw observed value
- threshold crossed
- severity bucket
- source reliability

### joined_training_data
Created only after matching worker exposure with trigger overlap. This is the dataset used for EDA and ML experiments.

## Sample scenario with numbers

Worker:
- hourly income = 84 INR
- shift hours = 11
- active days = 6
- trust score = 0.82
- bank_verified = 1
- GPS consistency = 0.91

Trigger:
- rain = 72 mm
- AQI = 240
- temperature = 41 C
- traffic delay = 48%
- outage = 12 min

Interpretation:
- the worker is in a high-severity week
- event overlap is real
- exposure is high because the shift is long and route accessibility is weak
- confidence stays high because trust and GPS consistency are good
- payout can be automated unless fraud score pushes the case into review

## Tech stack and why

- **Frontend:** React / Next.js or similar dashboard stack for fast UI iteration and clean investor demo
- **Backend:** Python FastAPI or Node-based API layer for trigger orchestration and transparent endpoint design
- **Cache:** Redis-like cache layer to avoid repeating expensive trigger fetch and simulation work
- **Data science:** pandas, numpy, scikit-learn for bootstrap EDA and Random Forest baseline
- **Storage:** relational storage for policies, claims, audit events, and payout logs
- **Visualization:** chart components for claim analytics, trigger mix, severity mix, and loss ratio

## Evaluator quick-start

1. Clone the repo.
2. Run the mock data generator.
3. Generate `worker_data.csv`, `trigger_data.csv`, and `joined_training_data.csv`.
4. Open the worker dashboard and insurer dashboard.
5. Trigger one sample scenario.
6. Verify the claim decision, fraud score, and payout output.
7. Check the dashboards for analytics updates.

## Folder ownership suggestion

- frontend: UI flows and user experience
- backend: orchestration and APIs
- claim-engine: claim decision rules
- fraud: anomaly logic and verification
- ml: severity modeling and pricing experiments
- data: synthetic data generation and CSV assets
- caching: cache rules and TTL behavior
- integrations: external signal connectors and payment mocks
- docs: pitch assets, diagrams, formula notes, references

## What judges should immediately understand

- the project is about **income loss**, not generic insurance
- the platform uses **weekly pricing**
- the system is **parametric**
- the claims are **partially automated**
- the fraud layer is **real logic, not a fake buzzword section**
- the repo is **readable enough to evaluate quickly**
