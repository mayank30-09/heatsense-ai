"""Independent Spatial Holdout Evaluation for HEATSENSE AI.

Implements strict spatial block holdout partitioning (~20% untouched spatial test blocks,
~80% development spatial blocks) with zero spatial leakage.

Guarantees:
1. `train_blocks.isdisjoint(test_blocks) == True`
2. Every row in the dataset belongs to exactly one split.
3. Untouched test blocks are evaluated ONLY ONCE after model configuration is locked.
4. Full provenance: persists metadata, block lists, row counts, and dataset SHA-256 hashes.

Outputs:
    artifacts/final_holdout/holdout_metadata.json
    artifacts/final_holdout/test_blocks.json
    artifacts/final_holdout/development_blocks.json
    artifacts/final_holdout/holdout_performance.json
    artifacts/final_holdout/holdout_season_performance.csv
    artifacts/final_holdout/holdout_hotspot_performance.csv
    reports/holdout_spatial_residuals.geojson
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import xgboost as xgb

from gis.ml.rf_model import compute_regression_metrics
from gis.ml.xgb_tuning import FEATURE_COLUMNS, TARGET_COLUMN, validate_dataset_schema
from gis.quality.hotspot_definitions import (
    CHRONIC_HOTSPOT_FREQ_THRESHOLD,
    PERSISTENT_HOTSPOT_FREQ_THRESHOLD,
    is_active_hotspot,
    is_chronic_hotspot,
    is_non_hotspot,
    is_persistent_hotspot,
)

DEFAULT_DATASET = PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"
DEFAULT_PARAMS = PROJECT_ROOT / "artifacts" / "xgb_tuning" / "xgb_best_params.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "final_holdout"
DEFAULT_REPORTS = PROJECT_ROOT / "reports"


def compute_file_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hexadecimal digest of a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def create_spatial_holdout_split(
    df: pd.DataFrame,
    test_ratio: float = 0.20,
    random_state: int = 42,
    block_col: str = "block_id",
) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    """
    Partition spatial blocks into disjoint development and untouched test sets.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing `block_col`.
    test_ratio : float
        Fraction of spatial blocks reserved for independent testing (default 0.20).
    random_state : int
        Deterministic random seed (default 42).
    block_col : str
        Name of the block identifier column.

    Returns
    -------
    tuple[np.ndarray, np.ndarray, list[str], list[str]]
        (dev_indices, test_indices, dev_block_ids, test_block_ids)
    """
    if block_col not in df.columns:
        raise ValueError(f"Block column '{block_col}' missing from DataFrame.")

    unique_blocks = np.sort(df[block_col].unique())
    n_total_blocks = len(unique_blocks)
    n_test_blocks = int(np.round(n_total_blocks * test_ratio))

    rng = np.random.RandomState(random_state)
    shuffled_blocks = rng.permutation(unique_blocks)

    test_blocks = sorted(list(shuffled_blocks[:n_test_blocks]))
    dev_blocks = sorted(list(shuffled_blocks[n_test_blocks:]))

    # Assert spatial disjointness
    assert set(dev_blocks).isdisjoint(set(test_blocks)), "Spatial overlap detected between dev and test blocks!"

    test_mask = df[block_col].isin(test_blocks).to_numpy()
    dev_mask = ~test_mask

    df_indices = np.arange(len(df))
    dev_idx = df_indices[dev_mask]
    test_idx = df_indices[test_mask]

    assert len(dev_idx) + len(test_idx) == len(df), "Row count mismatch in holdout partition!"

    return dev_idx, test_idx, dev_blocks, test_blocks


def run_independent_holdout_evaluation(
    dataset_path: Path = DEFAULT_DATASET,
    params_path: Path = DEFAULT_PARAMS,
    output_dir: Path = DEFAULT_OUTPUT,
    reports_dir: Path = DEFAULT_REPORTS,
    test_ratio: float = 0.20,
    random_state: int = 42,
) -> dict[str, Any]:
    """Execute complete independent spatial holdout training and evaluation."""
    print("=" * 80)
    print("HEATSENSE AI: INDEPENDENT SPATIAL HOLDOUT VALIDATION")
    print("=" * 80)

    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset missing: {dataset_path}")
    if not params_path.exists():
        raise FileNotFoundError(f"Parameters missing: {params_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load dataset & validate schema
    df = pd.read_parquet(dataset_path)
    validate_dataset_schema(df)
    total_rows = len(df)
    dataset_sha = compute_file_sha256(dataset_path)
    print(f"Dataset loaded: {total_rows:,} rows | SHA-256: {dataset_sha[:16]}...")

    # 2. Load tuned parameters
    with open(params_path) as f:
        params_payload = json.load(f)
    best_params = params_payload.get("best_params", {})
    fixed_params = params_payload.get("fixed_params", {
        "objective": "reg:squarederror",
        "tree_method": "hist",
        "random_state": 42,
        "n_jobs": -1,
    })
    xgb_params = {**best_params, **fixed_params}

    # 3. Create independent spatial holdout split
    dev_idx, test_idx, dev_blocks, test_blocks = create_spatial_holdout_split(
        df, test_ratio=test_ratio, random_state=random_state
    )

    n_dev_rows = len(dev_idx)
    n_test_rows = len(test_idx)
    print(f"\nSpatial Block Partitioning (Seed {random_state}):")
    print(f"  Development Blocks : {len(dev_blocks)} blocks ({n_dev_rows:,} rows, {n_dev_rows/total_rows*100:.1f}%)")
    print(f"  Untouched Test Set : {len(test_blocks)} blocks ({n_test_rows:,} rows, {n_test_rows/total_rows*100:.1f}%)")
    print(f"  Spatial Disjoint   : {set(dev_blocks).isdisjoint(set(test_blocks))}")

    # Persist holdout block metadata
    with open(output_dir / "test_blocks.json", "w") as f:
        json.dump(test_blocks, f, indent=2)
    with open(output_dir / "development_blocks.json", "w") as f:
        json.dump(dev_blocks, f, indent=2)

    holdout_meta = {
        "dataset_path": str(dataset_path),
        "dataset_sha256": dataset_sha,
        "total_rows": total_rows,
        "total_blocks": len(df["block_id"].unique()),
        "test_ratio": test_ratio,
        "random_state": random_state,
        "development_blocks_count": len(dev_blocks),
        "development_rows_count": n_dev_rows,
        "test_blocks_count": len(test_blocks),
        "test_rows_count": n_test_rows,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(output_dir / "holdout_metadata.json", "w") as f:
        json.dump(holdout_meta, f, indent=2)

    # 4. Train model STRICTLY on development blocks
    X_dev = df.iloc[dev_idx][FEATURE_COLUMNS].to_numpy()
    y_dev = df.iloc[dev_idx][TARGET_COLUMN].to_numpy()

    X_test = df.iloc[test_idx][FEATURE_COLUMNS].to_numpy()
    y_test = df.iloc[test_idx][TARGET_COLUMN].to_numpy()

    print(f"\nTraining Tuned XGBoost on 80% Development Data ({n_dev_rows:,} rows)...")
    t0 = time.time()
    model = xgb.XGBRegressor(**xgb_params)
    model.fit(X_dev, y_dev)
    fit_time = time.time() - t0
    print(f"Model fit complete in {fit_time:.1f}s.")

    # 5. Evaluate model ONCE on untouched 20% test blocks
    print(f"\nEvaluating on Untouched 20% Test Blocks ({n_test_rows:,} rows)...")
    y_pred_test = model.predict(X_test)
    test_metrics = compute_regression_metrics(y_test, y_pred_test)

    print("=" * 80)
    print("INDEPENDENT SPATIAL HOLDOUT RESULTS (UNTOUCHED TEST SET):")
    print("=" * 80)
    print(f"  Test Sample Count (N) : {test_metrics['n_samples']:,}")
    print(f"  Test MAE              : {test_metrics['MAE']:.4f} degC")
    print(f"  Test RMSE             : {test_metrics['RMSE']:.4f} degC")
    print(f"  Test R2               : {test_metrics['R2']:.4f}")

    # Build test residual DataFrame
    df_test = df.iloc[test_idx][[
        "year", "season", "row", "col", "longitude", "latitude", "block_id",
        "LST_C", "hotspot_frequency", "is_persistent_hotspot", "eligibility",
        "quality_flag", "is_partial_season"
    ]].copy()
    residuals = y_test - y_pred_test
    df_test["prediction"] = np.round(y_pred_test, 3)
    df_test["residual"] = np.round(residuals, 3)
    df_test["absolute_error"] = np.round(np.abs(residuals), 3)

    # 6. Stratified Seasonal Performance on Holdout
    season_records = []
    for s in ["winter", "summer", "monsoon", "post_monsoon"]:
        s_df = df_test[df_test["season"] == s]
        if len(s_df) > 0:
            s_met = compute_regression_metrics(s_df["LST_C"], s_df["prediction"])
            has_partial = (s == "monsoon" and (s_df["is_partial_season"]).any())
            season_records.append({
                "season": s,
                "n_samples": s_met["n_samples"],
                "MAE": s_met["MAE"],
                "RMSE": s_met["RMSE"],
                "R2": s_met["R2"],
                "contains_partial_season": bool(has_partial),
                "notes": "2026 monsoon contains partial acquisitions" if has_partial else "Complete seasonal series",
            })
    df_seasons = pd.DataFrame(season_records)
    df_seasons.to_csv(output_dir / "holdout_season_performance.csv", index=False)

    print("\nHoldout Seasonal Breakdown:")
    for _, r in df_seasons.iterrows():
        print(f"  {r['season']:14s} | n={r['n_samples']:,} | MAE: {r['MAE']:.3f} degC | RMSE: {r['RMSE']:.3f} degC | R2: {r['R2']:.3f}")

    # 7. Stratified Hotspot Performance on Holdout (Using Canonical Definitions)
    hotspot_records = []
    # Non-hotspot
    mask_non = is_non_hotspot(df_test["hotspot_frequency"])
    met_non = compute_regression_metrics(df_test.loc[mask_non, "LST_C"], df_test.loc[mask_non, "prediction"])
    hotspot_records.append({
        "hotspot_category": "non_hotspot",
        "definition": "hotspot_frequency == 0",
        "n_samples": met_non["n_samples"],
        "MAE": met_non["MAE"],
        "RMSE": met_non["RMSE"],
        "R2": met_non["R2"],
    })

    # Active hotspot
    mask_active = is_active_hotspot(df_test["hotspot_frequency"])
    met_active = compute_regression_metrics(df_test.loc[mask_active, "LST_C"], df_test.loc[mask_active, "prediction"])
    hotspot_records.append({
        "hotspot_category": "active_hotspot",
        "definition": "hotspot_frequency > 0",
        "n_samples": met_active["n_samples"],
        "MAE": met_active["MAE"],
        "RMSE": met_active["RMSE"],
        "R2": met_active["R2"],
    })

    # Persistent hotspot (freq >= 0.25)
    mask_pers = is_persistent_hotspot(df_test["hotspot_frequency"], df_test["is_persistent_hotspot"])
    met_pers = compute_regression_metrics(df_test.loc[mask_pers, "LST_C"], df_test.loc[mask_pers, "prediction"])
    hotspot_records.append({
        "hotspot_category": "persistent_hotspot",
        "definition": f"hotspot_frequency >= {PERSISTENT_HOTSPOT_FREQ_THRESHOLD} or is_persistent_hotspot",
        "n_samples": met_pers["n_samples"],
        "MAE": met_pers["MAE"],
        "RMSE": met_pers["RMSE"],
        "R2": met_pers["R2"],
    })

    # Chronic hotspot (freq >= 0.50)
    mask_chronic = is_chronic_hotspot(df_test["hotspot_frequency"], threshold=CHRONIC_HOTSPOT_FREQ_THRESHOLD)
    met_chronic = compute_regression_metrics(df_test.loc[mask_chronic, "LST_C"], df_test.loc[mask_chronic, "prediction"])
    hotspot_records.append({
        "hotspot_category": "chronic_hotspot",
        "definition": f"hotspot_frequency >= {CHRONIC_HOTSPOT_FREQ_THRESHOLD} (highest persistence tier)",
        "n_samples": met_chronic["n_samples"],
        "MAE": met_chronic["MAE"],
        "RMSE": met_chronic["RMSE"],
        "R2": met_chronic["R2"],
    })

    df_hotspots = pd.DataFrame(hotspot_records)
    df_hotspots.to_csv(output_dir / "holdout_hotspot_performance.csv", index=False)

    print("\nHoldout Hotspot Stratification:")
    for _, r in df_hotspots.iterrows():
        print(f"  {r['hotspot_category']:18s} | n={r['n_samples']:,} | MAE: {r['MAE']:.3f} degC | RMSE: {r['RMSE']:.3f} degC | R2: {r['R2']:.3f}")

    # 8. Spatial Residuals Diagnostic GeoJSON
    sample_res = pd.concat([
        df_test.nlargest(300, "absolute_error"),
        df_test.sample(n=min(700, len(df_test)), random_state=random_state),
    ]).drop_duplicates()

    features_geojson = []
    for _, r in sample_res.iterrows():
        feat = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(r["longitude"]), float(r["latitude"])],
            },
            "properties": {
                "year": int(r["year"]),
                "season": r["season"],
                "LST_C": float(r["LST_C"]),
                "prediction": float(r["prediction"]),
                "residual": float(r["residual"]),
                "absolute_error": float(r["absolute_error"]),
                "block_id": r["block_id"],
                "hotspot_frequency": float(r["hotspot_frequency"]),
            },
        }
        features_geojson.append(feat)

    geojson_payload = {
        "type": "FeatureCollection",
        "name": "holdout_spatial_residuals_diagnostic",
        "features": features_geojson,
    }
    with open(reports_dir / "holdout_spatial_residuals.geojson", "w") as f:
        json.dump(geojson_payload, f)

    # 9. Summary Performance Payload
    perf_payload = {
        "holdout_type": "independent_spatial_blocks_20pct",
        "n_samples": test_metrics["n_samples"],
        "MAE": test_metrics["MAE"],
        "RMSE": test_metrics["RMSE"],
        "R2": test_metrics["R2"],
        "fit_time_seconds": round(fit_time, 2),
        "test_blocks_count": len(test_blocks),
        "dev_blocks_count": len(dev_blocks),
    }
    with open(output_dir / "holdout_performance.json", "w") as f:
        json.dump(perf_payload, f, indent=2)

    return perf_payload


if __name__ == "__main__":
    run_independent_holdout_evaluation()
