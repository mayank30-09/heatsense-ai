"""Heat Persistence Layer for Heat Priority.

Evaluates multi-season recurrence of extreme surface temperatures across 19 seasons.
Distinguishes transient thermal anomalies from chronic urban heat accumulation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from gis.quality.hotspot_definitions import (
    CHRONIC_HOTSPOT_FREQ_THRESHOLD,
    PERSISTENT_HOTSPOT_FREQ_THRESHOLD,
)


def compute_heat_persistence(
    hotspot_frequency: np.ndarray | pd.Series,
    is_persistent_hotspot: np.ndarray | pd.Series | None = None,
    valid_mask: np.ndarray | pd.Series | None = None,
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

    # Base persistence is normalized recurrence frequency
    base_score = np.clip(freq[mask], 0.0, 1.0)

    # If persistence flag is active, ensure persistence score is at least the persistence threshold
    if is_persistent_hotspot is not None:
        pers_flag = np.asarray(is_persistent_hotspot, dtype=bool)[mask]
        base_score = np.where(pers_flag, np.maximum(base_score, PERSISTENT_HOTSPOT_FREQ_THRESHOLD), base_score)

    persistence[mask] = base_score
    return persistence
