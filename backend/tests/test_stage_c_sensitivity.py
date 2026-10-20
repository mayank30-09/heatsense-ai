"""Acceptance Tests for Stage C HPI Sensitivity Analysis (T-20).

Requirements:
- T-20: Parameter Sensitivity Analysis:
  - Component weight perturbations (±0.05) maintain Spearman rank correlation >= 0.97.
  - Top-decile hotspot overlap >= 85.0%.
  - Confirms robustness against arbitrary heuristic weight changes.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import spearmanr

from gis.heat_priority.scoring import (
    DEFAULT_WEIGHT_BUILTUP,
    DEFAULT_WEIGHT_PERSISTENCE,
    DEFAULT_WEIGHT_THERMAL,
    DEFAULT_WEIGHT_VEGETATION,
    compute_heat_priority_composite,
)


def _top_decile_overlap(base: np.ndarray, pert: np.ndarray) -> float:
    """Calculate percentage overlap in top 10% of ranked cells."""
    n = len(base)
    k = max(1, int(0.10 * n))
    top_base = set(np.argsort(base)[-k:])
    top_pert = set(np.argsort(pert)[-k:])
    return len(top_base.intersection(top_pert)) / float(k) * 100.0


def test_t20_weight_perturbation_sensitivity() -> None:
    """T-20: Test that ±0.05 component weight perturbations maintain rank correlation >= 0.97 and top-decile overlap >= 85%."""
    rng = np.random.default_rng(12345)
    n = 2000

    lst = rng.uniform(32.0, 48.0, size=n)
    freq = rng.uniform(0.10, 0.90, size=n)
    ndvi = rng.uniform(0.08, 0.40, size=n)
    ndbi = rng.uniform(-0.15, 0.12, size=n)

    # Baseline HPI (0.40, 0.30, 0.15, 0.15)
    base_hpi, _, _, _, _ = compute_heat_priority_composite(
        observed_lst=lst,
        hotspot_frequency=freq,
        ndvi=ndvi,
        ndbi=ndbi,
        w_t=DEFAULT_WEIGHT_THERMAL,
        w_p=DEFAULT_WEIGHT_PERSISTENCE,
        w_v=DEFAULT_WEIGHT_VEGETATION,
        w_b=DEFAULT_WEIGHT_BUILTUP,
    )

    perturbations = [
        # (w_t, w_p, w_v, w_b)
        (0.45, 0.25, 0.15, 0.15),  # High thermal
        (0.35, 0.35, 0.15, 0.15),  # High persistence
        (0.40, 0.30, 0.20, 0.10),  # High vegetation
        (0.40, 0.30, 0.10, 0.20),  # High built-up
    ]

    for wt, wp, wv, wb in perturbations:
        pert_hpi, _, _, _, _ = compute_heat_priority_composite(
            observed_lst=lst,
            hotspot_frequency=freq,
            ndvi=ndvi,
            ndbi=ndbi,
            w_t=wt,
            w_p=wp,
            w_v=wv,
            w_b=wb,
        )

        rho, _ = spearmanr(base_hpi, pert_hpi)
        overlap = _top_decile_overlap(base_hpi, pert_hpi)

        assert rho >= 0.970, (
            f"Spearman rank correlation {rho:.4f} fell below 0.970 for weights ({wt}, {wp}, {wv}, {wb})"
        )
        assert overlap >= 85.0, (
            f"Top-decile overlap {overlap:.2f}% fell below 85.0% for weights ({wt}, {wp}, {wv}, {wb})"
        )
