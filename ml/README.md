# ML — Data Science & Severity Modeling

> This folder contains the data-science side of the project. The first job is not to chase fancy models. The first job is to **prove that the numbers make sense** — and then let the model improve them.

---

## Implementation Status

| Component | Status |
|-----------|--------|
| Bootstrap pipeline design | 📝 Documented |
| Random Forest baseline results | 📝 Documented |
| Feature importance analysis | 📝 Documented |
| Boxplot outlier analysis | 📝 Documented |
| Severity normalization method | 📝 Documented |
| Pricing integration formula | 📝 Documented |
| ML training scripts | 📋 Planned |
| EDA notebooks | 📋 Planned |
| XGBoost comparison | 📋 Planned |
| Feedback loop implementation | 📋 Planned |

---

## Data Science Pipeline

```mermaid
flowchart TD
    SD["8-Row Seed Dataset"]
    SG["Synthetic Generator<br/>(Perturbation)"]
    WD["worker_data.csv"]
    TD["trigger_data.csv"]
    JD["joined_training_data.csv"]
    EDA["EDA & Boxplots"]
    SN["Severity<br/>Normalization"]
    RF["Random Forest<br/>Baseline"]
    FI["Feature Importance<br/>Analysis"]
    OA["Outlier Analysis<br/>(Tukey IQR)"]
    PR["Premium & Payout<br/>Calculation"]
    FB["Feedback Loop<br/>(Future)"]

    SD --> SG
    SG --> WD & TD
    WD & TD --> JD
    JD --> EDA
    JD --> SN
    SN --> RF
    RF --> FI
    EDA --> OA
    OA --> PR
    RF --> PR
    PR --> FB

    style SD fill:#4a9eff,color:#fff
    style RF fill:#2ecc71,color:#fff
    style PR fill:#f39c12,color:#fff
    style FB fill:#9b59b6,color:#fff
```

---

## Pipeline Workflow

### Step 1 — Seed Dataset
Start with the [8-row manually created base dataset](../data/README.md) covering diverse zone/risk combinations.

### Step 2 — Synthetic Expansion
Perturb seed rows using controlled variation to create a larger scenario set for stress testing. Variables are bounded by public threshold ranges.

### Step 3 — Feature Engineering
Engineer hazard, exposure, and confidence features from the joined dataset:
- **Severity Score (S):** weighted composite of 8 disruption components
- **Exposure (E):** shift duration + route accessibility
- **Confidence (C):** trust-adjusted verification score after fraud penalty

### Step 4 — Random Forest Baseline
Fit a `RandomForestClassifier` (scikit-learn) on the joined training data to predict `claim_flag`.

**Why Random Forest first?** The current dataset is small and synthetic. Random Forest handles tabular mixtures well, gives quick feature-importance feedback, and is easier to defend in an early-stage hackathon build than jumping directly into XGBoost.

### Step 5 — Outlier Analysis
Apply the Tukey IQR rule on the gross-premium distribution:
```
Q1 = 25th percentile
Q3 = 75th percentile
IQR = Q3 − Q1
High-risk cutoff = Q3 + 1.5 × IQR
```

If `gross_premium > high-risk cutoff`, apply outlier uplift:
```
U = min(1.35, gross_premium / median_premium)
```
Applied to **both** premium and payout cap so the relationship stays fair.

### Step 6 — Premium & Payout Outputs
Use ML-predicted claim probability `p` in the premium formula:
```
Expected Payout = p × B × S × E × C × (1 − FH)
Gross Premium = [Expected Payout / (1 − 0.12 − 0.10)] × U
```

---

## Bootstrap Results

> **📝 Status:** These results are from the documented bootstrap pipeline run on the synthetic scenario set.

| Metric | Value |
|--------|-------|
| Median weekly premium | ₹ 218.7 |
| Median payout (if triggered) | ₹ 442.6 |
| Model AUC (holdout) | 0.647 |
| Outlier share (Tukey IQR) | 5.5% |
| High-risk cutoff | ≈ ₹ 1,012.8 |
| Premium-payout correlation | 0.93 |

---

## Feature Importance (Random Forest Baseline)

| Rank | Feature | Importance |
|------|---------|-----------|
| 1 | `traffic_delay_pct` | 0.109 |
| 2 | `accessibility_score` | 0.106 |
| 3 | `rain_mm` | 0.092 |
| 4 | `temp_c` | 0.086 |
| 5 | `gps_consistency` | 0.086 |
| 6 | `aqi` | 0.083 |
| 7 | `trust_score` | 0.082 |
| 8 | `demand_drop_pct` | 0.075 |

> **Visual:** Feature importance and bootstrap pricing distribution charts from the data-science pipeline:

![Feature Importance — Random Forest Baseline](../docs/assets/insurance/feature_importance.png)

![Bootstrap Pricing Distribution](../docs/assets/insurance/premium_payout_boxplot.png)

---

## Severity Normalization

Each severity component is normalized to 0–1 using threshold anchor points:

| Component | Normalization basis | Weight in S |
|-----------|-------------------|-------------|
| `rain_sev` | 0 at 0mm, 1 at ≥ 115.6mm (IMD very heavy) | 0.23 |
| `aqi_sev` | 0 at ≤ 50, 1 at ≥ 401 (CPCB extreme) | 0.14 |
| `heat_sev` | 0 at ≤ 35°C, 1 at ≥ 47°C (severe heat) | 0.14 |
| `traffic_sev` | 0 at 0%, 1 at ≥ 80% delay | 0.10 |
| `outage_sev` | 0 at 0 min, 1 at ≥ 120 min | 0.12 |
| `closure_sev` | Binary: 0 or 1 | 0.10 |
| `demand_sev` | 0 at 0%, 1 at ≥ 70% drop | 0.07 |
| `access_sev` | 1 − accessibility_score | 0.10 |

```
S = 0.23·rain + 0.14·aqi + 0.14·heat + 0.10·traffic + 0.12·outage + 0.10·closure + 0.07·demand + 0.10·access
```

---

## How ML Connects to Premium & Payout

```mermaid
flowchart LR
    ML["ML Model<br/>(Random Forest)"]
    P["Claim probability (p)"]
    PE["Premium Engine"]
    PO["Payout Engine"]
    CE["Claim Engine"]

    ML --> P
    P --> PE
    P --> PO
    P --> CE

    style ML fill:#2ecc71,color:#fff
    style PE fill:#f39c12,color:#fff
    style PO fill:#f39c12,color:#fff
```

The ML model's predicted `p` is the key input that bridges data science and insurance logic:
- **Premium:** `Gross Premium = [p × B × S × E × C × (1 − FH) / (1 − α − β)] × U`
- **Payout:** `Payout = min(Cap, B × S × E × C × (1 − FH))` (triggered when claim approved)

---

## Inputs

| Input | Source |
|-------|--------|
| `joined_training_data.csv` | Data layer (zone+time matched) |
| `worker_data.csv` | Data layer |
| `trigger_data.csv` | Data layer |
| Variable dictionary | [data/README.md](../data/README.md) |
| Threshold reference sheet | [data/README.md](../data/README.md) |

## Outputs

| Output | Consumer |
|--------|----------|
| Feature importance chart | Docs / judges |
| Outlier plots (boxplots) | Docs / judges |
| Severity score model | Claim engine, premium engine |
| Claim probability `p` | Premium and payout formulas |
| Premium sensitivity analysis | Insurer dashboard |
| Model performance summary | Docs / judges |

---

## Key Questions This Folder Should Answer

1. Which variables matter most for loss-of-income severity?
2. Which cases behave as outliers, and how should they affect premium + payout together?
3. Are our claim thresholds too loose or too strict?
4. Does the Random Forest baseline produce numbers that "make sense" when reviewed?
5. How does the model's predicted claim probability map to observable disruption patterns?

---

## Tools

| Tool | Purpose |
|------|---------|
| Python | Primary language |
| pandas, numpy | Data handling and transformation |
| scikit-learn | `RandomForestClassifier` baseline, train/test split |
| matplotlib | Boxplots, feature importance charts, EDA visuals |
| XGBoost (future) | Benchmark comparison if data complexity warrants it |

---

## Pricing Baseline and Reference Notes

**Why Random Forest?** Random Forest ([Breiman, 2001](https://doi.org/10.1023/A:1010933404324)) was selected as the baseline severity classifier because it provides interpretable feature-importance rankings, handles mixed feature types without extensive preprocessing, and is robust against overfitting on small datasets — critical for an 8-row bootstrap seed.

**Why XGBoost as future benchmark?** XGBoost ([Chen & Guestrin, 2016](https://doi.org/10.1145/2939672.2939785)) is retained as a planned benchmark if dataset scale and feature complexity warrant gradient-boosted tree performance. It is not yet used in the current pipeline.

**Role of ML in the pricing pipeline:** The Random Forest model estimates claim probability `p` on the joined worker-trigger row. Premium and payout are **not predicted directly by ML alone** — they are derived from documented formulas (`B × S × E × C × (1 − FH)`) where ML contributes only the `p` factor. This keeps the pricing pipeline explainable and auditable.

**Feature normalization provenance:** Environmental features (rain_mm, AQI, temp_c) are normalized against official public-source thresholds from [CPCB](https://www.cpcb.nic.in/aqi_report.php), [IMD](https://mausam.imd.gov.in/imd_latest/contents/pdf/pubbrochures/Heavy%20Rainfall%20Warning%20Services.pdf), and [NDMA](https://ndma.gov.in/Natural-Hazards/Heat-Wave). Operational features (traffic_delay_pct, outage_min, demand_drop_pct) use internal product thresholds documented in the [root README](../README.md#threshold-references-and-why-they-were-chosen).

**Actuarial grounding:** The gross premium formula uses an expected-loss loading approach grounded in *Loss Data Analytics* ([Ch. 7: Premium Foundations](https://openacttexts.github.io/Loss-Data-Analytics/ChapPremiumFoundations.html)) and *Non-Life Insurance Mathematics* ([Mikosch, 2004](https://unina2.on-line.it/sebina/repository/catalogazione/documenti/Mikosch%20-%20Non-life%20insurance%20mathematics.pdf)). The expense load (α = 0.12) and risk margin (β = 0.10) are hackathon assumptions that must be tuned with real data.

> For the full reference register with all 9 sources, see [docs/README.md](../docs/README.md#reference-register).

---

## Rule

> Keep everything explainable enough for judges to understand in one minute. If a model output cannot be traced back to input features and threshold logic, it fails the transparency test.
