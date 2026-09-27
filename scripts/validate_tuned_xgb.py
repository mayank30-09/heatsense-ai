"""Full-Data Spatial Confirmation, Model Comparison, SHAP Rerun, and Residual Analysis.

Executes:
1. Full-data 5-fold spatial cross-validation with tuned XGBoost hyperparameters.
2. Direct 3-way model comparison: RF Baseline vs XGBoost Baseline vs XGBoost Tuned.
3. Season-stratified performance evaluation (preserving 2026 partial-monsoon notation).
4. Hotspot-stratified performance evaluation (non-hotspot, active, chronic).
5. Out-of-fold spatial residual analysis and GeoJSON diagnostic generation.
6. SHAP TreeExplainer attribution refresh on the confirmed tuned model.

Outputs:
    artifacts/xgb_tuning/tuned_xgb_spatial_folds.csv
    artifacts/xgb_tuning/tuned_xgb_spatial_summary.json
    artifacts/xgb_tuning/tuned_spatial_residuals.parquet
    artifacts/xgb_tuning/tuned_shap_summary.csv
    artifacts/xgb_tuning/tuned_shap_stability.csv
    reports/xgb_model_comparison.csv
    reports/xgb_season_errors.csv
    reports/xgb_hotspot_errors.csv
    reports/xgb_spatial_residuals.geojson
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import xgboost as xgb

from gis.ml.explainability import compare_shap_stability, compute_tree_shap_values
from gis.ml.rf_model import compute_regression_metrics
from gis.ml.spatial_validation import (
    get_fold_metadata,
    spatial_block_folds,
    validate_fold_separation,
)
from gis.ml.xgb_tuning import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    validate_dataset_schema,
)

DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"
DEFAULT_PARAMS = PROJECT_ROOT / "artifacts" / "xgb_tuning" / "xgb_best_params.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "xgb_tuning"
DEFAULT_REPORTS = PROJECT_ROOT / "reports"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HEATSENSE AI: Full-Data Spatial Confirmation of Tuned XGBoost",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to full Policy D analysis dataset.",
    )
    parser.add_argument(
        "--params",
        type=Path,
        default=DEFAULT_PARAMS,
        help="Path to xgb_best_params.json from Optuna tuning.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory to store confirmation artifacts.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=DEFAULT_REPORTS,
        help="Directory to store comparative report CSVs and GeoJSON.",
    )
    parser.add_argument(
        "--shap-sample-size",
        type=int,
        default=2000,
        help="Sample size per fold for TreeExplainer computation.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Deterministic random seed.",
    )
    return parser


def load_tuned_params(params_path: Path) -> dict[str, Any]:
    with open(params_path) as f:
        payload = json.load(f)

    # Combine best_params with fixed params
    best_params = payload.get("best_params", {})
    fixed_params = payload.get("fixed_params", {
        "objective": "reg:squarederror",
        "tree_method": "hist",
        "random_state": 42,
        "n_jobs": -1,
    })
    combined = {**best_params, **fixed_params}
    return combined


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input dataset not found at: {args.input}")
    if not args.params.exists():
        raise FileNotFoundError(f"Parameters file not found at: {args.params}")

    args.output.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("HEATSENSE AI: FULL-DATA SPATIAL CONFIRMATION OF TUNED XGBOOST")
    print("=" * 80)
    print(f"Dataset      : {args.input}")
    print(f"Parameters   : {args.params}")
    print(f"Output Dir   : {args.output}")
    print(f"Reports Dir  : {args.reports_dir}")

    # 1. Load full dataset
    df = pd.read_parquet(args.input)
    validate_dataset_schema(df)
    total_samples = len(df)
    print(f"\nLoaded full Policy D dataset: {total_samples:,} observations across {df['block_id'].nunique()} spatial blocks.")

    # 2. Load tuned parameters
    tuned_params = load_tuned_params(args.params)
    print("\nTuned Hyperparameters to Confirm:")
    for k, v in tuned_params.items():
        if isinstance(v, float):
            print(f"  {k:20s}: {v:.6f}")
        else:
            print(f"  {k:20s}: {v}")

    # 3. Canonical 5-fold spatial cross-validation
    folds = spatial_block_folds(df, n_splits=5, random_state=args.random_state)
    validate_fold_separation(df, folds)
    print("  [SPATIAL LEAKAGE CHECK PASSED]: train_blocks INTERSECT val_blocks = empty for all folds.")

    X = df[FEATURE_COLUMNS].to_numpy()
    y = df[TARGET_COLUMN].to_numpy()

    oof_predictions = np.zeros(total_samples, dtype=np.float32)
    fold_assignment = np.zeros(total_samples, dtype=np.int32)

    fold_records = []
    shap_fold_results = []

    print("\nExecuting full-data 5-fold spatial cross-validation...")
    for fold_idx, (train_idx, val_idx) in enumerate(folds):
        t0 = time.time()
        model = xgb.XGBRegressor(**tuned_params)
        model.fit(X[train_idx], y[train_idx])
        fit_time = time.time() - t0

        y_pred = model.predict(X[val_idx])
        oof_predictions[val_idx] = y_pred
        fold_assignment[val_idx] = fold_idx + 1

        metrics = compute_regression_metrics(y[val_idx], y_pred)
        print(
            f"  Fold {fold_idx + 1}/5: MAE={metrics['MAE']:.3f} degC, "
            f"RMSE={metrics['RMSE']:.3f} degC, R2={metrics['R2']:.3f} ({fit_time:.1f}s)"
        )

        fold_records.append({
            "model": "XGBoost_Tuned",
            "fold": fold_idx + 1,
            "MAE": metrics["MAE"],
            "RMSE": metrics["RMSE"],
            "R2": metrics["R2"],
            "n_samples": metrics["n_samples"],
            "fit_time_seconds": round(fit_time, 2),
        })

        # SHAP calculation on a deterministic sample from validation set
        rng = np.random.RandomState(args.random_state + fold_idx)
        sample_n = min(args.shap_sample_size, len(val_idx))
        sample_sub_idx = rng.choice(val_idx, size=sample_n, replace=False)
        shap_res = compute_tree_shap_values(model, X[sample_sub_idx], FEATURE_COLUMNS)
        shap_fold_results.append(shap_res)

    df_folds = pd.DataFrame(fold_records)
    df_folds.to_csv(args.output / "tuned_xgb_spatial_folds.csv", index=False)
    print(f"\nSaved fold metrics to: {args.output / 'tuned_xgb_spatial_folds.csv'}")

    # Summary statistics
    summary_metrics = {
        "model": "XGBoost_Tuned",
        "n_samples": total_samples,
        "n_folds": 5,
        "mean_mae": round(float(df_folds["MAE"].mean()), 4),
        "std_mae": round(float(df_folds["MAE"].std()), 4),
        "min_mae": round(float(df_folds["MAE"].min()), 4),
        "max_mae": round(float(df_folds["MAE"].max()), 4),
        "mean_rmse": round(float(df_folds["RMSE"].mean()), 4),
        "std_rmse": round(float(df_folds["RMSE"].std()), 4),
        "min_rmse": round(float(df_folds["RMSE"].min()), 4),
        "max_rmse": round(float(df_folds["RMSE"].max()), 4),
        "mean_r2": round(float(df_folds["R2"].mean()), 4),
        "std_r2": round(float(df_folds["R2"].std()), 4),
        "min_r2": round(float(df_folds["R2"].min()), 4),
        "max_r2": round(float(df_folds["R2"].max()), 4),
    }
    with open(args.output / "tuned_xgb_spatial_summary.json", "w") as f:
        json.dump(summary_metrics, f, indent=2)
    print(f"Saved confirmation summary to: {args.output / 'tuned_xgb_spatial_summary.json'}")

    # 4. Model Comparison Table (RF Baseline vs XGB Baseline vs XGB Tuned)
    print("\n" + "=" * 80)
    print("3-WAY MODEL COMPARISON (IDENTICAL 5-FOLD SPATIAL SPLITS):")
    print("=" * 80)
    rf_folds_path = PROJECT_ROOT / "data" / "diagnostics" / "ml" / "rf_policy_sensitivity.csv"
    xgb_base_folds_path = PROJECT_ROOT / "data" / "diagnostics" / "ml" / "xgb_spatial_cv.csv"

    comparison_rows = []
    # Load RF
    if rf_folds_path.exists():
        df_rf = pd.read_csv(rf_folds_path)
        df_rf_d = df_rf[df_rf["policy"] == "policy_d"]
        comparison_rows.append({
            "model": "RandomForest_Baseline",
            "mean_MAE": round(float(df_rf_d["MAE"].mean()), 4),
            "std_MAE": round(float(df_rf_d["MAE"].std()), 4),
            "mean_RMSE": round(float(df_rf_d["RMSE"].mean()), 4),
            "std_RMSE": round(float(df_rf_d["RMSE"].std()), 4),
            "mean_R2": round(float(df_rf_d["R2"].mean()), 4),
            "std_R2": round(float(df_rf_d["R2"].std()), 4),
        })

    # Load XGB Baseline
    if xgb_base_folds_path.exists():
        df_xgb_base = pd.read_csv(xgb_base_folds_path)
        comparison_rows.append({
            "model": "XGBoost_Baseline",
            "mean_MAE": round(float(df_xgb_base["MAE"].mean()), 4),
            "std_MAE": round(float(df_xgb_base["MAE"].std()), 4),
            "mean_RMSE": round(float(df_xgb_base["RMSE"].mean()), 4),
            "std_RMSE": round(float(df_xgb_base["RMSE"].std()), 4),
            "mean_R2": round(float(df_xgb_base["R2"].mean()), 4),
            "std_R2": round(float(df_xgb_base["R2"].std()), 4),
        })

    # Tuned XGB
    comparison_rows.append({
        "model": "XGBoost_Tuned",
        "mean_MAE": summary_metrics["mean_mae"],
        "std_MAE": summary_metrics["std_mae"],
        "mean_RMSE": summary_metrics["mean_rmse"],
        "std_RMSE": summary_metrics["std_rmse"],
        "mean_R2": summary_metrics["mean_r2"],
        "std_R2": summary_metrics["std_r2"],
    })

    df_comparison = pd.DataFrame(comparison_rows)
    comp_path = args.reports_dir / "xgb_model_comparison.csv"
    df_comparison.to_csv(comp_path, index=False)
    for _, r in df_comparison.iterrows():
        print(
            f"  {r['model']:22s} | MAE: {r['mean_MAE']:.3f}+/-{r['std_MAE']:.3f} degC | "
            f"RMSE: {r['mean_RMSE']:.3f}+/-{r['std_RMSE']:.3f} degC | R2: {r['mean_R2']:.3f}+/-{r['std_R2']:.3f}"
        )
    print(f"Saved model comparison to: {comp_path}")

    # 5. Spatial Residuals Calculation
    print("\n" + "=" * 80)
    print("SPATIAL RESIDUAL & STRATIFIED ERROR ANALYSIS")
    print("=" * 80)
    residuals = y - oof_predictions
    abs_errors = np.abs(residuals)

    df_residuals = df[[
        "year", "season", "row", "col", "longitude", "latitude", "block_id",
        "LST_C", "hotspot_frequency", "is_persistent_hotspot", "eligibility", "quality_flag", "is_partial_season"
    ]].copy()
    df_residuals["prediction"] = np.round(oof_predictions, 3)
    df_residuals["residual"] = np.round(residuals, 3)
    df_residuals["absolute_error"] = np.round(abs_errors, 3)
    df_residuals["spatial_fold"] = fold_assignment

    res_pq_path = args.output / "tuned_spatial_residuals.parquet"
    df_residuals.to_parquet(res_pq_path, index=False)
    print(f"Saved full spatial residuals ({len(df_residuals):,} rows) to: {res_pq_path}")

    # 6. Season-Specific Analysis
    season_records = []
    for s in ["winter", "summer", "monsoon", "post_monsoon"]:
        s_df = df_residuals[df_residuals["season"] == s]
        if len(s_df) > 0:
            met = compute_regression_metrics(s_df["LST_C"], s_df["prediction"])
            has_partial = (s == "monsoon" and (s_df["is_partial_season"]).any())
            season_records.append({
                "season": s,
                "n_samples": met["n_samples"],
                "MAE": met["MAE"],
                "RMSE": met["RMSE"],
                "R2": met["R2"],
                "contains_partial_season": bool(has_partial),
                "notes": "2026 monsoon contains partial acquisitions" if has_partial else "Complete seasonal series",
            })
    df_seasons = pd.DataFrame(season_records)
    season_csv_path = args.reports_dir / "xgb_season_errors.csv"
    df_seasons.to_csv(season_csv_path, index=False)
    print(f"\nSeasonal Performance:")
    for _, r in df_seasons.iterrows():
        print(f"  {r['season']:14s} | n={r['n_samples']:,} | MAE: {r['MAE']:.3f} degC | RMSE: {r['RMSE']:.3f} degC | R2: {r['R2']:.3f}")
    print(f"Saved seasonal errors to: {season_csv_path}")

    # 7. Hotspot-Specific Analysis
    hotspot_records = []
    # Non-hotspot (freq == 0)
    mask_non = df_residuals["hotspot_frequency"] == 0
    met_non = compute_regression_metrics(df_residuals.loc[mask_non, "LST_C"], df_residuals.loc[mask_non, "prediction"])
    hotspot_records.append({
        "hotspot_category": "non_hotspot",
        "definition": "hotspot_frequency == 0",
        "n_samples": met_non["n_samples"],
        "MAE": met_non["MAE"],
        "RMSE": met_non["RMSE"],
        "R2": met_non["R2"],
    })

    # Active hotspot (freq > 0)
    mask_active = df_residuals["hotspot_frequency"] > 0
    met_active = compute_regression_metrics(df_residuals.loc[mask_active, "LST_C"], df_residuals.loc[mask_active, "prediction"])
    hotspot_records.append({
        "hotspot_category": "active_hotspot",
        "definition": "hotspot_frequency > 0",
        "n_samples": met_active["n_samples"],
        "MAE": met_active["MAE"],
        "RMSE": met_active["RMSE"],
        "R2": met_active["R2"],
    })

    # Chronic hotspot (freq >= 6 or is_persistent_hotspot)
    mask_chronic = (df_residuals["hotspot_frequency"] >= 6) | (df_residuals["is_persistent_hotspot"] == True)
    met_chronic = compute_regression_metrics(df_residuals.loc[mask_chronic, "LST_C"], df_residuals.loc[mask_chronic, "prediction"])
    hotspot_records.append({
        "hotspot_category": "chronic_hotspot",
        "definition": "hotspot_frequency >= 6 or is_persistent_hotspot",
        "n_samples": met_chronic["n_samples"],
        "MAE": met_chronic["MAE"],
        "RMSE": met_chronic["RMSE"],
        "R2": met_chronic["R2"],
    })

    df_hotspots = pd.DataFrame(hotspot_records)
    hotspot_csv_path = args.reports_dir / "xgb_hotspot_errors.csv"
    df_hotspots.to_csv(hotspot_csv_path, index=False)
    print(f"\nHotspot Stratified Performance:")
    for _, r in df_hotspots.iterrows():
        print(f"  {r['hotspot_category']:16s} | n={r['n_samples']:,} | MAE: {r['MAE']:.3f} degC | RMSE: {r['RMSE']:.3f} degC | R2: {r['R2']:.3f}")
    print(f"Saved hotspot errors to: {hotspot_csv_path}")

    # 8. Spatial Residual Diagnostic GeoJSON
    sample_res = pd.concat([
        df_residuals.nlargest(500, "absolute_error"),
        df_residuals.sample(n=min(1000, len(df_residuals)), random_state=args.random_state),
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
        "name": "tuned_xgb_spatial_residuals_diagnostic",
        "features": features_geojson,
    }
    geojson_out_path = args.reports_dir / "xgb_spatial_residuals.geojson"
    with open(geojson_out_path, "w") as f:
        json.dump(geojson_payload, f)
    print(f"Saved spatial residuals GeoJSON ({len(features_geojson)} points) to: {geojson_out_path}")

    # 9. SHAP Refresh
    print("\n" + "=" * 80)
    print("SHAP ATTRIBUTION REFRESH (TUNED MODEL)")
    print("=" * 80)
    df_stability = compare_shap_stability(shap_fold_results, FEATURE_COLUMNS)
    df_stability.to_csv(args.output / "tuned_shap_stability.csv", index=False)
    print("Tuned Model Feature Attribution across Spatial Folds (mean |SHAP|):")
    for _, row in df_stability.iterrows():
        print(f"  {row['feature']:18s}: {row['mean_shap']:.4f} +/- {row['std_shap']:.4f} (CoV: {row['cov_percent']}%)")

    all_shap_mat = np.vstack([res["shap_values"] for res in shap_fold_results])
    global_mean_abs = np.mean(np.abs(all_shap_mat), axis=0)
    shap_summary_records = [
        {"feature": feat, "mean_abs_shap": round(float(val), 4)}
        for feat, val in zip(FEATURE_COLUMNS, global_mean_abs)
    ]
    df_shap_sum = pd.DataFrame(shap_summary_records).sort_values("mean_abs_shap", ascending=False)
    df_shap_sum.to_csv(args.output / "tuned_shap_summary.csv", index=False)
    print(f"Saved tuned SHAP summary to: {args.output / 'tuned_shap_summary.csv'}")


if __name__ == "__main__":
    main()
