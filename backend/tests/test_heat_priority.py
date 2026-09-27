"""Unit Tests for HEATSENSE AI Heat Priority Engine.

Tests:
1. LST Severity calculation (percentile ranking on observed satellite LST).
2. Heat persistence evaluation (recurrence frequency & persistence flag fusion).
3. Quality confidence calculation (observation support & eligibility context).
4. Separation of observed LST from model prediction (primary vs supplementary evidence).
5. Transparent scoring combination with configurable weights.
6. Preservation of individual distinct layers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gis.heat_priority.lst_priority import compute_lst_severity
from gis.heat_priority.persistence import compute_heat_persistence
from gis.heat_priority.quality import compute_quality_confidence
from gis.heat_priority.scoring import (
    DEFAULT_PERSISTENCE_WEIGHT,
    DEFAULT_SEVERITY_WEIGHT,
    compute_heat_priority_layers,
    compute_heat_priority_score,
)


def test_lst_severity_ranking() -> None:
    """Test that observed LST is mapped to empirical percentiles [0.0, 1.0]."""
    lst_vals = np.array([30.0, 32.0, 34.0, 36.0, 40.0])
    severity = compute_lst_severity(lst_vals)

    assert severity.shape == lst_vals.shape
    assert severity[0] == pytest.approx(0.0)
    assert severity[-1] == pytest.approx(1.0)
    assert np.all(np.diff(severity) > 0)  # Monotonically increasing


def test_lst_severity_handles_nodata() -> None:
    """Test that NoData / non-finite values are assigned NaN without disturbing valid ranks."""
    lst_vals = np.array([30.0, -9999.0, 40.0, np.nan, 35.0])
    severity = compute_lst_severity(lst_vals)

    assert np.isnan(severity[1])
    assert np.isnan(severity[3])
    assert severity[0] == pytest.approx(0.0)
    assert severity[4] == pytest.approx(0.5)
    assert severity[2] == pytest.approx(1.0)


def test_heat_persistence_scoring() -> None:
    """Test that multi-season recurrence frequency is normalized in [0.0, 1.0]."""
    freqs = np.array([0.0, 0.10, 0.25, 0.50, 1.0])
    scores = compute_heat_persistence(freqs)

    assert scores[0] == 0.0
    assert scores[2] == 0.25
    assert scores[3] == 0.50
    assert scores[4] == 1.0


def test_heat_persistence_with_flag() -> None:
    """Test that is_persistent_hotspot flag ensures at least persistence threshold."""
    freqs = np.array([0.15, 0.15])
    flags = np.array([False, True])
    scores = compute_heat_persistence(freqs, is_persistent_hotspot=flags)

    assert scores[0] == pytest.approx(0.15)
    assert scores[1] == pytest.approx(0.25)


def test_quality_confidence_temporal_support() -> None:
    """Test that higher scene support yields higher quality confidence."""
    obs = np.array([0, 1, 2, 4])
    conf = compute_quality_confidence(obs)

    assert conf[0] == 0.0
    assert conf[1] == pytest.approx(0.65)
    assert conf[2] == pytest.approx(0.90)
    assert conf[3] == pytest.approx(1.0)


def test_quality_confidence_eligibility_weighting() -> None:
    """Test that FLAG status discounts confidence and EXCLUDE zeroes it."""
    obs = np.array([3, 3, 3])
    elig = np.array([1.0, 2.0, 0.0])  # ACCEPT, FLAG, EXCLUDE
    conf = compute_quality_confidence(obs, eligibility_code=elig)

    assert conf[0] == pytest.approx(1.0)
    assert conf[1] == pytest.approx(0.85)  # 1.0 * 0.85
    assert conf[2] == pytest.approx(0.0)


def test_heat_priority_transparent_scoring() -> None:
    """Test transparent weighted combination with default weights (0.60 sev, 0.40 pers)."""
    sev = np.array([1.0, 0.5, 0.0])
    pers = np.array([1.0, 0.5, 0.0])
    score = compute_heat_priority_score(sev, pers, w_severity=0.60, w_persistence=0.40)

    assert score[0] == pytest.approx(1.0)
    assert score[1] == pytest.approx(0.5)
    assert score[2] == pytest.approx(0.0)


def test_heat_priority_custom_weights() -> None:
    """Test custom severity and persistence weights."""
    sev = np.array([1.0])
    pers = np.array([0.0])
    # 80% severity, 20% persistence
    score = compute_heat_priority_score(sev, pers, w_severity=0.80, w_persistence=0.20)
    assert score[0] == pytest.approx(0.80)


def test_heat_priority_layers_preservation() -> None:
    """Test that all component layers are preserved distinctly and not collapsed into a single black-box score."""
    observed_lst = np.array([30.0, 35.0, 42.0])
    model_pred = np.array([31.0, 34.0, 39.0])
    freq = np.array([0.0, 0.30, 0.60])
    obs_count = np.array([3, 2, 4])

    layers = compute_heat_priority_layers(
        observed_lst=observed_lst,
        hotspot_frequency=freq,
        obs_count=obs_count,
        model_prediction=model_pred,
    )

    # Invariant: Component layers remain separately inspectable
    assert len(layers.heat_severity) == 3
    assert len(layers.heat_persistence) == 3
    assert len(layers.quality_confidence) == 3
    assert layers.model_uncertainty is not None
    assert len(layers.model_uncertainty) == 3

    # Residuals: |30-31|=1.0, |35-34|=1.0, |42-39|=3.0
    assert layers.model_uncertainty[0] == pytest.approx(1.0)
    assert layers.model_uncertainty[1] == pytest.approx(1.0)
    assert layers.model_uncertainty[2] == pytest.approx(3.0)

    # Priority score is populated
    assert np.all(layers.heat_priority_score >= 0.0)
    assert np.all(layers.heat_priority_score <= 1.0)

    # DataFrame conversion works cleanly
    df = layers.to_dataframe()
    assert "heat_severity" in df.columns
    assert "heat_persistence" in df.columns
    assert "quality_confidence" in df.columns
    assert "model_uncertainty" in df.columns
    assert "heat_priority_score" in df.columns
