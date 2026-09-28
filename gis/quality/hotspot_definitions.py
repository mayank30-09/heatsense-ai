"""Canonical Hotspot and Persistence Definitions for HEATSENSE AI.

This module provides the single authoritative implementation for hotspot classification,
resolving previous ambiguities between recurrence counts and normalized recurrence frequencies.

Definitions:
- Non-Hotspot: Pixel has never exhibited hot extreme behavior (hotspot_frequency == 0.0).
- Active Hotspot: Pixel was in Top 1% or Top 20 in at least one observed season (hotspot_frequency > 0.0).
- Frequent Hotspot: Recurrence frequency between 25% and 50% (0.25 <= hotspot_frequency < 0.50).
- Persistent Hotspot: Pixel satisfies the overall persistence threshold (hotspot_frequency >= 0.25).
- Chronic Hotspot: Highest tier of persistence; active in >= 50% of observed seasons (hotspot_frequency >= 0.50).

Scientific Note on Previous Discrepancies:
In some early script drafts, the expression `hotspot_frequency >= 6` was used, mistakenly treating
normalized frequency (which ranges from 0.0 to 1.0) as an integer season count. Since `hotspot_frequency`
is stored as a float in [0.0, 1.0], `hotspot_frequency >= 6` evaluated to identically False.
The canonical definition formally uses normalized float frequencies, with `CHRONIC_HOTSPOT_FREQ_THRESHOLD = 0.50`
and `PERSISTENT_HOTSPOT_FREQ_THRESHOLD = 0.25`.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

# Canonical Frequency Thresholds (normalized fraction of valid seasons in Top 1% LST)
NON_HOTSPOT_FREQ_THRESHOLD: float = 0.0
ACTIVE_HOTSPOT_FREQ_THRESHOLD: float = 0.0
OCCASIONAL_HOTSPOT_FREQ_THRESHOLD: float = 0.10

# Preferred canonical constants per scientific freeze specification
PERSISTENT_FREQUENCY_THRESHOLD: float = 0.25
CHRONIC_FREQUENCY_THRESHOLD: float = 0.50

# Backward compatibility aliases
PERSISTENT_HOTSPOT_FREQ_THRESHOLD: float = PERSISTENT_FREQUENCY_THRESHOLD
CHRONIC_HOTSPOT_FREQ_THRESHOLD: float = CHRONIC_FREQUENCY_THRESHOLD

HOTSPOT_TIER_NAMES = [
    "non_hotspot",
    "transient_extreme",
    "occasional_hotspot",
    "frequent_hotspot",
    "chronic_hotspot",
]


def classify_hotspot_tier(freq: float) -> str:
    """
    Classify a normalized hotspot recurrence frequency into its canonical tier.

    Parameters
    ----------
    freq : float
        Fraction of observed seasons the pixel was in upper percentiles (0.0 to 1.0).

    Returns
    -------
    str
        One of 'non_hotspot', 'transient_extreme', 'occasional_hotspot',
        'frequent_hotspot', 'chronic_hotspot'.
    """
    if freq <= 0.0:
        return "non_hotspot"
    elif freq < OCCASIONAL_HOTSPOT_FREQ_THRESHOLD:
        return "transient_extreme"
    elif freq < PERSISTENT_HOTSPOT_FREQ_THRESHOLD:
        return "occasional_hotspot"
    elif freq < CHRONIC_HOTSPOT_FREQ_THRESHOLD:
        return "frequent_hotspot"
    else:
        return "chronic_hotspot"


def is_non_hotspot(freq: float | np.ndarray | pd.Series) -> bool | np.ndarray | pd.Series:
    """Return True if pixel has never been a hotspot (freq == 0)."""
    return freq == 0.0


def is_active_hotspot(freq: float | np.ndarray | pd.Series) -> bool | np.ndarray | pd.Series:
    """Return True if pixel has been an active hotspot in at least 1 season (freq > 0)."""
    return freq > 0.0


def persistent_hotspot_mask(
    hotspot_frequency: float | np.ndarray | pd.Series,
    existing_persistent_flag: bool | np.ndarray | pd.Series | None = None,
) -> bool | np.ndarray | pd.Series:
    """Array-safe canonical persistent hotspot mask.

    The canonical recurrence policy for persistence is:
        is_persistent = (hotspot_frequency >= 0.25) OR authoritative existing persistent-hotspot flag

    Parameters
    ----------
    hotspot_frequency : float or array-like
        Normalized recurrence frequency in [0.0, 1.0].
    existing_persistent_flag : bool or array-like, optional
        Precomputed / authoritative persistence flag.

    Returns
    -------
    bool or array-like of bool
        Boolean indicator / mask of persistence.
    """
    if isinstance(hotspot_frequency, pd.Series):
        mask = hotspot_frequency >= PERSISTENT_FREQUENCY_THRESHOLD
        if existing_persistent_flag is not None:
            if isinstance(existing_persistent_flag, pd.Series):
                mask = mask | existing_persistent_flag.astype(bool)
            else:
                flag_arr = np.asarray(existing_persistent_flag, dtype=bool)
                mask = mask | flag_arr
        return mask

    freq_arr = np.asarray(hotspot_frequency)
    mask = freq_arr >= PERSISTENT_FREQUENCY_THRESHOLD
    if existing_persistent_flag is not None:
        flag_arr = np.asarray(existing_persistent_flag, dtype=bool)
        mask = mask | flag_arr

    if np.ndim(hotspot_frequency) == 0 and (
        existing_persistent_flag is None or np.ndim(existing_persistent_flag) == 0
    ):
        return bool(mask)
    return mask


def is_persistent_hotspot(
    freq: float | np.ndarray | pd.Series,
    is_persistent_flag: bool | np.ndarray | pd.Series | None = None,
) -> bool | np.ndarray | pd.Series:
    """Return True if pixel meets the multi-season persistence criterion.

    Delegates to canonical persistent_hotspot_mask:
        frequency >= 0.25 OR authoritative existing persistent-hotspot flag.
    """
    return persistent_hotspot_mask(freq, is_persistent_flag)


def is_chronic_hotspot(
    freq: float | np.ndarray | pd.Series,
    threshold: float = CHRONIC_HOTSPOT_FREQ_THRESHOLD,
) -> bool | np.ndarray | pd.Series:
    """
    Return True if pixel is in the highest chronic persistence tier (freq >= 0.50).

    Parameters
    ----------
    freq : float or array-like
        Normalized recurrence frequency in [0.0, 1.0].
    threshold : float, default 0.50
        Frequency threshold for chronic tier.
    """
    return freq >= threshold
