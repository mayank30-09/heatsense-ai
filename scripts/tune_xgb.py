"""CLI Script for XGBoost Spatial Hyperparameter Tuning with Optuna.

Usage:
    python scripts/tune_xgb.py --input data/processed/sensitivity/policy_d/analysis.parquet --trials 30 --sample-size 250000 --output artifacts/xgb_tuning
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from gis.ml.spatial_validation import (
    get_fold_metadata,
    spatial_block_folds,
    validate_fold_separation,
)
from gis.ml.xgb_tuning import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    build_tuning_metadata,
    run_optuna_study,
    sample_spatially_stratified,
    validate_dataset_schema,
)

DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "xgb_tuning"


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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HEATSENSE AI: XGBoost Spatial Hyperparameter Tuning with Optuna",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to input Parquet analysis dataset.",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=30,
        help="Number of Optuna optimization trials.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=250000,
        help="Spatially stratified search sample size (0 for full dataset).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory to store tuning artifacts.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Deterministic random seed for sampling, partitioning, and optimization.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    input_path = args.input
    if not input_path.exists():
        raise FileNotFoundError(f"Input analysis dataset not found at: {input_path}")

    print("=" * 80)
    print("HEATSENSE AI: XGBOOST SPATIAL HYPERPARAMETER TUNING (OPTUNA)")
    print("=" * 80)
    print(f"Input Dataset      : {input_path}")
    print(f"Total Trials       : {args.trials}")
    print(f"Search Sample Size : {args.sample_size if args.sample_size > 0 else 'FULL DATASET'}")
    print(f"Output Directory   : {args.output}")

    t0 = time.time()
    df_full = pd.read_parquet(input_path)
    total_rows = len(df_full)
    print(f"\nLoaded full dataset: {total_rows:,} rows across {df_full['block_id'].nunique()} spatial blocks.")

    # Validate schema
    validate_dataset_schema(df_full)
    print("  [SCHEMA VALIDATION PASSED]: Required features, target, and block_id are present and finite.")

    # Spatially stratified proportional sampling
    if 0 < args.sample_size < total_rows:
        df_search = sample_spatially_stratified(
            df_full,
            sample_size=args.sample_size,
            random_state=args.random_state,
        )
        print(
            f"  [STRATIFIED SAMPLING]: Subsampled {len(df_search):,} rows proportionally "
            f"across all {df_search['block_id'].nunique()} spatial blocks."
        )
    else:
        df_search = df_full
        print(f"  [FULL DATASET SEARCH]: Using all {len(df_search):,} rows.")

    # Generate and validate spatial folds
    folds = spatial_block_folds(df_search, n_splits=5, random_state=args.random_state)
    validate_fold_separation(df_search, folds)
    print("  [SPATIAL LEAKAGE CHECK PASSED]: train_blocks INTERSECT val_blocks = empty for all 5 folds.")

    # Persist spatial fold definition
    fold_meta = get_fold_metadata(df_search, folds)
    args.output.mkdir(parents=True, exist_ok=True)

    fold_def_path = args.output / "spatial_fold_definition.json"
    with open(fold_def_path, "w") as f:
        json.dump(
            {
                "n_splits": 5,
                "random_state": args.random_state,
                "block_col": "block_id",
                "unique_blocks_count": df_search["block_id"].nunique(),
                "folds": fold_meta,
            },
            f,
            indent=2,
        )
    print(f"  Saved spatial fold definition to: {fold_def_path}")

    # Orchestrate Optuna study
    print(f"\nLaunching {args.trials} Optuna TPE optimization trials...")
    t_study_start = time.time()
    study, trial_records = run_optuna_study(
        df_search,
        folds,
        n_trials=args.trials,
        random_state=args.random_state,
    )
    study_duration = time.time() - t_study_start

    best_trial = study.best_trial
    best_rmse = float(best_trial.value)
    best_params = best_trial.params

    print("\n" + "=" * 80)
    print(f"OPTUNA STUDY COMPLETE in {study_duration:.1f}s ({args.trials} trials)")
    print("=" * 80)
    print(f"Best Trial Number : #{best_trial.number}")
    print(f"Best Search RMSE  : {best_rmse:.4f} degC")
    print("Best Hyperparameters:")
    for k, v in best_params.items():
        if isinstance(v, float):
            print(f"  {k:20s}: {v:.6f}")
        else:
            print(f"  {k:20s}: {v}")

    # Save xgb_best_params.json
    best_params_payload = {
        "best_trial_number": int(best_trial.number),
        "best_value_rmse": round(best_rmse, 4),
        "best_params": best_params,
        "fixed_params": {
            "objective": "reg:squarederror",
            "tree_method": "hist",
            "random_state": 42,
            "n_jobs": -1,
        },
        "n_trials": args.trials,
        "search_sample_size": len(df_search),
        "total_dataset_rows": total_rows,
    }
    with open(args.output / "xgb_best_params.json", "w") as f:
        json.dump(best_params_payload, f, indent=2)
    print(f"\nSaved best params to: {args.output / 'xgb_best_params.json'}")

    # Save xgb_tuning_trials.csv
    df_trials = pd.DataFrame(trial_records)
    trials_csv_path = args.output / "xgb_tuning_trials.csv"
    df_trials.to_csv(trials_csv_path, index=False)
    print(f"Saved trials log to: {trials_csv_path}")

    # Save xgb_tuning_metadata.json
    git_hash = get_git_commit_hash()
    metadata = build_tuning_metadata(
        dataset_path=input_path,
        total_dataset_rows=total_rows,
        search_sample_size=len(df_search),
        best_value_rmse=best_rmse,
        best_params=best_params,
        n_trials=args.trials,
        n_folds=5,
        random_state=args.random_state,
        git_hash=git_hash,
    )
    with open(args.output / "xgb_tuning_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved tuning metadata to: {args.output / 'xgb_tuning_metadata.json'}")


if __name__ == "__main__":
    main()
