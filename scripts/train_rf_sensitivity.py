"""Random Forest Policy Sensitivity, FLAG Sensitivity, and Temporal Validation.

Executes:
1. Phase 7: RF 5-Fold Spatial CV across Policies A, B, C, D.
2. Phase 8: FLAG Sample Weighting Sensitivity on Policy D (weights: 1.0, 0.75, 0.50, 0.25).
3. Phase 9: Temporal Validation (2022-2024 -> 2025, 2022-2025 -> 2026 partial monsoon).

Outputs saved to: data/diagnostics/ml/
"""

from __future__ import annotations

import argparse
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
from gis.ml.rf_model import (
    train_rf_regressor,
    compute_regression_metrics,
    DEFAULT_FEATURES,
    TARGET_COL,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "diagnostics" / "ml"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HEATSENSE AI: Random Forest Sensitivity & Temporal Validation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        help="Number of trees in Random Forest regressor (default: 100 for rapid baseline, 300 for full baseline).",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Number of samples to draw to train each base estimator (optional sub-sampling).",
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
        help="Directory to save diagnostic CSVs.",
    )
    parser.add_argument(
        "--skip-temporal",
        action="store_true",
        help="Skip temporal validation.",
    )
    parser.add_argument(
        "--skip-flag-weights",
        action="store_true",
        help="Skip FLAG weighting sensitivity.",
    )
    return parser


def run_rf_policy_sensitivity(
    policies: list[str],
    n_estimators: int,
    n_splits: int,
    output_dir: Path,
    max_samples: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Phase 7: Spatial CV across Policies A, B, C, D."""
    print("\n" + "=" * 80)
    print("PHASE 7: RANDOM FOREST SPATIAL CV POLICY SENSITIVITY")
    print("=" * 80)

    fold_records = []
    summary_records = []

    for pol_letter in policies:
        pol_key = f"policy_{pol_letter.lower()}"
        pq_path = DEFAULT_SENSITIVITY_ROOT / pol_key / "analysis.parquet"
        print(f"\nEvaluating {pol_key.upper()} from {pq_path}...")
        df = pd.read_parquet(pq_path)

        # Folds
        folds = spatial_block_folds(df, n_splits=n_splits, random_state=42)
        validate_fold_separation(df, folds)

        X = df[DEFAULT_FEATURES].to_numpy()
        y = df[TARGET_COL].to_numpy()

        pol_maes = []
        pol_rmses = []
        pol_r2s = []

        rf_params = {"n_estimators": n_estimators, "min_samples_leaf": 3, "random_state": 42, "n_jobs": -1}
        if max_samples:
            rf_params["max_samples"] = max_samples

        for fold_idx, (train_idx, val_idx) in enumerate(folds):
            t0 = time.time()
            model = train_rf_regressor(
                X[train_idx],
                y[train_idx],
                params=rf_params,
            )
            y_pred = model.predict(X[val_idx])
            metrics = compute_regression_metrics(y[val_idx], y_pred)
            elapsed = time.time() - t0

            fold_records.append({
                "policy": pol_key,
                "fold": fold_idx + 1,
                "MAE": metrics["MAE"],
                "RMSE": metrics["RMSE"],
                "R2": metrics["R2"],
                "n_samples": metrics["n_samples"],
                "fit_time_s": round(elapsed, 2),
            })
            pol_maes.append(metrics["MAE"])
            pol_rmses.append(metrics["RMSE"])
            pol_r2s.append(metrics["R2"])
            print(
                f"  Fold {fold_idx + 1}/{n_splits}: MAE={metrics['MAE']:.3f} degC, "
                f"RMSE={metrics['RMSE']:.3f} degC, R2={metrics['R2']:.3f} ({elapsed:.1f}s)"
            )

        summary_records.append({
            "policy": pol_key,
            "mean_mae": round(float(np.mean(pol_maes)), 4),
            "std_mae": round(float(np.std(pol_maes)), 4),
            "mean_rmse": round(float(np.mean(pol_rmses)), 4),
            "std_rmse": round(float(np.std(pol_rmses)), 4),
            "mean_r2": round(float(np.mean(pol_r2s)), 4),
            "std_r2": round(float(np.std(pol_r2s)), 4),
            "n_samples": len(df),
        })

    df_folds = pd.DataFrame(fold_records)
    df_summary = pd.DataFrame(summary_records)

    output_dir.mkdir(parents=True, exist_ok=True)
    df_folds.to_csv(output_dir / "rf_policy_sensitivity.csv", index=False)
    df_summary.to_csv(output_dir / "rf_policy_sensitivity_summary.csv", index=False)
    print(f"\nSaved fold metrics to: {output_dir / 'rf_policy_sensitivity.csv'}")
    print(f"Saved summary metrics to: {output_dir / 'rf_policy_sensitivity_summary.csv'}")

    return df_folds, df_summary


def run_flag_weight_sensitivity(
    n_estimators: int,
    n_splits: int,
    output_dir: Path,
    max_samples: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Phase 8: Sample weighting sensitivity on Policy D."""
    print("\n" + "=" * 80)
    print("PHASE 8: FLAG OBSERVATION WEIGHTING SENSITIVITY (POLICY D)")
    print("=" * 80)

    pq_path = DEFAULT_SENSITIVITY_ROOT / "policy_d" / "analysis.parquet"
    df = pd.read_parquet(pq_path)
    folds = spatial_block_folds(df, n_splits=n_splits, random_state=42)

    X = df[DEFAULT_FEATURES].to_numpy()
    y = df[TARGET_COL].to_numpy()
    eligibility = df["eligibility"].to_numpy()

    weights_to_test = [1.0, 0.75, 0.50, 0.25]
    fold_records = []
    summary_records = []

    rf_params = {"n_estimators": n_estimators, "min_samples_leaf": 3, "random_state": 42, "n_jobs": -1}
    if max_samples:
        rf_params["max_samples"] = max_samples

    for w in weights_to_test:
        print(f"\nTesting FLAG weight = {w:.2f} (ACCEPT=1.0, FLAG={w:.2f})...")
        sample_weights = np.ones(len(df), dtype=np.float32)
        sample_weights[eligibility == "FLAG"] = w
        sample_weights[eligibility == "EXCLUDE"] = 0.0

        w_maes = []
        w_rmses = []
        w_r2s = []

        for fold_idx, (train_idx, val_idx) in enumerate(folds):
            t0 = time.time()
            model = train_rf_regressor(
                X[train_idx],
                y[train_idx],
                sample_weight=sample_weights[train_idx],
                params=rf_params,
            )
            # Evaluate on unweighted validation data
            y_pred = model.predict(X[val_idx])
            metrics = compute_regression_metrics(y[val_idx], y_pred)
            elapsed = time.time() - t0

            fold_records.append({
                "policy": "policy_d",
                "flag_weight": w,
                "fold": fold_idx + 1,
                "MAE": metrics["MAE"],
                "RMSE": metrics["RMSE"],
                "R2": metrics["R2"],
                "n_samples": metrics["n_samples"],
            })
            w_maes.append(metrics["MAE"])
            w_rmses.append(metrics["RMSE"])
            w_r2s.append(metrics["R2"])

        summary_records.append({
            "policy": "policy_d",
            "flag_weight": w,
            "mean_mae": round(float(np.mean(w_maes)), 4),
            "std_mae": round(float(np.std(w_maes)), 4),
            "mean_rmse": round(float(np.mean(w_rmses)), 4),
            "std_rmse": round(float(np.std(w_rmses)), 4),
            "mean_r2": round(float(np.mean(w_r2s)), 4),
            "std_r2": round(float(np.std(w_r2s)), 4),
        })
        print(
            f"  FLAG Weight {w:.2f}: Mean MAE={np.mean(w_maes):.3f} degC, "
            f"Mean RMSE={np.mean(w_rmses):.3f} degC, Mean R2={np.mean(w_r2s):.3f}"
        )

    df_folds = pd.DataFrame(fold_records)
    df_summary = pd.DataFrame(summary_records)

    df_folds.to_csv(output_dir / "flag_weight_sensitivity.csv", index=False)
    df_summary.to_csv(output_dir / "flag_weight_sensitivity_summary.csv", index=False)
    print(f"\nSaved FLAG sensitivity results to: {output_dir / 'flag_weight_sensitivity.csv'}")

    return df_folds, df_summary


def run_temporal_validation(
    n_estimators: int,
    output_dir: Path,
    max_samples: int | None = None,
) -> pd.DataFrame:
    """Phase 9: Temporal Cross-Validation across years and seasons."""
    print("\n" + "=" * 80)
    print("PHASE 9: TEMPORAL VALIDATION (POLICY D)")
    print("=" * 80)

    pq_path = DEFAULT_SENSITIVITY_ROOT / "policy_d" / "analysis.parquet"
    df = pd.read_parquet(pq_path)

    X_all = df[DEFAULT_FEATURES].to_numpy()
    y_all = df[TARGET_COL].to_numpy()
    years = df["year"].to_numpy()
    seasons = df["season"].to_numpy()

    # Splits to evaluate
    splits = [
        {"train_years": [2022, 2023, 2024], "val_years": [2025], "name": "2022-2024 -> 2025"},
        {"train_years": [2022, 2023, 2024, 2025], "val_years": [2026], "name": "2022-2025 -> 2026 (partial monsoon)"},
    ]

    records = []

    rf_params = {"n_estimators": n_estimators, "min_samples_leaf": 3, "random_state": 42, "n_jobs": -1}
    if max_samples:
        rf_params["max_samples"] = max_samples

    for sp in splits:
        train_mask = np.isin(years, sp["train_years"])
        val_mask = np.isin(years, sp["val_years"])

        print(f"\nEvaluating Temporal Split: {sp['name']}")
        print(f"  Train: {np.sum(train_mask):,} samples | Val: {np.sum(val_mask):,} samples")

        model = train_rf_regressor(
            X_all[train_mask],
            y_all[train_mask],
            params=rf_params,
        )
        y_val_pred = model.predict(X_all[val_mask])
        val_metrics = compute_regression_metrics(y_all[val_mask], y_val_pred)

        records.append({
            "split_name": sp["name"],
            "train_years": ",".join(map(str, sp["train_years"])),
            "val_years": ",".join(map(str, sp["val_years"])),
            "season": "ALL",
            "is_partial_temporal_coverage": ("2026" in str(sp["val_years"])),
            "n_train": int(np.sum(train_mask)),
            "n_val": int(np.sum(val_mask)),
            "MAE": val_metrics["MAE"],
            "RMSE": val_metrics["RMSE"],
            "R2": val_metrics["R2"],
        })
        print(
            f"  ALL SEASONS: MAE={val_metrics['MAE']:.3f} degC, "
            f"RMSE={val_metrics['RMSE']:.3f} degC, R2={val_metrics['R2']:.3f}"
        )

        # By season evaluation
        for s in ["winter", "summer", "monsoon", "post_monsoon"]:
            s_mask = val_mask & (seasons == s)
            if np.sum(s_mask) == 0:
                continue

            y_s_val = y_all[s_mask]
            y_s_pred = model.predict(X_all[s_mask])
            s_metrics = compute_regression_metrics(y_s_val, y_s_pred)

            is_partial = (s == "monsoon" and "2026" in str(sp["val_years"]))
            records.append({
                "split_name": sp["name"],
                "train_years": ",".join(map(str, sp["train_years"])),
                "val_years": ",".join(map(str, sp["val_years"])),
                "season": s,
                "is_partial_temporal_coverage": is_partial,
                "n_train": int(np.sum(train_mask)),
                "n_val": int(np.sum(s_mask)),
                "MAE": s_metrics["MAE"],
                "RMSE": s_metrics["RMSE"],
                "R2": s_metrics["R2"],
            })
            print(
                f"    Season '{s}': n={np.sum(s_mask):,} | "
                f"MAE={s_metrics['MAE']:.3f} degC, RMSE={s_metrics['RMSE']:.3f} degC, R2={s_metrics['R2']:.3f}"
                f"{' [PARTIAL MONSOON]' if is_partial else ''}"
            )

    df_temporal = pd.DataFrame(records)
    df_temporal.to_csv(output_dir / "rf_temporal_validation.csv", index=False)
    print(f"\nSaved temporal validation results to: {output_dir / 'rf_temporal_validation.csv'}")

    return df_temporal


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # 1. RF Policy Sensitivity
    run_rf_policy_sensitivity(
        policies=["A", "B", "C", "D"],
        n_estimators=args.n_estimators,
        n_splits=args.n_splits,
        output_dir=args.output_dir,
        max_samples=args.max_samples,
    )

    # 2. FLAG Weighting Sensitivity
    if not args.skip_flag_weights:
        run_flag_weight_sensitivity(
            n_estimators=args.n_estimators,
            n_splits=args.n_splits,
            output_dir=args.output_dir,
            max_samples=args.max_samples,
        )

    # 3. Temporal Validation
    if not args.skip_temporal:
        run_temporal_validation(
            n_estimators=args.n_estimators,
            output_dir=args.output_dir,
            max_samples=args.max_samples,
        )


if __name__ == "__main__":
    main()
