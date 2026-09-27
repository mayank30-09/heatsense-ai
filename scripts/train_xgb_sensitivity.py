"""XGBoost Spatial Cross-Validation, SHAP Attribution, and Spatial Residual Analysis.

Executes:
1. Phase 10: 5-Fold Spatial CV using XGBoost on identical folds/features as RF.
2. Direct head-to-head comparison between RF and XGBoost.
3. Phase 11: TreeExplainer SHAP attribution & across-fold attribution stability.
4. Phase 12: Out-of-fold spatial residual analysis (LST_C - pred, absolute error)
   broken down overall, by season, and by hotspot status.

Outputs saved to: data/diagnostics/ml/
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
from gis.ml.dataset import DEFAULT_SENSITIVITY_ROOT
from gis.ml.spatial_validation import spatial_block_folds, validate_fold_separation
from gis.ml.rf_model import compute_regression_metrics, DEFAULT_FEATURES, TARGET_COL
from gis.ml.xgb_model import train_xgb_regressor
from gis.ml.explainability import compute_tree_shap_values, compare_shap_stability
from gis.quality.hotspot_definitions import (
    CHRONIC_HOTSPOT_FREQ_THRESHOLD,
    is_chronic_hotspot,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "diagnostics" / "ml"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HEATSENSE AI: XGBoost Spatial CV, SHAP Attribution, and Spatial Residuals",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--policy",
        type=str,
        default="D",
        choices=["A", "B", "C", "D", "a", "b", "c", "d"],
        help="Target policy dataset to evaluate (default: D).",
    )
    parser.add_argument(
        "--n-splits",
        type=int,
        default=5,
        help="Number of spatial folds.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to save diagnostic files.",
    )
    parser.add_argument(
        "--shap-sample-size",
        type=int,
        default=2000,
        help="Sample size per fold for TreeExplainer computation.",
    )
    return parser


def run_xgb_pipeline(
    policy_letter: str,
    n_splits: int,
    output_dir: Path,
    shap_sample_size: int,
) -> None:
    pol_key = f"policy_{policy_letter.lower()}"
    pq_path = DEFAULT_SENSITIVITY_ROOT / pol_key / "analysis.parquet"
    if not pq_path.exists():
        raise FileNotFoundError(f"Dataset not found at {pq_path}. Run build_analysis_dataset.py first.")

    print("\n" + "=" * 80)
    print(f"PHASE 10: XGBOOST SPATIAL CROSS-VALIDATION ({pol_key.upper()})")
    print("=" * 80)

    df = pd.read_parquet(pq_path)
    print(f"Loaded {len(df):,} observations from {pq_path}.")

    # Deterministic spatial folds
    folds = spatial_block_folds(df, n_splits=n_splits, random_state=42)
    validate_fold_separation(df, folds)

    X = df[DEFAULT_FEATURES].to_numpy()
    y = df[TARGET_COL].to_numpy()

    # Placeholders for out-of-fold predictions and residuals
    oof_predictions = np.zeros(len(df), dtype=np.float32)
    fold_assignment = np.zeros(len(df), dtype=np.int32)

    fold_records = []
    shap_fold_results = []

    for fold_idx, (train_idx, val_idx) in enumerate(folds):
        t0 = time.time()
        model = train_xgb_regressor(X[train_idx], y[train_idx])
        fit_time = time.time() - t0

        y_pred = model.predict(X[val_idx])
        oof_predictions[val_idx] = y_pred
        fold_assignment[val_idx] = fold_idx + 1

        metrics = compute_regression_metrics(y[val_idx], y_pred)
        print(
            f"  Fold {fold_idx + 1}/{n_splits}: MAE={metrics['MAE']:.3f} degC, "
            f"RMSE={metrics['RMSE']:.3f} degC, R2={metrics['R2']:.3f} ({fit_time:.1f}s)"
        )

        fold_records.append({
            "model": "XGBoost",
            "policy": pol_key,
            "fold": fold_idx + 1,
            "MAE": metrics["MAE"],
            "RMSE": metrics["RMSE"],
            "R2": metrics["R2"],
            "n_samples": metrics["n_samples"],
            "fit_time_s": round(fit_time, 2),
        })

        # SHAP calculation on a deterministic sample from validation set
        rng = np.random.RandomState(42 + fold_idx)
        sample_n = min(shap_sample_size, len(val_idx))
        sample_sub_idx = rng.choice(val_idx, size=sample_n, replace=False)
        shap_res = compute_tree_shap_values(model, X[sample_sub_idx], DEFAULT_FEATURES)
        shap_fold_results.append(shap_res)

    df_xgb_folds = pd.DataFrame(fold_records)
    output_dir.mkdir(parents=True, exist_ok=True)
    df_xgb_folds.to_csv(output_dir / "xgb_spatial_cv.csv", index=False)

    # -------------------------------------------------------------
    # RF vs XGBoost Comparison Table
    # -------------------------------------------------------------
    rf_folds_path = output_dir / "rf_policy_sensitivity.csv"
    if rf_folds_path.exists():
        df_rf_all = pd.read_csv(rf_folds_path)
        df_rf_pol = df_rf_all[df_rf_all["policy"] == pol_key].copy()
        df_rf_pol["model"] = "RandomForest"

        df_comparison = pd.concat([df_rf_pol, df_xgb_folds], ignore_index=True)
        comp_summary = df_comparison.groupby("model").agg(
            mean_MAE=("MAE", "mean"),
            std_MAE=("MAE", "std"),
            mean_RMSE=("RMSE", "mean"),
            std_RMSE=("RMSE", "std"),
            mean_R2=("R2", "mean"),
            std_R2=("R2", "std"),
        ).reset_index()
        comp_summary.to_csv(output_dir / "model_comparison_rf_xgb.csv", index=False)
        print("\n" + "=" * 60)
        print("HEAD-TO-HEAD COMPARISON (IDENTICAL 5-FOLD SPATIAL SPLITS):")
        print("=" * 60)
        for _, row in comp_summary.iterrows():
            print(
                f"  {row['model']:15s} | MAE: {row['mean_MAE']:.3f}+/-{row['std_MAE']:.3f} degC | "
                f"RMSE: {row['mean_RMSE']:.3f}+/-{row['std_RMSE']:.3f} degC | R2: {row['mean_R2']:.3f}+/-{row['std_R2']:.3f}"
            )

    # -------------------------------------------------------------
    # PHASE 11: SHAP Attribution & Stability
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 11: SHAP ATTRIBUTION ANALYSIS (NON-CAUSAL MODEL ATTRIBUTION)")
    print("=" * 80)

    df_stability = compare_shap_stability(shap_fold_results, DEFAULT_FEATURES)
    df_stability.to_csv(output_dir / "shap_stability.csv", index=False)
    print("Feature Attribution across Spatial Folds (mean |SHAP|):")
    for _, row in df_stability.iterrows():
        print(f"  {row['feature']:18s}: {row['mean_shap']:.4f} +/- {row['std_shap']:.4f} (CoV: {row['cov_percent']}%)")

    # Global summary
    all_shap_mat = np.vstack([res["shap_values"] for res in shap_fold_results])
    global_mean_abs = np.mean(np.abs(all_shap_mat), axis=0)
    shap_summary_records = [
        {"feature": feat, "mean_abs_shap": round(float(val), 4)}
        for feat, val in zip(DEFAULT_FEATURES, global_mean_abs)
    ]
    pd.DataFrame(shap_summary_records).sort_values("mean_abs_shap", ascending=False).to_csv(
        output_dir / "shap_summary.csv", index=False
    )

    # -------------------------------------------------------------
    # PHASE 12: Spatial Residuals
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 12: SPATIAL RESIDUAL ANALYSIS")
    print("=" * 80)

    residuals = y - oof_predictions
    abs_errors = np.abs(residuals)

    df_residuals = df[[
        "year", "season", "row", "col", "longitude", "latitude", "block_id",
        "LST_C", "hotspot_frequency", "eligibility", "quality_flag", "is_partial_season"
    ]].copy()
    df_residuals["prediction"] = np.round(oof_predictions, 3)
    df_residuals["residual"] = np.round(residuals, 3)
    df_residuals["absolute_error"] = np.round(abs_errors, 3)
    df_residuals["spatial_fold"] = fold_assignment
    df_residuals["policy"] = pol_key

    # Save out-of-fold spatial predictions
    res_pq_path = output_dir / "spatial_residuals.parquet"
    df_residuals.to_parquet(res_pq_path, index=False)
    print(f"Saved full spatial residuals ({len(df_residuals):,} rows) to: {res_pq_path}")

    # Residuals error breakdown
    # 1. Overall
    overall_metrics = compute_regression_metrics(df_residuals["LST_C"], df_residuals["prediction"])

    error_summary = []
    error_summary.append({
        "stratum": "Overall",
        "category": "ALL",
        "n_samples": overall_metrics["n_samples"],
        "MAE": overall_metrics["MAE"],
        "RMSE": overall_metrics["RMSE"],
        "R2": overall_metrics["R2"],
    })

    # 2. By Season
    for s in ["winter", "summer", "monsoon", "post_monsoon"]:
        s_df = df_residuals[df_residuals["season"] == s]
        if len(s_df) > 0:
            s_met = compute_regression_metrics(s_df["LST_C"], s_df["prediction"])
            error_summary.append({
                "stratum": "Season",
                "category": s,
                "n_samples": s_met["n_samples"],
                "MAE": s_met["MAE"],
                "RMSE": s_met["RMSE"],
                "R2": s_met["R2"],
            })

    # 3. By Hotspot Status
    is_hotspot = df_residuals["hotspot_frequency"] > 0
    hotspot_met = compute_regression_metrics(
        df_residuals.loc[is_hotspot, "LST_C"],
        df_residuals.loc[is_hotspot, "prediction"]
    )
    error_summary.append({
        "stratum": "Hotspot_Status",
        "category": "Hotspot (freq > 0)",
        "n_samples": hotspot_met["n_samples"],
        "MAE": hotspot_met["MAE"],
        "RMSE": hotspot_met["RMSE"],
        "R2": hotspot_met["R2"],
    })

    non_hotspot_met = compute_regression_metrics(
        df_residuals.loc[~is_hotspot, "LST_C"],
        df_residuals.loc[~is_hotspot, "prediction"]
    )
    error_summary.append({
        "stratum": "Hotspot_Status",
        "category": "Non-Hotspot (freq == 0)",
        "n_samples": non_hotspot_met["n_samples"],
        "MAE": non_hotspot_met["MAE"],
        "RMSE": non_hotspot_met["RMSE"],
        "R2": non_hotspot_met["R2"],
    })

    # 4. Chronic Hotspots (freq >= 0.50)
    is_chronic = is_chronic_hotspot(df_residuals["hotspot_frequency"], threshold=CHRONIC_HOTSPOT_FREQ_THRESHOLD).to_numpy()
    if is_chronic.sum() > 0:
        chronic_met = compute_regression_metrics(
            df_residuals.loc[is_chronic, "LST_C"],
            df_residuals.loc[is_chronic, "prediction"]
        )
        error_summary.append({
            "stratum": "Hotspot_Status",
            "category": "Chronic Hotspot (freq >= 0.50)",
            "n_samples": chronic_met["n_samples"],
            "MAE": chronic_met["MAE"],
            "RMSE": chronic_met["RMSE"],
            "R2": chronic_met["R2"],
        })

    df_err_summary = pd.DataFrame(error_summary)
    df_err_summary.to_csv(output_dir / "spatial_error_summary.csv", index=False)
    print(f"\nSaved spatial error summary to: {output_dir / 'spatial_error_summary.csv'}")

    print("\nSPATIAL ERROR STRATIFICATION:")
    for _, row in df_err_summary.iterrows():
        print(f"  [{row['stratum']:15s}] {row['category']:26s} | n={row['n_samples']:,} | MAE: {row['MAE']:.3f} degC | RMSE: {row['RMSE']:.3f} degC | R2: {row['R2']:.3f}")

    # Generate small GeoJSON sample for spatial visualization (e.g. 500 largest error points and 500 random points)
    sample_res = pd.concat([
        df_residuals.nlargest(500, "absolute_error"),
        df_residuals.sample(n=min(1000, len(df_residuals)), random_state=42),
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
                "hotspot_frequency": int(r["hotspot_frequency"]),
            },
        }
        features_geojson.append(feat)

    geojson_obj = {
        "type": "FeatureCollection",
        "name": "spatial_residuals_diagnostic",
        "features": features_geojson,
    }
    with open(output_dir / "spatial_residuals_sample.geojson", "w") as f:
        json.dump(geojson_obj, f)
    print(f"Saved GeoJSON sample ({len(features_geojson)} points) to: {output_dir / 'spatial_residuals_sample.geojson'}")


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    run_xgb_pipeline(
        policy_letter=args.policy,
        n_splits=args.n_splits,
        output_dir=args.output_dir,
        shap_sample_size=args.shap_sample_size,
    )


if __name__ == "__main__":
    main()
