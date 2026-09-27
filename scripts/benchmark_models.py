"""Benchmark Prediction Latency: Random Forest vs Tuned XGBoost.

Evaluates batch prediction throughput across sample sizes (10k, 50k, 100k, 500k, full dataset)
using repeated runs (3 iterations) to record mean, minimum, and maximum latency.

Outputs:
    reports/model_inference_benchmark.csv
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor

from gis.ml.xgb_tuning import FEATURE_COLUMNS, TARGET_COLUMN

DEFAULT_DATASET = PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"
DEFAULT_PARAMS = PROJECT_ROOT / "artifacts" / "xgb_tuning" / "xgb_best_params.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "model_inference_benchmark.csv"


def benchmark_inference(
    dataset_path: Path = DEFAULT_DATASET,
    params_path: Path = DEFAULT_PARAMS,
    output_path: Path = DEFAULT_OUTPUT,
    n_repeats: int = 3,
) -> pd.DataFrame:
    print("=" * 80)
    print("HEATSENSE AI: PREDICTION LATENCY BENCHMARK (RF vs TUNED XGBOOST)")
    print("=" * 80)

    df = pd.read_parquet(dataset_path)
    X = df[FEATURE_COLUMNS].to_numpy()
    y = df[TARGET_COLUMN].to_numpy()
    total_rows = len(df)
    print(f"Loaded dataset: {total_rows:,} rows.")

    # Load tuned XGB parameters
    with open(params_path) as f:
        p_data = json.load(f)
    best_params = p_data.get("best_params", {})
    fixed_params = p_data.get("fixed_params", {
        "objective": "reg:squarederror",
        "tree_method": "hist",
        "random_state": 42,
        "n_jobs": -1,
    })
    xgb_params = {**best_params, **fixed_params}

    # Fit both models on a 100k sample for benchmarking inference
    fit_sample_n = min(100000, total_rows)
    rng = np.random.RandomState(42)
    fit_idx = rng.choice(total_rows, size=fit_sample_n, replace=False)

    print(f"\nFitting Random Forest (n=100) on {fit_sample_n:,} samples...")
    rf_model = RandomForestRegressor(n_estimators=100, min_samples_leaf=3, random_state=42, n_jobs=-1)
    rf_model.fit(X[fit_idx], y[fit_idx])

    print(f"Fitting Tuned XGBoost (n={xgb_params.get('n_estimators', 1300)}) on {fit_sample_n:,} samples...")
    xgb_model = xgb.XGBRegressor(**xgb_params)
    xgb_model.fit(X[fit_idx], y[fit_idx])

    batch_sizes = [10000, 50000, 100000, 500000, total_rows]
    records = []

    print("\nRunning inference benchmark across batch sizes...")
    for n in batch_sizes:
        if n > total_rows:
            continue
        X_batch = X[:n]
        label = f"{n:,}" if n < total_rows else f"Full ({total_rows:,})"

        # Benchmark RF
        rf_times = []
        for _ in range(n_repeats):
            t0 = time.perf_counter()
            _ = rf_model.predict(X_batch)
            rf_times.append(time.perf_counter() - t0)

        # Benchmark XGBoost
        xgb_times = []
        for _ in range(n_repeats):
            t0 = time.perf_counter()
            _ = xgb_model.predict(X_batch)
            xgb_times.append(time.perf_counter() - t0)

        records.append({
            "batch_size": n,
            "batch_label": label,
            "rf_mean_seconds": round(float(np.mean(rf_times)), 4),
            "rf_min_seconds": round(float(np.min(rf_times)), 4),
            "rf_max_seconds": round(float(np.max(rf_times)), 4),
            "xgb_mean_seconds": round(float(np.mean(xgb_times)), 4),
            "xgb_min_seconds": round(float(np.min(xgb_times)), 4),
            "xgb_max_seconds": round(float(np.max(xgb_times)), 4),
            "speedup_ratio_xgb_vs_rf": round(float(np.mean(rf_times) / np.mean(xgb_times)), 2),
        })

        print(
            f"  Batch {label:16s} | RF: {np.mean(rf_times):.3f}s (min {np.min(rf_times):.3f}s) | "
            f"XGB: {np.mean(xgb_times):.3f}s (min {np.min(xgb_times):.3f}s) | "
            f"Ratio: {np.mean(rf_times) / np.mean(xgb_times):.2f}x"
        )

    res_df = pd.DataFrame(records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    res_df.to_csv(output_path, index=False)
    print(f"\nSaved benchmark results to: {output_path}")
    return res_df


if __name__ == "__main__":
    benchmark_inference()
