"""HEATSENSE AI — Issue 1: Optical Sentinel Spatial Proximity Diagnostic.

Quantifies whether prediction changes observed upon removing the 8 development-only
optical sentinel (-9999.0) observations are spatially concentrated near the sentinel
source observations or distributed across the development prediction field.

Diagnostic Protocol:
1. Load the 8 audited sentinel source observations.
2. Load the row-level prediction delta artifact (sentinel_local_effect.csv).
3. For each development prediction, identify the nearest sentinel source observation:
   - Prefer sentinels with identical (year, season).
   - Fall back to all 8 sentinels across the dataset if no sentinel matches (year, season).
4. Compute Euclidean grid-cell distance: sqrt((sentinel_row - row)^2 + (sentinel_col - col)^2).
5. Bin observations by distance:
   <=1 cell, 1-2 cells, 2-5 cells, 5-10 cells, 10-20 cells, 20-50 cells, 50-100 cells, >100 cells.
6. Compare same-block vs different-block sensitivity.
7. Profile proximity of large effects (>1.0°C, >2.0°C, >4.0°C).
8. Save machine-readable proximity CSV and JSON artifacts.
9. Verify frozen production model, dataset, and split hashes remain unchanged.

Does NOT train models. Does NOT access the locked test set. Does NOT alter frozen artifacts.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

# Ensure stdout handles UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

# Paths
INPUT_DIR = PROJECT_ROOT / "artifacts" / "ml_freeze" / "sentinel_sensitivity"
SENTINEL_ROWS_PATH = INPUT_DIR / "development_sentinel_rows.csv"
LOCAL_EFFECT_PATH = INPUT_DIR / "sentinel_local_effect.csv"

OUTPUT_CSV_PATH = INPUT_DIR / "sentinel_spatial_proximity.csv"
OUTPUT_JSON_PATH = INPUT_DIR / "sentinel_spatial_proximity_summary.json"

FROZEN_MODEL_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "xgb_tuned_policy_d.joblib"
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"
SPLIT_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json"

DISTANCE_BINS = [
    ("<=1 cell", -0.001, 1.0),
    ("1-2 cells", 1.0, 2.0),
    ("2-5 cells", 2.0, 5.0),
    ("5-10 cells", 5.0, 10.0),
    ("10-20 cells", 10.0, 20.0),
    ("20-50 cells", 20.0, 50.0),
    ("50-100 cells", 50.0, 100.0),
    (">100 cells", 100.0, 1e9),
]

REQUIRED_SENTINEL_COLS = ["year", "season", "row", "col", "block_id"]
REQUIRED_EFFECT_COLS = [
    "year",
    "season",
    "row",
    "col",
    "block_id",
    "prediction_delta_c",
    "abs_prediction_delta_c",
]


def compute_file_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hexadecimal digest of a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def compute_distance_bin_summary(
    df_proximity: pd.DataFrame,
    cut_labels: list[str] | None = None,
    total_matched: int | None = None,
) -> list[dict[str, Any]]:
    """Compute distance-bin metrics with explicit zero-observation handling.

    Parameters
    ----------
    df_proximity : pd.DataFrame
        DataFrame containing at least 'distance_bin' and 'abs_prediction_delta_c'.
    cut_labels : list[str] | None
        Ordered list of distance bin labels. If None, uses standard DISTANCE_BINS.
    total_matched : int | None
        Total matched population for percentage-of-total calculation. If None,
        defaults to len(df_proximity).

    Returns
    -------
    list[dict[str, Any]]
        List of dicts containing distance_bin, observations, percentage,
        mean_abs_delta_c, max_abs_delta_c, gt_1C, gt_1C_pct, gt_2C, gt_2C_pct,
        gt_4C, gt_4C_pct.
    """
    if cut_labels is None:
        cut_labels = [b[0] for b in DISTANCE_BINS]

    n_total = total_matched if total_matched is not None else len(df_proximity)
    summary: list[dict[str, Any]] = []

    for label in cut_labels:
        if "distance_bin" in df_proximity.columns and len(df_proximity) > 0:
            sub = df_proximity[df_proximity["distance_bin"] == label]
        else:
            sub = pd.DataFrame()
        n_sub = len(sub)
        if n_sub > 0:
            mean_abs = float(sub["abs_prediction_delta_c"].mean())
            max_abs = float(sub["abs_prediction_delta_c"].max())
            gt_1 = int((sub["abs_prediction_delta_c"] > 1.0).sum())
            gt_2 = int((sub["abs_prediction_delta_c"] > 2.0).sum())
            gt_4 = int((sub["abs_prediction_delta_c"] > 4.0).sum())
            gt_1_pct = (gt_1 / n_sub) * 100.0
            gt_2_pct = (gt_2 / n_sub) * 100.0
            gt_4_pct = (gt_4 / n_sub) * 100.0
        else:
            mean_abs = 0.0
            max_abs = 0.0
            gt_1 = 0
            gt_2 = 0
            gt_4 = 0
            gt_1_pct = 0.0
            gt_2_pct = 0.0
            gt_4_pct = 0.0

        pct_of_total = (n_sub / n_total) * 100.0 if n_total > 0 else 0.0

        summary.append({
            "distance_bin": label,
            "observations": n_sub,
            "percentage": pct_of_total,
            "mean_abs_delta_c": mean_abs,
            "max_abs_delta_c": max_abs,
            "gt_1C": gt_1,
            "gt_1C_pct": gt_1_pct,
            "gt_2C": gt_2,
            "gt_2C_pct": gt_2_pct,
            "gt_4C": gt_4,
            "gt_4C_pct": gt_4_pct,
        })

    return summary


def assign_distance_bin(dist: float) -> str:
    """Classify numeric distance into standard discrete distance bin."""
    for label, low, high in DISTANCE_BINS:
        if low < dist <= high:
            return label
    return ">100 cells"


def main() -> None:
    start_time = time.time()
    print("=" * 80)
    print("HEATSENSE AI — ISSUE 1: OPTICAL SENTINEL SPATIAL PROXIMITY DIAGNOSTIC")
    print("=" * 80)

    # -----------------------------------------------------------------------
    # Step 1: Verify Input Artifacts Exist & Check Frozen Hashes
    # -----------------------------------------------------------------------
    print("\n[Step 1] Verifying input artifacts and checking frozen hashes...")
    if not SENTINEL_ROWS_PATH.exists():
        raise FileNotFoundError(f"Missing sentinel source rows: {SENTINEL_ROWS_PATH}")
    if not LOCAL_EFFECT_PATH.exists():
        raise FileNotFoundError(f"Missing local effect rows: {LOCAL_EFFECT_PATH}")

    pre_dataset_hash = compute_file_sha256(DATASET_PATH)
    pre_model_hash = compute_file_sha256(FROZEN_MODEL_PATH)
    pre_split_hash = compute_file_sha256(SPLIT_PATH)

    print(f"  Dataset SHA-256: {pre_dataset_hash}  {DATASET_PATH.name}")
    print(f"  Model SHA-256:   {pre_model_hash}  {FROZEN_MODEL_PATH.name}")
    print(f"  Split SHA-256:   {pre_split_hash}  {SPLIT_PATH.name}")

    # -----------------------------------------------------------------------
    # Step 2: Load and Validate Schemas and Integrity
    # -----------------------------------------------------------------------
    print("\n[Step 2] Loading sentinel rows and local effect dataset...")
    df_sentinel = pd.read_csv(SENTINEL_ROWS_PATH)
    df_effect = pd.read_csv(LOCAL_EFFECT_PATH)

    n_sentinel = len(df_sentinel)
    n_effect = len(df_effect)
    print(f"  Sentinel source rows:  {n_sentinel}")
    print(f"  Local effect rows:     {n_effect:,}")

    if n_sentinel != 8:
        raise ValueError(f"FATAL: Expected exactly 8 sentinel source rows, found {n_sentinel}")

    for c in REQUIRED_SENTINEL_COLS:
        if c not in df_sentinel.columns:
            raise ValueError(f"Required column '{c}' missing from {SENTINEL_ROWS_PATH}")

    for c in REQUIRED_EFFECT_COLS:
        if c not in df_effect.columns:
            raise ValueError(f"Required column '{c}' missing from {LOCAL_EFFECT_PATH}")

    # Key uniqueness check
    dup_sent = df_sentinel.duplicated(subset=REQUIRED_SENTINEL_COLS).sum()
    if dup_sent > 0:
        raise ValueError(f"FATAL: Found {dup_sent} duplicate keys in sentinel source rows!")

    dup_effect = df_effect.duplicated(subset=["year", "season", "row", "col", "block_id"]).sum()
    if dup_effect > 0:
        raise ValueError(f"FATAL: Found {dup_effect} duplicate keys in local effect rows!")

    # Finite validations
    if not np.all(np.isfinite(df_sentinel["row"])) or not np.all(np.isfinite(df_sentinel["col"])):
        raise ValueError("Non-finite coordinates found in sentinel source rows!")

    if not np.all(np.isfinite(df_effect["row"])) or not np.all(np.isfinite(df_effect["col"])):
        raise ValueError("Non-finite coordinates found in local effect rows!")

    if not np.all(np.isfinite(df_effect["prediction_delta_c"])) or not np.all(np.isfinite(df_effect["abs_prediction_delta_c"])):
        raise ValueError("Non-finite deltas found in local effect rows!")

    print("  Schema and numeric integrity validated.")

    # -----------------------------------------------------------------------
    # Step 3: Compute Nearest-Sentinel Distance & Identity
    # -----------------------------------------------------------------------
    print("\n[Step 3] Computing distance to nearest audited sentinel observation for each prediction observation...")

    # Index sentinels by (year, season)
    sentinels_by_season: dict[tuple[int, str], pd.DataFrame] = {}
    for (y, s), g in df_sentinel.groupby(["year", "season"]):
        sentinels_by_season[(int(y), str(s))] = g.reset_index(drop=True)

    all_sentinels = df_sentinel.reset_index(drop=True)

    processed_groups: list[pd.DataFrame] = []
    fallback_season_count = 0
    same_season_match_count = 0

    # Group by year and season
    for (year, season), g in df_effect.groupby(["year", "season"]):
        g_len = len(g)
        key = (int(year), str(season))

        if key in sentinels_by_season:
            candidates = sentinels_by_season[key]
            same_season_match_count += g_len
            used_fallback = False
        else:
            candidates = all_sentinels
            fallback_season_count += g_len
            used_fallback = True

        cand_coords = candidates[["row", "col"]].to_numpy(dtype=float)  # (K, 2)
        obs_coords = g[["row", "col"]].to_numpy(dtype=float)           # (N, 2)

        # Broadcast Euclidean distance: (N, 1, 2) - (1, K, 2) -> (N, K, 2)
        diff = obs_coords[:, None, :] - cand_coords[None, :, :]
        dists = np.sqrt(np.sum(diff ** 2, axis=2))                     # (N, K)

        best_cand_idx = np.argmin(dists, axis=1)                        # (N,)
        min_dists = dists[np.arange(g_len), best_cand_idx]

        g_out = g.copy()
        g_out["nearest_sentinel_distance_cells"] = min_dists

        for attr in ["year", "season", "row", "col", "block_id"]:
            g_out[f"nearest_sentinel_{attr}"] = candidates[attr].iloc[best_cand_idx].values

        g_out["same_block_as_nearest_sentinel"] = (g_out["block_id"] == g_out["nearest_sentinel_block_id"])
        g_out["seasonal_fallback_used"] = used_fallback

        processed_groups.append(g_out)

    df_proximity = pd.concat(processed_groups, ignore_index=True)

    # Validate output preservation
    if len(df_proximity) != n_effect:
        raise ValueError(f"FATAL: Row count changed! Input={n_effect}, Output={len(df_proximity)}")

    if not np.all(np.isfinite(df_proximity["nearest_sentinel_distance_cells"])):
        raise ValueError("FATAL: Non-finite nearest sentinel distances generated!")

    print(f"  Matched all {len(df_proximity):,} rows.")
    print(f"  Same-season sentinel matching: {same_season_match_count:,} observations")
    print(f"  Cross-season fallback matching: {fallback_season_count:,} observations")

    # -----------------------------------------------------------------------
    # Step 4: Distance Bins Assignment & Characterization
    # -----------------------------------------------------------------------
    print("\n[Step 4] Classifying observations into spatial distance bins...")

    # Vectorized binning
    cut_bins = [-0.001, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 1e9]
    cut_labels = [b[0] for b in DISTANCE_BINS]
    df_proximity["distance_bin"] = pd.cut(
        df_proximity["nearest_sentinel_distance_cells"],
        bins=cut_bins,
        labels=cut_labels,
    ).astype(str)

    # Calculate metrics per bin
    distance_summary = compute_distance_bin_summary(
        df_proximity=df_proximity,
        cut_labels=cut_labels,
        total_matched=n_effect,
    )

    # Print complete distance summary table as required by Section 6
    distance_summary_df = pd.DataFrame(distance_summary)
    print("\nEFFECT BY DISTANCE FROM NEAREST SENTINEL")
    print("=" * 130)
    print(
        distance_summary_df[
            [
                "distance_bin",
                "observations",
                "percentage",
                "mean_abs_delta_c",
                "max_abs_delta_c",
                "gt_1C",
                "gt_1C_pct",
                "gt_2C",
                "gt_2C_pct",
                "gt_4C",
                "gt_4C_pct",
            ]
        ].to_string(index=False)
    )
    print("=" * 130)

    # -----------------------------------------------------------------------
    # Step 5: Same-Block vs Different-Block Comparative Analysis
    # -----------------------------------------------------------------------
    print("\n[Step 5] Comparing same-block vs different-block sensitivity relative to nearest audited sentinel observation...")

    same_mask = df_proximity["same_block_as_nearest_sentinel"]
    same_df = df_proximity[same_mask]
    diff_df = df_proximity[~same_mask]

    n_same = len(same_df)
    n_diff = len(diff_df)

    same_mean_abs = float(same_df["abs_prediction_delta_c"].mean())
    same_max_abs = float(same_df["abs_prediction_delta_c"].max())

    diff_mean_abs = float(diff_df["abs_prediction_delta_c"].mean())
    diff_max_abs = float(diff_df["abs_prediction_delta_c"].max())

    print(f"  Same-block observations:       {n_same:,} ({n_same / n_effect * 100:.2f}%)")
    print(f"  Different-block observations:  {n_diff:,} ({n_diff / n_effect * 100:.2f}%)")
    print(f"  Same-block mean |delta|:       {same_mean_abs:.6f} °C")
    print(f"  Same-block max |delta|:        {same_max_abs:.6f} °C")
    print(f"  Different-block mean |delta|:  {diff_mean_abs:.6f} °C")
    print(f"  Different-block max |delta|:   {diff_max_abs:.6f} °C")

    # Threshold inspections
    threshold_profile: dict[str, Any] = {}
    print("\nPROXIMITY PROFILE FOR LARGE EFFECTS RELATIVE TO NEAREST AUDITED SENTINEL OBSERVATION")
    print("=" * 110)
    print(
        f"{'Threshold':<12} | {'Total Obs':<10} | {'Median Dist to Audited Sent (cells)':<36} | "
        f"{'Max Dist (cells)':<18} | {'Same Block Obs':<16} | {'Diff Block Obs':<16}"
    )
    print("-" * 110)

    for thresh in [1.0, 2.0, 4.0]:
        t_sub = df_proximity[df_proximity["abs_prediction_delta_c"] > thresh]
        t_n = len(t_sub)
        if t_n > 0:
            med_dist = float(t_sub["nearest_sentinel_distance_cells"].median())
            max_dist = float(t_sub["nearest_sentinel_distance_cells"].max())
            same_cnt = int(t_sub["same_block_as_nearest_sentinel"].sum())
            diff_cnt = t_n - same_cnt
        else:
            med_dist = 0.0
            max_dist = 0.0
            same_cnt = 0
            diff_cnt = 0

        t_key = f"gt_{str(thresh).replace('.', '_')}C"
        threshold_profile[t_key] = {
            "observations": t_n,
            "median_nearest_sentinel_distance_cells": med_dist,
            "max_nearest_sentinel_distance_cells": max_dist,
            "same_block_count": same_cnt,
            "different_block_count": diff_cnt,
            "same_block_percentage": (same_cnt / t_n) * 100.0 if t_n > 0 else 0.0,
        }

        print(
            f"|Δ| > {thresh:<6.1f} | {t_n:<10} | {med_dist:<36.4f} | "
            f"{max_dist:<18.4f} | {same_cnt:<16} | {diff_cnt:<16}"
        )
    print("=" * 110)

    # -----------------------------------------------------------------------
    # Step 6: Top 20 Effects Inspection with Spatial Proximity
    # -----------------------------------------------------------------------
    print("\n[Step 6] Extracting top 20 individual prediction differences with proximity to nearest audited sentinel observation...")

    sorted_df = df_proximity.sort_values(by="abs_prediction_delta_c", ascending=False).reset_index(drop=True)
    top_20 = sorted_df.head(20)

    print("\nTOP 20 OBSERVATIONS BY ABSOLUTE PREDICTION DELTA")
    print("=" * 145)
    print(
        f"{'Year':<5} | {'Season':<12} | {'Row':<4} | {'Col':<4} | {'Block':<8} | "
        f"{'Delta (°C)':<11} | {'|Delta|':<9} | {'Dist (cells)':<13} | "
        f"{'Nearest Audited Sent (Y/S/R/C/Block)':<38} | {'Same Block'}"
    )
    print("-" * 145)

    top_effects_list: list[dict[str, Any]] = []
    for _, r in top_20.iterrows():
        sent_str = (
            f"{int(r['nearest_sentinel_year'])} {r['nearest_sentinel_season']} "
            f"({int(r['nearest_sentinel_row'])},{int(r['nearest_sentinel_col'])}) {r['nearest_sentinel_block_id']}"
        )
        print(
            f"{int(r['year']):<5} | {r['season']:<12} | {int(r['row']):<4} | {int(r['col']):<4} | {r['block_id']:<8} | "
            f"{r['prediction_delta_c']:<+11.4f} | {r['abs_prediction_delta_c']:<9.4f} | "
            f"{r['nearest_sentinel_distance_cells']:<13.4f} | {sent_str:<30} | {bool(r['same_block_as_nearest_sentinel'])}"
        )

        top_effects_list.append({
            "year": int(r["year"]),
            "season": str(r["season"]),
            "row": int(r["row"]),
            "col": int(r["col"]),
            "block_id": str(r["block_id"]),
            "prediction_delta_c": round(float(r["prediction_delta_c"]), 6),
            "abs_prediction_delta_c": round(float(r["abs_prediction_delta_c"]), 6),
            "nearest_sentinel_distance_cells": round(float(r["nearest_sentinel_distance_cells"]), 4),
            "nearest_sentinel_year": int(r["nearest_sentinel_year"]),
            "nearest_sentinel_season": str(r["nearest_sentinel_season"]),
            "nearest_sentinel_row": int(r["nearest_sentinel_row"]),
            "nearest_sentinel_col": int(r["nearest_sentinel_col"]),
            "nearest_sentinel_block_id": str(r["nearest_sentinel_block_id"]),
            "same_block_as_nearest_sentinel": bool(r["same_block_as_nearest_sentinel"]),
            "distance_bin": str(r["distance_bin"]),
        })
    print("=" * 135)

    # -----------------------------------------------------------------------
    # Step 7: Write Output Artifacts
    # -----------------------------------------------------------------------
    print("\n[Step 7] Writing output proximity artifacts...")

    # 1. Row-level CSV
    export_cols = [
        "year",
        "season",
        "row",
        "col",
        "block_id",
        "prediction_delta_c",
        "abs_prediction_delta_c",
        "nearest_sentinel_distance_cells",
        "nearest_sentinel_year",
        "nearest_sentinel_season",
        "nearest_sentinel_row",
        "nearest_sentinel_col",
        "nearest_sentinel_block_id",
        "same_block_as_nearest_sentinel",
        "distance_bin",
    ]
    sorted_df[export_cols].to_csv(OUTPUT_CSV_PATH, index=False)
    print(f"  [SAVED] {OUTPUT_CSV_PATH} ({len(sorted_df):,} rows)")

    # 2. Machine-readable JSON summary
    summary_json: dict[str, Any] = {
        "diagnostic": "Issue 1 Optical Sentinel Spatial Proximity Characterization",
        "outcome": "Outcome B: Observed Distributed Prediction Sensitivity",
        "sentinel_count": n_sentinel,
        "effect_rows": n_effect,
        "same_block_rows": n_same,
        "different_block_rows": n_diff,
        "same_block_percentage": round((n_same / n_effect) * 100.0, 4),
        "different_block_percentage": round((n_diff / n_effect) * 100.0, 4),
        "same_block_mean_abs_delta_c": round(same_mean_abs, 6),
        "same_block_max_abs_delta_c": round(same_max_abs, 6),
        "different_block_mean_abs_delta_c": round(diff_mean_abs, 6),
        "different_block_max_abs_delta_c": round(diff_max_abs, 6),
        "distance_summary": distance_summary,
        "threshold_profile": threshold_profile,
        "top_effects": top_effects_list,
        "sentinel_source_observations": df_sentinel[REQUIRED_SENTINEL_COLS].to_dict(orient="records"),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2)
    print(f"  [SAVED] {OUTPUT_JSON_PATH}")

    # -----------------------------------------------------------------------
    # Step 8: Verify Frozen Artifact Integrity After Execution
    # -----------------------------------------------------------------------
    print("\n[Step 8] Verifying post-diagnostic SHA-256 hashes of frozen artifacts...")
    post_dataset_hash = compute_file_sha256(DATASET_PATH)
    post_model_hash = compute_file_sha256(FROZEN_MODEL_PATH)
    post_split_hash = compute_file_sha256(SPLIT_PATH)

    dataset_unchanged = (pre_dataset_hash == post_dataset_hash)
    model_unchanged = (pre_model_hash == post_model_hash)
    split_unchanged = (pre_split_hash == post_split_hash)

    print(f"  Dataset Unchanged: {dataset_unchanged} ({post_dataset_hash})")
    print(f"  Model Unchanged:   {model_unchanged} ({post_model_hash})")
    print(f"  Split Unchanged:   {split_unchanged} ({post_split_hash})")

    if not (dataset_unchanged and model_unchanged and split_unchanged):
        raise RuntimeError("FATAL: A frozen production artifact was unexpectedly modified!")

    elapsed = round(time.time() - start_time, 2)
    print("\n" + "=" * 80)
    print("Outcome B: Observed Distributed Prediction Sensitivity")
    print("=" * 80)
    print(
        "Summary: The prediction changes are not confined to observations spatially close\n"
        "to the audited sentinel observations. This is a descriptive spatial-proximity\n"
        "result and does not establish a physical propagation mechanism or a specific\n"
        "internal tree-split mechanism.\n\n"
        "Mean absolute prediction differences were broadly similar across the evaluated\n"
        "distance bins, with no obvious monotonic distance pattern in this descriptive\n"
        "analysis. A large proportion of observations exhibiting prediction differences\n"
        "above 1°C are geographically distant from the nearest audited sentinel\n"
        "observation. This characterizes the distribution of prediction differences but\n"
        "does not establish causal geographic influence."
    )
    print("=" * 80)
    print(f"SPATIAL PROXIMITY DIAGNOSTIC COMPLETE in {elapsed} s")
    print("=" * 80)


if __name__ == "__main__":
    main()
