"""Heat Persistence Layer and Chronic Hotspot Classification.

Evaluates multi-season recurrence of extreme surface temperatures across 19 seasons.
Distinguishes transient thermal anomalies from chronic urban heat accumulation.

Scientific Invariants:
1. Recurrence is normalized by valid observed seasons (never cloud-missing seasons).
2. Chronic hotspot classification requires multi-year recurrence (>= 2 distinct calendar years).
3. 4 observations within a single calendar year CANNOT qualify as a chronic hotspot.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from gis.quality.hotspot_definitions import (
    CHRONIC_HOTSPOT_FREQ_THRESHOLD,
    PERSISTENT_HOTSPOT_FREQ_THRESHOLD,
    classify_hotspot_tier,
)

MIN_CHRONIC_SEASONS: int = 3
MIN_CHRONIC_YEARS: int = 2
MIN_ARCHIVE_VALID_SEASONS: int = 4


def compute_heat_persistence(
    hotspot_frequency: np.ndarray | pd.Series,
    is_persistent_hotspot: np.ndarray | pd.Series | None = None,
    valid_mask: np.ndarray | pd.Series | None = None,
    valid_seasons_count: np.ndarray | pd.Series | None = None,
    min_valid_seasons: int = MIN_ARCHIVE_VALID_SEASONS,
) -> np.ndarray:
    """
    Compute normalized multi-season heat persistence score [0.0, 1.0].

    Parameters
    ----------
    hotspot_frequency : np.ndarray or pd.Series
        Fraction of observed seasons the cell was in upper LST percentiles [0.0, 1.0].
    is_persistent_hotspot : np.ndarray or pd.Series, optional
        Precomputed persistence boolean flag from multi-season analysis.
    valid_mask : np.ndarray or pd.Series, optional
        Boolean mask of valid pixels.
    valid_seasons_count : np.ndarray or pd.Series, optional
        Number of valid observed seasons supporting the cell across the multi-year archive.
        If valid_seasons_count < min_valid_seasons (default 4), persistence score is 0.0.
    min_valid_seasons : int, default 4
        Minimum multi-season archive support required for non-zero persistence.

    Returns
    -------
    np.ndarray
        Persistence scores in [0.0, 1.0].
    """
    freq = np.asarray(hotspot_frequency, dtype=np.float64)

    if valid_mask is None:
        mask = np.isfinite(freq) & (freq >= 0.0)
    else:
        mask = np.asarray(valid_mask, dtype=bool) & np.isfinite(freq) & (freq >= 0.0)

    persistence = np.full(freq.shape, np.nan, dtype=np.float64)
    base_score = np.clip(freq[mask], 0.0, 1.0)

    if is_persistent_hotspot is not None:
        pers_flag = np.asarray(is_persistent_hotspot, dtype=bool)[mask]
        base_score = np.where(pers_flag, np.maximum(base_score, PERSISTENT_HOTSPOT_FREQ_THRESHOLD), base_score)

    if valid_seasons_count is not None:
        val_cnt = np.asarray(valid_seasons_count, dtype=np.int64)
        if np.ndim(val_cnt) == 0:
            if val_cnt < min_valid_seasons:
                base_score = np.zeros_like(base_score)
        else:
            insufficient = val_cnt[mask] < min_valid_seasons
            base_score = np.where(insufficient, 0.0, base_score)

    persistence[mask] = base_score
    return persistence


def classify_chronic_hotspots(
    hotspot_frequency: np.ndarray | pd.Series,
    hot_seasons_count: np.ndarray | pd.Series,
    distinct_years_count: np.ndarray | pd.Series,
    valid_seasons_count: np.ndarray | pd.Series,
    qualifying_obs_ge_2_count: np.ndarray | pd.Series | None = None,
) -> np.ndarray:
    """
    Classify whether cells satisfy the rigorous multi-year chronic hotspot criteria.

    A cell is a Chronic Hotspot if and only if ALL of the following hold:
    1. hotspot_frequency >= 0.50 (active in >= 50% of valid seasons)
    2. hot_seasons_count >= 3 (at least 3 qualifying seasonal passes)
    3. distinct_years_count >= 2 (must span at least 2 distinct calendar years)
    4. valid_seasons_count >= 4 (minimum multi-season archive support)
    5. qualifying_obs_ge_2_count >= 2 (at least 2 qualifying passes had OBS >= 2, if provided)

    Parameters
    ----------
    hotspot_frequency : np.ndarray or pd.Series
    hot_seasons_count : np.ndarray or pd.Series
    distinct_years_count : np.ndarray or pd.Series
    valid_seasons_count : np.ndarray or pd.Series
    qualifying_obs_ge_2_count : np.ndarray or pd.Series, optional

    Returns
    -------
    np.ndarray of bool
        Boolean mask of chronic hotspots.
    """
    freq = np.asarray(hotspot_frequency, dtype=np.float64)
    hot_cnt = np.asarray(hot_seasons_count, dtype=np.int64)
    yr_cnt = np.asarray(distinct_years_count, dtype=np.int64)
    val_cnt = np.asarray(valid_seasons_count, dtype=np.int64)

    cond_freq = freq >= CHRONIC_HOTSPOT_FREQ_THRESHOLD
    cond_hot = hot_cnt >= MIN_CHRONIC_SEASONS
    cond_yr = yr_cnt >= MIN_CHRONIC_YEARS
    cond_val = val_cnt >= MIN_ARCHIVE_VALID_SEASONS

    is_chronic = cond_freq & cond_hot & cond_yr & cond_val

    if qualifying_obs_ge_2_count is not None:
        obs2_cnt = np.asarray(qualifying_obs_ge_2_count, dtype=np.int64)
        is_chronic = is_chronic & (obs2_cnt >= 2)

    return is_chronic
