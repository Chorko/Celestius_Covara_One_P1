# ML README

## Goal

This folder contains the data science side of the project. The first job is not to chase fancy models. The first job is to prove that the numbers make sense.

## Recommended first pass

- EDA
- box plots for outlier inspection
- severity normalization
- Random Forest baseline
- compare with XGBoost only if the data justifies it

## Inputs

- joined_training_data.csv
- worker_data.csv
- trigger_data.csv
- variable dictionary
- threshold reference sheet

## Outputs

- feature importance chart
- outlier plots
- severity score experiments
- premium sensitivity analysis
- fraud-risk experiments
- model performance summary

## Key questions this folder should answer

- which variables matter most for loss-of-income severity?
- which cases behave as outliers?
- how should outliers affect premium and payout together?
- are our claim thresholds too loose or too strict?

## Rule

Keep everything explainable enough for judges to understand in one minute.
