"""CLI Script for XGBoost Spatial Hyperparameter Tuning with Optuna.

Strictly operates on the LOCKED DEVELOPMENT PARTITION (132 blocks).
Test blocks (33 blocks) are strictly excluded from dataset loading,
stratified sampling, spatial CV fold generation, and trial optimization.

Usage:
    python scripts/tune_xgb.py \
        --input data/processed/sensitivity/policy_d/analysis.parquet \
        --holdout-split artifacts/ml_freeze/holdout_split.json \
        --trials 30 \
        --sample-size 250000 \
        --output artifacts/ml_freeze/tuning
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
from gis.ml.development_cv import (
    development_spatial_folds,
    get_development_fold_metadata,
)
from gis.ml.holdout_split import (
    load_holdout_split,
    partition_dataset_by_holdout,
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
DEFAULT_HOLDOUT = PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "ml_freeze" / "tuning"


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
        description="HEATSENSE AI: XGBoost Spatial Hyperparameter Tuning with Optuna (Development Partition Only)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to input Parquet analysis dataset.",
    )
    parser.add_argument(
        "--holdout-split",
        type=Path,
        default=DEFAULT_HOLDOUT,
        help="Path to locked holdout_split.json (contains development and test block IDs).",
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
        help="Spatially stratified search sample size (0 for full dev dataset).",
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

    holdout_path = args.holdout_split
    if not holdout_path.exists():
        raise FileNotFoundError(f"Locked holdout split not found at: {holdout_path}")

    print("=" * 80)
    print("HEATSENSE AI: XGBOOST SPATIAL HYPERPARAMETER TUNING (OPTUNA)")
    print("DEVELOPMENT PARTITION ONLY — STRICT TEST BLOCK ISOLATION")
    print("=" * 80)
    print(f"Input Dataset      : {input_path}")
    print(f"Holdout Split      : {holdout_path}")
    print(f"Total Trials       : {args.trials}")
    print(f"Search Sample Size : {args.sample_size if args.sample_size > 0 else 'FULL DEV DATASET'}")
    print(f"Output Directory   : {args.output}")
    print(f"Random State       : {args.random_state}")

    t0 = time.time()
    df_full = pd.read_parquet(input_path)
    total_rows = len(df_full)
    print(f"\nLoaded full dataset: {total_rows:,} rows across {df_full['block_id'].nunique()} spatial blocks.")

    # Validate schema
    validate_dataset_schema(df_full)
    print("  [SCHEMA VALIDATION PASSED]: Required features, target, and block_id are present and finite.")

    # Load locked holdout split
    holdout_data = load_holdout_split(holdout_path)
    dev_blocks = holdout_data["development_blocks"]
    test_blocks = holdout_data["test_blocks"]

    # Partition dataset and enforce zero leakage assertions
    df_dev, df_test = partition_dataset_by_holdout(
        df_full, dev_blocks=dev_blocks, test_blocks=test_blocks, block_col="block_id"
    )

    dev_block_set = set(dev_blocks)
    test_block_set = set(test_blocks)

    assert set(df_dev["block_id"].astype(str)) == dev_block_set, "df_dev block mismatch!"
    assert set(df_test["block_id"].astype(str)) == test_block_set, "df_test block mismatch!"
    assert dev_block_set.isdisjoint(test_block_set), "Fatal error: dev and test blocks overlap!"

    print(f"\n[STRICT LEAKAGE ISOLATION ENFORCED]:")
    print(f"  Development blocks : {len(dev_blocks)} ({len(df_dev):,} rows) -> ACCESSIBLE FOR TUNING")
    print(f"  Test blocks        : {len(test_blocks)} ({len(df_test):,} rows) -> LOCKED & COMPLETELY EXCLUDED")

    # Drop test dataframe from memory to structurally prevent access
    del df_test
    del df_full

    # Spatially stratified proportional sampling WITHIN DEVELOPMENT BLOCKS ONLY
    if 0 < args.sample_size < len(df_dev):
        df_search = sample_spatially_stratified(
            df_dev,
            sample_size=args.sample_size,
            random_state=args.random_state,
        )
        print(
            f"  [STRATIFIED SAMPLING]: Subsampled {len(df_search):,} rows proportionally "
            f"across all {df_search['block_id'].nunique()} development spatial blocks."
        )
    else:
        df_search = df_dev
        print(f"  [FULL DEV DATASET SEARCH]: Using all {len(df_search):,} development rows.")

    # Generate and validate development-only spatial folds
    folds = development_spatial_folds(
        df_search,
        development_blocks=dev_blocks,
        n_splits=5,
        random_state=args.random_state,
        prohibited_test_blocks=test_blocks,
    )
    print("  [SPATIAL LEAKAGE CHECK PASSED]: train_blocks INTERSECT val_blocks = empty for all 5 folds.")
    print("  [TEST PROHIBITION PASSED]: Zero test blocks appear in any fold.")

    # Persist spatial fold definition
    fold_meta = get_development_fold_metadata(df_search, folds)
    args.output.mkdir(parents=True, exist_ok=True)

    fold_def_path = args.output / "spatial_fold_definition.json"
    with open(fold_def_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "n_splits": 5,
                "random_state": args.random_state,
                "block_col": "block_id",
                "development_blocks_count": len(dev_blocks),
                "test_blocks_isolated_count": len(test_blocks),
                "unique_blocks_in_search": df_search["block_id"].nunique(),
                "folds": fold_meta,
            },
            f,
            indent=2,
        )
    print(f"  Saved development spatial fold definition to: {fold_def_path}")

    # Orchestrate Optuna study strictly on development partition
    print(f"\nLaunching {args.trials} Optuna TPE optimization trials on development blocks...")
    t_study_start = time.time()
    study, trial_records = run_optuna_study(
        df_search,
        folds,
        n_trials=args.trials,
        random_state=args.random_state,
    )
    study_duration = time.time() - t_study_start
    print(f"OPTUNA STUDY COMPLETE in {study_duration:.1f}s ({args.trials} trials)")
    print(f"  Best Trial Number : #{study.best_trial.number}")
    print(f"  Best Dev-CV RMSE  : {study.best_value:.4f} degC")
    print(f"  Best Parameters   : {study.best_params}")

    # Persist best parameters
    best_params_path = args.output / "xgb_best_params.json"
    with open(best_params_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "best_trial_number": study.best_trial.number,
                "best_cv_rmse": round(float(study.best_value), 4),
                "best_params": study.best_params,
                "fixed_params": {
                    "objective": "reg:squarederror",
                    "tree_method": "hist",
                    "random_state": args.random_state,
                    "n_jobs": -1,
                },
                "search_sample_size": len(df_search),
                "development_blocks": len(dev_blocks),
                "test_blocks_excluded": len(test_blocks),
            },
            f,
            indent=2,
        )
    print(f"  Saved best parameters to: {best_params_path}")

    # Persist all trial records
    trials_csv_path = args.output / "xgb_tuning_trials.csv"
    pd.DataFrame(trial_records).to_csv(trials_csv_path, index=False)
    print(f"  Saved trial records to: {trials_csv_path}")

    # Build and persist metadata
    git_hash = get_git_commit_hash()
    meta = build_tuning_metadata(
        dataset_path=input_path,
        total_dataset_rows=total_rows,
        search_sample_size=len(df_search),
        best_value_rmse=study.best_value,
        best_params=study.best_params,
        n_trials=args.trials,
        n_folds=5,
        random_state=args.random_state,
        git_hash=git_hash,
    )
    meta["holdout_split_path"] = str(holdout_path)
    meta["development_rows"] = len(df_dev)
    meta["development_blocks"] = len(dev_blocks)
    meta["test_blocks_excluded"] = len(test_blocks)

    meta_path = args.output / "xgb_tuning_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"  Saved tuning metadata to: {meta_path}")

    total_time = time.time() - t0
    print("\n" + "=" * 80)
    print(f"DEVELOPMENT TUNING PIPELINE COMPLETED SUCCESSFULLY IN {total_time:.1f}s")
    print(f"Zero test blocks were used in this optimization.")
    print("=" * 80)


if __name__ == "__main__":
    main()
