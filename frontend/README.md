# Frontend README

## Goal

The frontend should make the whole insurance journey understandable for two personas:
- gig worker
- insurer operations reviewer

The UI is not just for beauty. It is part of the explanation layer for judges.

## Main pages

### Worker side
- onboarding page
- weekly quote page
- active policy card
- trigger alert view
- claim status timeline
- payout history
- notifications

### Insurer side
- trigger queue
- review dashboard
- claim lifecycle dashboard
- fraud case panel
- payout reconciliation panel
- analytics dashboard

## Inputs coming into the frontend

From backend APIs:
- worker profile
- quote response
- active policy status
- trigger alerts
- claim decision
- fraud score band
- payout status
- analytics summaries

## Outputs sent from the frontend

To backend APIs:
- onboarding form data
- policy purchase request
- assisted claim confirmation
- document upload if review is needed
- insurer review action
- manual approval or hold decision

## UI rule

Every screen should answer one question only.

Examples:
- worker dashboard answers: what am I covered for, what is happening right now, and did I get paid?
- insurer dashboard answers: which claims need action, why were they flagged, and what happened after payout?

## Recommended components

- policy card
- trigger severity banner
- step timeline
- fraud badge
- payout summary tile
- charts for claim mix and trigger mix
- audit trail drawer

## What must be visible to judges

- weekly premium
- trigger that caused claim
- payout formula summary
- fraud status
- full claim lifecycle
