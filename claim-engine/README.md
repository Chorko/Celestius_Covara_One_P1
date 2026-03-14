# Claim Engine README

## Goal

This folder owns the trigger-to-claim-to-approval decision flow.

## Claim stages

1. trigger fires
2. signal is validated
3. worker exposure is checked
4. severity is calculated
5. payout estimate is created
6. fraud score is applied
7. claim is approved, held, or rejected
8. payout and audit events are recorded

## Inputs

- trigger payload
- worker profile
- active policy
- zone and shift overlap
- severity score
- fraud score

## Outputs

- claim decision
- payout amount
- review requirement
- audit events

## Golden rule

Every stage should emit one small event so the claim can be reconstructed later as a timeline.
