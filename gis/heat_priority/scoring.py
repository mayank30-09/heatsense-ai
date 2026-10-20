"""Transparent Heat Priority Scoring Engine for HEATSENSE AI.

Combines thermal evidence layers transparently without collapsing them into an opaque black box.
Supports both the canonical Stage C 4-Component formulation and the backward-compatible
diagnostic layer preservation.

Canonical Stage C 4-Component Formulation:
    HPI = 100.0 * (w_T * T_norm + w_P * P_persist + w_V * V_deficit + w_B * B_density)

Approved Baseline Parameters:
- Thermal Severity Weight (w_T): 0.40 (LST bounds [30.0, 50.0] deg C)
- Multi-Year Persistence Weight (w_P): 0.30 (Recurrence frequency in [0.0, 1.0])
- Vegetation Deficit Weight (w_V): 0.15 (NDVI deficit bounds [0.05, 0.45])
- Built-Up Density Weight (w_B): 0.15 (NDBI density bounds [-0.25, 0.15])

Scientific Invariants:
1. OBSERVED LST is PRIMARY THERMAL EVIDENCE (never substituted by model predictions).
2. MODEL PREDICTION is SUPPLEMENTARY MODEL EVIDENCE (for spatial/hypothetical interpolation).
3. Missing summer observed LST results in strict NULL score (no modeled temperature fallback).
4. All components are bounded in [0.0, 1.0] and composite HPI is bounded in [0.0, 100.0].
5. Distinct components and confidence indices are preserved separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np
import pandas as pd

from gis.heat_priority.lst_priority import (
    DEFAULT_NDBI_MAX,
    DEFAULT_NDBI_MIN,
    DEFAULT_NDVI_MIN,
    DEFAULT_NDVI_TARGET,
    DEFAULT_T_MAX,
    DEFAULT_T_MIN,
    compute_builtup_density,
    compute_lst_severity,
    compute_vegetation_deficit,
    normalize_lst_severity,
)
from gis.heat_priority.persistence import compute_heat_persistence
from gis.heat_priority.quality import (
    compute_calibrated_confidence_index,
    compute_obs_multiplier,
    compute_qa_multiplier,
    compute_quality_confidence,
    compute_season_multiplier,
)

# Approved canonical Stage C weights
DEFAULT_WEIGHT_THERMAL: float = 0.40
DEFAULT_WEIGHT_PERSISTENCE: float = 0.30
DEFAULT_WEIGHT_VEGETATION: float = 0.15
DEFAULT_WEIGHT_BUILTUP: float = 0.15

# Legacy 2-component weights
DEFAULT_SEVERITY_WEIGHT: float = 0.60
DEFAULT_PERSISTENCE_WEIGHT: float = 0.40


def sanitize_for_sql(val: Any) -> Any:
    """
    Convert float NaNs, out-of-range sentinels (<= -9000), or pd.NA to genuine SQL None.

    Ensures PostgreSQL receives true SQL NULL rather than NaN, 0.0, or -9999.0.
    """
    if val is None or val is pd.NA:
        return None
    try:
        if isinstance(val, (float, np.floating)):
            if np.isnan(val) or val <= -9000.0:
                return None
            return float(val)
        if isinstance(val, (int, np.integer)):
            if val <= -9000:
                return None
            return int(val)
    except Exception:
        pass
    return val


@dataclass(frozen=True)
class HeatPriorityLayers:
    """Container holding distinct, uncollapsed heat priority layers."""

    heat_severity: np.ndarray
    heat_persistence: np.ndarray
    quality_confidence: np.ndarray
    model_uncertainty: np.ndarray | None
    heat_priority_score: np.ndarray
    weights: dict[str, float]
    vegetation_deficit: np.ndarray | None = None
    builtup_density: np.ndarray | None = None
    confidence_index: np.ndarray | None = None
    confidence_tier: np.ndarray | None = None
    spec_version: str = "v2.0"

    def to_dataframe(self, index: pd.Index | None = None) -> pd.DataFrame:
        """Export layers to a structured pandas DataFrame."""
        data = {
            "heat_severity": self.heat_severity,
            "heat_persistence": self.heat_persistence,
            "quality_confidence": self.quality_confidence,
            "heat_priority_score": self.heat_priority_score,
        }
        if self.model_uncertainty is not None:
            data["model_uncertainty"] = self.model_uncertainty
        if self.vegetation_deficit is not None:
            data["vegetation_deficit"] = self.vegetation_deficit
        if self.builtup_density is not None:
            data["builtup_density"] = self.builtup_density
        if self.confidence_index is not None:
            data["confidence_index"] = self.confidence_index
        if self.confidence_tier is not None:
            data["confidence_tier"] = self.confidence_tier
        return pd.DataFrame(data, index=index)

    def to_sql_records(self, index: pd.Index | None = None) -> list[dict[str, Any]]:
        """Export layers to a list of dicts with genuine SQL None for all invalid/missing entries."""
        df = self.to_dataframe(index=index)
        records = df.to_dict(orient="records")
        return [{k: sanitize_for_sql(v) for k, v in r.items()} for r in records]


def compute_heat_priority_composite(
    observed_lst: np.ndarray | pd.Series,
    hotspot_frequency: np.ndarray | pd.Series,
    ndvi: np.ndarray | pd.Series,
    ndbi: np.ndarray | pd.Series,
    w_t: float = DEFAULT_WEIGHT_THERMAL,
    w_p: float = DEFAULT_WEIGHT_PERSISTENCE,
    w_v: float = DEFAULT_WEIGHT_VEGETATION,
    w_b: float = DEFAULT_WEIGHT_BUILTUP,
    t_min: float = DEFAULT_T_MIN,
    t_max: float = DEFAULT_T_MAX,
    v_min: float = DEFAULT_NDVI_MIN,
    v_target: float = DEFAULT_NDVI_TARGET,
    b_min: float = DEFAULT_NDBI_MIN,
    b_max: float = DEFAULT_NDBI_MAX,
    valid_mask: np.ndarray | pd.Series | None = None,
    valid_seasons_count: np.ndarray | pd.Series | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute 4-component Heat Priority Index composite score and its component layers in [0.0, 100.0].

    Returns
    -------
    tuple of (hpi_score, t_norm, p_persist, v_deficit, b_density)
    """
    total_w = w_t + w_p + w_v + w_b
    if not (0.999 <= total_w <= 1.001):
        raise ValueError(f"Sum of component weights must equal 1.0 (got {total_w})")

    t_norm = normalize_lst_severity(observed_lst, t_min=t_min, t_max=t_max, valid_mask=valid_mask)
    p_persist = compute_heat_persistence(
        hotspot_frequency, valid_mask=valid_mask, valid_seasons_count=valid_seasons_count
    )
    v_def = compute_vegetation_deficit(ndvi, v_min=v_min, v_target=v_target, valid_mask=valid_mask)
    b_den = compute_builtup_density(ndbi, b_min=b_min, b_max=b_max, valid_mask=valid_mask)

    hpi_score = np.full(t_norm.shape, np.nan, dtype=np.float64)
    eligible = np.isfinite(t_norm) & np.isfinite(p_persist) & np.isfinite(v_def) & np.isfinite(b_den)

    if np.any(eligible):
        raw_score = 100.0 * (
            w_t * t_norm[eligible]
            + w_p * p_persist[eligible]
            + w_v * v_def[eligible]
            + w_b * b_den[eligible]
        )
        hpi_score[eligible] = np.clip(raw_score, 0.0, 100.0)

    return hpi_score, t_norm, p_persist, v_def, b_den


def compute_heat_priority_score(
    heat_severity: np.ndarray | pd.Series,
    heat_persistence: np.ndarray | pd.Series,
    w_severity: float = DEFAULT_SEVERITY_WEIGHT,
    w_persistence: float = DEFAULT_PERSISTENCE_WEIGHT,
) -> np.ndarray:
    """
    Compute transparent Heat Priority composite score in [0.0, 1.0].
    Preserved for backward-compatibility with Stage B tests.
    """
    total_w = w_severity + w_persistence
    if total_w <= 0:
        raise ValueError("Sum of severity and persistence weights must be positive.")

    w1 = w_severity / total_w
    w2 = w_persistence / total_w

    sev = np.asarray(heat_severity, dtype=np.float64)
    pers = np.asarray(heat_persistence, dtype=np.float64)

    valid_mask = np.isfinite(sev) & np.isfinite(pers)
    score = np.full(sev.shape, np.nan, dtype=np.float64)
    score[valid_mask] = np.clip(w1 * sev[valid_mask] + w2 * pers[valid_mask], 0.0, 1.0)
    return score


def compute_heat_priority_layers(
    observed_lst: np.ndarray | pd.Series,
    hotspot_frequency: np.ndarray | pd.Series,
    obs_count: np.ndarray | pd.Series,
    is_persistent_hotspot: np.ndarray | pd.Series | None = None,
    eligibility_code: np.ndarray | pd.Series | None = None,
    qa_uncertainty_k: np.ndarray | pd.Series | None = None,
    model_prediction: np.ndarray | pd.Series | None = None,
    valid_mask: np.ndarray | pd.Series | None = None,
    w_severity: float = DEFAULT_SEVERITY_WEIGHT,
    w_persistence: float = DEFAULT_PERSISTENCE_WEIGHT,
) -> HeatPriorityLayers:
    """
    Compute transparent heat priority layers preserving distinct component layers.
    Maintains compatibility with test_heat_priority.py.
    """
    heat_severity = compute_lst_severity(observed_lst, valid_mask=valid_mask)
    heat_persistence = compute_heat_persistence(
        hotspot_frequency, is_persistent_hotspot=is_persistent_hotspot, valid_mask=valid_mask
    )
    quality_confidence = compute_quality_confidence(
        obs_count,
        eligibility_code=eligibility_code,
        qa_uncertainty_k=qa_uncertainty_k,
        valid_mask=valid_mask,
    )

    model_uncertainty: np.ndarray | None = None
    if model_prediction is not None:
        obs_arr = np.asarray(observed_lst, dtype=np.float64)
        pred_arr = np.asarray(model_prediction, dtype=np.float64)
        model_uncertainty = np.abs(obs_arr - pred_arr)

    priority_score = compute_heat_priority_score(
        heat_severity, heat_persistence, w_severity=w_severity, w_persistence=w_persistence
    )

    weights = {"w_severity": w_severity, "w_persistence": w_persistence}

    return HeatPriorityLayers(
        heat_severity=heat_severity,
        heat_persistence=heat_persistence,
        quality_confidence=quality_confidence,
        model_uncertainty=model_uncertainty,
        heat_priority_score=priority_score,
        weights=weights,
    )
