"""CLI Script to Build Policy-Sensitive Analysis Datasets for HEATSENSE AI.

Builds experimental sensitivity datasets under Policies A, B, C, and D,
integrating pixel quality diagnostics, hotspot persistence, authoritative
eligibility classification, and deterministic spatial block partitions.

Usage:
    python scripts/build_analysis_dataset.py --policy A
    python scripts/build_analysis_dataset.py --policy B
    python scripts/build_analysis_dataset.py --policy C
    python scripts/build_analysis_dataset.py --policy D
    python scripts/build_analysis_dataset.py --policy all
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

from gis.ml.dataset import (
    build_analysis_dataset,
    DEFAULT_SENSITIVITY_ROOT,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HEATSENSE AI: Policy-Sensitive Analysis Dataset Builder",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--policy",
        type=str,
        required=True,
        choices=["A", "B", "C", "D", "a", "b", "c", "d", "all", "ALL"],
        help="Target eligibility policy: A, B, C, D, or 'all'.",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=20,
        help="Grid cells per spatial block (default: 20, ~2km on 100m grid).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_SENSITIVITY_ROOT,
        help="Root output directory for sensitivity datasets.",
    )
    return parser


def run_build_for_policy(policy_letter: str, block_size: int, output_root: Path) -> None:
    pol_key = f"policy_{policy_letter.lower()}"
    out_dir = output_root / pol_key

    print("=" * 80)
    print(f"BUILDING ANALYSIS DATASET: {pol_key.upper()}")
    print("=" * 80)
    print(f"Output Directory : {out_dir}")
    print(f"Block Size       : {block_size} x {block_size} cells (~{block_size*100}m x {block_size*100}m)")

    t0 = time.time()
    df, summary = build_analysis_dataset(
        policy_name=pol_key,
        block_size=block_size,
        output_dir=out_dir,
    )
    elapsed = time.time() - t0

    print(f"\n[Completed in {elapsed:.2f}s]")
    print(f"  Total input pixels    : {summary['total_input_pixels']:,}")
    print(f"  Total retained pixels : {summary['total_retained_pixels']:,} ({summary['overall_retention_percent']}%)")
    print(f"  Total flagged pixels  : {summary['total_flagged_pixels']:,}")
    print(f"  Total excluded pixels : {summary['total_excluded_pixels']:,}")
    print(f"  Unique spatial blocks : {summary['unique_blocks_count']:,}")
    print(f"  Saved Parquet         : {out_dir / 'analysis.parquet'}")
    print(f"  Saved Summary JSON    : {out_dir / 'summary.json'}")


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    pol_arg = args.policy.upper()
    if pol_arg == "ALL":
        target_policies = ["A", "B", "C", "D"]
    else:
        target_policies = [pol_arg]

    for p in target_policies:
        run_build_for_policy(
            policy_letter=p,
            block_size=args.block_size,
            output_root=args.output_root,
        )


if __name__ == "__main__":
    main()
