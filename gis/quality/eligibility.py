"""Pixel Eligibility Policies for HEATSENSE AI.

This module applies analytical eligibility policies to pixel quality metrics.
It separates diagnostic calculations (`gis.quality.pixel_quality`) from policy
decision-making, enabling controlled sensitivity analysis between candidate rules.

Framework:
- ACCEPT: Pixel has sufficient evidence and no strong anomaly signal.
- FLAG: Pixel is retained for analysis but carries a quality warning.
- EXCLUDE: Pixel has strong evidence of being an artifact or unobservable.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class EligibilityStatus(str, Enum):
    """Tripartite analytical eligibility status."""
    ACCEPT = "ACCEPT"
    FLAG = "FLAG"
    EXCLUDE = "EXCLUDE"


# ---------------------------------------------------------------------------
# Candidate Policy A: OBS_COUNT >= 1 (Unconstrained Baseline)
# ---------------------------------------------------------------------------

def evaluate_policy_a(
    obs_count: float | int | None,
    quality_flags: list[str] | None = None,
    **kwargs: Any,
) -> tuple[EligibilityStatus, str]:
    """
    Policy A: Retains all valid pixels with at least 1 observation.

    - OBS >= 2: ACCEPT
    - OBS == 1: FLAG (retained with low-temporal-support warning)
    - OBS < 1 or missing: EXCLUDE
    """
    if obs_count is None or obs_count < 1:
        return EligibilityStatus.EXCLUDE, "No observation support (OBS < 1)"

    if obs_count == 1:
        return EligibilityStatus.FLAG, "Retained under Policy A with low temporal support (OBS=1)"

    return EligibilityStatus.ACCEPT, "Eligible under Policy A (OBS >= 2)"


# ---------------------------------------------------------------------------
# Candidate Policy B: OBS_COUNT >= 2 (Strict Multi-Observation Requirement)
# ---------------------------------------------------------------------------

def evaluate_policy_b(
    obs_count: float | int | None,
    quality_flags: list[str] | None = None,
    **kwargs: Any,
) -> tuple[EligibilityStatus, str]:
    """
    Policy B: Strict multi-observation cutoff.

    - OBS >= 2: ACCEPT (or FLAG if spatial anomaly present)
    - OBS < 2: EXCLUDE
    """
    if obs_count is None or obs_count < 2:
        return EligibilityStatus.EXCLUDE, "Excluded under Policy B (OBS < 2)"

    flags = quality_flags or []
    if "SPATIAL_ANOMALY" in flags:
        return EligibilityStatus.FLAG, "Retained under Policy B (OBS >= 2) with spatial anomaly warning"

    return EligibilityStatus.ACCEPT, "Eligible under Policy B (OBS >= 2)"


# ---------------------------------------------------------------------------
# Candidate Policy C: OBS_COUNT >= 2 OR Spatially Persistent Extreme
# ---------------------------------------------------------------------------

def evaluate_policy_c(
    obs_count: float | int | None,
    is_persistent_hotspot: bool = False,
    quality_flags: list[str] | None = None,
    **kwargs: Any,
) -> tuple[EligibilityStatus, str]:
    """
    Policy C: Requires OBS >= 2, but rescues chronic, multi-season persistent
    hotspots that happen to have OBS = 1 in a cloud-restricted season.

    - OBS >= 2: ACCEPT (or FLAG if spatial anomaly)
    - OBS == 1 AND is_persistent_hotspot: FLAG (rescued persistent hotspot)
    - OBS == 1 AND NOT is_persistent_hotspot: EXCLUDE
    - OBS < 1: EXCLUDE
    """
    if obs_count is None or obs_count < 1:
        return EligibilityStatus.EXCLUDE, "Excluded (OBS < 1)"

    if obs_count >= 2:
        flags = quality_flags or []
        if "SPATIAL_ANOMALY" in flags:
            return EligibilityStatus.FLAG, "Retained under Policy C (OBS >= 2) with spatial anomaly warning"
        return EligibilityStatus.ACCEPT, "Eligible under Policy C (OBS >= 2)"

    # OBS == 1 case
    if is_persistent_hotspot:
        return EligibilityStatus.FLAG, "Rescued under Policy C as verified multi-season persistent hotspot (OBS=1)"

    return EligibilityStatus.EXCLUDE, "Excluded under Policy C (OBS=1 and non-persistent)"


# ---------------------------------------------------------------------------
# Candidate Policy D: OBS_COUNT >= 1 BUT Exclude Strong Spatial Anomalies
# ---------------------------------------------------------------------------

def evaluate_policy_d(
    obs_count: float | int | None,
    quality_flags: list[str] | None = None,
    abs_diff_med: float | None = None,
    valid_neighbor_count: int = 8,
    is_boundary_context: bool = False,
    anomaly_diff_thresh: float = 10.0,
    **kwargs: Any,
) -> tuple[EligibilityStatus, str]:
    """
    Policy D: Nuanced physical anomaly filter.
    Accepts all OBS >= 1, but selectively purges pixels that have OBS == 1
    AND exhibit strong spatial anomaly signals (e.g. cloud shadows at edges).

    - OBS >= 2: ACCEPT (or FLAG if spatial anomaly)
    - OBS == 1 AND strong spatial anomaly (abs_diff > thresh or boundary + anomaly): EXCLUDE
    - OBS == 1 AND spatially coherent: FLAG (retained with low-support warning)
    - OBS < 1: EXCLUDE
    """
    if obs_count is None or obs_count < 1:
        return EligibilityStatus.EXCLUDE, "Excluded (OBS < 1)"

    flags = quality_flags or []

    if obs_count >= 2:
        if "SPATIAL_ANOMALY" in flags:
            return EligibilityStatus.FLAG, "Retained under Policy D (OBS >= 2) with spatial anomaly warning"
        return EligibilityStatus.ACCEPT, "Eligible under Policy D (OBS >= 2)"

    # OBS == 1
    # Check for severe spatial anomaly:
    # Condition 1: Tagged as LOW_SUPPORT_SPATIAL_EXTREME
    # Condition 2: Explicit abs_diff_med > anomaly_diff_thresh
    # Condition 3: Boundary edge with severe deviation
    has_large_dev = (abs_diff_med is not None and abs_diff_med > anomaly_diff_thresh)
    is_severe_anomaly = ("LOW_SUPPORT_SPATIAL_EXTREME" in flags) or has_large_dev

    if is_severe_anomaly:
        return EligibilityStatus.EXCLUDE, "Excluded under Policy D (OBS=1 with severe spatial neighborhood anomaly)"

    if is_boundary_context and valid_neighbor_count < 4:
        return EligibilityStatus.FLAG, "Retained under Policy D (OBS=1 on boundary edge, review recommended)"

    return EligibilityStatus.FLAG, "Retained under Policy D (OBS=1, spatially coherent, flagged for temporal support)"


# ---------------------------------------------------------------------------
# Unified Evaluator
# ---------------------------------------------------------------------------

POLICIES = {
    "policy_a": evaluate_policy_a,
    "policy_b": evaluate_policy_b,
    "policy_c": evaluate_policy_c,
    "policy_d": evaluate_policy_d,
}


def evaluate_pixel_eligibility(
    obs_count: float | int | None,
    policy_name: str = "policy_d",
    quality_flags: list[str] | None = None,
    is_persistent_hotspot: bool = False,
    abs_diff_med: float | None = None,
    valid_neighbor_count: int = 8,
    is_boundary_context: bool = False,
    **kwargs: Any,
) -> tuple[EligibilityStatus, str]:
    """
    Evaluate eligibility status using the specified candidate policy.

    Parameters
    ----------
    obs_count : float | int | None
        Observation count.
    policy_name : str
        One of "policy_a", "policy_b", "policy_c", "policy_d".
    quality_flags : list[str] | None
        Condition flags from `gis.quality.pixel_quality.assign_quality_flags`.
    is_persistent_hotspot : bool
        Whether the pixel is verified as a chronic multi-season hotspot.
    abs_diff_med : float | None
        Absolute difference between pixel and 3x3 neighborhood median.
    valid_neighbor_count : int
        Count of valid neighbors.
    is_boundary_context : bool
        Whether pixel is at raster edge or surrounded by NoData.

    Returns
    -------
    tuple[EligibilityStatus, str]
        (Status, Reason)
    """
    key = policy_name.lower().strip()
    if key not in POLICIES:
        raise ValueError(f"Unknown policy '{policy_name}'. Available: {list(POLICIES.keys())}")

    fn = POLICIES[key]
    return fn(
        obs_count=obs_count,
        quality_flags=quality_flags,
        is_persistent_hotspot=is_persistent_hotspot,
        abs_diff_med=abs_diff_med,
        valid_neighbor_count=valid_neighbor_count,
        is_boundary_context=is_boundary_context,
        **kwargs,
    )
