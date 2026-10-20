"""HEATSENSE AI — Issue 1: Optical Sentinel Sensitivity Audit.

Determines whether the 8 optical-feature sentinel-containing observations (-9999.0)
in the development partition materially affect the frozen XGBoost model's
spatial cross-validation behavior.

This is a development-only audit experiment. The locked independent test set
(203,758 observations, 33 blocks) is strictly isolated and never evaluated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

# Reconfigure stdout to utf-8 if supported
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
import xgboost as xgb

from gis.ml.development_cv import development_spatial_folds

# Paths
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"
SPLIT_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json"
FROZEN_MODEL_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "xgb_tuned_policy_d.joblib"
MODEL_METADATA_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "model_metadata.json"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "ml_freeze" / "sentinel_sensitivity"

# Schema & Constants
FEATURES = ["NDVI", "NDBI", "NDWI", "LST_OBS_COUNT", "LST_QA_MEDIAN_K"]
TARGET = "LST_C"
SENTINEL_VALUE = -9999.0
MERGE_KEYS = ["year", "season", "row", "col", "block_id"]

SENTINEL_EXPORT_COLS = [
    "year",
    "season",
    "row",
    "col",
    "block_id",
    "quality_flag",
    "eligibility",
    "LST_C",
    "NDVI",
    "NDBI",
    "NDWI",
    "LST_OBS_COUNT",
    "LST_QA_MEDIAN_K",
    "is_boundary_context",
]

# Authoritative Frozen XGBoost Configuration
FROZEN_XGB_PARAMS = {
    "n_estimators": 900,
    "max_depth": 9,
    "learning_rate": 0.03662937937931856,
    "min_child_weight": 3.253330265581497,
    "subsample": 0.6539539403049981,
    "colsample_bytree": 0.6285481356546664,
    "gamma": 1.2827623793054954,
    "reg_alpha": 6.448517630611331e-06,
    "reg_lambda": 12.086733674708716,
    "objective": "reg:squarederror",
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": -1,
}


def compute_file_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hexadecimal digest of a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def detect_sentinels(df: pd.DataFrame) -> pd.Series:
    """Exact logical definition of optical sentinel presence."""
    return (
        df["NDVI"].eq(SENTINEL_VALUE)
        | df["NDBI"].eq(SENTINEL_VALUE)
        | df["NDWI"].eq(SENTINEL_VALUE)
    )


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Compute regression metrics including residual and bias conventions."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)

    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(root_mean_squared_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    # Standard conventions:
    # residual = observed - predicted
    # model bias = predicted - observed
    mean_residual = float(np.mean(y_true - y_pred))
    mean_bias = float(np.mean(y_pred - y_true))

    return {
        "n_samples": int(len(y_true)),
        "MAE": round(mae, 4),
        "RMSE": round(rmse, 4),
        "R2": round(r2, 4),
        "mean_residual": round(mean_residual, 4),
        "mean_model_bias": round(mean_bias, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="HEATSENSE AI — Issue 1 Optical Sentinel Sensitivity Audit")
    parser.add_argument("--force-retrain", action="store_true", help="Force retrain models even if valid OOF parquet files exist")
    args = parser.parse_args()

    start_time = time.time()
    print("=" * 80)
    print("HEATSENSE AI — ISSUE 1: OPTICAL SENTINEL SENSITIVITY AUDIT")
    print("=" * 80)

    # -----------------------------------------------------------------------
    # Step 1: Record Pre-Experiment Hashes
    # -----------------------------------------------------------------------
    print("\n[Step 1] Recording pre-experiment SHA-256 hashes of frozen artifacts...")
    pre_dataset_hash = compute_file_sha256(DATASET_PATH)
    pre_model_hash = compute_file_sha256(FROZEN_MODEL_PATH)
    pre_split_hash = compute_file_sha256(SPLIT_PATH)

    print(f"  Dataset:      {pre_dataset_hash}  {DATASET_PATH.name}")
    print(f"  Frozen Model: {pre_model_hash}  {FROZEN_MODEL_PATH.name}")
    print(f"  Locked Split: {pre_split_hash}  {SPLIT_PATH.name}")

    # Verify against authoritative metadata if present
    if MODEL_METADATA_PATH.exists():
        with open(MODEL_METADATA_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)
        best_p = meta.get("best_parameters", {})
        fixed_p = meta.get("fixed_parameters", {})
        for k, v in best_p.items():
            assert FROZEN_XGB_PARAMS.get(k) == v, f"Param mismatch for {k}: {FROZEN_XGB_PARAMS.get(k)} vs {v}"
        for k, v in fixed_p.items():
            assert FROZEN_XGB_PARAMS.get(k) == v, f"Param mismatch for {k}: {FROZEN_XGB_PARAMS.get(k)} vs {v}"
        print("  Authoritative XGBoost parameters verified against model_metadata.json.")

    # -----------------------------------------------------------------------
    # Step 2: Load Dataset and Holdout Split
    # -----------------------------------------------------------------------
    print("\n[Step 2] Loading authoritative dataset and locked holdout split...")
    df = pd.read_parquet(DATASET_PATH)
    total_rows = len(df)
    print(f"  Total dataset rows: {total_rows:,}")
    if total_rows != 924731:
        raise ValueError(f"FATAL: Expected 924,731 rows, found {total_rows}")

    with open(SPLIT_PATH, "r", encoding="utf-8") as f:
        split_data = json.load(f)

    dev_blocks = list(split_data["development_blocks"])
    test_blocks = list(split_data["test_blocks"])
    dev_block_set = set(dev_blocks)
    test_block_set = set(test_blocks)

    print(f"  Development blocks: {len(dev_blocks)}, Test blocks: {len(test_blocks)}")
    if len(dev_blocks) != 132 or len(test_blocks) != 33:
        raise ValueError(f"FATAL: Expected 132 dev and 33 test blocks, found {len(dev_blocks)} and {len(test_blocks)}")

    if not dev_block_set.isdisjoint(test_block_set):
        raise ValueError("FATAL LEAKAGE: Development and test blocks overlap!")

    # Partition dataset
    dev_mask = df["block_id"].isin(dev_block_set)
    test_mask = df["block_id"].isin(test_block_set)

    dev_df = df[dev_mask].copy().reset_index(drop=True)
    test_df = df[test_mask].copy().reset_index(drop=True)

    print(f"  Development rows: {len(dev_df):,}")
    print(f"  Locked test rows: {len(test_df):,}")

    if len(dev_df) != 720973:
        raise ValueError(f"FATAL: Expected 720,973 development rows, found {len(dev_df)}")
    if len(test_df) != 203758:
        raise ValueError(f"FATAL: Expected 203,758 test rows, found {len(test_df)}")

    # -----------------------------------------------------------------------
    # Step 3: Hard Test-Set Safety Check & Sentinel Inventory
    # -----------------------------------------------------------------------
    print("\n[Step 3] Performing hard test-set safety check and sentinel inventory...")
    test_sentinel_mask = detect_sentinels(test_df)
    test_sentinel_count = int(test_sentinel_mask.sum())
    print(f"  Locked test sentinel rows: {test_sentinel_count}")

    if test_sentinel_count > 0:
        raise RuntimeError(
            f"ABORT EXPERIMENT: Locked test set contains {test_sentinel_count} sentinel observations! "
            "Independent test set purity violated."
        )

    dev_sentinel_mask = detect_sentinels(dev_df)
    dev_sentinel_count = int(dev_sentinel_mask.sum())
    print(f"  Development sentinel rows: {dev_sentinel_count}")

    if dev_sentinel_count != 8:
        raise ValueError(f"FATAL: Expected exactly 8 development sentinel rows, found {dev_sentinel_count}")

    ndvi_sentinel_count = int(df["NDVI"].eq(SENTINEL_VALUE).sum())
    ndbi_sentinel_count = int(df["NDBI"].eq(SENTINEL_VALUE).sum())
    ndwi_sentinel_count = int(df["NDWI"].eq(SENTINEL_VALUE).sum())
    print(f"  Full dataset sentinel counts: NDVI={ndvi_sentinel_count}, NDBI={ndbi_sentinel_count}, NDWI={ndwi_sentinel_count}")

    assert ndvi_sentinel_count == 7, f"Expected NDVI sentinels 7, found {ndvi_sentinel_count}"
    assert ndbi_sentinel_count == 2, f"Expected NDBI sentinels 2, found {ndbi_sentinel_count}"
    assert ndwi_sentinel_count == 3, f"Expected NDWI sentinels 3, found {ndwi_sentinel_count}"

    # Verify sentinel block distribution
    sentinel_blocks = sorted(dev_df.loc[dev_sentinel_mask, "block_id"].unique().tolist())
    print(f"  Sentinel-containing blocks: {sentinel_blocks}")
    assert sentinel_blocks == ["B_05_11", "B_10_04"], f"Unexpected sentinel blocks: {sentinel_blocks}"

    # -----------------------------------------------------------------------
    # Step 4: Export Exact Sentinel Rows
    # -----------------------------------------------------------------------
    print("\n[Step 4] Exporting the exact 8 sentinel development rows...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sentinel_rows_df = dev_df.loc[dev_sentinel_mask, SENTINEL_EXPORT_COLS].copy()
    sentinel_export_path = OUTPUT_DIR / "development_sentinel_rows.csv"
    sentinel_rows_df.to_csv(sentinel_export_path, index=False)
    print(f"  [SAVED] {sentinel_export_path} ({len(sentinel_rows_df)} rows)")

    # -----------------------------------------------------------------------
    # Step 5: Canonical Development Spatial Cross-Validation Folds
    # -----------------------------------------------------------------------
    print("\n[Step 5] Generating canonical 5-fold development spatial cross-validation...")
    splits = development_spatial_folds(
        df_dev=dev_df,
        development_blocks=dev_blocks,
        n_splits=5,
        random_state=42,
        block_col="block_id",
        prohibited_test_blocks=test_blocks,
    )

    dev_df["is_sentinel"] = dev_sentinel_mask

    exp_a_metrics_path = OUTPUT_DIR / "original_fold_metrics.csv"
    exp_a_oof_path = OUTPUT_DIR / "original_oof_predictions.parquet"
    exp_b_metrics_path = OUTPUT_DIR / "sentinel_excluded_fold_metrics.csv"
    exp_b_oof_path = OUTPUT_DIR / "sentinel_excluded_oof_predictions.parquet"

    can_reuse = (
        not args.force_retrain
        and exp_a_oof_path.exists()
        and exp_b_oof_path.exists()
        and exp_a_metrics_path.exists()
        and exp_b_metrics_path.exists()
    )

    if can_reuse:
        print("\n[Step 6 & 7] Loading verified existing OOF prediction artifacts...")
        exp_a_oof_df = pd.read_parquet(exp_a_oof_path)
        exp_b_oof_df = pd.read_parquet(exp_b_oof_path)
        exp_a_metrics_df = pd.read_csv(exp_a_metrics_path)
        exp_b_metrics_df = pd.read_csv(exp_b_metrics_path)

        assert len(exp_a_oof_df) == 720973, f"Unexpected length in exp_a_oof_df: {len(exp_a_oof_df)}"
        assert len(exp_b_oof_df) == 720973, f"Unexpected length in exp_b_oof_df: {len(exp_b_oof_df)}"
        print(f"  [LOADED] {exp_a_oof_path} ({len(exp_a_oof_df):,} rows)")
        print(f"  [LOADED] {exp_b_oof_path} ({len(exp_b_oof_df):,} rows)")
        print("  (Pass --force-retrain to rerun model training across all 10 folds)")
    else:
        # -----------------------------------------------------------------------
        # Step 6: Experiment A — Original Training (with Sentinels)
        # -----------------------------------------------------------------------
        print("\n[Step 6] Running Experiment A: Original Training (sentinels included in train folds)...")
        exp_a_fold_metrics: list[dict[str, Any]] = []
        exp_a_oof_dfs: list[pd.DataFrame] = []

        for fold_idx, (train_idx, val_idx) in enumerate(splits, 1):
            fold_start = time.time()
            train_sub = dev_df.iloc[train_idx]
            val_sub = dev_df.iloc[val_idx]

            train_sentinel_count = int(train_sub["is_sentinel"].sum())
            val_sentinel_count = int(val_sub["is_sentinel"].sum())

            X_train = train_sub[FEATURES]
            y_train = train_sub[TARGET]
            X_val = val_sub[FEATURES]
            y_val = val_sub[TARGET]

            print(
                f"  [Exp A] Fold {fold_idx}/5: train_n={len(train_sub):,} (sentinels={train_sentinel_count}), "
                f"val_n={len(val_sub):,} (sentinels={val_sentinel_count})..."
            )

            model_a = xgb.XGBRegressor(**FROZEN_XGB_PARAMS)
            model_a.fit(X_train, y_train)

            y_pred = model_a.predict(X_val)

            metrics = compute_metrics(y_val.to_numpy(), y_pred)
            metrics["fold"] = fold_idx
            metrics["train_samples"] = len(train_sub)
            metrics["val_samples"] = len(val_sub)
            metrics["train_sentinel_count"] = train_sentinel_count
            metrics["val_sentinel_count"] = val_sentinel_count
            metrics["elapsed_s"] = round(time.time() - fold_start, 2)
            exp_a_fold_metrics.append(metrics)

            print(
                f"    -> MAE={metrics['MAE']:.4f} deg C, RMSE={metrics['RMSE']:.4f} deg C, "
                f"R2={metrics['R2']:.4f}, bias={metrics['mean_model_bias']:.4f} deg C ({metrics['elapsed_s']} s)"
            )

            oof_fold = val_sub[MERGE_KEYS + [TARGET, "is_sentinel"]].copy()
            oof_fold["fold"] = fold_idx
            oof_fold["pred_orig"] = y_pred
            exp_a_oof_dfs.append(oof_fold)

        exp_a_oof_df = pd.concat(exp_a_oof_dfs, ignore_index=True)
        exp_a_metrics_df = pd.DataFrame(exp_a_fold_metrics)

        exp_a_metrics_df.to_csv(exp_a_metrics_path, index=False)
        exp_a_oof_df.to_parquet(exp_a_oof_path, index=False)
        print(f"  [SAVED] {exp_a_metrics_path}")
        print(f"  [SAVED] {exp_a_oof_path}")

        # -----------------------------------------------------------------------
        # Step 7: Experiment B — Sentinel-Excluded Training
        # -----------------------------------------------------------------------
        print("\n[Step 7] Running Experiment B: Sentinel-Excluded Training...")
        exp_b_fold_metrics: list[dict[str, Any]] = []
        exp_b_oof_dfs: list[pd.DataFrame] = []

        for fold_idx, (train_idx, val_idx) in enumerate(splits, 1):
            fold_start = time.time()
            train_sub_all = dev_df.iloc[train_idx]
            val_sub = dev_df.iloc[val_idx]  # Validation fold is UNCHANGED

            # Exclude sentinel rows ONLY from training
            clean_train_mask = ~train_sub_all["is_sentinel"]
            train_sub_clean = train_sub_all[clean_train_mask]

            train_sentinel_count = int(train_sub_clean["is_sentinel"].sum())  # Should be 0
            removed_count = int(train_sub_all["is_sentinel"].sum())
            val_sentinel_count = int(val_sub["is_sentinel"].sum())

            X_train = train_sub_clean[FEATURES]
            y_train = train_sub_clean[TARGET]
            X_val = val_sub[FEATURES]
            y_val = val_sub[TARGET]

            print(
                f"  [Exp B] Fold {fold_idx}/5: clean_train_n={len(train_sub_clean):,} (removed={removed_count}), "
                f"val_n={len(val_sub):,} (sentinels={val_sentinel_count})..."
            )

            model_b = xgb.XGBRegressor(**FROZEN_XGB_PARAMS)
            model_b.fit(X_train, y_train)

            y_pred = model_b.predict(X_val)

            metrics = compute_metrics(y_val.to_numpy(), y_pred)
            metrics["fold"] = fold_idx
            metrics["train_samples"] = len(train_sub_clean)
            metrics["val_samples"] = len(val_sub)
            metrics["train_sentinels_removed"] = removed_count
            metrics["val_sentinel_count"] = val_sentinel_count
            metrics["elapsed_s"] = round(time.time() - fold_start, 2)
            exp_b_fold_metrics.append(metrics)

            print(
                f"    -> MAE={metrics['MAE']:.4f} deg C, RMSE={metrics['RMSE']:.4f} deg C, "
                f"R2={metrics['R2']:.4f}, bias={metrics['mean_model_bias']:.4f} deg C ({metrics['elapsed_s']} s)"
            )

            oof_fold = val_sub[MERGE_KEYS + [TARGET, "is_sentinel"]].copy()
            oof_fold["fold"] = fold_idx
            oof_fold["pred_clean"] = y_pred
            exp_b_oof_dfs.append(oof_fold)

        exp_b_oof_df = pd.concat(exp_b_oof_dfs, ignore_index=True)
        exp_b_metrics_df = pd.DataFrame(exp_b_fold_metrics)

        exp_b_metrics_df.to_csv(exp_b_metrics_path, index=False)
        exp_b_oof_df.to_parquet(exp_b_oof_path, index=False)
        print(f"  [SAVED] {exp_b_metrics_path}")
        print(f"  [SAVED] {exp_b_oof_path}")

    # -----------------------------------------------------------------------
    # Step 8: Common Non-Sentinel Population Evaluation & Prediction Deltas
    # -----------------------------------------------------------------------
    print("\n[Step 8] Evaluating models on common non-sentinel validation population...")

    # Filter to common non-sentinel validation observations
    common_a = exp_a_oof_df[~exp_a_oof_df["is_sentinel"]].copy()
    common_b = exp_b_oof_df[~exp_b_oof_df["is_sentinel"]].copy()

    n_common = len(common_a)
    print(f"  Common non-sentinel validation rows: {n_common:,}")
    if n_common != 720965:
        raise ValueError(f"FATAL: Expected exactly 720,965 common non-sentinel rows, found {n_common}")
    if len(common_b) != 720965:
        raise ValueError(f"FATAL: Expected exactly 720,965 common rows in Exp B, found {len(common_b)}")

    # Merge on MERGE_KEYS
    merged_common = pd.merge(
        common_a,
        common_b[MERGE_KEYS + ["pred_clean"]],
        on=MERGE_KEYS,
        how="inner",
    )
    if len(merged_common) != n_common:
        raise ValueError(f"Merge discrepancy: expected {n_common}, merged {len(merged_common)}")

    y_true_common = merged_common[TARGET].to_numpy()
    pred_orig_common = merged_common["pred_orig"].to_numpy()
    pred_clean_common = merged_common["pred_clean"].to_numpy()

    metrics_a_common = compute_metrics(y_true_common, pred_orig_common)
    metrics_b_common = compute_metrics(y_true_common, pred_clean_common)

    print("\n  Common Non-Sentinel Validation Population Performance:")
    print("  " + "-" * 70)
    print(f"  {'Metric':<20} | {'Experiment A (Original)':<24} | {'Experiment B (Clean)':<24}")
    print("  " + "-" * 70)
    print(f"  {'MAE (deg C)':<20} | {metrics_a_common['MAE']:<24.4f} | {metrics_b_common['MAE']:<24.4f}")
    print(f"  {'RMSE (deg C)':<20} | {metrics_a_common['RMSE']:<24.4f} | {metrics_b_common['RMSE']:<24.4f}")
    print(f"  {'R2':<20} | {metrics_a_common['R2']:<24.4f} | {metrics_b_common['R2']:<24.4f}")
    print(f"  {'Mean Residual (deg C)':<20} | {metrics_a_common['mean_residual']:<24.4f} | {metrics_b_common['mean_residual']:<24.4f}")
    print(f"  {'Model Bias (deg C)':<20} | {metrics_a_common['mean_model_bias']:<24.4f} | {metrics_b_common['mean_model_bias']:<24.4f}")
    print("  " + "-" * 70)

    # Prediction Delta Analysis: prediction_delta = clean_prediction - original_prediction
    prediction_delta = pred_clean_common - pred_orig_common
    abs_delta = np.abs(prediction_delta)

    delta_mean = float(np.mean(prediction_delta))
    delta_mae = float(np.mean(abs_delta))
    delta_rmse = float(np.sqrt(np.mean(prediction_delta ** 2)))
    delta_p95 = float(np.percentile(abs_delta, 95))
    delta_p99 = float(np.percentile(abs_delta, 99))
    delta_max = float(np.max(abs_delta))

    prediction_delta_stats = {
        "n_observations": int(n_common),
        "mean_c": round(delta_mean, 6),
        "mean_absolute_c": round(delta_mae, 6),
        "RMSE_delta_c": round(delta_rmse, 6),
        "p95_absolute_c": round(delta_p95, 6),
        "p99_absolute_c": round(delta_p99, 6),
        "max_absolute_c": round(delta_max, 6),
    }

    print("\n  Prediction Delta Analysis (clean_prediction - original_prediction):")
    print("  " + "-" * 70)
    print(f"  Mean Delta:           {delta_mean:+.6f} deg C")
    print(f"  Mean Absolute Delta:   {delta_mae:.6f} deg C")
    print(f"  RMSE Delta:            {delta_rmse:.6f} deg C")
    print(f"  95th Percentile |Delta|: {delta_p95:.6f} deg C")
    print(f"  99th Percentile |Delta|: {delta_p99:.6f} deg C")
    print(f"  Max Absolute Delta:    {delta_max:.6f} deg C")
    print("  " + "-" * 70)

    # Fold-level prediction delta analysis
    fold_prediction_deltas: dict[str, Any] = {}
    for f_idx in range(1, 6):
        f_mask = merged_common["fold"] == f_idx
        f_deltas = prediction_delta[f_mask]
        f_abs = np.abs(f_deltas)
        fold_prediction_deltas[f"fold_{f_idx}"] = {
            "n_samples": int(f_mask.sum()),
            "mean_c": round(float(np.mean(f_deltas)), 6),
            "mean_absolute_c": round(float(np.mean(f_abs)), 6),
            "RMSE_delta_c": round(float(np.sqrt(np.mean(f_deltas ** 2))), 6),
            "p95_absolute_c": round(float(np.percentile(f_abs, 95)), 6),
            "max_absolute_c": round(float(np.max(f_abs)), 6),
        }

    # -----------------------------------------------------------------------
    # Step 9: Post-Experiment Hash Protection
    # -----------------------------------------------------------------------
    print("\n[Step 9] Recomputing post-experiment SHA-256 hashes of frozen artifacts...")
    post_dataset_hash = compute_file_sha256(DATASET_PATH)
    post_model_hash = compute_file_sha256(FROZEN_MODEL_PATH)
    post_split_hash = compute_file_sha256(SPLIT_PATH)

    dataset_unchanged = (pre_dataset_hash == post_dataset_hash)
    model_unchanged = (pre_model_hash == post_model_hash)
    split_unchanged = (pre_split_hash == post_split_hash)

    print(f"  Dataset Hash Match:      {dataset_unchanged} ({post_dataset_hash})")
    print(f"  Frozen Model Hash Match: {model_unchanged} ({post_model_hash})")
    print(f"  Locked Split Hash Match: {split_unchanged} ({post_split_hash})")

    if not (dataset_unchanged and model_unchanged and split_unchanged):
        raise RuntimeError("FATAL: A frozen artifact was unexpectedly modified during execution!")

    # -----------------------------------------------------------------------
    # Step 10: Scientific Classification & Summary JSON
    # -----------------------------------------------------------------------
    print("\n[Step 10] Generating summary artifact and determining scientific status...")

    diff_mae = abs(metrics_b_common["MAE"] - metrics_a_common["MAE"])
    diff_rmse = abs(metrics_b_common["RMSE"] - metrics_a_common["RMSE"])
    diff_r2 = abs(metrics_b_common["R2"] - metrics_a_common["R2"])

    # Scientific classification based on measured empirical metrics
    is_negligible = (diff_rmse <= 0.005) and (delta_mae <= 0.10) and (delta_rmse <= 0.15)

    scientific_status = (
        "RESOLVED BY SENSITIVITY EVIDENCE" if is_negligible else "INVESTIGATION REQUIRED"
    )

    summary_data = {
        "dataset": str(DATASET_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "total_rows": total_rows,
        "development_rows": len(dev_df),
        "development_sentinel_rows": dev_sentinel_count,
        "test_rows": len(test_df),
        "test_sentinel_rows": test_sentinel_count,
        "ndvi_sentinel_count": ndvi_sentinel_count,
        "ndbi_sentinel_count": ndbi_sentinel_count,
        "ndwi_sentinel_count": ndwi_sentinel_count,
        "development_blocks": len(dev_blocks),
        "test_blocks": len(test_blocks),
        "spatial_folds": 5,
        "common_non_sentinel_validation_rows": n_common,
        "original_common_non_sentinel_metrics": metrics_a_common,
        "sentinel_excluded_common_non_sentinel_metrics": metrics_b_common,
        "metric_differences_abs": {
            "delta_MAE": round(diff_mae, 6),
            "delta_RMSE": round(diff_rmse, 6),
            "delta_R2": round(diff_r2, 6),
        },
        "prediction_delta_on_common_non_sentinel": prediction_delta_stats,
        "fold_prediction_deltas": fold_prediction_deltas,
        "frozen_hashes": {
            "dataset_sha256": post_dataset_hash,
            "frozen_model_sha256": post_model_hash,
            "holdout_split_sha256": post_split_hash,
        },
        "frozen_model_changed": not model_unchanged,
        "authoritative_dataset_changed": not dataset_unchanged,
        "locked_test_modified": False,
        "status": scientific_status,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    summary_path = OUTPUT_DIR / "sentinel_sensitivity_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"  [SAVED] {summary_path}")

    elapsed_total = round(time.time() - start_time, 2)
    print("\n" + "=" * 80)
    print(f"AUDIT COMPLETE in {elapsed_total} s")
    print(f"SCIENTIFIC STATUS: {scientific_status}")
    print("=" * 80)


if __name__ == "__main__":
    main()
