"""Unit tests for gis/quality/eligibility.py module."""

import pytest

from gis.quality.eligibility import (
    EligibilityStatus,
    evaluate_policy_a,
    evaluate_policy_b,
    evaluate_policy_c,
    evaluate_policy_d,
    evaluate_pixel_eligibility,
)


def test_policy_a():
    # OBS >= 2 -> ACCEPT
    status, _ = evaluate_policy_a(obs_count=5)
    assert status == EligibilityStatus.ACCEPT

    # OBS == 1 -> FLAG
    status_1, _ = evaluate_policy_a(obs_count=1)
    assert status_1 == EligibilityStatus.FLAG

    # OBS < 1 -> EXCLUDE
    status_0, _ = evaluate_policy_a(obs_count=0)
    assert status_0 == EligibilityStatus.EXCLUDE


def test_policy_b():
    # OBS >= 2 -> ACCEPT
    status, _ = evaluate_policy_b(obs_count=2)
    assert status == EligibilityStatus.ACCEPT

    # OBS == 1 -> EXCLUDE
    status_1, _ = evaluate_policy_b(obs_count=1)
    assert status_1 == EligibilityStatus.EXCLUDE


def test_policy_c_persistent_hotspot_rescue():
    # OBS == 1, NOT persistent -> EXCLUDE
    status_non_pers, _ = evaluate_policy_c(obs_count=1, is_persistent_hotspot=False)
    assert status_non_pers == EligibilityStatus.EXCLUDE

    # OBS == 1, IS persistent hotspot -> Rescued as FLAG!
    status_pers, _ = evaluate_policy_c(obs_count=1, is_persistent_hotspot=True)
    assert status_pers == EligibilityStatus.FLAG

    # OBS >= 2 -> ACCEPT
    status_obs2, _ = evaluate_policy_c(obs_count=2, is_persistent_hotspot=False)
    assert status_obs2 == EligibilityStatus.ACCEPT


def test_policy_d_selective_spatial_anomaly_exclusion():
    # Real coherent hotspot: OBS=1, coherent diff (5.0C), NOT severe anomaly -> FLAG
    status_hot, _ = evaluate_policy_d(
        obs_count=1,
        abs_diff_med=5.0,
        quality_flags=["LOW_TEMPORAL_SUPPORT", "SPATIALLY_COHERENT"],
    )
    assert status_hot == EligibilityStatus.FLAG

    # Unflagged cloud shadow: OBS=1, severe diff (15.4C) -> EXCLUDE
    status_shadow, _ = evaluate_policy_d(
        obs_count=1,
        abs_diff_med=15.4,
        quality_flags=["LOW_TEMPORAL_SUPPORT", "SPATIAL_ANOMALY", "LOW_SUPPORT_SPATIAL_EXTREME"],
    )
    assert status_shadow == EligibilityStatus.EXCLUDE

    # Normal robust pixel: OBS=10 -> ACCEPT
    status_norm, _ = evaluate_policy_d(obs_count=10, abs_diff_med=1.0)
    assert status_norm == EligibilityStatus.ACCEPT


def test_unified_evaluator():
    status_a, _ = evaluate_pixel_eligibility(obs_count=1, policy_name="policy_a")
    assert status_a == EligibilityStatus.FLAG

    status_b, _ = evaluate_pixel_eligibility(obs_count=1, policy_name="policy_b")
    assert status_b == EligibilityStatus.EXCLUDE

    status_c, _ = evaluate_pixel_eligibility(obs_count=1, policy_name="policy_c", is_persistent_hotspot=True)
    assert status_c == EligibilityStatus.FLAG

    with pytest.raises(ValueError):
        evaluate_pixel_eligibility(obs_count=1, policy_name="non_existent_policy")
