"""Spatial Cross-Validation Diagnostic Script for HEATSENSE AI.

Verifies deterministic spatial block partitioning, fold separation (zero leakage),
and sample distributions across policies.

Usage:
    python scripts/spatial_cv.py --policy D
    python scripts/spatial_cv.py --policy all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from gis.ml.dataset import DEFAULT_SENSITIVITY_ROOT
from gis.ml.spatial_validation import (
    spatial_block_folds,
    validate_fold_separation,
    get_fold_metadata,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HEATSENSE AI: Spatial Cross-Validation Partitioning and Leakage Verification",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--policy",
        type=str,
        default="D",
        choices=["A", "B", "C", "D", "a", "b", "c", "d", "all", "ALL"],
        help="Target policy dataset to evaluate.",
    )
    parser.add_argument(
        "--n-splits",
        type=int,
        default=5,
        help="Number of spatial folds.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Deterministic random seed.",
    )
    return parser


def evaluate_policy_spatial_cv(
    policy_letter: str,
    n_splits: int = 5,
    random_state: int = 42,
) -> dict:
    pol_key = f"policy_{policy_letter.lower()}"
    pq_path = DEFAULT_SENSITIVITY_ROOT / pol_key / "analysis.parquet"
    if not pq_path.exists():
        raise FileNotFoundError(f"Analysis dataset not found at {pq_path}. Run build_analysis_dataset.py first.")

    print(f"\n--- Evaluating Spatial CV for {pol_key.upper()} ---")
    df = pd.read_parquet(pq_path)
    print(f"Total rows: {len(df):,} | Unique blocks: {df['block_id'].nunique()}")

    folds = spatial_block_folds(df, n_splits=n_splits, random_state=random_state)
    validate_fold_separation(df, folds)
    print("  [LEAKAGE CHECK PASSED]: train_blocks INTERSECT val_blocks = empty for all folds.")

    meta = get_fold_metadata(df, folds)
    for m in meta:
        pct = (m["val_samples"] / len(df)) * 100.0
        print(
            f"  Fold {m['fold']}: Val Samples = {m['val_samples']:,} ({pct:.1f}%) | "
            f"Val Blocks = {m['val_blocks']} | Train Blocks = {m['train_blocks']}"
        )

    return {
        "policy": pol_key,
        "total_samples": len(df),
        "total_blocks": df["block_id"].nunique(),
        "n_splits": n_splits,
        "leakage_passed": True,
        "folds": meta,
    }


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    pol_arg = args.policy.upper()
    policies = ["A", "B", "C", "D"] if pol_arg == "ALL" else [pol_arg]

    results = []
    for p in policies:
        res = evaluate_policy_spatial_cv(p, n_splits=args.n_splits, random_state=args.random_state)
        results.append(res)

    # Cross-policy fold block consistency verification
    if len(policies) > 1:
        print("\n" + "=" * 60)
        print("CROSS-POLICY SPATIAL BLOCK FOLD EQUIVALENCE VERIFICATION")
        print("=" * 60)
        # Load block IDs per fold for each policy
        pol_fold_blocks: dict[str, list[set[str]]] = {}
        for p in policies:
            pol_key = f"policy_{p.lower()}"
            df = pd.read_parquet(DEFAULT_SENSITIVITY_ROOT / pol_key / "analysis.parquet")
            folds = spatial_block_folds(df, n_splits=args.n_splits, random_state=args.random_state)
            pol_fold_blocks[pol_key] = [
                set(df.iloc[val_idx]["block_id"].unique()) for _, val_idx in folds
            ]

        ref_key = f"policy_{policies[0].lower()}"
        all_match = True
        for other_key in pol_fold_blocks:
            if other_key == ref_key:
                continue
            for f_idx in range(args.n_splits):
                if pol_fold_blocks[ref_key][f_idx] != pol_fold_blocks[other_key][f_idx]:
                    all_match = False
                    print(f"  MISMATCH between {ref_key} and {other_key} in fold {f_idx + 1}!")
        if all_match:
            print("  [SUCCESS] All policies have IDENTICAL spatial block partitions in every fold.")


if __name__ == "__main__":
    main()
