"""Unit tests for policy comparison logic and edge cases."""

import pytest
from gis.quality.eligibility import (
    EligibilityStatus,
    evaluate_policy_a,
    evaluate_policy_b,
    evaluate_policy_c,
    evaluate_policy_d,
)


@pytest.mark.parametrize("obs", [0, 1, 2, 3, 10])
def test_policy_deterministic_outputs(obs):
    """Verify that policies return deterministic states across observation counts."""
    # Policy A
    st_a, _ = evaluate_policy_a(obs_count=obs)
    if obs < 1:
        assert st_a == EligibilityStatus.EXCLUDE
    elif obs == 1:
        assert st_a == EligibilityStatus.FLAG
    else:
        assert st_a == EligibilityStatus.ACCEPT

    # Policy B
    st_b, _ = evaluate_policy_b(obs_count=obs)
    if obs < 2:
        assert st_b == EligibilityStatus.EXCLUDE
    else:
        assert st_b == EligibilityStatus.ACCEPT


def test_policy_c_persistent_hotspot_preservation():
    """Verify that Policy C rescues chronic hotspots with OBS=1 while excluding transient OBS=1."""
    # Transient extreme
    st_trans, _ = evaluate_policy_c(obs_count=1, is_persistent_hotspot=False)
    assert st_trans == EligibilityStatus.EXCLUDE

    # Chronic persistent hotspot (e.g. Pandesara industrial corridor)
    st_chron, _ = evaluate_policy_c(obs_count=1, is_persistent_hotspot=True)
    assert st_chron == EligibilityStatus.FLAG


def test_policy_d_spatial_anomaly_vs_coherent_hotspot():
    """Verify that Policy D selectively purges low-support anomalies while preserving coherent hotspots."""
    # Case 1: 6.47°C anomaly: OBS=1, dev=-15.39°C, boundary=True -> EXCLUDE
    st_cloud, _ = evaluate_policy_d(
        obs_count=1,
        abs_diff_med=15.39,
        valid_neighbor_count=4,
        is_boundary_context=True,
        quality_flags=["LOW_TEMPORAL_SUPPORT", "SPATIAL_ANOMALY", "LOW_SUPPORT_SPATIAL_EXTREME"],
    )
    assert st_cloud == EligibilityStatus.EXCLUDE

    # Case 2: Coherent hotspot: OBS=1, dev=5.0°C, valid_neighbors=8, boundary=False -> FLAG (RETAINED!)
    st_hot, _ = evaluate_policy_d(
        obs_count=1,
        abs_diff_med=5.0,
        valid_neighbor_count=8,
        is_boundary_context=False,
        quality_flags=["LOW_TEMPORAL_SUPPORT", "SPATIALLY_COHERENT"],
    )
    assert st_hot == EligibilityStatus.FLAG

    # Case 3: Missing neighborhood / NoData surroundings on boundary with OBS=1 -> FLAG (review recommended)
    st_edge, _ = evaluate_policy_d(
        obs_count=1,
        abs_diff_med=2.0,
        valid_neighbor_count=2,
        is_boundary_context=True,
    )
    assert st_edge == EligibilityStatus.FLAG
