"""Analysis Dataset Builder for HEATSENSE AI.

Converts seasonal multi-band COGs into tabular analysis datasets,
integrating pixel-quality diagnostics, multi-season hotspot persistence,
authoritative eligibility policies (A-D), and deterministic spatial blocks.

Optimized with vectorized C-level array processing for high performance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.mask
import rasterio.transform

from gis.quality.eligibility import EligibilityStatus

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BOUNDARY_PATH = PROJECT_ROOT / "data" / "raw" / "boundaries" / "surat_smc_boundary.geojson"
SEASONAL_COG_ROOT = PROJECT_ROOT / "data" / "processed" / "seasonal"
PERSISTENCE_SUMMARY_PATH = PROJECT_ROOT / "data" / "diagnostics" / "quality" / "hotspot_persistence_summary.csv"
SEASONAL_SUMMARY_PATH = PROJECT_ROOT / "data" / "diagnostics" / "quality" / "seasonal_quality_summary.csv"
EXTREMES_CSV_PATH = PROJECT_ROOT / "data" / "diagnostics" / "quality" / "extreme_pixel_quality.csv"
DEFAULT_SENSITIVITY_ROOT = PROJECT_ROOT / "data" / "processed" / "sensitivity"

SEASONS = ("winter", "summer", "monsoon", "post_monsoon")
START_YEAR = 2022
END_YEAR = 2026
TOTAL_SMC_GRID_CELLS = 50752


def assign_spatial_blocks(
    df: pd.DataFrame,
    block_size: int = 20,
) -> pd.DataFrame:
    """
    Assign deterministic spatial block identifiers based on grid row and column.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing 'row' and 'col' columns.
    block_size : int
        Grid cells per block side (default: 20, ~2km x 2km on 100m grid).

    Returns
    -------
    pd.DataFrame
        DataFrame with added 'block_id' column formatted as 'B_{row_block:02d}_{col_block:02d}'.
    """
    df = df.copy()
    b_rows = (df["row"] // block_size).astype(int)
    b_cols = (df["col"] // block_size).astype(int)
    df["block_id"] = b_rows.apply(lambda r: f"B_{r:02d}") + "_" + b_cols.apply(lambda c: f"{c:02d}")
    return df


def load_hotspot_persistence_map() -> tuple[dict[tuple[int, int], float], set[tuple[int, int]]]:
    """Load hotspot frequency map and persistent locations set."""
    freq_map: dict[tuple[int, int], float] = {}
    pers_set: set[tuple[int, int]] = set()

    if PERSISTENCE_SUMMARY_PATH.exists():
        df_p = pd.read_csv(PERSISTENCE_SUMMARY_PATH)
        for _, r in df_p.iterrows():
            loc = (int(r["row"]), int(r["col"]))
            freq = float(r["hotspot_frequency"])
            freq_map[loc] = freq
            if r.get("is_persistent_hotspot", False):
                pers_set.add(loc)

    return freq_map, pers_set


def load_qa_reference_data() -> tuple[dict[tuple[int, str], float], dict[tuple[int, str, int, int], float]]:
    """Load seasonal median QA values and exact sampled extreme QA values."""
    seasonal_qa_median: dict[tuple[int, str], float] = {}
    extreme_qa_map: dict[tuple[int, str, int, int], float] = {}

    if SEASONAL_SUMMARY_PATH.exists():
        df_s = pd.read_csv(SEASONAL_SUMMARY_PATH)
        for _, r in df_s.iterrows():
            seasonal_qa_median[(int(r["year"]), str(r["season"]))] = float(r["qa_p50"])

    if EXTREMES_CSV_PATH.exists():
        df_e = pd.read_csv(EXTREMES_CSV_PATH)
        for _, r in df_e.iterrows():
            if pd.notna(r.get("qa_k")):
                k = (int(r["year"]), str(r["season"]), int(r["row"]), int(r["col"]))
                extreme_qa_map[k] = float(r["qa_k"])

    return seasonal_qa_median, extreme_qa_map


def compute_vectorized_3x3_neighborhood(lst_grid: np.ndarray, nodata_val: float = -9999.0):
    """
    Compute non-circular 3x3 neighborhood statistics across the entire 2D grid
    using vectorized array shifts. Center pixel is strictly excluded.
    """
    arr = np.where(lst_grid == nodata_val, np.nan, lst_grid)
    padded = np.pad(arr, 1, constant_values=np.nan)

    # 8 neighbor shifts (excluding center pixel (1, 1))
    shifts = [
        padded[:-2, :-2], padded[:-2, 1:-1], padded[:-2, 2:],
        padded[1:-1, :-2],                   padded[1:-1, 2:],
        padded[2:, :-2],  padded[2:, 1:-1],  padded[2:, 2:]
    ]
    stack = np.stack(shifts, axis=0)

    # Suppress All-NaN slice warnings for areas far outside the city
    with np.errstate(all="ignore"):
        nbr_median = np.nanmedian(stack, axis=0)
        nbr_std = np.nanstd(stack, axis=0)

    valid_nbr_count = np.sum(~np.isnan(stack), axis=0).astype(np.int32)
    diff_med = arr - nbr_median
    abs_diff = np.abs(diff_med)

    return nbr_median, nbr_std, valid_nbr_count, diff_med, abs_diff


def load_seasonal_cog_df(
    cog_path: Path,
    boundary_geom: list[Any],
    year: int,
    season: str,
    policy_name: str,
    persistence_freq_map: dict[tuple[int, int], float],
    persistent_hotspots: set[tuple[int, int]],
    seasonal_qa_median: dict[tuple[int, str], float],
    extreme_qa_map: dict[tuple[int, str, int, int], float],
) -> pd.DataFrame | None:
    """
    Load a single seasonal COG, mask with SMC boundary, compute vectorized quality metrics,
    and evaluate eligibility under the specified policy.
    """
    if not cog_path.exists():
        return None

    with rasterio.open(cog_path) as src:
        masked_arr, _ = rasterio.mask.mask(src, boundary_geom, crop=False, nodata=-9999.0)
        transform = src.transform
        lst_grid = masked_arr[0]
        ndvi_grid = masked_arr[1]
        ndbi_grid = masked_arr[2]
        ndwi_grid = masked_arr[3]
        obs_grid = masked_arr[4]

    valid_mask = (lst_grid != -9999.0) & np.isfinite(lst_grid) & (obs_grid > 0)
    if not np.any(valid_mask):
        return None

    # Vectorized 3x3 non-circular neighborhood
    nbr_median, nbr_std, valid_nbr_count, diff_med, abs_diff = compute_vectorized_3x3_neighborhood(lst_grid)

    grid_rows, grid_cols = lst_grid.shape
    is_edge = np.zeros_like(lst_grid, dtype=bool)
    is_edge[0, :] = is_edge[-1, :] = is_edge[:, 0] = is_edge[:, -1] = True
    is_boundary = is_edge | (valid_nbr_count < 4)

    # Persistent hotspot boolean grid
    is_pers_grid = np.zeros_like(lst_grid, dtype=bool)
    for (r, c) in persistent_hotspots:
        if 0 <= r < grid_rows and 0 <= c < grid_cols:
            is_pers_grid[r, c] = True

    pol = policy_name.lower().strip()

    # Vectorized eligibility determination
    obs_val = obs_grid
    if pol == "policy_a":
        # OBS >= 2: ACCEPT; OBS == 1: FLAG; OBS < 1: EXCLUDE
        elig_grid = np.where(obs_val >= 2, EligibilityStatus.ACCEPT.value,
                             np.where(obs_val == 1, EligibilityStatus.FLAG.value, EligibilityStatus.EXCLUDE.value))
    elif pol == "policy_b":
        # OBS >= 2: ACCEPT; OBS < 2: EXCLUDE
        elig_grid = np.where(obs_val >= 2, EligibilityStatus.ACCEPT.value, EligibilityStatus.EXCLUDE.value)
    elif pol == "policy_c":
        # OBS >= 2: ACCEPT; OBS == 1 & persistent: FLAG; else EXCLUDE
        elig_grid = np.where(obs_val >= 2, EligibilityStatus.ACCEPT.value,
                             np.where((obs_val == 1) & is_pers_grid, EligibilityStatus.FLAG.value, EligibilityStatus.EXCLUDE.value))
    elif pol == "policy_d":
        # OBS >= 2: ACCEPT
        # OBS == 1 & severe spatial anomaly (abs_diff > 10.0): EXCLUDE
        # OBS == 1 & spatially coherent: FLAG
        severe_anomaly = (obs_val == 1) & (abs_diff > 10.0)
        elig_grid = np.where(obs_val >= 2, EligibilityStatus.ACCEPT.value,
                             np.where(severe_anomaly, EligibilityStatus.EXCLUDE.value,
                                      np.where(obs_val == 1, EligibilityStatus.FLAG.value, EligibilityStatus.EXCLUDE.value)))
    else:
        raise ValueError(f"Unknown policy '{policy_name}'")

    rows_idx, cols_idx = np.where(valid_mask)
    xs, ys = rasterio.transform.xy(transform, rows_idx, cols_idx, offset="center")

    default_qa = seasonal_qa_median.get((year, season), 2.5)

    # QA extraction (fast map lookup)
    qa_vals = np.full(len(rows_idx), default_qa, dtype=np.float32)
    for i, (r, c) in enumerate(zip(rows_idx, cols_idx)):
        k = (year, season, r, c)
        if k in extreme_qa_map:
            qa_vals[i] = extreme_qa_map[k]

    # Hotspot frequency map lookup
    hot_freqs = np.zeros(len(rows_idx), dtype=np.float32)
    for i, (r, c) in enumerate(zip(rows_idx, cols_idx)):
        loc = (r, c)
        if loc in persistence_freq_map:
            hot_freqs[i] = persistence_freq_map[loc]

    # Condition flags vectorization
    is_low_obs = obs_grid[valid_mask] <= 1
    is_spat_anom = (valid_nbr_count[valid_mask] >= 4) & (abs_diff[valid_mask] > 10.0)
    is_spat_coh = (valid_nbr_count[valid_mask] >= 4) & (abs_diff[valid_mask] <= 10.0)
    is_bound_pix = is_boundary[valid_mask]

    flag_strings = []
    for lo, sa, sc, bp in zip(is_low_obs, is_spat_anom, is_spat_coh, is_bound_pix):
        f = []
        if lo:
            f.append("LOW_TEMPORAL_SUPPORT")
        if sa:
            f.append("SPATIAL_ANOMALY")
        elif sc:
            f.append("SPATIALLY_COHERENT")
        if bp:
            f.append("BOUNDARY_CONTEXT")
        if lo and sa:
            f.append("LOW_SUPPORT_SPATIAL_EXTREME")
        if not f:
            f.append("VALID")
        flag_strings.append(";".join(f))

    df = pd.DataFrame({
        "year": year,
        "season": season,
        "row": rows_idx,
        "col": cols_idx,
        "longitude": np.round(xs, 6),
        "latitude": np.round(ys, 6),
        "LST_C": np.round(lst_grid[valid_mask], 4),
        "NDVI": np.round(ndvi_grid[valid_mask], 4),
        "NDBI": np.round(ndbi_grid[valid_mask], 4),
        "NDWI": np.round(ndwi_grid[valid_mask], 4),
        "LST_OBS_COUNT": np.round(obs_grid[valid_mask], 1),
        "LST_QA_MEDIAN_K": np.round(qa_vals, 3),
        "quality_flag": flag_strings,
        "eligibility": elig_grid[valid_mask],
        "hotspot_frequency": np.round(hot_freqs, 4),
        "is_persistent_hotspot": is_pers_grid[valid_mask],
        "neighborhood_median": np.round(nbr_median[valid_mask], 4),
        "neighborhood_std": np.round(nbr_std[valid_mask], 4),
        "pixel_minus_neighborhood_median": np.round(diff_med[valid_mask], 4),
        "absolute_pixel_minus_neighborhood_median": np.round(abs_diff[valid_mask], 4),
        "valid_neighbor_count": valid_nbr_count[valid_mask],
        "is_boundary_context": is_boundary[valid_mask],
        "is_partial_season": (year == 2026 and season == "monsoon"),
    })

    return df


def build_analysis_dataset(
    policy_name: str,
    years: list[int] | None = None,
    seasons: list[str] | None = None,
    block_size: int = 20,
    output_dir: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build the full multi-seasonal analysis dataset for a given policy.

    Parameters
    ----------
    policy_name : str
        One of "policy_a", "policy_b", "policy_c", "policy_d".
    years : list[int] | None
        Target years (default: 2022-2026).
    seasons : list[str] | None
        Target seasons (default: winter, summer, monsoon, post_monsoon).
    block_size : int
        Grid cells per spatial block.
    output_dir : Path | None
        Directory to save analysis.parquet and summary.json.

    Returns
    -------
    tuple[pd.DataFrame, dict[str, Any]]
        (df_retained_analysis, summary_dict)
    """
    target_years = years or list(range(START_YEAR, END_YEAR + 1))
    target_seasons = seasons or list(SEASONS)

    if not BOUNDARY_PATH.exists():
        raise FileNotFoundError(f"SMC Boundary not found at {BOUNDARY_PATH}")

    gdf_boundary = gpd.read_file(BOUNDARY_PATH).to_crs("EPSG:4326")
    boundary_geom = [gdf_boundary.geometry.union_all()]

    freq_map, pers_set = load_hotspot_persistence_map()
    qa_med_map, extreme_qa_map = load_qa_reference_data()

    all_dfs: list[pd.DataFrame] = []
    seasonal_summaries: list[dict[str, Any]] = []

    total_input_pixels = 0
    total_retained_pixels = 0
    total_flagged_pixels = 0
    total_excluded_pixels = 0

    for y in target_years:
        for s in target_seasons:
            cog_path = SEASONAL_COG_ROOT / str(y) / s / f"surat_{y}_{s}_features_cog.tif"
            if not cog_path.exists():
                continue

            df_season = load_seasonal_cog_df(
                cog_path=cog_path,
                boundary_geom=boundary_geom,
                year=y,
                season=s,
                policy_name=policy_name,
                persistence_freq_map=freq_map,
                persistent_hotspots=pers_set,
                seasonal_qa_median=qa_med_map,
                extreme_qa_map=extreme_qa_map,
            )

            if df_season is None or df_season.empty:
                continue

            n_in = len(df_season)
            total_input_pixels += n_in

            # Retain ACCEPT and FLAG
            retained_mask = df_season["eligibility"].isin([EligibilityStatus.ACCEPT.value, EligibilityStatus.FLAG.value])
            df_retained = df_season[retained_mask].copy()

            n_ret = len(df_retained)
            n_flag = int(np.sum(df_season["eligibility"] == EligibilityStatus.FLAG.value))
            n_excl = int(np.sum(df_season["eligibility"] == EligibilityStatus.EXCLUDE.value))

            total_retained_pixels += n_ret
            total_flagged_pixels += n_flag
            total_excluded_pixels += n_excl

            ret_pct = round((n_ret / n_in) * 100.0, 2)
            cov_pct = round((n_ret / TOTAL_SMC_GRID_CELLS) * 100.0, 2)

            all_dfs.append(df_retained)

            seasonal_summaries.append({
                "year": y,
                "season": s,
                "is_partial_season": bool(y == 2026 and s == "monsoon"),
                "input_pixels": n_in,
                "retained_pixels": n_ret,
                "flagged_pixels": n_flag,
                "excluded_pixels": n_excl,
                "retention_percent": ret_pct,
                "spatial_coverage": cov_pct,
                "LST_min": round(float(df_retained["LST_C"].min()), 2) if n_ret > 0 else None,
                "LST_p95": round(float(np.percentile(df_retained["LST_C"], 95)), 2) if n_ret > 0 else None,
                "LST_p99": round(float(np.percentile(df_retained["LST_C"], 99)), 2) if n_ret > 0 else None,
                "LST_max": round(float(df_retained["LST_C"].max()), 2) if n_ret > 0 else None,
            })

    if not all_dfs:
        raise RuntimeError(f"No valid seasonal data found for policy {policy_name}")

    full_df = pd.concat(all_dfs, ignore_index=True)

    # Assign deterministic spatial blocks
    full_df = assign_spatial_blocks(full_df, block_size=block_size)

    # Validate dataset integrity
    assert "LST_C" in full_df.columns, "Target LST_C missing"
    assert np.all(np.isfinite(full_df["LST_C"])), "Non-finite LST_C found in analysis dataset"
    assert "block_id" in full_df.columns, "Spatial block_id missing"

    summary_meta = {
        "policy": policy_name,
        "block_size": block_size,
        "total_input_pixels": total_input_pixels,
        "total_retained_pixels": total_retained_pixels,
        "total_flagged_pixels": total_flagged_pixels,
        "total_excluded_pixels": total_excluded_pixels,
        "overall_retention_percent": round((total_retained_pixels / total_input_pixels) * 100.0, 2),
        "unique_blocks_count": int(full_df["block_id"].nunique()),
        "seasonal_breakdown": seasonal_summaries,
    }

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        parquet_file = output_dir / "analysis.parquet"
        full_df.to_parquet(parquet_file, index=False)

        summary_file = output_dir / "summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary_meta, f, indent=2)

    return full_df, summary_meta
