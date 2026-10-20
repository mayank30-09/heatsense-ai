"""Acceptance Tests for Stage C Heat Priority Scoring Engine (T-04, T-05, T-06, T-07, T-08).

Requirements:
- T-04: Thermal severity normalization bounds ([30°C, 50°C] -> [0.0, 1.0]).
- T-05: Vegetation deficit normalization bounds ([0.05, 0.45] -> [1.0, 0.0]).
- T-06: Built-up density normalization bounds ([-0.25, 0.15] -> [0.0, 1.0]).
- T-07: Mandatory summer presence policy (Missing summer LST -> HPI is NULL, status INSUFFICIENT_DATA).
- T-08: 4-Component HPI score bounded in [0.0, 100.0] for all valid operational cells.
"""

from __future__ import annotations

import numpy as np
import pytest

from gis.heat_priority.lst_priority import (
    DEFAULT_NDBI_MAX,
    DEFAULT_NDBI_MIN,
    DEFAULT_NDVI_MIN,
    DEFAULT_NDVI_TARGET,
    DEFAULT_T_MAX,
    DEFAULT_T_MIN,
    compute_builtup_density,
    compute_vegetation_deficit,
    normalize_lst_severity,
)
from gis.heat_priority.scoring import (
    DEFAULT_WEIGHT_BUILTUP,
    DEFAULT_WEIGHT_PERSISTENCE,
    DEFAULT_WEIGHT_THERMAL,
    DEFAULT_WEIGHT_VEGETATION,
    HeatPriorityLayers,
    compute_heat_priority_composite,
    compute_heat_priority_layers,
    sanitize_for_sql,
)


def test_t04_lst_thermal_severity_bounds() -> None:
    """T-04: Test thermal severity clamping and scaling with bounds [30.0, 50.0]°C."""
    lst_inputs = np.array([25.0, 30.0, 40.0, 50.0, 55.0])
    t_norm = normalize_lst_severity(
        lst_inputs,
        t_min=DEFAULT_T_MIN,
        t_max=DEFAULT_T_MAX,
    )

    expected = np.array([0.0, 0.0, 0.5, 1.0, 1.0])
    np.testing.assert_allclose(t_norm, expected, atol=1e-5)


def test_t05_vegetation_deficit_bounds() -> None:
    """T-05: Test vegetation deficit inverted scaling with bounds [0.05, 0.45]."""
    ndvi_inputs = np.array([-0.10, 0.05, 0.25, 0.45, 0.60])
    v_deficit = compute_vegetation_deficit(
        ndvi_inputs,
        v_min=DEFAULT_NDVI_MIN,
        v_target=DEFAULT_NDVI_TARGET,
    )

    # NDVI=0.05 -> Deficit=1.0 (maximum deficit)
    # NDVI=0.45 -> Deficit=0.0 (no deficit / lush canopy)
    # NDVI=0.25 -> Deficit=0.5
    expected = np.array([1.0, 1.0, 0.5, 0.0, 0.0])
    np.testing.assert_allclose(v_deficit, expected, atol=1e-5)


def test_t06_built_up_density_bounds() -> None:
    """T-06: Test built-up density scaling with bounds [-0.25, 0.15]."""
    ndbi_inputs = np.array([-0.35, -0.25, -0.05, 0.15, 0.25])
    b_density = compute_builtup_density(
        ndbi_inputs,
        b_min=DEFAULT_NDBI_MIN,
        b_max=DEFAULT_NDBI_MAX,
    )

    # NDBI=-0.25 -> Density=0.0
    # NDBI=0.15 -> Density=1.0
    # NDBI=-0.05 -> Density=0.5
    expected = np.array([0.0, 0.0, 0.5, 1.0, 1.0])
    np.testing.assert_allclose(b_density, expected, atol=1e-5)


def test_t07_missing_summer_policy() -> None:
    """T-07: Test that cells missing observed summer LST yield NaN HPI and cannot receive an operational score."""
    lst = np.array([42.0, np.nan, -9999.0])
    freq = np.array([0.60, 0.80, 0.20])
    ndvi = np.array([0.15, 0.10, 0.30])
    ndbi = np.array([0.05, 0.10, -0.10])

    hpi_scores, t_norm, p_persist, v_def, b_den = compute_heat_priority_composite(
        observed_lst=lst,
        hotspot_frequency=freq,
        ndvi=ndvi,
        ndbi=ndbi,
    )

    assert not np.isnan(hpi_scores[0])
    assert np.isnan(hpi_scores[1])
    assert np.isnan(hpi_scores[2])


def test_t08_four_component_score_bounds() -> None:
    """T-08: Test that 4-component composite score is strictly bounded in [0.0, 100.0]."""
    rng = np.random.default_rng(42)
    n = 1000

    random_lst = rng.uniform(20.0, 60.0, size=n)
    random_freq = rng.uniform(0.0, 1.0, size=n)
    random_ndvi = rng.uniform(-0.20, 0.80, size=n)
    random_ndbi = rng.uniform(-0.40, 0.40, size=n)

    hpi_scores, _, _, _, _ = compute_heat_priority_composite(
        observed_lst=random_lst,
        hotspot_frequency=random_freq,
        ndvi=random_ndvi,
        ndbi=random_ndbi,
        w_t=DEFAULT_WEIGHT_THERMAL,
        w_p=DEFAULT_WEIGHT_PERSISTENCE,
        w_v=DEFAULT_WEIGHT_VEGETATION,
        w_b=DEFAULT_WEIGHT_BUILTUP,
    )

    assert np.all(hpi_scores >= 0.0), "HPI score must be non-negative"
    assert np.all(hpi_scores <= 100.0), "HPI score must not exceed 100.0"

    # Extreme boundary conditions:
    # 1. Absolute minimum condition (cold 25°C, no persistence, lush canopy, zero built-up)
    min_hpi, _, _, _, _ = compute_heat_priority_composite(
        observed_lst=np.array([25.0]),
        hotspot_frequency=np.array([0.0]),
        ndvi=np.array([0.60]),
        ndbi=np.array([-0.30]),
    )
    assert min_hpi[0] == pytest.approx(0.0)

    # 2. Absolute maximum condition (extreme hot 55°C, full persistence 1.0, zero vegetation, extreme built-up)
    max_hpi, _, _, _, _ = compute_heat_priority_composite(
        observed_lst=np.array([55.0]),
        hotspot_frequency=np.array([1.0]),
        ndvi=np.array([0.00]),
        ndbi=np.array([0.30]),
    )
    assert max_hpi[0] == pytest.approx(100.0)


def test_genuine_sql_null_sanitization() -> None:
    """Test that sanitize_for_sql converts float NaNs, sentinels, and pd.NA to genuine SQL None."""
    import pandas as pd

    assert sanitize_for_sql(np.nan) is None
    assert sanitize_for_sql(float("nan")) is None
    assert sanitize_for_sql(-9999.0) is None
    assert sanitize_for_sql(-9999) is None
    assert sanitize_for_sql(-9001.0) is None
    assert sanitize_for_sql(None) is None
    assert sanitize_for_sql(pd.NA) is None

    # Valid values preserved
    assert sanitize_for_sql(42.5) == 42.5
    assert sanitize_for_sql(0.0) == 0.0
    assert sanitize_for_sql(100) == 100
    assert sanitize_for_sql("HIGH") == "HIGH"


def test_heat_priority_layers_sql_records() -> None:
    """Test HeatPriorityLayers.to_sql_records preserves genuine SQL None for missing scores."""
    layers = compute_heat_priority_layers(
        observed_lst=np.array([42.0, np.nan]),
        hotspot_frequency=np.array([0.60, 0.40]),
        obs_count=np.array([4.0, 0.0]),
    )

    records = layers.to_sql_records()
    assert len(records) == 2

    # First record is valid
    assert records[0]["heat_priority_score"] is not None
    assert records[0]["heat_severity"] is not None

    # Second record has missing observed LST -> severity and score must be genuine SQL None
    assert records[1]["heat_severity"] is None
    assert records[1]["heat_priority_score"] is None


def test_component_weight_conservation() -> None:
    """Test that 4-component weights must strictly sum to 1.00."""
    with pytest.raises(ValueError, match="Sum of component weights must equal 1.0"):
        compute_heat_priority_composite(
            observed_lst=np.array([40.0]),
            hotspot_frequency=np.array([0.5]),
            ndvi=np.array([0.2]),
            ndbi=np.array([0.0]),
            w_t=0.50,
            w_p=0.50,
            w_v=0.20,
            w_b=0.20,  # Sum = 1.40 != 1.0
        )
