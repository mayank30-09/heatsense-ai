"""Deterministic Optical Sentinel (-9999) Imputation and Guardrails.

Handles invalid or sentinel optical index values (-9999, NaN, out of bounds)
using a deterministic 8-connected Moore neighborhood window.

Scientific Invariants:
1. Optical sentinels are MISSING DATA, not physical measurements.
2. Imputation is strictly deterministic (median for >=4 valid, mean for 1-3, neutral fallback for 0).
3. Every imputed cell receives an auditable flag and a confidence multiplier penalty.
4. Imputed cells are strictly DISQUALIFIED from ML counterfactual cooling simulations.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

OPTICAL_SENTINEL_THRESHOLD: float = -9000.0

# Neutral fallback defaults
NEUTRAL_OPTICAL_FALLBACK: dict[str, float] = {
    "NDVI": 0.20,
    "NDBI": 0.00,
    "NDWI": -0.30,
}

# Confidence multipliers per imputation tier
CONFIDENCE_SENTINEL_CLEAN: float = 1.00
CONFIDENCE_SENTINEL_MEDIAN: float = 0.70
CONFIDENCE_SENTINEL_BOUNDARY: float = 0.50
CONFIDENCE_SENTINEL_NEUTRAL: float = 0.30

FLAG_CLEAN: str = "NONE"
FLAG_MEDIAN: str = "OPTICAL_IMPUTED_MEDIAN"
FLAG_BOUNDARY: str = "OPTICAL_IMPUTED_BOUNDARY"
FLAG_NEUTRAL: str = "OPTICAL_FALLBACK_NEUTRAL"


def is_optical_invalid(val: Any) -> bool | np.ndarray:
    """Check if value is a sentinel, NaN, Inf, or out of [-1.0, 1.0]."""
    if isinstance(val, (pd.Series, pd.Index)):
        s = pd.to_numeric(val, errors="coerce")
        arr = s.to_numpy(dtype=np.float64)
    elif val is pd.NA:
        return True
    else:
        try:
            arr = np.asarray(val, dtype=np.float64)
        except (TypeError, ValueError):
            s = pd.to_numeric(pd.Series(val), errors="coerce")
            arr = s.to_numpy(dtype=np.float64)

    invalid = (
        ~np.isfinite(arr)
        | (arr <= OPTICAL_SENTINEL_THRESHOLD)
        | (arr < -1.0)
        | (arr > 1.0)
    )
    return invalid if np.ndim(arr) > 0 else bool(invalid)


def impute_optical_raster(
    grid_2d: np.ndarray,
    index_name: str = "NDVI",
    valid_land_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Impute invalid optical index pixels across a 2D raster grid using 8-connected Moore neighborhood.

    Parameters
    ----------
    grid_2d : np.ndarray
        2D array of shape (height, width) containing optical index values.
    index_name : str, default 'NDVI'
        Name of the optical index for default fallback mapping ('NDVI', 'NDBI', 'NDWI').
    valid_land_mask : np.ndarray, optional
        Boolean 2D mask of active study area pixels.

    Returns
    -------
    tuple of (imputed_grid, flags_grid, c_sentinel_grid)
        - imputed_grid: 2D Float32 array with imputed values.
        - flags_grid: 2D object/str array with imputation flag strings.
        - c_sentinel_grid: 2D Float32 array with confidence multipliers [0.30, 1.00].
    """
    if grid_2d.ndim != 2:
        raise ValueError(f"grid_2d must be 2D, got shape {grid_2d.shape}")

    h, w = grid_2d.shape
    arr = np.asarray(grid_2d, dtype=np.float32).copy()

    # Identify invalid optical pixels
    invalid_mask = is_optical_invalid(arr)
    if valid_land_mask is not None:
        invalid_mask = invalid_mask & np.asarray(valid_land_mask, dtype=bool)

    flags = np.full((h, w), FLAG_CLEAN, dtype=object)
    c_sentinel = np.full((h, w), CONFIDENCE_SENTINEL_CLEAN, dtype=np.float32)

    if not np.any(invalid_mask):
        return arr, flags, c_sentinel

    # Prepare array where invalid values are NaN for clean neighborhood slicing
    valid_vals = np.where(is_optical_invalid(arr), np.nan, arr)
    padded = np.pad(valid_vals, 1, constant_values=np.nan)

    # 8-connected neighbor shifts
    shifts = [
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    ]

    invalid_rows, invalid_cols = np.where(invalid_mask)
    fallback_val = NEUTRAL_OPTICAL_FALLBACK.get(index_name.upper(), 0.0)

    for r, c in zip(invalid_rows, invalid_cols):
        pr, pc = r + 1, c + 1
        nbr_vals = []
        for dr, dc in shifts:
            val = padded[pr + dr, pc + dc]
            if np.isfinite(val) and -1.0 <= val <= 1.0:
                nbr_vals.append(val)

        n_valid = len(nbr_vals)
        if n_valid >= 4:
            arr[r, c] = float(np.median(nbr_vals))
            flags[r, c] = FLAG_MEDIAN
            c_sentinel[r, c] = CONFIDENCE_SENTINEL_MEDIAN
        elif 1 <= n_valid <= 3:
            arr[r, c] = float(np.mean(nbr_vals))
            flags[r, c] = FLAG_BOUNDARY
            c_sentinel[r, c] = CONFIDENCE_SENTINEL_BOUNDARY
        else:
            arr[r, c] = float(fallback_val)
            flags[r, c] = FLAG_NEUTRAL
            c_sentinel[r, c] = CONFIDENCE_SENTINEL_NEUTRAL

    return arr, flags, c_sentinel


def is_disqualified_from_ml_scenario(
    imputation_flag: str | np.ndarray | pd.Series,
) -> bool | np.ndarray | pd.Series:
    """Return True if pixel relies on optical imputation, disqualifying it from ML cooling projections."""
    if isinstance(imputation_flag, pd.Series):
        return imputation_flag != FLAG_CLEAN
    elif isinstance(imputation_flag, np.ndarray):
        return imputation_flag != FLAG_CLEAN
    else:
        return str(imputation_flag) != FLAG_CLEAN
