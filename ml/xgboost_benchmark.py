"""
Covara One — XGBoost Benchmark

Benchmarking script to evaluate if XGBoost provides sufficient uplift over the 
RandomForest baseline for claim severity prediction.
"""

import os
import json

try:
    import pandas as pd
    import xgboost as xgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, roc_auc_score
except ImportError:
    print("Dependencies not installed. Run: pip install pandas xgboost scikit-learn")
    exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED_CSV = os.path.join(ROOT, "data", "samples", "joined_training_data_seed.csv")

FEATURE_COLS = [
    "rain_mm", "aqi", "temp_c", "traffic_delay_pct",
    "outage_min", "demand_drop_pct", "accessibility_score",
    "trust_score", "gps_consistency",
]
TARGET_COL = "claim_flag"

def run_benchmark():
    df = pd.read_csv(SEED_CSV)
    
    if TARGET_COL not in df.columns:
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

    clf = xgb.XGBClassifier(
        n_estimators=100, 
        max_depth=6, 
        learning_rate=0.1, 
        random_state=42, 
        use_label_encoder=False, 
        eval_metric='logloss'
    )
    
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)

    report = classification_report(y_test, y_pred, output_dict=True)
    try:
        auc = round(roc_auc_score(y_test, y_proba[:, 1]), 4)
    except Exception:
        auc = None

    importances = dict(zip(available, [round(float(v), 4) for v in clf.feature_importances_]))
    importances = dict(sorted(importances.items(), key=lambda x: -x[1]))

    results = {
        "model": "XGBoostClassifier",
        "accuracy": round(report["accuracy"], 4),
        "auc": auc,
        "feature_importance": importances,
    }

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    if os.path.exists(SEED_CSV):
        run_benchmark()
    else:
        print(f"Seed file not found at {SEED_CSV}")
