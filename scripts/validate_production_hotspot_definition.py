"""Validation Script for Production Analytical COG Persistence Bands.

Verifies that Band 10 (IS_PERSISTENT_HOTSPOT) in all 19 production analytical COGs
under data/processed/analytical/ strictly equals the canonical hotspot recurrence policy:
    is_persistent = (hotspot_frequency >= 0.25) OR authoritative existing persistent-hotspot flag

Outputs per-raster metrics:
- total valid pixels
- matching pixels
- differing pixels
- percentage difference
- PASS/FAIL status
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import rasterio

from gis.quality.hotspot_definitions import (
    PERSISTENT_FREQUENCY_THRESHOLD,
    persistent_hotspot_mask,
)

DEFAULT_ANALYTICAL_DIR = PROJECT_ROOT / "data" / "processed" / "analytical"
DEFAULT_PERSISTENCE_SUMMARY = (
    PROJECT_ROOT / "data" / "diagnostics" / "quality" / "hotspot_persistence_summary.csv"
)


def load_authoritative_persistent_locations(summary_path: Path) -> set[tuple[int, int]]:
    """Load authoritative persistent hotspot locations from persistence summary CSV."""
    if not summary_path.exists():
        print(f"  [INFO] Persistence summary not found at {summary_path}; evaluating frequency only.")
        return set()

    df = pd.read_csv(summary_path)
    pers_mask = df.get("is_persistent_hotspot", pd.Series([False] * len(df))) == True
    pers_rows = df.loc[pers_mask, ["row", "col"]].drop_duplicates()
    return set(zip(pers_rows["row"].astype(int), pers_rows["col"].astype(int)))


def validate_cog_persistence(
    cog_path: Path,
    authoritative_pers_locs: set[tuple[int, int]],
) -> dict[str, Any]:
    """Validate persistence band (Band 10) against Band 9 and authoritative flag."""
    with rasterio.open(cog_path) as src:
        band9_freq = src.read(9)
        band10_pers = src.read(10)
        nodata = src.nodata

    valid_mask = (band9_freq != nodata) & (band10_pers != nodata) & np.isfinite(band9_freq)
    total_valid = int(np.sum(valid_mask))

    if total_valid == 0:
        return {
            "cog_name": cog_path.name,
            "total_pixels": 0,
            "matching_pixels": 0,
            "differing_pixels": 0,
            "diff_percentage": 0.0,
            "status": "PASS",
        }

    rows, cols = np.where(valid_mask)
    freq_vals = band9_freq[valid_mask]
    actual_pers = band10_pers[valid_mask] == 1.0

    # Build authoritative flag array for valid pixels
    if authoritative_pers_locs:
        existing_flags = np.array(
            [(r, c) in authoritative_pers_locs for r, c in zip(rows, cols)],
            dtype=bool,
        )
    else:
        existing_flags = None

    # Canonical evaluation
    expected_pers = persistent_hotspot_mask(freq_vals, existing_flags)
    expected_bool = np.asarray(expected_pers, dtype=bool)

    diff_mask = actual_pers != expected_bool
    differing_pixels = int(np.sum(diff_mask))
    matching_pixels = total_valid - differing_pixels
    diff_pct = (differing_pixels / total_valid) * 100.0 if total_valid > 0 else 0.0
    status = "PASS" if differing_pixels == 0 else "FAIL"

    return {
        "cog_name": cog_path.name,
        "total_pixels": total_valid,
        "matching_pixels": matching_pixels,
        "differing_pixels": differing_pixels,
        "diff_percentage": diff_pct,
        "status": status,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify persistence bands in production analytical COGs against canonical policy."
    )
    parser.add_argument("--dir", type=Path, default=DEFAULT_ANALYTICAL_DIR)
    parser.add_argument("--summary", type=Path, default=DEFAULT_PERSISTENCE_SUMMARY)
    args = parser.parse_args()

    print("=" * 80)
    print("HEATSENSE AI: PRODUCTION COG HOTSPOT PERSISTENCE VERIFICATION")
    print(f"Canonical Threshold : frequency >= {PERSISTENT_FREQUENCY_THRESHOLD} OR existing_flag")
    print("=" * 80)

    cog_files = sorted(args.dir.glob("surat_*_analytical_cog.tif"))
    if not cog_files:
        print(f"Error: No production COGs found in {args.dir}")
        sys.exit(1)

    pers_locs = load_authoritative_persistent_locations(args.summary)
    print(f"Loaded {len(pers_locs):,} authoritative persistent locations from summary.\n")

    results = []
    all_pass = True

    print(
        f"{'COG Name':<45} | {'Valid Px':>9} | {'Match Px':>9} | {'Diff Px':>8} | {'Diff %':>7} | {'Status':>6}"
    )
    print("-" * 96)

    total_valid_all = 0
    total_match_all = 0
    total_diff_all = 0

    for cog_file in cog_files:
        res = validate_cog_persistence(cog_file, pers_locs)
        results.append(res)
        total_valid_all += res["total_pixels"]
        total_match_all += res["matching_pixels"]
        total_diff_all += res["differing_pixels"]

        if res["status"] != "PASS":
            all_pass = False

        print(
            f"{res['cog_name']:<45} | {res['total_pixels']:>9,d} | {res['matching_pixels']:>9,d} | "
            f"{res['differing_pixels']:>8,d} | {res['diff_percentage']:>6.2f}% | {res['status']:>6}"
        )

    print("-" * 96)
    diff_all_pct = (total_diff_all / total_valid_all * 100.0) if total_valid_all > 0 else 0.0
    print(
        f"{'TOTAL / SUMMARY (' + str(len(cog_files)) + ' COGs)':<45} | {total_valid_all:>9,d} | "
        f"{total_match_all:>9,d} | {total_diff_all:>8,d} | {diff_all_pct:>6.2f}% | "
        f"{'PASS' if all_pass else 'FAIL':>6}"
    )
    print("=" * 80)

    if all_pass and len(cog_files) == 19:
        print(f"\n[SUCCESS] 19/19 Production Analytical COGs conform to canonical hotspot persistence.")
        print(f"Total Differing Pixels across entire dataset: 0")
        sys.exit(0)
    else:
        print(f"\n[FAIL] Found persistence discrepancies in {len(cog_files) - sum(r['status'] == 'PASS' for r in results)} files.")
        sys.exit(1)


if __name__ == "__main__":
    main()
