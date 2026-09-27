"""Quality and Eligibility package for HEATSENSE AI.

Provides modular, testable pixel-quality diagnostic calculations
and candidate eligibility policy evaluations.
"""

from gis.quality.pixel_quality import (
    classify_temporal_support,
    compute_neighborhood_metrics,
    evaluate_boundary_context,
    classify_extreme_status,
    classify_qa_uncertainty,
    assign_quality_flags,
)
from gis.quality.eligibility import (
    EligibilityStatus,
    evaluate_pixel_eligibility,
    evaluate_policy_a,
    evaluate_policy_b,
    evaluate_policy_c,
    evaluate_policy_d,
)

from gis.quality.hotspot_definitions import (
    CHRONIC_HOTSPOT_FREQ_THRESHOLD,
    PERSISTENT_HOTSPOT_FREQ_THRESHOLD,
    classify_hotspot_tier,
    is_active_hotspot,
    is_chronic_hotspot,
    is_non_hotspot,
    is_persistent_hotspot,
)

__all__ = [
    "classify_temporal_support",
    "compute_neighborhood_metrics",
    "evaluate_boundary_context",
    "classify_extreme_status",
    "classify_qa_uncertainty",
    "assign_quality_flags",
    "EligibilityStatus",
    "evaluate_pixel_eligibility",
    "evaluate_policy_a",
    "evaluate_policy_b",
    "evaluate_policy_c",
    "evaluate_policy_d",
    "CHRONIC_HOTSPOT_FREQ_THRESHOLD",
    "PERSISTENT_HOTSPOT_FREQ_THRESHOLD",
    "classify_hotspot_tier",
    "is_active_hotspot",
    "is_chronic_hotspot",
    "is_non_hotspot",
    "is_persistent_hotspot",
]
