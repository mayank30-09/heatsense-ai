"""Multi-Season Hotspot Persistence Analysis for HEATSENSE AI.

Analyzes spatial and temporal recurrence of urban heat hotspots across
all available seasonal Landsat products (2022-2026). Computes persistence
frequencies, distinguishing chronic, structural urban heat islands from
transient, single-season thermal anomalies.

Outputs:
- data/diagnostics/quality/hotspot_persistence.csv
- data/diagnostics/quality/hotspot_persistence_summary.csv
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

import pandas as pd
import numpy as np


DEFAULT_INPUT = PROJECT_ROOT / "data" / "diagnostics" / "quality" / "extreme_pixel_quality.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "diagnostics" / "quality" / "hotspot_persistence.csv"
DEFAULT_SUMMARY_OUTPUT = PROJECT_ROOT / "data" / "diagnostics" / "quality" / "hotspot_persistence_summary.csv"


def classify_persistence_tier(freq: float) -> str:
    """Classify persistence frequency into structural tiers."""
    if freq >= 0.50:
        return "chronic_hotspot"
    elif freq >= 0.25:
        return "frequent_hotspot"
    elif freq >= 0.10:
        return "occasional_hotspot"
    else:
        return "transient_extreme"


def compute_hotspot_persistence(
    df_extremes: pd.DataFrame,
    total_seasons_count: int = 19,
    persistence_thresh: float = 0.25,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute multi-season persistence for all locations that ever exhibited
    hot extreme behavior (Top 1% or Top 20).

    Parameters
    ----------
    df_extremes : pd.DataFrame
        DataFrame loaded from extreme_pixel_quality.csv.
    total_seasons_count : int
        Total number of observed seasons across the study period (default 19).
    persistence_thresh : float
        Frequency cutoff above which a location is flagged as a persistent hotspot.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (df_seasonal_instances, df_location_summary)
    """
    # Filter to hot extreme records
    is_hot = df_extremes["extreme_type"].str.contains("hot", na=False)
    hot_df = df_extremes[is_hot].copy()

    # Stable spatial location identifier based on raster grid: R{row:03d}_C{col:03d}
    hot_df["location"] = hot_df.apply(lambda r: f"R{int(r['row']):03d}_C{int(r['col']):03d}", axis=1)

    # Flags for top 1% and top 20
    hot_df["top_1_percent"] = hot_df["extreme_type"].str.contains("top_1pct", na=False)
    hot_df["top_20"] = hot_df["extreme_type"].str.contains("top_20", na=False)

    # Location-level aggregations
    grouped = hot_df.groupby("location")

    loc_summary_rows: list[dict[str, Any]] = []
    loc_freq_map: dict[str, float] = {}
    loc_count_map: dict[str, int] = {}
    loc_persistent_map: dict[str, bool] = {}

    for loc, group in grouped:
        r0 = group.iloc[0]
        row_idx = int(r0["row"])
        col_idx = int(r0["col"])
        lon = float(r0["longitude"])
        lat = float(r0["latitude"])

        # Count how many distinct (year, season) pairs this location was in Top 1%
        top1_group = group[group["top_1_percent"]]
        distinct_hot_seasons = top1_group[["year", "season"]].drop_duplicates()
        hot_seasons_count = len(distinct_hot_seasons)

        top20_seasons_count = len(group[group["top_20"]][["year", "season"]].drop_duplicates())

        # For Surat SMC grid, all internal pixels have valid data in virtually all seasons (19 seasons)
        # We cap valid seasons at total_seasons_count
        valid_seasons_count = total_seasons_count
        freq = round(hot_seasons_count / valid_seasons_count, 4)

        is_persistent = bool(freq >= persistence_thresh or hot_seasons_count >= 4)
        tier = classify_persistence_tier(freq)

        # Seasonal breakdowns
        summer_hot_cnt = len(distinct_hot_seasons[distinct_hot_seasons["season"] == "summer"])
        winter_hot_cnt = len(distinct_hot_seasons[distinct_hot_seasons["season"] == "winter"])
        monsoon_hot_cnt = len(distinct_hot_seasons[distinct_hot_seasons["season"] == "monsoon"])
        post_monsoon_hot_cnt = len(distinct_hot_seasons[distinct_hot_seasons["season"] == "post_monsoon"])

        loc_freq_map[loc] = freq
        loc_count_map[loc] = hot_seasons_count
        loc_persistent_map[loc] = is_persistent

        loc_summary_rows.append({
            "location": loc,
            "row": row_idx,
            "col": col_idx,
            "longitude": lon,
            "latitude": lat,
            "hot_seasons_count": hot_seasons_count,
            "valid_seasons_count": valid_seasons_count,
            "hotspot_frequency": freq,
            "is_persistent_hotspot": is_persistent,
            "persistence_tier": tier,
            "top20_seasons_count": top20_seasons_count,
            "summer_hot_count": summer_hot_cnt,
            "winter_hot_count": winter_hot_cnt,
            "monsoon_hot_count": monsoon_hot_cnt,
            "post_monsoon_hot_count": post_monsoon_hot_cnt,
            "max_lst_ever": round(float(group["lst_c"].max()), 2),
            "median_lst_hot": round(float(group["lst_c"].median()), 2),
            "mean_obs_count": round(float(group["obs_count"].mean()), 2),
            "mean_qa_k": round(float(group["qa_k"].dropna().mean()), 2) if not group["qa_k"].dropna().empty else None,
            "mean_ndvi": round(float(group["ndvi"].mean()), 3),
            "mean_ndbi": round(float(group["ndbi"].mean()), 3),
            "mean_ndwi": round(float(group["ndwi"].mean()), 3),
        })

    df_loc_summary = pd.DataFrame(loc_summary_rows).sort_values("hotspot_frequency", ascending=False)

    # Map back to seasonal instances
    hot_df["hotspot_frequency"] = hot_df["location"].map(loc_freq_map)
    hot_df["hot_seasons_count"] = hot_df["location"].map(loc_count_map)
    hot_df["is_persistent_hotspot"] = hot_df["location"].map(loc_persistent_map)
    hot_df["persistence_tier"] = hot_df["hotspot_frequency"].apply(classify_persistence_tier)

    # Reorder columns to ensure prompt minimums are present
    ordered_cols = [
        "location",
        "year",
        "season",
        "lst_c",
        "top_1_percent",
        "top_20",
        "obs_count",
        "qa_k",
        "hotspot_frequency",
        "is_persistent_hotspot",
        "persistence_tier",
        "longitude",
        "latitude",
        "row",
        "col",
        "ndvi",
        "ndbi",
        "ndwi",
        "neighborhood_median",
        "pixel_minus_neighborhood_median",
        "valid_neighbor_count",
        "quality_flag",
    ]
    # Filter to available columns
    final_cols = [c for c in ordered_cols if c in hot_df.columns]
    df_seasonal_instances = hot_df[final_cols].sort_values(["year", "season", "lst_c"], ascending=[True, True, False])

    return df_seasonal_instances, df_loc_summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HEATSENSE AI: Multi-Season Hotspot Persistence Analysis",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to extreme_pixel_quality.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to output hotspot_persistence.csv",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=DEFAULT_SUMMARY_OUTPUT,
        help="Path to output hotspot_persistence_summary.csv",
    )
    parser.add_argument(
        "--persistence-threshold",
        type=float,
        default=0.25,
        help="Fraction of valid seasons required to classify as persistent (default: 0.25)",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    input_path: Path = args.input
    output_path: Path = args.output
    summary_path: Path = args.summary_output

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found at {input_path}")

    print("=" * 80)
    print("HEATSENSE AI — MULTI-SEASON HOTSPOT PERSISTENCE ANALYSIS")
    print("=" * 80)
    print(f"Reading extreme records from: {input_path}")

    df_extremes = pd.read_csv(input_path)
    print(f"Loaded {len(df_extremes)} total extreme records across {df_extremes['year'].nunique()} years.")

    df_instances, df_summary = compute_hotspot_persistence(
        df_extremes,
        persistence_thresh=args.persistence_threshold,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    df_instances.to_csv(output_path, index=False)
    print(f"Saved seasonal hotspot persistence: {output_path} ({len(df_instances)} records)")

    df_summary.to_csv(summary_path, index=False)
    print(f"Saved location persistence summary : {summary_path} ({len(df_summary)} unique locations)")

    # Print high-level summary
    chronic_cnt = len(df_summary[df_summary["persistence_tier"] == "chronic_hotspot"])
    frequent_cnt = len(df_summary[df_summary["persistence_tier"] == "frequent_hotspot"])
    occasional_cnt = len(df_summary[df_summary["persistence_tier"] == "occasional_hotspot"])
    transient_cnt = len(df_summary[df_summary["persistence_tier"] == "transient_extreme"])

    print("\nHotspot Persistence Tiers:")
    print(f"  - Chronic Hotspots  (>= 50% seasons) : {chronic_cnt} locations")
    print(f"  - Frequent Hotspots (25-49% seasons): {frequent_cnt} locations")
    print(f"  - Occasional Hotspots(10-24% seasons): {occasional_cnt} locations")
    print(f"  - Transient Extremes (< 10% seasons) : {transient_cnt} locations")

    # Inspect top persistent hotspot
    top_loc = df_summary.iloc[0]
    print(f"\nTop Persistent Hotspot: {top_loc['location']} (lon={top_loc['longitude']:.6f}, lat={top_loc['latitude']:.6f})")
    print(f"  Hot in {top_loc['hot_seasons_count']}/{top_loc['valid_seasons_count']} seasons (freq={top_loc['hotspot_frequency']:.2f})")
    print(f"  Max LST: {top_loc['max_lst_ever']} C | Mean OBS: {top_loc['mean_obs_count']}")


if __name__ == "__main__":
    main()
