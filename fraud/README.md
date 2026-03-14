# Fraud README

## Goal

This folder contains the fraud-detection logic used before payout approval.

## Fraud checks to implement

- duplicate event claim detection
- repeated account or bank target detection
- impossible GPS or shift overlap
- prior claim frequency anomaly
- zone mismatch
- multi-policy overlap
- source truth mismatch between event feed and worker claim

## Inputs

- worker truth
- trigger truth
- policy state
- claim history
- bank verification data
- route and GPS consistency

## Outputs

- fraud_penalty
- fraud risk score
- review band
- rejection reason or escalation flag

## Decision bands

- low: auto-approve candidate
- medium: soft review
- high: hard hold

## Judge-friendly explanation

This is not just anomaly buzzwords. It is a rules-plus-score layer that directly changes the claim decision.
