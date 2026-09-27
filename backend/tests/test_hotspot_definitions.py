"""Unit tests for canonical hotspot and persistence definitions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gis.quality.hotspot_definitions import (
    CHRONIC_HOTSPOT_FREQ_THRESHOLD,
    PERSISTENT_HOTSPOT_FREQ_THRESHOLD,
    classify_hotspot_tier,
    is_active_hotspot,
    is_chronic_hotspot,
    is_non_hotspot,
    is_persistent_hotspot,
)


def test_hotspot_tier_classification():
    assert classify_hotspot_tier(0.0) == "non_hotspot"
    assert classify_hotspot_tier(0.05) == "transient_extreme"
    assert classify_hotspot_tier(0.15) == "occasional_hotspot"
    assert classify_hotspot_tier(0.30) == "frequent_hotspot"
    assert classify_hotspot_tier(0.50) == "chronic_hotspot"
    assert classify_hotspot_tier(0.95) == "chronic_hotspot"


def test_boolean_filters_scalar():
    assert is_non_hotspot(0.0) is True or is_non_hotspot(0.0) == True
    assert is_non_hotspot(0.1) is False or is_non_hotspot(0.1) == False

    assert is_active_hotspot(0.0) is False or is_active_hotspot(0.0) == False
    assert is_active_hotspot(0.05) is True or is_active_hotspot(0.05) == True

    assert is_persistent_hotspot(0.20) is False or is_persistent_hotspot(0.20) == False
    assert is_persistent_hotspot(0.25) is True or is_persistent_hotspot(0.25) == True

    assert is_chronic_hotspot(0.49) is False or is_chronic_hotspot(0.49) == False
    assert is_chronic_hotspot(0.50) is True or is_chronic_hotspot(0.50) == True


def test_boolean_filters_series():
    s = pd.Series([0.0, 0.05, 0.20, 0.25, 0.45, 0.50, 0.90])
    
    non_hot = is_non_hotspot(s)
    assert non_hot.sum() == 1

    active = is_active_hotspot(s)
    assert active.sum() == 6

    persistent = is_persistent_hotspot(s)
    assert persistent.sum() == 4  # 0.25, 0.45, 0.50, 0.90

    chronic = is_chronic_hotspot(s)
    assert chronic.sum() == 2  # 0.50, 0.90


def test_persistent_flag_or_override():
    freqs = pd.Series([0.10, 0.15, 0.30])
    flags = pd.Series([False, True, False])
    result = is_persistent_hotspot(freqs, is_persistent_flag=flags)
    assert result.tolist() == [False, True, True]
