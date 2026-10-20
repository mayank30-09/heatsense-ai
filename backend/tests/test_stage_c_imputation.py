"""Acceptance Tests for Optical Sentinel Detection, Imputation, and ML Disqualification (T-12, T-13, T-14, T-15).

Requirements:
- T-12: 8-Connected Moore neighborhood median imputation (>= 4 valid neighbors -> median, flag OPTICAL_IMPUTED_MEDIAN, C_sentinel=0.70).
- T-13: Boundary mean imputation (1–3 valid neighbors -> mean, flag OPTICAL_IMPUTED_BOUNDARY, C_sentinel=0.50).
- T-14: Isolated neutral fallback (0 valid neighbors -> neutral constants, flag OPTICAL_FALLBACK_NEUTRAL, C_sentinel=0.30).
- T-15: ML Disqualification Guardrail (imputed cells disqualified from ML counterfactual cooling simulations).
"""

from __future__ import annotations

import numpy as np
import pytest

from gis.quality.imputation import (
    CONFIDENCE_SENTINEL_BOUNDARY,
    CONFIDENCE_SENTINEL_CLEAN,
    CONFIDENCE_SENTINEL_MEDIAN,
    CONFIDENCE_SENTINEL_NEUTRAL,
    FLAG_BOUNDARY,
    FLAG_CLEAN,
    FLAG_MEDIAN,
    FLAG_NEUTRAL,
    NEUTRAL_OPTICAL_FALLBACK,
    impute_optical_raster,
    is_disqualified_from_ml_scenario,
    is_optical_invalid,
)


def test_t12_eight_connected_median_imputation() -> None:
    """T-12: Test Moore neighborhood median imputation with >= 4 valid neighbors."""
    # 3x3 raster grid with center pixel as sentinel -9999.0
    raster = np.array([
        [0.10, 0.20, 0.30],
        [0.40, -9999.0, 0.50],
        [0.60, 0.70, 0.80],
    ])

    imputed_raster, flags, c_factors = impute_optical_raster(
        raster,
        index_name="NDVI",
    )

    # Valid neighbors: 8 -> Median of [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80] is 0.45
    assert flags[1, 1] == FLAG_MEDIAN
    assert c_factors[1, 1] == pytest.approx(CONFIDENCE_SENTINEL_MEDIAN)  # 0.70
    assert imputed_raster[1, 1] == pytest.approx(0.45)

    # Unaffected neighbor remains unchanged
    assert flags[0, 0] == FLAG_CLEAN
    assert c_factors[0, 0] == pytest.approx(CONFIDENCE_SENTINEL_CLEAN)
    assert imputed_raster[0, 0] == pytest.approx(0.10)


def test_t13_boundary_mean_imputation() -> None:
    """T-13: Test mean imputation when 1 to 3 valid neighbors exist."""
    raster = np.array([
        [-9999.0, 0.20, -9999.0],
        [0.40, -9999.0, -9999.0],
        [-9999.0, -9999.0, -9999.0],
    ])

    imputed_raster, flags, c_factors = impute_optical_raster(
        raster,
        index_name="NDBI",
    )

    # (0, 0) has 2 valid neighbors (0.20 and 0.40) -> Mean is 0.30
    assert flags[0, 0] == FLAG_BOUNDARY
    assert c_factors[0, 0] == pytest.approx(CONFIDENCE_SENTINEL_BOUNDARY)  # 0.50
    assert imputed_raster[0, 0] == pytest.approx(0.30)


def test_t14_isolated_neutral_fallback() -> None:
    """T-14: Test neutral fallback when 0 valid neighbors exist."""
    raster = np.full((3, 3), -9999.0)

    # Test NDVI fallback
    imputed_ndvi, flags_ndvi, c_ndvi = impute_optical_raster(
        raster,
        index_name="NDVI",
    )
    assert flags_ndvi[1, 1] == FLAG_NEUTRAL
    assert c_ndvi[1, 1] == pytest.approx(CONFIDENCE_SENTINEL_NEUTRAL)  # 0.30
    assert imputed_ndvi[1, 1] == pytest.approx(NEUTRAL_OPTICAL_FALLBACK["NDVI"])  # 0.20

    # Test NDBI fallback
    imputed_ndbi, flags_ndbi, c_ndbi = impute_optical_raster(
        raster,
        index_name="NDBI",
    )
    assert flags_ndbi[1, 1] == FLAG_NEUTRAL
    assert imputed_ndbi[1, 1] == pytest.approx(NEUTRAL_OPTICAL_FALLBACK["NDBI"])  # 0.00


def test_t15_ml_disqualification_guardrail() -> None:
    """T-15: Test that any cell with imputed optical index is disqualified from downstream ML simulations."""
    # Clean cell -> Not disqualified
    assert is_disqualified_from_ml_scenario(FLAG_CLEAN) is False

    # Imputed cells -> Strictly Disqualified
    assert is_disqualified_from_ml_scenario(FLAG_MEDIAN) is True
    assert is_disqualified_from_ml_scenario(FLAG_BOUNDARY) is True
    assert is_disqualified_from_ml_scenario(FLAG_NEUTRAL) is True


def test_is_optical_invalid_robustness() -> None:
    """Test is_optical_invalid across scalars, pandas Series, pd.NA, and boundary limits."""
    import pandas as pd

    # Physical valid bounds [-1.0, 1.0]
    assert is_optical_invalid(0.0) is False
    assert is_optical_invalid(0.5) is False
    assert is_optical_invalid(-0.5) is False
    assert is_optical_invalid(-1.0) is False
    assert is_optical_invalid(1.0) is False

    # Out of physical bounds
    assert is_optical_invalid(1.01) is True
    assert is_optical_invalid(-1.01) is True
    assert is_optical_invalid(10.0) is True

    # Sentinel and missing values
    assert is_optical_invalid(-9999.0) is True
    assert is_optical_invalid(-9000.0) is True
    assert is_optical_invalid(np.nan) is True
    assert is_optical_invalid(float("inf")) is True
    assert is_optical_invalid(None) is True
    assert is_optical_invalid(pd.NA) is True

    # Pandas Series with nullable/NA entries
    s = pd.Series([0.25, -9999.0, pd.NA, np.nan, 1.5, -0.30])
    res = is_optical_invalid(s)
    expected = np.array([False, True, True, True, True, False])
    np.testing.assert_array_equal(res, expected)


def test_ndwi_neutral_fallback() -> None:
    """Test that NDWI neutral fallback uses the approved constant -0.30."""
    raster = np.full((3, 3), -9999.0)
    imputed_ndwi, flags_ndwi, c_ndwi = impute_optical_raster(
        raster,
        index_name="NDWI",
    )
    assert flags_ndwi[1, 1] == FLAG_NEUTRAL
    assert c_ndwi[1, 1] == pytest.approx(CONFIDENCE_SENTINEL_NEUTRAL)  # 0.30
    assert imputed_ndwi[1, 1] == pytest.approx(-0.30)
