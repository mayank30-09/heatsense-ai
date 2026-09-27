"""Final Independent Spatial Holdout Evaluation for HEATSENSE AI.

Trains the final candidate XGBoost model on all 132 development blocks (720,973 rows)
using hyperparameters selected exclusively from development-only Optuna tuning, then
evaluates the model EXACTLY ONCE on the 33 locked, untouched test blocks (203,758 rows).

Generates authoritative freeze performance artifacts:
- artifacts/ml_freeze/xgb_tuned_policy_d.json
- artifacts/ml_freeze/xgb_tuned_policy_d.joblib
- artifacts/ml_freeze/feature_schema.json
- artifacts/ml_freeze/holdout_performance.json
- artifacts/ml_freeze/holdout_season_performance.csv
- artifacts/ml_freeze/holdout_hotspot_performance.csv
- artifacts/ml_freeze/holdout_spatial_residuals.geojson
- artifacts/ml_freeze/model_metadata.json
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb

from gis.ml.holdout_split import (
    load_holdout_split,
    partition_dataset_by_holdout,
)
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
DEFAULT_HOLDOUT = PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json"
DEFAULT_PARAMS = PROJECT_ROOT / "artifacts" / "ml_freeze" / "tuning" / "xgb_best_params.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "ml_freeze"


def get_git_commit_hash() -> str | None:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="HEATSENSE AI: Train on 132 Dev Blocks & Evaluate on 33 Locked Test Blocks",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to Policy D analysis parquet file.",
    )
    parser.add_argument(
        "--holdout-split",
        type=Path,
        default=DEFAULT_HOLDOUT,
        help="Path to locked holdout_split.json.",
    )
    parser.add_argument(
        "--params",
        type=Path,
        default=DEFAULT_PARAMS,
        help="Path to xgb_best_params.json from development-only Optuna tuning.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory to save final freeze artifacts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 80)
    print("HEATSENSE AI: FINAL INDEPENDENT SPATIAL HOLDOUT EVALUATION")
    print("STRICT ONE-TIME TEST PARTITION EVALUATION")
    print("=" * 80)
    print(f"Dataset path   : {args.dataset}")
    print(f"Holdout split  : {args.holdout_split}")
    print(f"Best params    : {args.params}")
    print(f"Output dir     : {args.output_dir}")

    if not args.dataset.exists():
        raise FileNotFoundError(f"Dataset not found: {args.dataset}")
    if not args.holdout_split.exists():
        raise FileNotFoundError(f"Holdout split not found: {args.holdout_split}")
    if not args.params.exists():
        raise FileNotFoundError(f"Tuning params not found: {args.params}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load dataset
    print("\n1. Loading Policy D dataset...")
    df_full = pd.read_parquet(args.dataset)
    validate_dataset_schema(df_full)
    total_rows = len(df_full)
    n_blocks = df_full["block_id"].nunique()
    print(f"   Loaded {total_rows:,} rows across {n_blocks} spatial blocks.")

    # 2. Load locked holdout split
    print("\n2. Loading locked spatial holdout split...")
    holdout_data = load_holdout_split(args.holdout_split)
    dev_blocks = holdout_data["development_blocks"]
    test_blocks = holdout_data["test_blocks"]

    # 3. Partition dataset
    print("\n3. Enforcing strict spatial partitioning...")
    df_dev, df_test = partition_dataset_by_holdout(
        df_full, dev_blocks=dev_blocks, test_blocks=test_blocks, block_col="block_id"
    )

    dev_set = set(dev_blocks)
    test_set = set(test_blocks)

    assert set(df_dev["block_id"].astype(str)) == dev_set, "Dev block mismatch!"
    assert set(df_test["block_id"].astype(str)) == test_set, "Test block mismatch!"
    assert dev_set.isdisjoint(test_set), "Fatal error: dev and test blocks overlap!"

    print(f"   [DISJOINT ISOLATION VERIFIED]:")
    print(f"   Development set: {len(df_dev):,} rows across {len(dev_blocks)} blocks.")
    print(f"   Test set       : {len(df_test):,} rows across {len(test_blocks)} blocks.")

    # 4. Load tuned hyperparameters
    print("\n4. Loading development-tuned hyperparameters...")
    with open(args.params, "r", encoding="utf-8") as f:
        params_data = json.load(f)

    raw_params = params_data.get("best_params", params_data)
    fixed_params = params_data.get("fixed_params", {
        "objective": "reg:squarederror",
        "tree_method": "hist",
        "random_state": 42,
        "n_jobs": -1,
    })
    model_params = {**raw_params, **fixed_params}
    print(f"   Best Dev-CV RMSE from tuning: {params_data.get('best_cv_rmse', 'N/A')} degC")
    print(f"   Parameters: {raw_params}")

    # 5. Train final model on ALL 132 development blocks
    print(f"\n5. Fitting final candidate XGBoost on all {len(dev_blocks)} development blocks ({len(df_dev):,} rows)...")
    X_dev = df_dev[FEATURE_COLUMNS].to_numpy()
    y_dev = df_dev[TARGET_COLUMN].to_numpy()

    t_train_start = time.time()
    final_model = xgb.XGBRegressor(**model_params)
    final_model.fit(X_dev, y_dev)
    train_duration = time.time() - t_train_start
    print(f"   Training completed in {train_duration:.2f}s.")

    # 6. Save model artifacts
    model_json_path = args.output_dir / "xgb_tuned_policy_d.json"
    final_model.save_model(str(model_json_path))
    print(f"   Saved native model JSON: {model_json_path}")

    model_joblib_path = args.output_dir / "xgb_tuned_policy_d.joblib"
    joblib.dump(final_model, model_joblib_path)
    print(f"   Saved joblib bundle   : {model_joblib_path}")

    # 7. Evaluate on the 33 UNTOUCHED test blocks exactly once
    print(f"\n6. Predicting on {len(test_blocks)} UNTOUCHED test blocks ({len(df_test):,} rows)...")
    X_test = df_test[FEATURE_COLUMNS].to_numpy()
    y_test = df_test[TARGET_COLUMN].to_numpy()

    t_infer_start = time.time()
    y_pred_test = final_model.predict(X_test)
    infer_duration = time.time() - t_infer_start

    overall_metrics = compute_regression_metrics(y_test, y_pred_test)
    print(f"\n" + "=" * 80)
    print("FINAL INDEPENDENT SPATIAL TEST METRICS (EVALUATION COUNT = 1):")
    print(f"  MAE  : {overall_metrics['MAE']:.4f} degC")
    print(f"  RMSE : {overall_metrics['RMSE']:.4f} degC")
    print(f"  R2   : {overall_metrics['R2']:.4f}")
    print(f"  Inference Latency: {infer_duration:.3f}s for {len(df_test):,} rows")
    print("=" * 80)

    # 8. Compute seasonal breakdown
    print("\n7. Computing holdout seasonal metrics...")
    season_records = []
    df_test = df_test.copy()
    df_test["predicted_lst"] = y_pred_test
    df_test["residual"] = y_pred_test - y_test
    df_test["abs_residual"] = np.abs(df_test["residual"])

    for season_name in ["winter", "summer", "monsoon", "post_monsoon"]:
        mask_s = df_test["season"].str.lower() == season_name.lower()
        sub = df_test[mask_s]
        if len(sub) > 0:
            m = compute_regression_metrics(sub[TARGET_COLUMN].to_numpy(), sub["predicted_lst"].to_numpy())
            season_records.append({
                "season": season_name.upper(),
                "n_samples": m["n_samples"],
                "sample_pct": round(m["n_samples"] / len(df_test) * 100, 2),
                "MAE": round(m["MAE"], 4),
                "RMSE": round(m["RMSE"], 4),
                "R2": round(m["R2"], 4),
                "mean_bias": round(float(np.mean(sub["residual"])), 4),
            })

    season_df = pd.DataFrame(season_records)
    season_csv_path = args.output_dir / "holdout_season_performance.csv"
    season_df.to_csv(season_csv_path, index=False)
    print(f"   Saved seasonal metrics to: {season_csv_path}")

    # 9. Compute canonical hotspot tier breakdown
    print("\n8. Computing holdout canonical hotspot tier metrics...")
    hotspot_records = []

    # Non-hotspot (frequency == 0)
    mask_non = is_non_hotspot(df_test["hotspot_frequency"]).to_numpy()
    sub_non = df_test[mask_non]
    m_non = compute_regression_metrics(sub_non[TARGET_COLUMN].to_numpy(), sub_non["predicted_lst"].to_numpy())
    hotspot_records.append({
        "tier": "non_hotspot",
        "definition": "hotspot_frequency == 0.0",
        "n_samples": m_non["n_samples"],
        "sample_pct": round(m_non["n_samples"] / len(df_test) * 100, 2),
        "MAE": round(m_non["MAE"], 4),
        "RMSE": round(m_non["RMSE"], 4),
        "R2": round(m_non["R2"], 4),
        "mean_bias": round(float(np.mean(sub_non["residual"])), 4),
    })

    # Active hotspot (frequency > 0)
    mask_act = is_active_hotspot(df_test["hotspot_frequency"]).to_numpy()
    sub_act = df_test[mask_act]
    m_act = compute_regression_metrics(sub_act[TARGET_COLUMN].to_numpy(), sub_act["predicted_lst"].to_numpy())
    hotspot_records.append({
        "tier": "active_hotspot",
        "definition": "hotspot_frequency > 0.0",
        "n_samples": m_act["n_samples"],
        "sample_pct": round(m_act["n_samples"] / len(df_test) * 100, 2),
        "MAE": round(m_act["MAE"], 4),
        "RMSE": round(m_act["RMSE"], 4),
        "R2": round(m_act["R2"], 4),
        "mean_bias": round(float(np.mean(sub_act["residual"])), 4),
    })

    # Persistent hotspot (freq >= 0.25 or is_persistent_hotspot)
    pers_flag = df_test["is_persistent_hotspot"] if "is_persistent_hotspot" in df_test.columns else None
    mask_pers = np.asarray(is_persistent_hotspot(df_test["hotspot_frequency"], is_persistent_flag=pers_flag))
    sub_pers = df_test[mask_pers]
    m_pers = compute_regression_metrics(sub_pers[TARGET_COLUMN].to_numpy(), sub_pers["predicted_lst"].to_numpy())
    hotspot_records.append({
        "tier": "persistent_hotspot",
        "definition": "hotspot_frequency >= 0.25 or is_persistent_hotspot",
        "n_samples": m_pers["n_samples"],
        "sample_pct": round(m_pers["n_samples"] / len(df_test) * 100, 2),
        "MAE": round(m_pers["MAE"], 4),
        "RMSE": round(m_pers["RMSE"], 4),
        "R2": round(m_pers["R2"], 4),
        "mean_bias": round(float(np.mean(sub_pers["residual"])), 4),
    })

    # Chronic hotspot (freq >= 0.50)
    mask_chr = is_chronic_hotspot(df_test["hotspot_frequency"], threshold=CHRONIC_HOTSPOT_FREQ_THRESHOLD).to_numpy()
    sub_chr = df_test[mask_chr]
    m_chr = compute_regression_metrics(sub_chr[TARGET_COLUMN].to_numpy(), sub_chr["predicted_lst"].to_numpy())
    hotspot_records.append({
        "tier": "chronic_hotspot",
        "definition": "hotspot_frequency >= 0.50",
        "n_samples": m_chr["n_samples"],
        "sample_pct": round(m_chr["n_samples"] / len(df_test) * 100, 2),
        "MAE": round(m_chr["MAE"], 4),
        "RMSE": round(m_chr["RMSE"], 4),
        "R2": round(m_chr["R2"], 4),
        "mean_bias": round(float(np.mean(sub_chr["residual"])), 4),
    })

    hotspot_df = pd.DataFrame(hotspot_records)
    hotspot_csv_path = args.output_dir / "holdout_hotspot_performance.csv"
    hotspot_df.to_csv(hotspot_csv_path, index=False)
    print(f"   Saved hotspot tier metrics to: {hotspot_csv_path}")

    # 10. Persist holdout performance JSON
    perf_json_path = args.output_dir / "holdout_performance.json"
    perf_data = {
        "holdout_type": "independent_spatial_blocks_20pct",
        "development_blocks": len(dev_blocks),
        "test_blocks": len(test_blocks),
        "evaluation_count": 1,
        "development_rows": len(df_dev),
        "test_rows": len(df_test),
        "MAE": round(overall_metrics["MAE"], 4),
        "RMSE": round(overall_metrics["RMSE"], 4),
        "R2": round(overall_metrics["R2"], 4),
        "training_time_seconds": round(train_duration, 2),
        "inference_time_seconds": round(infer_duration, 3),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(perf_json_path, "w", encoding="utf-8") as f:
        json.dump(perf_data, f, indent=2)
    print(f"   Saved holdout performance to: {perf_json_path}")

    # 11. Generate spatial residuals GeoJSON aggregated by test block
    print("\n9. Generating spatial residuals GeoJSON aggregated by block...")
    block_summary = (
        df_test.groupby("block_id")
        .agg(
            n_samples=("residual", "count"),
            mean_residual=("residual", "mean"),
            mae=("abs_residual", "mean"),
            rmse=("residual", lambda x: np.sqrt(np.mean(x**2))),
            mean_obs=("LST_C", "mean"),
            mean_pred=("predicted_lst", "mean"),
            lat_approx=("y", "mean") if "y" in df_test.columns else ("block_id", lambda _: 0.0),
            lon_approx=("x", "mean") if "x" in df_test.columns else ("block_id", lambda _: 0.0),
        )
        .reset_index()
    )

    geojson_features = []
    for _, row in block_summary.iterrows():
        lon = float(row["lon_approx"])
        lat = float(row["lat_approx"])
        geojson_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "block_id": str(row["block_id"]),
                "n_samples": int(row["n_samples"]),
                "mae": round(float(row["mae"]), 4),
                "rmse": round(float(row["rmse"]), 4),
                "mean_residual": round(float(row["mean_residual"]), 4),
                "mean_obs_lst": round(float(row["mean_obs"]), 2),
                "mean_pred_lst": round(float(row["mean_pred"]), 2),
            },
        })

    geojson_payload = {
        "type": "FeatureCollection",
        "description": "HEATSENSE AI Holdout Spatial Residuals aggregated by 2km block",
        "features": geojson_features,
    }

    geojson_path = args.output_dir / "holdout_spatial_residuals.geojson"
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson_payload, f, indent=2)
    print(f"   Saved spatial residuals GeoJSON to: {geojson_path}")

    # 12. Create feature schema JSON
    schema_path = args.output_dir / "feature_schema.json"
    schema_payload = {
        "schema_version": "1.0",
        "target": TARGET_COLUMN,
        "features": FEATURE_COLUMNS,
        "feature_order_locked": True,
        "features_description": {
            "NDVI": "Normalized Difference Vegetation Index (surface greenness)",
            "NDBI": "Normalized Difference Built-Up Index (built density/impervious surface)",
            "NDWI": "Normalized Difference Water Index (surface water/moisture)",
            "LST_OBS_COUNT": "Landsat Level-2 clear-sky seasonal observation count (temporal support)",
            "LST_QA_MEDIAN_K": "Landsat Level-2 radiometric uncertainty / atmospheric retrieval context (Kelvin)",
        },
    }
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema_payload, f, indent=2)
    print(f"   Saved locked feature schema to: {schema_path}")

    # 13. Create model metadata JSON
    git_hash = get_git_commit_hash()
    meta_path = args.output_dir / "model_metadata.json"
    meta_payload = {
        "model_id": "xgb_tuned_policy_d_v1",
        "status": "candidate",  # Kept as candidate until all freeze gates pass
        "target": TARGET_COLUMN,
        "features": FEATURE_COLUMNS,
        "quality_policy": "D",
        "dataset_rows": total_rows,
        "development_rows": len(df_dev),
        "test_rows": len(df_test),
        "total_spatial_blocks": n_blocks,
        "development_blocks": len(dev_blocks),
        "test_blocks": len(test_blocks),
        "spatial_block_size": "2km",
        "random_state": 42,
        "optuna_trials": 30,
        "best_development_cv_rmse": params_data.get("best_cv_rmse"),
        "best_parameters": raw_params,
        "fixed_parameters": fixed_params,
        "holdout_evaluation": {
            "evaluation_count": 1,
            "MAE": round(overall_metrics["MAE"], 4),
            "RMSE": round(overall_metrics["RMSE"], 4),
            "R2": round(overall_metrics["R2"], 4),
        },
        "environment": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "xgboost_version": xgb.__version__,
            "sklearn_version": sklearn.__version__,
        },
        "git_commit": git_hash or "uncommitted",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_payload, f, indent=2)
    print(f"   Saved model metadata to: {meta_path}")

    print("\n" + "=" * 80)
    print("FINAL HOLDOUT EVALUATION COMPLETE — ZERO TEST LEAKAGE OBSERVED")
    print("=" * 80)


if __name__ == "__main__":
    main()
