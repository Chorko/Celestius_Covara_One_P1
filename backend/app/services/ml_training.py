"""
Covara One — ML Training Pipeline (Severity Classifier)

Minimal scikit-learn training script for the Random Forest severity
classifier documented in ml/README.md.

Usage:
    python -m backend.app.services.ml_training

Reads:  data/samples/joined_training_data_seed.csv
Writes: ml/model_artifacts/severity_rf.joblib (if artifacts dir exists)
"""

import os
import sys
import json

try:
    import pandas as pd
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, roc_auc_score
except ImportError:
    print(
        "ML dependencies not installed. Run: "
        "pip install pandas numpy scikit-learn"
    )
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
SEED_CSV = os.path.join(ROOT, "data", "samples", "joined_training_data_seed.csv")

# ── Feature columns & target ──────────────────────────────────────────
FEATURE_COLS = [
    "rain_mm", "aqi", "temp_c", "traffic_delay_pct",
    "outage_min", "demand_drop_pct", "accessibility_score",
    "trust_score", "gps_consistency",
]
TARGET_COL = "claim_flag"


def load_data(csv_path: str = SEED_CSV) -> pd.DataFrame:
    """Load the seed CSV; synthesize extra rows via perturbation."""
    df = pd.read_csv(csv_path)

    # If dataset is tiny (< 30 rows), perturb to create training volume
    if len(df) < 30:
        frames = [df]
        rng = np.random.default_rng(42)
        for _ in range(50):
            noisy = df.copy()
            for col in FEATURE_COLS:
                if col in noisy.columns:
                    noise = rng.normal(0, 0.08, size=len(noisy))
                    noisy[col] = noisy[col] * (1 + noise)
            frames.append(noisy)
        df = pd.concat(frames, ignore_index=True)

    return df


def train_model(df: pd.DataFrame) -> dict:
    """Train a RandomForestClassifier and return metrics."""
    # Ensure target exists; if not, derive from severity heuristic
    if TARGET_COL not in df.columns:
        # Create a binary claim flag based on severity proxy
        severity_proxy = (
            df.get("rain_mm", 0) / 115.6 * 0.23
            + df.get("aqi", 0) / 401 * 0.14
            + df.get("temp_c", 0) / 47 * 0.14
        )
        df[TARGET_COL] = (severity_proxy > 0.12).astype(int)

    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].fillna(0)
    y = df[TARGET_COL].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=100, max_depth=6, random_state=42, n_jobs=-1
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)

    # Metrics
    report = classification_report(y_test, y_pred, output_dict=True)
    try:
        auc = round(roc_auc_score(y_test, y_proba[:, 1]), 4)
    except Exception:
        auc = None

    # Feature importance
    importances = dict(zip(available, [round(float(v), 4) for v in clf.feature_importances_]))
    importances = dict(sorted(importances.items(), key=lambda x: -x[1]))

    results = {
        "model": "RandomForestClassifier",
        "n_estimators": 100,
        "max_depth": 6,
        "train_size": len(X_train),
        "test_size": len(X_test),
        "accuracy": round(report["accuracy"], 4),
        "auc": auc,
        "feature_importance": importances,
        "classification_report": {
            k: v for k, v in report.items()
            if k in ("0", "1", "macro avg", "weighted avg")
        },
    }

    # Optionally save model
    try:
        import joblib
        artifacts_dir = os.path.join(ROOT, "ml", "model_artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)
        joblib.dump(clf, os.path.join(artifacts_dir, "severity_rf.joblib"))
        results["model_saved"] = True
    except Exception:
        results["model_saved"] = False

    return results


if __name__ == "__main__":
    print("Loading seed data...")
    df = load_data()
    print(f"Training on {len(df)} rows...")
    results = train_model(df)
    print(json.dumps(results, indent=2))
""",
    """Covara One — Severity Classifier baseline training.
    
    Run: python -m backend.app.services.ml_training
    """
