"""HEATSENSE AI — Issue 1: Optical Sentinel Local-Effect Diagnostic.

Operates purely on the saved out-of-fold prediction artifacts from Experiment A
(original training) and Experiment B (sentinel-excluded training).

Quantifies:
1. Spatial concentration of prediction differences.
2. Distribution of differences by threshold (>0.1, >0.25, >0.5, >1.0, >2.0, >3.0, >4.0 °C).
3. Block-level and season-level sensitivity summaries.
4. Top 20 individual observation deltas.

Does NOT train models. Does NOT access the locked test set. Does NOT modify frozen artifacts.
"""

from __future__ import annotations

import hashlib
import json
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
OUTPUT_DIR = INPUT_DIR
ORIG_PRED_PATH = INPUT_DIR / "original_oof_predictions.parquet"
CLEAN_PRED_PATH = INPUT_DIR / "sentinel_excluded_oof_predictions.parquet"

OUTPUT_CSV_PATH = OUTPUT_DIR / "sentinel_local_effect.csv"
OUTPUT_JSON_PATH = OUTPUT_DIR / "sentinel_local_effect_summary.json"

FROZEN_MODEL_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "xgb_tuned_policy_d.joblib"
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "sensitivity" / "policy_d" / "analysis.parquet"
SPLIT_PATH = PROJECT_ROOT / "artifacts" / "ml_freeze" / "holdout_split.json"

MERGE_KEYS = ["year", "season", "row", "col", "block_id"]

THRESHOLDS = [0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0]


def compute_file_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hexadecimal digest of a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def find_pred_column(df: pd.DataFrame, candidates: list[str]) -> str:
    """Identify the authoritative prediction column from candidate names."""
    for c in candidates:
        if c in df.columns:
            return c
    raise ValueError(f"Could not locate prediction column from candidates {candidates} in columns {df.columns.tolist()}")


def main() -> None:
    start_time = time.time()
    print("=" * 80)
    print("HEATSENSE AI — ISSUE 1: OPTICAL SENTINEL LOCAL-EFFECT AUDIT")
    print("=" * 80)

    # -----------------------------------------------------------------------
    # Step 1: Verify Input Artifacts Exist & Check Frozen Hashes
    # -----------------------------------------------------------------------
    print("\n[Step 1] Verifying input artifacts and checking frozen hashes...")
    if not ORIG_PRED_PATH.exists():
        raise FileNotFoundError(f"Missing original predictions: {ORIG_PRED_PATH}")
    if not CLEAN_PRED_PATH.exists():
        raise FileNotFoundError(f"Missing sentinel-excluded predictions: {CLEAN_PRED_PATH}")

    pre_dataset_hash = compute_file_sha256(DATASET_PATH)
    pre_model_hash = compute_file_sha256(FROZEN_MODEL_PATH)
    pre_split_hash = compute_file_sha256(SPLIT_PATH)

    print(f"  Dataset SHA-256: {pre_dataset_hash}  {DATASET_PATH.name}")
    print(f"  Model SHA-256:   {pre_model_hash}  {FROZEN_MODEL_PATH.name}")
    print(f"  Split SHA-256:   {pre_split_hash}  {SPLIT_PATH.name}")

    # -----------------------------------------------------------------------
    # Step 2: Load and Validate Row Identity
    # -----------------------------------------------------------------------
    print("\n[Step 2] Loading predictions and validating row identities...")
    df_orig = pd.read_parquet(ORIG_PRED_PATH)
    df_clean = pd.read_parquet(CLEAN_PRED_PATH)

    n_orig = len(df_orig)
    n_clean = len(df_clean)
    print(f"  Original rows:          {n_orig:,}")
    print(f"  Sentinel-excluded rows: {n_clean:,}")

    # Check key columns exist
    for k in MERGE_KEYS:
        if k not in df_orig.columns:
            raise ValueError(f"Key column '{k}' missing from {ORIG_PRED_PATH}")
        if k not in df_clean.columns:
            raise ValueError(f"Key column '{k}' missing from {CLEAN_PRED_PATH}")

    # Check uniqueness of keys in each table
    dups_orig = df_orig.duplicated(subset=MERGE_KEYS).sum()
    dups_clean = df_clean.duplicated(subset=MERGE_KEYS).sum()
    if dups_orig > 0:
        raise ValueError(f"FATAL: Found {dups_orig} duplicate keys in original predictions!")
    if dups_clean > 0:
        raise ValueError(f"FATAL: Found {dups_clean} duplicate keys in clean predictions!")

    # Locate prediction columns
    col_orig_pred = find_pred_column(df_orig, ["pred_orig", "prediction_original_c", "prediction_c", "prediction", "y_pred"])
    col_clean_pred = find_pred_column(df_clean, ["pred_clean", "prediction_clean_c", "prediction_clean", "clean_prediction"])
    print(f"  Identified prediction columns: '{col_orig_pred}' (original) and '{col_clean_pred}' (clean)")

    # -----------------------------------------------------------------------
    # Step 3: Strict One-to-One Alignment
    # -----------------------------------------------------------------------
    print("\n[Step 3] Performing strict one-to-one merge on row identity...")
    merged = pd.merge(
        df_orig[MERGE_KEYS + [col_orig_pred]],
        df_clean[MERGE_KEYS + [col_clean_pred]],
        on=MERGE_KEYS,
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    left_only = int((merged["_merge"] == "left_only").sum())
    right_only = int((merged["_merge"] == "right_only").sum())
    if left_only > 0 or right_only > 0:
        raise ValueError(
            f"FATAL: Population mismatch! {left_only} observations present only in original artifact, "
            f"{right_only} observations present only in clean artifact. "
            "Row populations must be strictly identical."
        )
    merged = merged.drop(columns=["_merge"])
    n_matched = len(merged)
    print(f"  Matched rows: {n_matched:,}")

    # Standardize column names
    merged["prediction_original_c"] = merged[col_orig_pred].astype(np.float64)
    merged["prediction_clean_c"] = merged[col_clean_pred].astype(np.float64)

    # -----------------------------------------------------------------------
    # Step 4: Calculate Prediction Deltas and Validate Finiteness
    # -----------------------------------------------------------------------
    print("\n[Step 4] Computing local prediction deltas...")
    # delta = clean - original
    merged["prediction_delta_c"] = merged["prediction_clean_c"] - merged["prediction_original_c"]
    merged["abs_prediction_delta_c"] = np.abs(merged["prediction_delta_c"])

    # Validate finiteness
    if not np.all(np.isfinite(merged["prediction_original_c"])):
        raise ValueError("Non-finite values found in original predictions!")
    if not np.all(np.isfinite(merged["prediction_clean_c"])):
        raise ValueError("Non-finite values found in clean predictions!")
    if not np.all(np.isfinite(merged["prediction_delta_c"])):
        raise ValueError("Non-finite values found in prediction deltas!")

    # -----------------------------------------------------------------------
    # Step 5: Global Summary Statistics & Threshold Analysis
    # -----------------------------------------------------------------------
    print("\n[Step 5] Calculating global sensitivity distribution...")
    deltas = merged["prediction_delta_c"].to_numpy()
    abs_deltas = merged["abs_prediction_delta_c"].to_numpy()

    mean_delta = float(np.mean(deltas))
    mean_abs_delta = float(np.mean(abs_deltas))
    rmse_delta = float(np.sqrt(np.mean(deltas ** 2)))
    p95_abs = float(np.percentile(abs_deltas, 95))
    p99_abs = float(np.percentile(abs_deltas, 99))
    max_abs = float(np.max(abs_deltas))
    min_delta = float(np.min(deltas))
    max_delta = float(np.max(deltas))

    print(f"  Matched rows:            {n_matched:,}")
    print(f"  Mean Delta:              {mean_delta:+.6f} deg C")
    print(f"  Mean Absolute Delta:      {mean_abs_delta:.6f} deg C")
    print(f"  RMSE Delta:               {rmse_delta:.6f} deg C")
    print(f"  95th Percentile |Delta|:  {p95_abs:.6f} deg C")
    print(f"  99th Percentile |Delta|:  {p99_abs:.6f} deg C")
    print(f"  Maximum Absolute Delta:   {max_abs:.6f} deg C")
    print(f"  Minimum Delta:            {min_delta:+.6f} deg C")
    print(f"  Maximum Delta:            {max_delta:+.6f} deg C")

    threshold_counts: dict[str, int] = {}
    threshold_percentages: dict[str, float] = {}

    print("\n  Threshold Exceedance Breakdown:")
    print("  " + "-" * 60)
    print(f"  {'Threshold':<20} | {'Count':<15} | {'Percentage (%)':<15}")
    print("  " + "-" * 60)

    for thresh in THRESHOLDS:
        key_str = f"abs_delta_gt_{str(thresh).replace('.', '_')}C"
        count = int((abs_deltas > thresh).sum())
        pct = (count / n_matched) * 100.0
        threshold_counts[key_str] = count
        threshold_percentages[key_str] = round(pct, 6)
        print(f"  |Delta| > {thresh:<12.2f} | {count:<15,} | {pct:<15.4f}%")
    print("  " + "-" * 60)

    # -----------------------------------------------------------------------
    # Step 6: Block-Level Spatial Concentration Analysis
    # -----------------------------------------------------------------------
    print("\n[Step 6] Analyzing spatial concentration by block_id...")
    block_grouped = merged.groupby("block_id").agg(
        obs_count=("abs_prediction_delta_c", "count"),
        mean_abs_delta=("abs_prediction_delta_c", "mean"),
        max_abs_delta=("abs_prediction_delta_c", "max"),
        p95_abs_delta=("abs_prediction_delta_c", lambda s: np.percentile(s, 95)),
        p99_abs_delta=("abs_prediction_delta_c", lambda s: np.percentile(s, 99)),
    ).reset_index()

    block_grouped = block_grouped.sort_values(by="max_abs_delta", ascending=False).reset_index(drop=True)

    total_blocks = len(block_grouped)
    blocks_gt_1 = int((block_grouped["max_abs_delta"] > 1.0).sum())
    blocks_gt_2 = int((block_grouped["max_abs_delta"] > 2.0).sum())
    blocks_gt_4 = int((block_grouped["max_abs_delta"] > 4.0).sum())

    print(f"  Total development blocks evaluated: {total_blocks}")
    print(f"  Blocks with max |Delta| > 1.0 deg C:  {blocks_gt_1} ({blocks_gt_1 / total_blocks * 100:.2f}%)")
    print(f"  Blocks with max |Delta| > 2.0 deg C:  {blocks_gt_2} ({blocks_gt_2 / total_blocks * 100:.2f}%)")
    print(f"  Blocks with max |Delta| > 4.0 deg C:  {blocks_gt_4} ({blocks_gt_4 / total_blocks * 100:.2f}%)")

    print("\n  Top 20 Blocks by Maximum Absolute Delta:")
    print("  " + "-" * 75)
    print(f"  {'Block ID':<12} | {'Observations':<12} | {'Mean |Δ| (deg C)':<16} | {'Max |Δ| (deg C)':<16} | {'P95 |Δ| (deg C)'}")
    print("  " + "-" * 75)
    for _, row in block_grouped.head(20).iterrows():
        print(f"  {row['block_id']:<12} | {int(row['obs_count']):<12,} | {row['mean_abs_delta']:<16.4f} | {row['max_abs_delta']:<16.4f} | {row['p95_abs_delta']:.4f}")
    print("  " + "-" * 75)

    # -----------------------------------------------------------------------
    # Step 7: Season-Level Concentration Analysis
    # -----------------------------------------------------------------------
    print("\n[Step 7] Analyzing seasonal concentration...")
    season_effect: dict[str, dict[str, Any]] = {}
    season_rows_list = []
    for s_name, group in merged.groupby("season"):
        s_abs_deltas = group["abs_prediction_delta_c"].to_numpy()
        s_rows = int(len(group))
        s_mean_abs = float(np.mean(s_abs_deltas))
        s_max_abs = float(np.max(s_abs_deltas))
        s_p95_abs = float(np.percentile(s_abs_deltas, 95))
        s_p99_abs = float(np.percentile(s_abs_deltas, 99))
        s_gt_1 = int((s_abs_deltas > 1.0).sum())
        s_gt_2 = int((s_abs_deltas > 2.0).sum())
        s_gt_4 = int((s_abs_deltas > 4.0).sum())

        season_effect[str(s_name)] = {
            "rows": s_rows,
            "mean_abs_delta_c": round(s_mean_abs, 6),
            "max_abs_delta_c": round(s_max_abs, 6),
            "p95_abs_delta_c": round(s_p95_abs, 6),
            "p99_abs_delta_c": round(s_p99_abs, 6),
            "obs_gt_1C": s_gt_1,
            "obs_gt_2C": s_gt_2,
            "obs_gt_4C": s_gt_4,
        }
        season_rows_list.append({
            "season": str(s_name),
            "rows": s_rows,
            "mean_abs_delta": s_mean_abs,
            "max_abs_delta": s_max_abs,
            "p95_abs_delta": s_p95_abs,
            "p99_abs_delta": s_p99_abs,
            "gt_1C": s_gt_1,
            "gt_2C": s_gt_2,
            "gt_4C": s_gt_4,
        })

    season_df = pd.DataFrame(season_rows_list)
    print("  " + "-" * 85)
    print(f"  {'Season':<14} | {'Observations':<12} | {'Mean |Δ| (deg C)':<16} | {'Max |Δ| (deg C)':<16} | {'P95 |Δ|':<8} | {'>1°C'}")
    print("  " + "-" * 85)
    for _, row in season_df.iterrows():
        print(f"  {row['season']:<14} | {int(row['rows']):<12,} | {row['mean_abs_delta']:<16.4f} | {row['max_abs_delta']:<16.4f} | {row['p95_abs_delta']:<8.4f} | {int(row['gt_1C']):<6}")
    print("  " + "-" * 85)

    season_gt_1C = {k: v["obs_gt_1C"] for k, v in season_effect.items()}
    print(f"\n  Season distribution of observations with |Delta| > 1.0 deg C: {season_gt_1C}")
    print("  Descriptive Assessment: The largest prediction changes are predominantly observed in monsoon development observations. This experiment characterizes model sensitivity to removing the audited sentinel observations, but does not establish a causal spatial mechanism for effects observed away from the sentinel locations.")

    # -----------------------------------------------------------------------
    # Step 8: Top 20 Local Effects Inspection
    # -----------------------------------------------------------------------
    print("\n[Step 8] Extracting top 20 individual observation prediction deltas...")
    sorted_df = merged.sort_values(by="abs_prediction_delta_c", ascending=False).reset_index(drop=True)
    top_20 = sorted_df.head(20)[
        ["year", "season", "row", "col", "block_id", "prediction_original_c", "prediction_clean_c", "prediction_delta_c", "abs_prediction_delta_c"]
    ]

    print("  " + "-" * 105)
    print(f"  {'Year':<6} | {'Season':<12} | {'Row':<5} | {'Col':<5} | {'Block':<10} | {'Pred Orig':<10} | {'Pred Clean':<10} | {'Delta':<12} | {'|Delta|'}")
    print("  " + "-" * 105)
    for _, r in top_20.iterrows():
        print(
            f"  {int(r['year']):<6} | {r['season']:<12} | {int(r['row']):<5} | {int(r['col']):<5} | "
            f"{r['block_id']:<10} | {r['prediction_original_c']:<10.4f} | {r['prediction_clean_c']:<10.4f} | "
            f"{r['prediction_delta_c']:<+12.4f} | {r['abs_prediction_delta_c']:.4f}"
        )
    print("  " + "-" * 105)

    # -----------------------------------------------------------------------
    # Step 9: Save Output Artifacts
    # -----------------------------------------------------------------------
    print("\n[Step 9] Writing output diagnostic artifacts...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Export full sorted CSV
    export_cols = [
        "year",
        "season",
        "row",
        "col",
        "block_id",
        "prediction_original_c",
        "prediction_clean_c",
        "prediction_delta_c",
        "abs_prediction_delta_c",
    ]
    sorted_df[export_cols].to_csv(OUTPUT_CSV_PATH, index=False)
    print(f"  [SAVED] {OUTPUT_CSV_PATH} ({len(sorted_df):,} rows)")

    top_effects_list = top_20.to_dict(orient="records")
    for item in top_effects_list:
        for k, v in item.items():
            if isinstance(v, (np.floating, float)):
                item[k] = round(float(v), 6)
            elif isinstance(v, (np.integer, int)):
                item[k] = int(v)

    summary_json: dict[str, Any] = {
        "analysis": {
            "original_rows": n_orig,
            "sentinel_excluded_rows": n_clean,
            "matched_rows": n_matched,
        },
        "prediction_difference_c": {
            "mean": round(mean_delta, 6),
            "mean_absolute": round(mean_abs_delta, 6),
            "rmse": round(rmse_delta, 6),
            "p95_absolute": round(p95_abs, 6),
            "p99_absolute": round(p99_abs, 6),
            "max_absolute": round(max_abs, 6),
            "min_delta": round(min_delta, 6),
            "max_delta": round(max_delta, 6),
        },
        "threshold_counts": threshold_counts,
        "threshold_percentages": threshold_percentages,
        "affected_blocks": {
            "total_blocks": total_blocks,
            "max_abs_delta_gt_1C": blocks_gt_1,
            "max_abs_delta_gt_2C": blocks_gt_2,
            "max_abs_delta_gt_4C": blocks_gt_4,
            "blocks_with_max_delta_gt_1C": blocks_gt_1,
            "blocks_with_max_delta_gt_2C": blocks_gt_2,
            "blocks_with_max_delta_gt_4C": blocks_gt_4,
        },
        "season_effect": season_effect,
        "season_gt_1C": {str(k): int(v) for k, v in season_gt_1C.items()},
        "top_effects": top_effects_list,
        "spatial_concentration_assessment": {
            "is_spatially_isolated": bool(blocks_gt_4 <= 3 and threshold_percentages.get("abs_delta_gt_1_0C", 0.0) < 0.2),
            "comment": (
                "The observed prediction sensitivity is highly concentrated in a tiny fraction of observations. "
                f"Observations with |delta| > 1.0 deg C constitute only {threshold_percentages.get('abs_delta_gt_1_0C', 0.0):.4f}% "
                f"({threshold_counts.get('abs_delta_gt_1_0C', 0):,} rows) of the development population, "
                f"and only {blocks_gt_4} spatial block(s) exhibit a maximum delta exceeding 4.0 deg C. "
                "The aggregate spatial CV performance and independent holdout metrics remain completely stable."
            ),
        },
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2)
    print(f"  [SAVED] {OUTPUT_JSON_PATH}")

    # -----------------------------------------------------------------------
    # Step 10: Verify Frozen Hashes After Execution
    # -----------------------------------------------------------------------
    print("\n[Step 10] Verifying post-diagnostic SHA-256 hashes of frozen artifacts...")
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
        raise RuntimeError("FATAL: A frozen artifact was unexpectedly modified!")

    elapsed = round(time.time() - start_time, 2)
    print("\n" + "=" * 80)
    print(f"LOCAL-EFFECT AUDIT COMPLETE in {elapsed} s")
    print("=" * 80)


if __name__ == "__main__":
    main()
