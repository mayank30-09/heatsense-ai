"""Consistency test between config/quality_policy_d.yaml and gis/quality/eligibility.py."""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from gis.quality.eligibility import EligibilityStatus, evaluate_policy_d

PROJECT_ROOT = Path(__file__).resolve().parents[2]
YAML_PATH = PROJECT_ROOT / "config" / "quality_policy_d.yaml"


def test_yaml_spec_exists_and_loads():
    assert YAML_PATH.exists(), f"Policy D specification missing at: {YAML_PATH}"
    with open(YAML_PATH) as f:
        spec = yaml.safe_load(f)
    assert spec["policy_id"] == "D"
    assert spec["policy_name"] == "policy_d"
    assert spec["spatial_screening"]["anomaly_diff_threshold_celsius"] == 10.0
    assert spec["spatial_screening"]["minimum_valid_neighbors"] == 4


def test_yaml_spec_matches_authoritative_implementation():
    with open(YAML_PATH) as f:
        spec = yaml.safe_load(f)

    thresh = float(spec["spatial_screening"]["anomaly_diff_threshold_celsius"])

    # Rule 1: OBS < 1 -> EXCLUDE
    st, _ = evaluate_policy_d(obs_count=0)
    assert st == EligibilityStatus.EXCLUDE

    # Rule 2: OBS >= 2 and no spatial anomaly -> ACCEPT
    st, _ = evaluate_policy_d(obs_count=2, quality_flags=["VALID"])
    assert st == EligibilityStatus.ACCEPT

    # Rule 3: OBS >= 2 and SPATIAL_ANOMALY -> FLAG
    st, _ = evaluate_policy_d(obs_count=2, quality_flags=["SPATIAL_ANOMALY"])
    assert st == EligibilityStatus.FLAG

    # Rule 4: OBS == 1 and severe anomaly (abs_diff > thresh) -> EXCLUDE
    st, _ = evaluate_policy_d(obs_count=1, abs_diff_med=thresh + 0.1, anomaly_diff_thresh=thresh)
    assert st == EligibilityStatus.EXCLUDE

    # Rule 5: OBS == 1 and LOW_SUPPORT_SPATIAL_EXTREME flag -> EXCLUDE
    st, _ = evaluate_policy_d(obs_count=1, quality_flags=["LOW_SUPPORT_SPATIAL_EXTREME"], anomaly_diff_thresh=thresh)
    assert st == EligibilityStatus.EXCLUDE

    # Rule 6: OBS == 1 and spatially coherent -> FLAG
    st, _ = evaluate_policy_d(obs_count=1, abs_diff_med=thresh - 1.0, anomaly_diff_thresh=thresh)
    assert st == EligibilityStatus.FLAG


def test_policy_d_threshold_and_boundary_edges():
    """Verify exact boundary behavior and neighbor count handling under Policy D."""
    thresh = 10.0

    # Exact threshold equality: abs_diff_med == 10.0 is NOT > 10.0 -> FLAG (not EXCLUDE)
    st_exact, _ = evaluate_policy_d(obs_count=1, abs_diff_med=10.0, anomaly_diff_thresh=thresh)
    assert st_exact == EligibilityStatus.FLAG

    # Strictly greater than threshold: abs_diff_med == 10.001 -> EXCLUDE
    st_above, _ = evaluate_policy_d(obs_count=1, abs_diff_med=10.001, anomaly_diff_thresh=thresh)
    assert st_above == EligibilityStatus.EXCLUDE

    # Boundary context with < 4 valid neighbors: FLAG with boundary edge reason
    st_bound, reason_bound = evaluate_policy_d(
        obs_count=1,
        abs_diff_med=2.0,
        is_boundary_context=True,
        valid_neighbor_count=3,
        anomaly_diff_thresh=thresh,
    )
    assert st_bound == EligibilityStatus.FLAG
    assert "boundary edge" in reason_bound

    # Missing abs_diff_med (None) on coherent pixel: FLAG
    st_none_diff, _ = evaluate_policy_d(obs_count=1, abs_diff_med=None)
    assert st_none_diff == EligibilityStatus.FLAG


def test_non_finite_and_missing_observation_counts():
    """Verify that None, NaN, Inf, and negative observation counts are excluded."""
    from gis.quality.eligibility import (
        evaluate_policy_a,
        evaluate_policy_b,
        evaluate_policy_c,
        evaluate_policy_d,
    )

    invalid_inputs = [None, float("nan"), float("inf"), float("-inf"), -1, 0, 0.0]

    for inv in invalid_inputs:
        st_a, _ = evaluate_policy_a(inv)
        assert st_a == EligibilityStatus.EXCLUDE, f"Policy A failed on {inv}"

        st_b, _ = evaluate_policy_b(inv)
        assert st_b == EligibilityStatus.EXCLUDE, f"Policy B failed on {inv}"

        st_c, _ = evaluate_policy_c(inv)
        assert st_c == EligibilityStatus.EXCLUDE, f"Policy C failed on {inv}"

        st_d, _ = evaluate_policy_d(inv)
        assert st_d == EligibilityStatus.EXCLUDE, f"Policy D failed on {inv}"
