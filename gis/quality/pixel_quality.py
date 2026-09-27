"""Pixel Quality Diagnostic Calculations for HEATSENSE AI.

This module provides purely diagnostic calculation functions for Landsat LST
and optical feature rasters. It evaluates temporal support, spatial consistency
(3x3 non-circular neighborhood), boundary/edge context, extreme-value status,
and radiometric QA uncertainty.

IMPORTANT: This module does NOT make eligibility or filtering decisions.
It calculates quality indicators and condition flags only.
Policy decisions are exclusively handled by `gis.quality.eligibility`.
"""

from __future__ import annotations

from typing import Any
import numpy as np


# ---------------------------------------------------------------------------
# Temporal Support Diagnostic
# ---------------------------------------------------------------------------

def classify_temporal_support(
    obs_count: float | int | None,
    thresholds: tuple[int, int] = (2, 4),
) -> str:
    """
    Classify observation support count into exploratory categories.

    Parameters
    ----------
    obs_count : float | int | None
        Number of valid clear-sky scenes contributing to the pixel composite.
    thresholds : tuple[int, int]
        Cutoffs (low_limit, high_limit). Default: (2, 4).
        - obs < 2: "low" (single-pass or no observation)
        - 2 <= obs < 4: "moderate"
        - obs >= 4: "high"

    Returns
    -------
    str
        "low", "moderate", "high", or "unknown".
    """
    if obs_count is None or not np.isfinite(obs_count) or obs_count < 0:
        return "unknown"

    low_thresh, high_thresh = thresholds
    if obs_count < low_thresh:
        return "low"
    elif obs_count < high_thresh:
        return "moderate"
    else:
        return "high"


# ---------------------------------------------------------------------------
# Spatial Consistency: 3x3 Neighborhood Metrics
# ---------------------------------------------------------------------------

def compute_neighborhood_metrics(
    grid: np.ndarray,
    row: int,
    col: int,
    nodata_val: float = -9999.0,
) -> dict[str, float | int | None]:
    """
    Calculate 3x3 neighborhood statistics on a raster grid strictly EXCLUDING
    the center pixel to prevent circularity.

    Parameters
    ----------
    grid : np.ndarray
        2D raster array (e.g. LST_C).
    row : int
        Row index of the center pixel.
    col : int
        Column index of the center pixel.
    nodata_val : float
        Value denoting invalid/unobserved cells (default: -9999.0).

    Returns
    -------
    dict[str, float | int | None]
        - neighborhood_median: float | None
        - neighborhood_mean: float | None
        - neighborhood_std: float | None
        - valid_neighbor_count: int (0 to 8)
        - pixel_minus_neighborhood_median: float | None
        - absolute_pixel_minus_neighborhood_median: float | None
    """
    rows, cols = grid.shape
    center_val = grid[row, col]

    neighbors: list[float] = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = row + dr, col + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                val = grid[nr, nc]
                if val != nodata_val and np.isfinite(val):
                    neighbors.append(float(val))

    valid_count = len(neighbors)
    if valid_count == 0:
        return {
            "neighborhood_median": None,
            "neighborhood_mean": None,
            "neighborhood_std": None,
            "valid_neighbor_count": 0,
            "pixel_minus_neighborhood_median": None,
            "absolute_pixel_minus_neighborhood_median": None,
        }

    n_med = float(np.median(neighbors))
    n_mean = float(np.mean(neighbors))
    n_std = float(np.std(neighbors))

    if center_val != nodata_val and np.isfinite(center_val):
        diff_med = float(center_val - n_med)
        abs_diff = float(abs(diff_med))
    else:
        diff_med = None
        abs_diff = None

    return {
        "neighborhood_median": round(n_med, 4),
        "neighborhood_mean": round(n_mean, 4),
        "neighborhood_std": round(n_std, 4),
        "valid_neighbor_count": valid_count,
        "pixel_minus_neighborhood_median": round(diff_med, 4) if diff_med is not None else None,
        "absolute_pixel_minus_neighborhood_median": round(abs_diff, 4) if abs_diff is not None else None,
    }


# ---------------------------------------------------------------------------
# Boundary / Raster Edge Context
# ---------------------------------------------------------------------------

def evaluate_boundary_context(
    row: int,
    col: int,
    rows: int,
    cols: int,
    valid_neighbor_count: int,
    min_neighbors: int = 4,
) -> dict[str, bool]:
    """
    Evaluate whether a pixel resides in a boundary, edge, or NoData context.

    Parameters
    ----------
    row : int
        Row index.
    col : int
        Column index.
    rows : int
        Total grid rows.
    cols : int
        Total grid columns.
    valid_neighbor_count : int
        Number of valid 3x3 neighbors.
    min_neighbors : int
        Threshold for sufficient neighbor coverage (default: 4 of 8).

    Returns
    -------
    dict[str, bool]
        - is_raster_edge: bool (perimeter row or column of raster)
        - insufficient_neighborhood: bool (fewer than min_neighbors valid cells)
        - is_boundary_context: bool (edge OR insufficient neighbors)
    """
    is_edge = (row == 0 or row == rows - 1 or col == 0 or col == cols - 1)
    is_insufficient = (valid_neighbor_count < min_neighbors)
    return {
        "is_raster_edge": is_edge,
        "insufficient_neighborhood": is_insufficient,
        "is_boundary_context": is_edge or is_insufficient,
    }


# ---------------------------------------------------------------------------
# Extreme Status Classification
# ---------------------------------------------------------------------------

def classify_extreme_status(
    lst_c: float | None,
    p_low: float,
    p_high: float,
    rank_hot: int | None = None,
    rank_cold: int | None = None,
    top_n: int = 20,
    bottom_n: int = 20,
) -> list[str]:
    """
    Classify whether an LST value belongs to extreme upper or lower percentiles
    or absolute ranked subsets.

    Parameters
    ----------
    lst_c : float | None
        Land surface temperature in Celsius.
    p_low : float
        Lower percentile threshold (e.g. P01).
    p_high : float
        Upper percentile threshold (e.g. P99).
    rank_hot : int | None
        1-based rank from highest LST downward.
    rank_cold : int | None
        1-based rank from lowest LST upward.
    top_n : int
        Cutoff for absolute hottest ranks (default: 20).
    bottom_n : int
        Cutoff for absolute coldest ranks (default: 20).

    Returns
    -------
    list[str]
        List of matching extreme tags (e.g. ["hot_top_20", "hot_top_1pct"]),
        or ["normal"] if not extreme.
    """
    if lst_c is None or not np.isfinite(lst_c):
        return ["invalid"]

    tags: list[str] = []

    if rank_hot is not None and 1 <= rank_hot <= top_n:
        tags.append(f"hot_top_{top_n}")
    if lst_c >= p_high:
        tags.append("hot_top_1pct")

    if rank_cold is not None and 1 <= rank_cold <= bottom_n:
        tags.append(f"cold_bottom_{bottom_n}")
    if lst_c <= p_low:
        tags.append("cold_bottom_1pct")

    return tags if tags else ["normal"]


# ---------------------------------------------------------------------------
# Radiometric QA Uncertainty Diagnostic
# ---------------------------------------------------------------------------

def classify_qa_uncertainty(
    qa_k: float | None,
    thresholds: tuple[float, float] = (5.0, 15.0),
) -> str:
    """
    Classify USGS Level-2 ST_QA radiometric uncertainty in Kelvin.

    Parameters
    ----------
    qa_k : float | None
        Median ST_QA uncertainty in Kelvin.
    thresholds : tuple[float, float]
        Cutoffs (moderate_limit, high_limit). Default: (5.0, 15.0).

    Returns
    -------
    str
        "low_uncertainty", "moderate_uncertainty", "high_uncertainty", or "unknown".
    """
    if qa_k is None or not np.isfinite(qa_k):
        return "unknown"

    low_lim, high_lim = thresholds
    if qa_k < low_lim:
        return "low_uncertainty"
    elif qa_k < high_lim:
        return "moderate_uncertainty"
    else:
        return "high_uncertainty"


# ---------------------------------------------------------------------------
# Quality Flag Assignment
# ---------------------------------------------------------------------------

def assign_quality_flags(
    obs_count: float | int | None,
    qa_k: float | None,
    abs_diff_med: float | None,
    valid_neighbor_count: int,
    is_boundary: bool,
    anomaly_diff_thresh: float = 10.0,
    min_neighbors: int = 4,
    low_obs_thresh: int = 1,
    high_qa_thresh: float = 15.0,
) -> list[str]:
    """
    Identify specific diagnostic quality conditions for a pixel.

    Conditions detected:
    - VALID: No anomalies or low-support conditions.
    - LOW_TEMPORAL_SUPPORT: obs_count <= low_obs_thresh (e.g. 1 scene).
    - SPATIAL_ANOMALY: abs_diff_med > anomaly_diff_thresh with sufficient neighbors.
    - SPATIALLY_COHERENT: abs_diff_med <= anomaly_diff_thresh with sufficient neighbors.
    - BOUNDARY_CONTEXT: is_boundary is True or valid_neighbor_count < min_neighbors.
    - HIGH_RETRIEVAL_UNCERTAINTY: qa_k > high_qa_thresh.
    - LOW_SUPPORT_SPATIAL_EXTREME: obs_count <= low_obs_thresh AND abs_diff_med > anomaly_diff_thresh.

    Returns
    -------
    list[str]
        List of condition flags.
    """
    flags: list[str] = []

    # Check temporal support
    has_low_obs = False
    if obs_count is not None and np.isfinite(obs_count) and obs_count <= low_obs_thresh:
        flags.append("LOW_TEMPORAL_SUPPORT")
        has_low_obs = True

    # Check spatial consistency
    has_spatial_anomaly = False
    if abs_diff_med is not None and np.isfinite(abs_diff_med):
        if valid_neighbor_count >= min_neighbors:
            if abs_diff_med > anomaly_diff_thresh:
                flags.append("SPATIAL_ANOMALY")
                has_spatial_anomaly = True
            else:
                flags.append("SPATIALLY_COHERENT")

    # Boundary context
    if is_boundary or valid_neighbor_count < min_neighbors:
        flags.append("BOUNDARY_CONTEXT")

    # High radiometric uncertainty
    if qa_k is not None and np.isfinite(qa_k) and qa_k > high_qa_thresh:
        flags.append("HIGH_RETRIEVAL_UNCERTAINTY")

    # Interaction: low support + spatial anomaly
    if has_low_obs and has_spatial_anomaly:
        flags.append("LOW_SUPPORT_SPATIAL_EXTREME")

    if not flags:
        flags.append("VALID")

    return flags
