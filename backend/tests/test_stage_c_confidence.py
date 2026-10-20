"""Acceptance Tests for Stage C Confidence Index Engine (T-09, T-10, T-11).

Requirements:
- T-09: Multi-Season Dry Quality (OBS=4, QA=2.1 K, Summer+Winter -> CI=0.90, HIGH tier).
- T-10: Summer-Only Season Penalty (OBS=4, QA=2.1 K, Summer-only -> CI=0.70, MODERATE tier).
- T-11: Missing Summer Season Penalty (OBS=3, QA=2.0 K, Winter-only -> CI=0.35, LOW tier).
- Confidence tier boundary classification (HIGH >= 0.75, MODERATE [0.50, 0.75), LOW [0.25, 0.50), INSUFFICIENT < 0.25).
"""

from __future__ import annotations

import numpy as np
import pytest

from gis.heat_priority.quality import (
    TIER_HIGH,
    TIER_INSUFFICIENT,
    TIER_LOW,
    TIER_MODERATE,
    classify_confidence_tier,
    compute_calibrated_confidence_index,
    compute_obs_multiplier,
    compute_qa_multiplier,
    compute_season_multiplier,
)


def test_t09_multi_season_dry_quality() -> None:
    """T-09: Test multi-season dry quality (Summer + Winter) achieves CI=0.90 and HIGH tier."""
    c_obs = compute_obs_multiplier(4.0)
    c_qa = compute_qa_multiplier(2.10)
    c_season = compute_season_multiplier(has_summer=True, has_winter=True, has_post_monsoon=False, has_monsoon=False)
    c_sent = 1.00

    ci, tier = compute_calibrated_confidence_index(
        obs_count=4.0,
        qa_uncertainty_k=2.10,
        has_summer=True,
        has_winter=True,
        has_post_monsoon=False,
        has_monsoon=False,
        c_sentinel=c_sent,
    )

    assert c_obs == pytest.approx(1.00)
    assert c_qa == pytest.approx(1.00)
    assert c_season == pytest.approx(0.90)
    assert ci == pytest.approx(0.90)
    assert tier == TIER_HIGH


def test_t10_summer_only_season_penalty() -> None:
    """T-10: Test summer-only observation is penalized with C_season=0.70 yielding CI=0.70 and MODERATE tier."""
    c_obs = compute_obs_multiplier(4.0)
    c_qa = compute_qa_multiplier(2.10)
    c_season = compute_season_multiplier(has_summer=True, has_winter=False, has_post_monsoon=False, has_monsoon=False)
    c_sent = 1.00

    ci, tier = compute_calibrated_confidence_index(
        obs_count=4.0,
        qa_uncertainty_k=2.10,
        has_summer=True,
        has_winter=False,
        has_post_monsoon=False,
        has_monsoon=False,
        c_sentinel=c_sent,
    )

    assert c_obs == pytest.approx(1.00)
    assert c_qa == pytest.approx(1.00)
    assert c_season == pytest.approx(0.70)
    assert ci == pytest.approx(0.70)
    assert tier == TIER_MODERATE


def test_t11_missing_summer_season_penalty() -> None:
    """T-11: Test winter-only observation is penalized with C_season=0.35 yielding CI=0.35 and LOW tier."""
    c_obs = compute_obs_multiplier(3.0)
    c_qa = compute_qa_multiplier(2.00)
    c_season = compute_season_multiplier(has_summer=False, has_winter=True, has_post_monsoon=False, has_monsoon=False)
    c_sent = 1.00

    ci, tier = compute_calibrated_confidence_index(
        obs_count=3.0,
        qa_uncertainty_k=2.00,
        has_summer=False,
        has_winter=True,
        has_post_monsoon=False,
        has_monsoon=False,
        c_sentinel=c_sent,
    )

    assert c_obs == pytest.approx(0.85)  # OBS=3 -> 0.85
    assert c_qa == pytest.approx(1.00)
    assert c_season == pytest.approx(0.35)
    assert ci == pytest.approx(0.85 * 1.00 * 0.35 * 1.00)
    assert tier == TIER_LOW


def test_confidence_tier_boundaries() -> None:
    """Test boundary conditions for confidence classification."""
    ci_values = np.array([1.00, 0.75, 0.7499, 0.50, 0.4999, 0.25, 0.2499, 0.00])
    tiers = classify_confidence_tier(ci_values)

    expected = np.array([
        TIER_HIGH,
        TIER_HIGH,
        TIER_MODERATE,
        TIER_MODERATE,
        TIER_LOW,
        TIER_LOW,
        TIER_INSUFFICIENT,
        TIER_INSUFFICIENT,
    ])
    np.testing.assert_array_equal(tiers, expected)


def test_2026_operational_seasonal_profile() -> None:
    """
    Test 2026 operational scoring configuration.
    Post-Monsoon 2026 does not exist in the satellite archive (has_post_monsoon=False).
    C_season evaluates to 0.90 (dry season complete), yielding CI = 0.90 (HIGH tier).
    """
    c_season_2026 = compute_season_multiplier(
        has_summer=True,
        has_winter=True,
        has_post_monsoon=False,
        has_monsoon=True,
    )
    assert c_season_2026 == pytest.approx(0.90)

    ci, tier = compute_calibrated_confidence_index(
        obs_count=4.0,
        qa_uncertainty_k=2.10,
        has_summer=True,
        has_winter=True,
        has_post_monsoon=False,
        has_monsoon=True,
        c_sentinel=1.00,
    )
    assert ci == pytest.approx(0.90)
    assert tier == TIER_HIGH


def test_full_seasonal_profile_matrix_p1_to_p9() -> None:
    """Test all patterns P1 through P9 from Section 7.2 of Stage C specification."""
    # P1: Full profile (Summer + Winter + Post-Monsoon + Monsoon) -> 1.00
    assert compute_season_multiplier(has_summer=True, has_winter=True, has_post_monsoon=True, has_monsoon=True) == pytest.approx(1.00)

    # P2: Summer + Winter + Post-Monsoon (no Monsoon) -> 1.00
    assert compute_season_multiplier(has_summer=True, has_winter=True, has_post_monsoon=True, has_monsoon=False) == pytest.approx(1.00)

    # P3: Summer + Winter + Monsoon (no Post-Monsoon) -> 0.90
    assert compute_season_multiplier(has_summer=True, has_winter=True, has_post_monsoon=False, has_monsoon=True) == pytest.approx(0.90)

    # P4: Summer + Winter only -> 0.90
    assert compute_season_multiplier(has_summer=True, has_winter=True, has_post_monsoon=False, has_monsoon=False) == pytest.approx(0.90)

    # P5: Summer + Monsoon (no Winter, no Post-Monsoon) -> 0.80
    assert compute_season_multiplier(has_summer=True, has_winter=False, has_post_monsoon=False, has_monsoon=True) == pytest.approx(0.80)

    # P6: Summer Only -> 0.70
    assert compute_season_multiplier(has_summer=True, has_winter=False, has_post_monsoon=False, has_monsoon=False) == pytest.approx(0.70)

    # P7: Winter + Post-Monsoon (Summer missing) -> 0.40
    assert compute_season_multiplier(has_summer=False, has_winter=True, has_post_monsoon=True, has_monsoon=False) == pytest.approx(0.40)

    # P8: Monsoon Only (Summer, Winter, Post-Monsoon missing) -> 0.25
    assert compute_season_multiplier(has_summer=False, has_winter=False, has_post_monsoon=False, has_monsoon=True) == pytest.approx(0.25)

    # P9: All missing -> 0.00
    assert compute_season_multiplier(has_summer=False, has_winter=False, has_post_monsoon=False, has_monsoon=False) == pytest.approx(0.00)
