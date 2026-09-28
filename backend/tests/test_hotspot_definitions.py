"""Unit tests for canonical hotspot and persistence definitions.

Verifies canonical recurrence policy, boundary thresholds, array-safe masking,
and persistence flag preservation per the HEATSENSE AI Scientific Freeze specification.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gis.quality.hotspot_definitions import (
    CHRONIC_FREQUENCY_THRESHOLD,
    CHRONIC_HOTSPOT_FREQ_THRESHOLD,
    PERSISTENT_FREQUENCY_THRESHOLD,
    PERSISTENT_HOTSPOT_FREQ_THRESHOLD,
    classify_hotspot_tier,
    is_active_hotspot,
    is_chronic_hotspot,
    is_non_hotspot,
    is_persistent_hotspot,
    persistent_hotspot_mask,
)


def test_canonical_constants():
    """Verify canonical frequency threshold constants."""
    assert PERSISTENT_FREQUENCY_THRESHOLD == 0.25
    assert CHRONIC_FREQUENCY_THRESHOLD == 0.50
    # Backward compatibility aliases
    assert PERSISTENT_HOTSPOT_FREQ_THRESHOLD == 0.25
    assert CHRONIC_HOTSPOT_FREQ_THRESHOLD == 0.50


def test_hotspot_tier_classification():
    assert classify_hotspot_tier(0.0) == "non_hotspot"
    assert classify_hotspot_tier(0.05) == "transient_extreme"
    assert classify_hotspot_tier(0.15) == "occasional_hotspot"
    assert classify_hotspot_tier(0.30) == "frequent_hotspot"
    assert classify_hotspot_tier(0.50) == "chronic_hotspot"
    assert classify_hotspot_tier(0.95) == "chronic_hotspot"


def test_specification_minimum_cases():
    """Verify the exact test matrix specified in the scientific freeze instructions:
    
    frequency = 0.00
    -> active=False, persistent=False, chronic=False

    frequency = 0.10
    -> active=True, persistent=False, chronic=False

    frequency = 0.25
    -> active=True, persistent=True, chronic=False

    frequency = 0.50
    -> active=True, persistent=True, chronic=True

    frequency = 0.10 + existing_persistent_flag=True
    -> active=True, persistent=True, chronic=False
    """
    # 1. freq = 0.00
    assert bool(is_active_hotspot(0.00)) is False
    assert bool(is_persistent_hotspot(0.00)) is False
    assert bool(is_chronic_hotspot(0.00)) is False

    # 2. freq = 0.10
    assert bool(is_active_hotspot(0.10)) is True
    assert bool(is_persistent_hotspot(0.10)) is False
    assert bool(is_chronic_hotspot(0.10)) is False

    # 3. freq = 0.25
    assert bool(is_active_hotspot(0.25)) is True
    assert bool(is_persistent_hotspot(0.25)) is True
    assert bool(is_chronic_hotspot(0.25)) is False

    # 4. freq = 0.50
    assert bool(is_active_hotspot(0.50)) is True
    assert bool(is_persistent_hotspot(0.50)) is True
    assert bool(is_chronic_hotspot(0.50)) is True

    # 5. freq = 0.10 + existing_persistent_flag=True
    assert bool(is_active_hotspot(0.10)) is True
    assert bool(is_persistent_hotspot(0.10, is_persistent_flag=True)) is True
    assert bool(is_chronic_hotspot(0.10)) is False


def test_exact_threshold_boundaries():
    """Test precise threshold boundaries to prevent off-by-one or strict-inequality regressions."""
    # Active boundary: freq > 0.0
    assert bool(is_active_hotspot(0.0)) is False
    assert bool(is_active_hotspot(1e-7)) is True

    # Persistent boundary: freq >= 0.25
    assert bool(is_persistent_hotspot(0.249999)) is False
    assert bool(is_persistent_hotspot(0.250000)) is True
    assert bool(is_persistent_hotspot(0.250001)) is True

    # Chronic boundary: freq >= 0.50
    assert bool(is_chronic_hotspot(0.499999)) is False
    assert bool(is_chronic_hotspot(0.500000)) is True
    assert bool(is_chronic_hotspot(0.500001)) is True


def test_persistent_flag_regression_prevention():
    """Prevent regression to `persistent = frequency >= 0.25` when existing_persistent_flag is True."""
    # When frequency is below 0.25, but authoritative flag is True, must return True
    assert bool(persistent_hotspot_mask(0.00, existing_persistent_flag=True)) is True
    assert bool(persistent_hotspot_mask(0.10, existing_persistent_flag=True)) is True
    assert bool(persistent_hotspot_mask(0.24, existing_persistent_flag=True)) is True

    # When frequency is below 0.25, and flag is False, must return False
    assert bool(persistent_hotspot_mask(0.00, existing_persistent_flag=False)) is False
    assert bool(persistent_hotspot_mask(0.10, existing_persistent_flag=False)) is False
    assert bool(persistent_hotspot_mask(0.24, existing_persistent_flag=False)) is False

    # When frequency >= 0.25, must return True regardless of flag
    assert bool(persistent_hotspot_mask(0.25, existing_persistent_flag=False)) is True
    assert bool(persistent_hotspot_mask(0.25, existing_persistent_flag=True)) is True
    assert bool(persistent_hotspot_mask(0.75, existing_persistent_flag=None)) is True


def test_array_safe_mask_numpy_and_pandas():
    """Verify array-safe execution on NumPy 1D/2D arrays and pandas Series."""
    freq_arr = np.array([0.00, 0.10, 0.25, 0.50, 0.10])
    flag_arr = np.array([False, False, False, False, True])

    mask = persistent_hotspot_mask(freq_arr, flag_arr)
    np.testing.assert_array_equal(mask, [False, False, True, True, True])

    # 2D raster simulation (e.g., 324 x 318 raster)
    freq_2d = np.zeros((10, 10), dtype=np.float32)
    flag_2d = np.zeros((10, 10), dtype=bool)

    freq_2d[2, 2] = 0.30
    flag_2d[4, 4] = True
    mask_2d = persistent_hotspot_mask(freq_2d, flag_2d)

    assert mask_2d.shape == (10, 10)
    assert mask_2d[2, 2] == True  # by frequency
    assert mask_2d[4, 4] == True  # by authoritative flag
    assert mask_2d[0, 0] == False # non-hotspot

    # pandas Series
    s_freq = pd.Series([0.0, 0.05, 0.20, 0.25, 0.45, 0.50, 0.90])
    s_flag = pd.Series([False, False, True, False, False, False, False])
    s_result = persistent_hotspot_mask(s_freq, s_flag)
    assert isinstance(s_result, pd.Series)
    # 0.20 has flag=True -> True. 0.25, 0.45, 0.50, 0.90 >= 0.25 -> True
    assert s_result.tolist() == [False, False, True, True, True, True, True]
