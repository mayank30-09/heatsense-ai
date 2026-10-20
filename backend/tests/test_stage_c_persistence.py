"""Acceptance Tests for Heat Persistence and Multi-Year Chronic Hotspot Classification (T-16, T-17).

Requirements:
- T-16: Single-year spike rejection (4 hot observations in 2024, 0 in other years -> is_chronic_hotspot = False).
- T-17: Multi-year chronic hotspot criteria (>= 50% frequency, >= 3 hot passes, >= 2 distinct years, >= 4 valid seasons -> is_chronic_hotspot = True).
"""

from __future__ import annotations

import numpy as np
import pytest

from gis.heat_priority.persistence import classify_chronic_hotspots, compute_heat_persistence


def test_t16_single_year_spike_rejection() -> None:
    """T-16: Test that 4 hot observations confined to a single calendar year fail the chronic hotspot test."""
    # Cell with 4 hot seasons all occurring in 2024 (distinct_years_count = 1)
    is_chronic = classify_chronic_hotspots(
        hotspot_frequency=np.array([1.00]),
        hot_seasons_count=np.array([4]),
        distinct_years_count=np.array([1]),  # Fails distinct years constraint!
        valid_seasons_count=np.array([4]),
    )

    assert bool(is_chronic[0]) is False, "Single-year spike must not qualify as a chronic hotspot"


def test_t17_multi_year_chronic_hotspots() -> None:
    """T-17: Test that recurrent hotspots spanning >= 2 distinct calendar years qualify as chronic hotspots."""
    # Cell A: 3 hot passes across 2 distinct years (2023, 2024) out of 5 valid seasons (freq = 3/5 = 0.60)
    # Cell B: 2 hot passes across 2 years (fails min 3 passes)
    # Cell C: 4 hot passes across 3 years (2022, 2023, 2024) out of 8 valid seasons (freq = 4/8 = 0.50)
    # Cell D: 3 hot passes across 2 years out of 8 valid seasons (freq = 3/8 = 0.375 -> fails freq >= 0.50)

    freqs = np.array([0.60, 0.50, 0.50, 0.375])
    hot_cnt = np.array([3, 2, 4, 3])
    year_cnt = np.array([2, 2, 3, 2])
    valid_cnt = np.array([5, 4, 8, 8])

    is_chronic = classify_chronic_hotspots(
        hotspot_frequency=freqs,
        hot_seasons_count=hot_cnt,
        distinct_years_count=year_cnt,
        valid_seasons_count=valid_cnt,
    )

    assert bool(is_chronic[0]) is True, "Cell A must qualify as chronic hotspot"
    assert bool(is_chronic[1]) is False, "Cell B must fail due to < 3 hot seasons"
    assert bool(is_chronic[2]) is True, "Cell C must qualify as chronic hotspot"
    assert bool(is_chronic[3]) is False, "Cell D must fail due to frequency < 0.50"


def test_heat_persistence_normalization() -> None:
    """Test heat persistence score normalization across valid frequencies."""
    freqs = np.array([0.0, 0.25, 0.50, 0.80, 1.00])
    scores = compute_heat_persistence(freqs)

    np.testing.assert_allclose(scores, freqs, atol=1e-5)


def test_persistence_denominator_valid_seasons_support() -> None:
    """Test that persistence denominator requires N_valid_seasons >= 4 and zeroes out under-supported cells."""
    freqs = np.array([0.75, 0.80, 0.60, 0.90])
    # Cell 0 has 2 valid seasons (< 4) -> must be 0.0
    # Cell 1 has 3 valid seasons (< 4) -> must be 0.0
    # Cell 2 has 4 valid seasons (>= 4) -> 0.60
    # Cell 3 has 19 valid seasons (>= 4) -> 0.90
    valid_counts = np.array([2, 3, 4, 19])

    scores = compute_heat_persistence(
        hotspot_frequency=freqs,
        valid_seasons_count=valid_counts,
        min_valid_seasons=4,
    )

    assert scores[0] == pytest.approx(0.0)
    assert scores[1] == pytest.approx(0.0)
    assert scores[2] == pytest.approx(0.60)
    assert scores[3] == pytest.approx(0.90)


def test_chronic_hotspots_qualifying_obs_criteria() -> None:
    """Test that chronic hotspots require at least 2 qualifying passes with OBS >= 2."""
    freqs = np.array([0.60, 0.60])
    hot_cnt = np.array([4, 4])
    year_cnt = np.array([2, 2])
    valid_cnt = np.array([6, 6])
    obs2_cnt = np.array([1, 2])  # Cell 0 has only 1 pass with OBS >= 2, Cell 1 has 2

    is_chronic = classify_chronic_hotspots(
        hotspot_frequency=freqs,
        hot_seasons_count=hot_cnt,
        distinct_years_count=year_cnt,
        valid_seasons_count=valid_cnt,
        qualifying_obs_ge_2_count=obs2_cnt,
    )

    assert bool(is_chronic[0]) is False, "Cell with only 1 OBS >= 2 pass must fail"
    assert bool(is_chronic[1]) is True, "Cell with >= 2 OBS >= 2 passes must pass"
