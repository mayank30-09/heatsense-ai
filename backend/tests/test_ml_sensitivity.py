"""Tests for ML Sensitivity, Residual Calculations, and Temporal Splits."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def test_residual_and_absolute_error_formula():
    """Verify residual = target - prediction and absolute_error = abs(residual)."""
    target = np.array([35.2, 42.1, 28.0, 50.4])
    prediction = np.array([34.0, 43.1, 28.0, 48.0])

    residual = target - prediction
    abs_err = np.abs(residual)

    np.testing.assert_allclose(residual, [1.2, -1.0, 0.0, 2.4])
    np.testing.assert_allclose(abs_err, [1.2, 1.0, 0.0, 2.4])


def test_temporal_split_temporal_leakage_prevention():
    """Verify training period strictly precedes validation period in temporal validation."""
    years = np.array([2022, 2022, 2023, 2024, 2025, 2026])

    # Split 1: 2022-2024 -> 2025
    train_mask_1 = np.isin(years, [2022, 2023, 2024])
    val_mask_1 = np.isin(years, [2025])
    assert not np.any(years[train_mask_1] >= 2025), "Training set contains validation or future year observations!"

    # Split 2: 2022-2025 -> 2026
    train_mask_2 = np.isin(years, [2022, 2023, 2024, 2025])
    val_mask_2 = np.isin(years, [2026])
    assert not np.any(years[train_mask_2] >= 2026), "Training set contains validation year observations!"


def test_flag_weight_assignment():
    """Verify sample weights assign 1.0 to ACCEPT, configured weight to FLAG, and 0.0 to EXCLUDE."""
    eligibility = np.array(["ACCEPT", "FLAG", "ACCEPT", "EXCLUDE", "FLAG"])
    flag_weight = 0.50

    sample_weights = np.ones(len(eligibility), dtype=np.float32)
    sample_weights[eligibility == "FLAG"] = flag_weight
    sample_weights[eligibility == "EXCLUDE"] = 0.0

    expected = np.array([1.0, 0.50, 1.0, 0.0, 0.50], dtype=np.float32)
    np.testing.assert_allclose(sample_weights, expected)
