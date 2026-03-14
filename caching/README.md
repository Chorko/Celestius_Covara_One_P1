# Caching README

## Why this folder exists

External signal fetching, repeated dashboard loading, and repeated claim simulations can create unnecessary load. The cache avoids repeated recomputation and makes the demo feel fast.

## Good candidates for caching

- trigger feeds by city and zone
- threshold lookup tables
- generated mock datasets
- dashboard summary cards
- scenario simulation outputs

## Example cache policy

- trigger feed cache TTL: short
- dashboard cache TTL: short to medium
- threshold tables: long
- mock-data generation summaries: medium

## Inputs

- city
- zone
- date range
- trigger type
- simulation request keys

## Outputs

- cached JSON payload
- cache hit or miss metadata

## What goes next

The cached response is returned to backend services and then surfaced to the frontend.

## Judge-friendly explanation

This folder exists so we do not repeatedly fetch or recompute the same environmental signal logic during demos.
