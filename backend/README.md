# Backend README

## Goal

The backend orchestrates the insurance logic. It should be easy to read, easy to demo, and segmented cleanly enough that an evaluator can follow the flow without reverse engineering the code.

## Core modules

- auth and onboarding
- policy service
- pricing service
- trigger monitor
- claim orchestrator
- fraud scoring service
- payout service
- analytics service

## Suggested endpoints

- `POST /workers`
- `POST /policies/quote`
- `POST /policies/activate`
- `GET /triggers/live`
- `GET /mock-data/generate`
- `GET /simulate/claim-scenario`
- `POST /claims/initiate`
- `GET /claims/{id}`
- `POST /claims/{id}/review`
- `GET /analytics/summary`

## Inputs

- worker details
- zone and city
- trigger stream or mock trigger stream
- bank verification state
- policy state
- prior claim information

## Outputs

- premium quote
- claim status
- fraud risk band
- payout amount
- analytics aggregates
- audit events

## What comes next

Most backend outputs move to:
- frontend dashboards
- claim-engine
- fraud module
- analytics layer
