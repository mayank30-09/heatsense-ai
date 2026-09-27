"""Comparative Evaluation of Candidate Pixel Eligibility Policies for HEATSENSE AI.

Evaluates 4 candidate pixel-eligibility policies across all available seasonal
Landsat products (2022-2026):
- Policy A: OBS_COUNT >= 1 (Unconstrained Baseline)
- Policy B: OBS_COUNT >= 2 (Strict Multi-Observation Cutoff)
- Policy C: OBS_COUNT >= 2 OR Spatially Persistent Hotspot
- Policy D: OBS_COUNT >= 1 BUT Exclude Strong Spatial Anomalies

Computes spatial coverage, retention rates, hotspot retention, cold-anomaly removal,
and post-filtering LST distribution metrics.

Output:
- data/diagnostics/quality/eligibility_policy_comparison.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.mask

from gis.quality.pixel_quality import (
    compute_neighborhood_metrics,
    evaluate_boundary_context,
    assign_quality_flags,
)
from gis.quality.eligibility import (
    EligibilityStatus,
    evaluate_pixel_eligibility,
)

BOUNDARY_PATH = PROJECT_ROOT / "data" / "raw" / "boundaries" / "surat_smc_boundary.geojson"
SEASONAL_COG_ROOT = PROJECT_ROOT / "data" / "processed" / "seasonal"
PERSISTENCE_SUMMARY_PATH = PROJECT_ROOT / "data" / "diagnostics" / "quality" / "hotspot_persistence_summary.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "diagnostics" / "quality" / "eligibility_policy_comparison.csv"
TOTAL_SMC_GRID_CELLS = 50752

SEASONS = ("winter", "summer", "monsoon", "post_monsoon")
START_YEAR = 2022
END_YEAR = 2026


POLICY_METADATA = {
    "policy_a": {
        "name": "Policy A (OBS >= 1)",
        "desc": "Unconstrained baseline: retains all valid pixels with OBS >= 1.",
    },
    "policy_b": {
        "name": "Policy B (OBS >= 2)",
        "desc": "Strict multi-observation cutoff: requires at least 2 clear-sky passes.",
    },
    "policy_c": {
        "name": "Policy C (OBS >= 2 OR Persistent Hotspot)",
        "desc": "Requires OBS >= 2, but rescues chronic multi-season persistent hotspots with OBS=1.",
    },
    "policy_d": {
        "name": "Policy D (OBS >= 1 Selective Anomaly Exclusion)",
        "desc": "Accepts OBS >= 1, but selectively purges pixels with OBS=1 and strong spatial anomalies.",
    },
}


def load_persistent_hotspots() -> set[tuple[int, int]]:
    """Load coordinates (row, col) of verified persistent hotspots."""
    if not PERSISTENCE_SUMMARY_PATH.exists():
        return set()
    df_p = pd.read_csv(PERSISTENCE_SUMMARY_PATH)
    pers = df_p[df_p["is_persistent_hotspot"] == True]
    return set(zip(pers["row"].astype(int), pers["col"].astype(int)))


def evaluate_season_policies(
    year: int,
    season: str,
    boundary_geom: list[Any],
    persistent_hotspots: set[tuple[int, int]],
    anomaly_diff_thresh: float = 10.0,
) -> list[dict[str, Any]] | None:
    """Evaluate policies A, B, C, D on a single seasonal COG."""
    cog_path = SEASONAL_COG_ROOT / str(year) / season / f"surat_{year}_{season}_features_cog.tif"
    if not cog_path.exists():
        return None

    with rasterio.open(cog_path) as src:
        masked_arr, _ = rasterio.mask.mask(src, boundary_geom, crop=False, nodata=-9999.0)
        lst_grid = masked_arr[0]
        obs_grid = masked_arr[4]

    valid_mask = (lst_grid != -9999.0) & np.isfinite(lst_grid) & (obs_grid > 0)
    valid_count = int(np.sum(valid_mask))
    if valid_count == 0:
        return None

    valid_lst = lst_grid[valid_mask]
    valid_obs = obs_grid[valid_mask]

    # Extreme thresholds
    p01 = float(np.percentile(valid_lst, 1.0))
    p95 = float(np.percentile(valid_lst, 95.0))
    p99 = float(np.percentile(valid_lst, 99.0))

    # Masks
    hot1_mask = valid_mask & (lst_grid >= p99)
    total_hot1 = int(np.sum(hot1_mask))

    # Persistent hotspots mask in this season
    pers_mask = np.zeros_like(valid_mask, dtype=bool)
    rows_idx, cols_idx = np.where(valid_mask)
    for r, c in zip(rows_idx, cols_idx):
        if (r, c) in persistent_hotspots:
            pers_mask[r, c] = True
    total_pers_active = int(np.sum(pers_mask))

    # Identify cold anomalies: LST <= p01 AND (OBS == 1 or delta < -10C)
    # First compute neighborhood metrics for candidate anomalous pixels (OBS == 1 or extreme tails)
    eval_candidates = valid_mask & ((obs_grid == 1) | (lst_grid <= p01) | (lst_grid >= p99))
    cand_rows, cand_cols = np.where(eval_candidates)

    grid_rows, grid_cols = lst_grid.shape
    pixel_metrics: dict[tuple[int, int], dict[str, Any]] = {}

    for r, c in zip(cand_rows, cand_cols):
        n_stats = compute_neighborhood_metrics(lst_grid, row=r, col=c, nodata_val=-9999.0)
        b_stats = evaluate_boundary_context(
            row=r,
            col=c,
            rows=grid_rows,
            cols=grid_cols,
            valid_neighbor_count=n_stats["valid_neighbor_count"],
        )
        flags = assign_quality_flags(
            obs_count=obs_grid[r, c],
            qa_k=None,
            abs_diff_med=n_stats["absolute_pixel_minus_neighborhood_median"],
            valid_neighbor_count=n_stats["valid_neighbor_count"],
            is_boundary=b_stats["is_boundary_context"],
            anomaly_diff_thresh=anomaly_diff_thresh,
        )
        pixel_metrics[(r, c)] = {
            "abs_diff_med": n_stats["absolute_pixel_minus_neighborhood_median"],
            "diff_med": n_stats["pixel_minus_neighborhood_median"],
            "valid_neighbor_count": n_stats["valid_neighbor_count"],
            "is_boundary_context": b_stats["is_boundary_context"],
            "flags": flags,
        }

    # Severe cold anomaly definition: LST <= p01 AND OBS == 1 AND (diff_med < -10.0 or boundary)
    cold_anomaly_mask = np.zeros_like(valid_mask, dtype=bool)
    for (r, c), m in pixel_metrics.items():
        if lst_grid[r, c] <= p01 and obs_grid[r, c] == 1:
            diff = m["diff_med"]
            if (diff is not None and diff < -10.0) or ("LOW_SUPPORT_SPATIAL_EXTREME" in m["flags"]):
                cold_anomaly_mask[r, c] = True
    total_cold_anomalies = int(np.sum(cold_anomaly_mask))

    results: list[dict[str, Any]] = []

    # Evaluate each candidate policy
    for pol_key, pol_meta in POLICY_METADATA.items():
        retained_mask = np.zeros_like(valid_mask, dtype=bool)

        for r, c in zip(rows_idx, cols_idx):
            obs_val = obs_grid[r, c]
            is_pers = (r, c) in persistent_hotspots

            # If pixel had detailed metrics computed, use them; else standard defaults
            if (r, c) in pixel_metrics:
                pm = pixel_metrics[(r, c)]
                abs_diff = pm["abs_diff_med"]
                v_count = pm["valid_neighbor_count"]
                is_bound = pm["is_boundary_context"]
                q_flags = pm["flags"]
            else:
                abs_diff = 0.0
                v_count = 8
                is_bound = False
                q_flags = ["VALID"] if obs_val >= 2 else ["LOW_TEMPORAL_SUPPORT"]

            status, _ = evaluate_pixel_eligibility(
                obs_count=obs_val,
                policy_name=pol_key,
                quality_flags=q_flags,
                is_persistent_hotspot=is_pers,
                abs_diff_med=abs_diff,
                valid_neighbor_count=v_count,
                is_boundary_context=is_bound,
                anomaly_diff_thresh=anomaly_diff_thresh,
            )

            # Both ACCEPT and FLAG are retained in the analytical dataset
            if status in (EligibilityStatus.ACCEPT, EligibilityStatus.FLAG):
                retained_mask[r, c] = True

        retained_count = int(np.sum(retained_mask))
        ret_pct = round((retained_count / valid_count) * 100.0, 2)
        spatial_cov = round((retained_count / TOTAL_SMC_GRID_CELLS) * 100.0, 2)

        # Hotspot retention
        hot_ret = round(float(np.sum(retained_mask & hot1_mask) / total_hot1 * 100.0), 2) if total_hot1 > 0 else 100.0

        # Persistent hotspot retention
        pers_ret = (
            round(float(np.sum(retained_mask & pers_mask) / total_pers_active * 100.0), 2)
            if total_pers_active > 0 else 100.0
        )

        # Cold anomaly removal % (100 - % retained)
        if total_cold_anomalies > 0:
            cold_anom_retained = int(np.sum(retained_mask & cold_anomaly_mask))
            cold_anom_removed_pct = round((1.0 - (cold_anom_retained / total_cold_anomalies)) * 100.0, 2)
        else:
            cold_anom_removed_pct = 100.0  # Zero anomalies to remove

        # Retained LST statistics
        ret_lst = lst_grid[retained_mask]
        if len(ret_lst) > 0:
            lst_min_val = round(float(np.min(ret_lst)), 2)
            lst_p95_val = round(float(np.percentile(ret_lst, 95.0)), 2)
            lst_p99_val = round(float(np.percentile(ret_lst, 99.0)), 2)
            lst_max_val = round(float(np.max(ret_lst)), 2)
        else:
            lst_min_val = lst_p95_val = lst_p99_val = lst_max_val = None

        results.append({
            "policy": pol_key,
            "policy_name": pol_meta["name"],
            "year": year,
            "season": season,
            "valid_pixels": valid_count,
            "retained_pixels": retained_count,
            "retention_percent": ret_pct,
            "spatial_coverage": spatial_cov,
            "hotspot_retention": hot_ret,
            "persistent_hotspot_retention": pers_ret,
            "cold_anomaly_removal": cold_anom_removed_pct,
            "lst_min": lst_min_val,
            "lst_p95": lst_p95_val,
            "lst_p99": lst_p99_val,
            "lst_max": lst_max_val,
        })

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="HEATSENSE AI: Comparative Policy Analysis Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to save eligibility_policy_comparison.csv",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("HEATSENSE AI — CANDIDATE PIXEL ELIGIBILITY POLICY COMPARISON")
    print("=" * 80)

    # Load Boundary
    if not BOUNDARY_PATH.exists():
        raise FileNotFoundError(f"Surat SMC boundary not found at {BOUNDARY_PATH}")
    gdf_boundary = gpd.read_file(BOUNDARY_PATH).to_crs("EPSG:4326")
    boundary_geom = [gdf_boundary.geometry.union_all()]

    persistent_hotspots = load_persistent_hotspots()
    print(f"Loaded {len(persistent_hotspots)} verified persistent hotspot locations.")

    all_comparison_rows: list[dict[str, Any]] = []

    for y in range(START_YEAR, END_YEAR + 1):
        for s in SEASONS:
            print(f"Evaluating policies for {y} {s.upper()}...")
            rows = evaluate_season_policies(
                year=y,
                season=s,
                boundary_geom=boundary_geom,
                persistent_hotspots=persistent_hotspots,
            )
            if rows is not None:
                all_comparison_rows.extend(rows)

    df_comp = pd.DataFrame(all_comparison_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df_comp.to_csv(args.output, index=False)
    print(f"\nSaved policy comparison: {args.output} ({len(df_comp)} evaluations)")

    # Print Summary Table by Policy for Monsoon
    print("\n" + "=" * 80)
    print("MONSOON POLICY COMPARISON SUMMARY (Means across 2022-2026)")
    print("=" * 80)
    monsoon_df = df_comp[df_comp["season"] == "monsoon"]
    mon_summary = monsoon_df.groupby("policy")[[
        "retention_percent",
        "spatial_coverage",
        "hotspot_retention",
        "persistent_hotspot_retention",
        "cold_anomaly_removal",
        "lst_min",
        "lst_max",
    ]].mean().round(2)
    print(mon_summary.to_string())

    print("\n" + "=" * 80)
    print("SUMMER / WINTER POLICY COMPARISON SUMMARY (Means across 2022-2026)")
    print("=" * 80)
    dry_df = df_comp[df_comp["season"].isin(["summer", "winter"])]
    dry_summary = dry_df.groupby("policy")[[
        "retention_percent",
        "spatial_coverage",
        "hotspot_retention",
        "persistent_hotspot_retention",
        "cold_anomaly_removal",
        "lst_min",
        "lst_max",
    ]].mean().round(2)
    print(dry_summary.to_string())


if __name__ == "__main__":
    main()
