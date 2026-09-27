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
