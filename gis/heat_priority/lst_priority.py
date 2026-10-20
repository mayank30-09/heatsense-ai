"""Thermal Severity and Land-Cover Deficit Components for Heat Priority.

Evaluates empirical thermal severity grounded strictly in observed satellite LST,
vegetation canopy deficit from NDVI, and built-up density from NDBI.

Scientific Invariants:
1. Observed LST is PRIMARY THERMAL EVIDENCE (never substituted by model predictions).
2. Clamping ensures all components are strictly bounded in [0.0, 1.0].
3. Missing or sentinel values are preserved as NaN and never falsely imputed as 0.0.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import rankdata

# Canonical baseline normalization constants
DEFAULT_T_MIN: float = 30.0  # Cool surface baseline (deg C)
DEFAULT_T_MAX: float = 50.0  # Urban thermal ceiling (deg C)

DEFAULT_NDVI_MIN: float = 0.05    # Minimum vegetated / paved threshold
DEFAULT_NDVI_TARGET: float = 0.45  # Optimal urban canopy target

DEFAULT_NDBI_MIN: float = -0.25   # Pervious / vegetated baseline
DEFAULT_NDBI_MAX: float = 0.15    # High density built-up ceiling


def normalize_lst_severity(
    observed_lst: np.ndarray | pd.Series,
    t_min: float = DEFAULT_T_MIN,
    t_max: float = DEFAULT_T_MAX,
    valid_mask: np.ndarray | pd.Series | None = None,
) -> np.ndarray:
    """
    Compute bounded thermal severity score [0.0, 1.0] from observed summer LST.

    Parameters
    ----------
    observed_lst : np.ndarray or pd.Series
        Array of observed Land Surface Temperatures (deg C).
    t_min : float, default 30.0
        Lower normalization bound (deg C).
    t_max : float, default 50.0
        Upper normalization bound (deg C).
    valid_mask : np.ndarray or pd.Series, optional
        Boolean mask of valid pixels.

    Returns
    -------
    np.ndarray
        Thermal severity values in [0.0, 1.0] for valid pixels (NaN for invalid).
    """
    if t_max <= t_min:
        raise ValueError(f"t_max ({t_max}) must be strictly greater than t_min ({t_min})")

    obs = np.asarray(observed_lst, dtype=np.float64)

    if valid_mask is None:
        mask = np.isfinite(obs) & (obs > -9000.0)
    else:
        mask = np.asarray(valid_mask, dtype=bool) & np.isfinite(obs) & (obs > -9000.0)

    severity = np.full(obs.shape, np.nan, dtype=np.float64)
    if not np.any(mask):
        return severity

    norm_vals = (obs[mask] - t_min) / (t_max - t_min)
    severity[mask] = np.clip(norm_vals, 0.0, 1.0)
    return severity


def compute_vegetation_deficit(
    ndvi: np.ndarray | pd.Series,
    v_min: float = DEFAULT_NDVI_MIN,
    v_target: float = DEFAULT_NDVI_TARGET,
    valid_mask: np.ndarray | pd.Series | None = None,
) -> np.ndarray:
    """
    Compute vegetation canopy deficit [0.0, 1.0] from NDVI.

    When NDVI >= v_target, deficit is 0.0 (ample vegetation).
    When NDVI <= v_min, deficit is 1.0 (severe canopy deficit).
    """
    if v_target <= v_min:
        raise ValueError(f"v_target ({v_target}) must be strictly greater than v_min ({v_min})")

    vals = np.asarray(ndvi, dtype=np.float64)

    if valid_mask is None:
        mask = np.isfinite(vals) & (vals >= -1.0) & (vals <= 1.0)
    else:
        mask = np.asarray(valid_mask, dtype=bool) & np.isfinite(vals) & (vals >= -1.0) & (vals <= 1.0)

    deficit = np.full(vals.shape, np.nan, dtype=np.float64)
    if not np.any(mask):
        return deficit

    def_vals = (v_target - vals[mask]) / (v_target - v_min)
    deficit[mask] = np.clip(def_vals, 0.0, 1.0)
    return deficit


def compute_builtup_density(
    ndbi: np.ndarray | pd.Series,
    b_min: float = DEFAULT_NDBI_MIN,
    b_max: float = DEFAULT_NDBI_MAX,
    valid_mask: np.ndarray | pd.Series | None = None,
) -> np.ndarray:
    """
    Compute built-up density component [0.0, 1.0] from NDBI.

    When NDBI <= b_min, density is 0.0 (pervious / open).
    When NDBI >= b_max, density is 1.0 (high-density impervious built-up).
    """
    if b_max <= b_min:
        raise ValueError(f"b_max ({b_max}) must be strictly greater than b_min ({b_min})")

    vals = np.asarray(ndbi, dtype=np.float64)

    if valid_mask is None:
        mask = np.isfinite(vals) & (vals >= -1.0) & (vals <= 1.0)
    else:
        mask = np.asarray(valid_mask, dtype=bool) & np.isfinite(vals) & (vals >= -1.0) & (vals <= 1.0)

    density = np.full(vals.shape, np.nan, dtype=np.float64)
    if not np.any(mask):
        return density

    den_vals = (vals[mask] - b_min) / (b_max - b_min)
    density[mask] = np.clip(den_vals, 0.0, 1.0)
    return density


def compute_lst_severity(
    observed_lst: np.ndarray | pd.Series,
    valid_mask: np.ndarray | pd.Series | None = None,
) -> np.ndarray:
    """
    Compute empirical thermal severity percentile ranking [0.0, 1.0] from observed LST.
    Preserved for backward-compatibility with Stage B evaluation suites.
    """
    obs = np.asarray(observed_lst, dtype=np.float64)

    if valid_mask is None:
        mask = np.isfinite(obs) & (obs > -9000.0)
    else:
        mask = np.asarray(valid_mask, dtype=bool) & np.isfinite(obs) & (obs > -9000.0)

    severity = np.full(obs.shape, np.nan, dtype=np.float64)
    valid_vals = obs[mask]
    n_valid = len(valid_vals)

    if n_valid == 0:
        return severity
    if n_valid == 1:
        severity[mask] = 1.0
        return severity

    ranks = rankdata(valid_vals, method="average")
    percentiles = (ranks - 1.0) / (n_valid - 1.0)
    severity[mask] = np.clip(percentiles, 0.0, 1.0)
    return severity
