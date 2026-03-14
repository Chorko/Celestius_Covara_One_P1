# Data README

## Goal

This folder owns synthetic data generation, bootstrap sample rows, variable definitions, and all CSV outputs used for analysis and demonstration.

## Required assets

- `worker_data.csv`
- `trigger_data.csv`
- `joined_training_data.csv`
- `summary.json`
- variable dictionary
- threshold reference table

## Data creation plan

1. Start with a manually written base dataset of around 8 rows.
2. Add public-threshold logic for rain, AQI, heat, closures, and outages.
3. Generate more rows using controlled synthetic variation.
4. Keep worker data and trigger data separate.
5. Join only after zone and shift overlap is checked.

## Inputs

- public threshold assumptions
- worker behavior assumptions
- event frequency assumptions
- city and zone mapping

## Outputs

- clean CSV files for EDA
- training-ready matched dataset
- summary counts by trigger and city

## Important rule

No random nonsense. Every variable should be documented with why it exists and how it influences premium or payout.
