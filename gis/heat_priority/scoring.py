"""Transparent Heat Priority Scoring Engine.

Combines thermal evidence layers transparently without collapsing them into an opaque black box.

Scientific Requirements:
1. OBSERVED LST is PRIMARY THERMAL EVIDENCE (never substituted by model predictions).
2. MODEL PREDICTION is SUPPLEMENTARY MODEL EVIDENCE (stored as distinct contextual layer).
3. Component layers (severity, persistence, quality, uncertainty) are preserved separately.
4. Formula:
   HeatPriority = w1 * heat_severity + w2 * heat_persistence
   with configurable default weights (w1 = 0.60, w2 = 0.40).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np
import pandas as pd

from gis.heat_priority.lst_priority import compute_lst_severity
from gis.heat_priority.persistence import compute_heat_persistence
from gis.heat_priority.quality import compute_quality_confidence

DEFAULT_SEVERITY_WEIGHT: float = 0.60
DEFAULT_PERSISTENCE_WEIGHT: float = 0.40


@dataclass(frozen=True)
class HeatPriorityLayers:
    """Container holding distinct, uncollapsed heat priority layers."""

    heat_severity: np.ndarray
    heat_persistence: np.ndarray
    quality_confidence: np.ndarray
    model_uncertainty: np.ndarray | None
    heat_priority_score: np.ndarray
    weights: dict[str, float]

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
        return pd.DataFrame(data, index=index)


def compute_heat_priority_score(
    heat_severity: np.ndarray | pd.Series,
    heat_persistence: np.ndarray | pd.Series,
    w_severity: float = DEFAULT_SEVERITY_WEIGHT,
    w_persistence: float = DEFAULT_PERSISTENCE_WEIGHT,
) -> np.ndarray:
    """
    Compute transparent Heat Priority composite score.

    Parameters
    ----------
    heat_severity : np.ndarray or pd.Series
        Thermal severity percentile [0.0, 1.0] derived from observed satellite LST.
    heat_persistence : np.ndarray or pd.Series
        Normalized multi-season recurrence frequency [0.0, 1.0].
    w_severity : float
        Weight for observed LST severity (default 0.60).
    w_persistence : float
        Weight for multi-season persistence (default 0.40).

    Returns
    -------
    np.ndarray
        Composite priority score in [0.0, 1.0].
    """
    total_w = w_severity + w_persistence
    if total_w <= 0:
        raise ValueError("Sum of severity and persistence weights must be positive.")

    w1 = w_severity / total_w
    w2 = w_persistence / total_w

    sev = np.asarray(heat_severity, dtype=np.float64)
    pers = np.asarray(heat_persistence, dtype=np.float64)

    # Valid mask where both components are valid
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
    w_severity: float = DEFAULT_SEVERITY_WEIGHT,
    w_persistence: float = DEFAULT_PERSISTENCE_WEIGHT,
    valid_mask: np.ndarray | pd.Series | None = None,
) -> HeatPriorityLayers:
    """
    Generate all separate component layers and the transparent Heat Priority score.

    Parameters
    ----------
    observed_lst : np.ndarray or pd.Series
        Observed Land Surface Temperature (degC) — PRIMARY THERMAL EVIDENCE.
    hotspot_frequency : np.ndarray or pd.Series
        Normalized multi-season extreme recurrence frequency.
    obs_count : np.ndarray or pd.Series
        Clear-sky seasonal observation support count.
    is_persistent_hotspot : np.ndarray or pd.Series, optional
        Precomputed multi-season persistence flag.
    eligibility_code : np.ndarray or pd.Series, optional
        Policy D eligibility code (1.0=ACCEPT, 2.0=FLAG, 0.0=EXCLUDE).
    qa_uncertainty_k : np.ndarray or pd.Series, optional
        USGS Level-2 radiometric uncertainty (Kelvin).
    model_prediction : np.ndarray or pd.Series, optional
        Trained model LST prediction (degC) — SUPPLEMENTARY MODEL EVIDENCE.
    w_severity : float
        Severity weight (default 0.60).
    w_persistence : float
        Persistence weight (default 0.40).
    valid_mask : np.ndarray or pd.Series, optional
        Boolean valid mask.

    Returns
    -------
    HeatPriorityLayers
        Container with severity, persistence, quality, model uncertainty, and priority score.
    """
    # 1. Compute LST Severity from OBSERVED LST (Primary Evidence)
    heat_severity = compute_lst_severity(observed_lst, valid_mask=valid_mask)

    # 2. Compute Heat Persistence
    heat_persistence = compute_heat_persistence(
        hotspot_frequency, is_persistent_hotspot=is_persistent_hotspot, valid_mask=valid_mask
    )

    # 3. Compute Quality Confidence
    quality_confidence = compute_quality_confidence(
        obs_count,
        eligibility_code=eligibility_code,
        qa_uncertainty_k=qa_uncertainty_k,
        valid_mask=valid_mask,
    )

    # 4. Compute Model Uncertainty / Residual Context if supplementary prediction provided
    model_uncertainty = None
    if model_prediction is not None:
        obs_arr = np.asarray(observed_lst, dtype=np.float64)
        pred_arr = np.asarray(model_prediction, dtype=np.float64)
        residual = obs_arr - pred_arr
        # Model uncertainty quantified by absolute residual magnitude
        model_uncertainty = np.where(np.isfinite(residual), np.abs(residual), np.nan)

    # 5. Transparent Weighted Priority Score
    priority_score = compute_heat_priority_score(
        heat_severity, heat_persistence, w_severity=w_severity, w_persistence=w_persistence
    )

    return HeatPriorityLayers(
        heat_severity=heat_severity,
        heat_persistence=heat_persistence,
        quality_confidence=quality_confidence,
        model_uncertainty=model_uncertainty,
        heat_priority_score=priority_score,
        weights={"w_severity": w_severity, "w_persistence": w_persistence},
    )
