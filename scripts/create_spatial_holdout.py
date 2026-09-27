"""CLI script to establish the locked spatial holdout split for HEATSENSE AI.

Strictly partitions unique spatial blocks (165 blocks) into:
- 132 Development Blocks (~80%)
- 33 Untouched Test Blocks (~20%)

Saves the canonical holdout partition to `artifacts/ml_freeze/holdout_split.json`.
Never trains or evaluates any model.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gis.ml.holdout_split import (
    create_spatial_holdout_split,
    partition_dataset_by_holdout,
    save_holdout_split,
)

DEFAULT_DATASET = PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Establish locked spatial holdout split (132 dev / 33 test blocks)."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to Policy D analysis parquet file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to save holdout_split.json.",
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.20,
        help="Fraction of spatial blocks for test set (default: 0.20).",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="RNG seed for deterministic block shuffling (default: 42).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 80)
    print("HEATSENSE AI: LOCK SPATIAL HOLDOUT PARTITION")
    print("=" * 80)
    print(f"Dataset path : {args.dataset}")
    print(f"Output path  : {args.output}")
    print(f"Test ratio   : {args.test_ratio}")
    print(f"Random state : {args.random_state}")

    if not args.dataset.exists():
        raise FileNotFoundError(f"Policy D dataset not found: {args.dataset}")

    print("\nLoading Policy D analysis dataset...")
    df = pd.read_parquet(args.dataset)
    total_rows = len(df)
    unique_blocks = sorted(df["block_id"].astype(str).unique())
    n_blocks = len(unique_blocks)
    print(f"Loaded {total_rows:,} rows across {n_blocks} spatial blocks.")

    # Generate spatial split
    dev_blocks, test_blocks = create_spatial_holdout_split(
        unique_blocks,
        test_ratio=args.test_ratio,
        random_state=args.random_state,
    )

    # Validate disjointness and coverage
    dev_set = set(dev_blocks)
    test_set = set(test_blocks)
    assert dev_set.isdisjoint(test_set), "Fatal error: dev and test blocks overlap!"
    assert len(dev_blocks) + len(test_blocks) == n_blocks, "Fatal error: block count mismatch!"

    # Partition dataset to report exact row counts
    df_dev, df_test = partition_dataset_by_holdout(
        df,
        dev_blocks=dev_blocks,
        test_blocks=test_blocks,
        block_col="block_id",
    )

    print("\n[PARTITION VERIFICATION SUCCESSFUL]:")
    print(f"  Total spatial blocks      : {n_blocks}")
    print(f"  Development spatial blocks: {len(dev_blocks)} ({len(dev_blocks)/n_blocks*100:.1f}%)")
    print(f"  Test spatial blocks       : {len(test_blocks)} ({len(test_blocks)/n_blocks*100:.1f}%)")
    print(f"  Development rows          : {len(df_dev):,} ({len(df_dev)/total_rows*100:.2f}%)")
    print(f"  Test rows                 : {len(df_test):,} ({len(df_test)/total_rows*100:.2f}%)")

    extra_meta = {
        "dataset_rows": total_rows,
        "development_rows": len(df_dev),
        "test_rows": len(df_test),
        "dataset_path": str(args.dataset),
    }

    out_file = save_holdout_split(
        dev_blocks=dev_blocks,
        test_blocks=test_blocks,
        output_path=args.output,
        random_state=args.random_state,
        test_ratio=args.test_ratio,
        metadata_extra=extra_meta,
    )
    print(f"\nLocked spatial holdout split saved to: {out_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
