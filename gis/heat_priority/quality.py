"""Calibrated Multiplier-Based Confidence Index for Heat Priority.

Evaluates observational, radiometric, seasonal, and optical reliability
to produce an uncompromised scalar Confidence Index in [0.0, 1.0].

Formula:
    CI = C_obs * C_qa * C_season * C_sentinel

Scientific Invariants:
1. Confidence factors are non-increasing as uncertainty increases.
2. In tropical Surat, nominal clear-sky ST_QA <= 2.50 K receives C_qa = 1.00.
3. Summer-only clear-sky passes receive C_season = 0.70, resulting in CI = 0.70 (MODERATE).
4. Multi-season dry (Summer + Winter) clear-sky passes receive C_season = 0.90, resulting in CI = 0.90 (HIGH).
5. Missing summer observations cannot exceed CI < 0.50 (LOW or INSUFFICIENT).
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

CONFIDENCE_HIGH_THRESHOLD: float = 0.75
CONFIDENCE_MODERATE_THRESHOLD: float = 0.50
CONFIDENCE_LOW_THRESHOLD: float = 0.25

TIER_HIGH: str = "HIGH"
TIER_MODERATE: str = "MODERATE"
TIER_LOW: str = "LOW"
TIER_INSUFFICIENT: str = "INSUFFICIENT"


def compute_obs_multiplier(obs_count: np.ndarray | pd.Series | float) -> np.ndarray | float:
    """Compute C_obs based on clear-sky scene count."""
    is_scalar = np.ndim(obs_count) == 0
    obs = np.asarray(obs_count, dtype=np.float64)

    c_obs = np.where(
        ~np.isfinite(obs) | (obs < 1.0),
        0.0,
        np.where(
            obs >= 4.0,
            1.00,
            np.where(obs >= 2.0, 0.85, 0.60),  # OBS == 1 receives 0.60
        ),
    )
    return float(c_obs) if is_scalar else c_obs


def compute_quality_confidence(
    obs_count: np.ndarray | pd.Series,
    eligibility_code: np.ndarray | pd.Series | None = None,
    qa_uncertainty_k: np.ndarray | pd.Series | None = None,
    valid_mask: np.ndarray | pd.Series | None = None,
) -> np.ndarray:
    """
    Compute observation quality confidence score [0.0, 1.0] (legacy/backward-compatible).
    """
    obs = np.asarray(obs_count, dtype=np.float64)

    if valid_mask is None:
        mask = np.isfinite(obs) & (obs >= 0.0)
    else:
        mask = np.asarray(valid_mask, dtype=bool) & np.isfinite(obs) & (obs >= 0.0)

    confidence = np.full(obs.shape, np.nan, dtype=np.float64)
    obs_v = obs[mask]

    c_temporal = np.where(
        obs_v >= 3.0,
        1.0,
        np.where(obs_v == 2.0, 0.90, np.where(obs_v == 1.0, 0.65, 0.0)),
    )

    if eligibility_code is not None:
        elig = np.asarray(eligibility_code, dtype=np.float64)[mask]
        c_temporal = np.where(elig == 0.0, 0.0, np.where(elig == 2.0, c_temporal * 0.85, c_temporal))

    if qa_uncertainty_k is not None:
        qa = np.asarray(qa_uncertainty_k, dtype=np.float64)[mask]
        valid_qa = np.isfinite(qa) & (qa > 0.0)
        qa_penalty = np.where(valid_qa & (qa > 4.0), np.clip(1.0 - (qa - 4.0) * 0.1, 0.5, 1.0), 1.0)
        c_temporal = c_temporal * qa_penalty

    confidence[mask] = np.clip(c_temporal, 0.0, 1.0)
    return confidence


def compute_qa_multiplier(qa_uncertainty_k: np.ndarray | pd.Series | float | None) -> np.ndarray | float:
    """Compute C_qa based on Landsat ST_QA uncertainty in Kelvin."""
    if qa_uncertainty_k is None:
        return 0.50

    is_scalar = np.ndim(qa_uncertainty_k) == 0
    qa = np.asarray(qa_uncertainty_k, dtype=np.float64)

    c_qa = np.where(
        ~np.isfinite(qa) | (qa <= 0.0),
        0.50,
        np.where(
            qa <= 2.50,
            1.00,
            np.where(qa <= 3.50, 0.80, 0.50),
        ),
    )
    return float(c_qa) if is_scalar else c_qa


def compute_season_multiplier(
    has_summer: bool | np.ndarray = True,
    has_winter: bool | np.ndarray = True,
    has_post_monsoon: bool | np.ndarray = False,
    has_monsoon: bool | np.ndarray = False,
) -> np.ndarray | float:
    """
    Compute C_season based on available seasonal profiles across the annual thermal cycle.
    """
    is_scalar = (
        np.ndim(has_summer) == 0
        and np.ndim(has_winter) == 0
        and np.ndim(has_post_monsoon) == 0
        and np.ndim(has_monsoon) == 0
    )

    s = np.asarray(has_summer, dtype=bool)
    w = np.asarray(has_winter, dtype=bool)
    pm = np.asarray(has_post_monsoon, dtype=bool)
    m = np.asarray(has_monsoon, dtype=bool)

    # Broadcast to common shape
    s, w, pm, m = np.broadcast_arrays(s, w, pm, m)

    c_season = np.zeros(s.shape, dtype=np.float64)

    # 1. Full multi-season profile: Summer + Winter + Post-Monsoon (± Monsoon)
    full_profile = s & w & pm
    c_season = np.where(full_profile, 1.00, c_season)

    # 2. Dry season complete: Summer + Winter (missing Post-Monsoon & Monsoon)
    dry_complete = s & w & (~pm)
    c_season = np.where(dry_complete, 0.90, c_season)

    # 3. Summer + Monsoon / Post-Monsoon (missing Winter)
    summer_partial = s & (~w) & (m | pm)
    c_season = np.where(summer_partial, 0.80, c_season)

    # 4. Summer Only
    summer_only = s & (~w) & (~pm) & (~m)
    c_season = np.where(summer_only, 0.70, c_season)

    # 5. Summer missing: Winter + Post-Monsoon
    winter_pm = (~s) & w & pm
    c_season = np.where(winter_pm, 0.40, c_season)

    # 6. Summer missing: Winter only
    winter_only = (~s) & w & (~pm)
    c_season = np.where(winter_only, 0.35, c_season)

    # 7. Monsoon Only
    monsoon_only = (~s) & (~w) & (~pm) & m
    c_season = np.where(monsoon_only, 0.25, c_season)

    return float(c_season.item()) if is_scalar else c_season


def classify_confidence_tier(confidence_index: float | np.ndarray) -> str | np.ndarray:
    """Classify scalar confidence score into its canonical tier."""
    is_scalar = np.ndim(confidence_index) == 0
    ci = np.asarray(confidence_index, dtype=np.float64)

    tier = np.where(
        ci >= CONFIDENCE_HIGH_THRESHOLD,
        TIER_HIGH,
        np.where(
            ci >= CONFIDENCE_MODERATE_THRESHOLD,
            TIER_MODERATE,
            np.where(ci >= CONFIDENCE_LOW_THRESHOLD, TIER_LOW, TIER_INSUFFICIENT),
        ),
    )
    return str(tier.item()) if is_scalar else tier


def compute_calibrated_confidence_index(
    obs_count: np.ndarray | pd.Series | float,
    qa_uncertainty_k: np.ndarray | pd.Series | float | None = None,
    has_summer: bool | np.ndarray = True,
    has_winter: bool | np.ndarray = True,
    has_post_monsoon: bool | np.ndarray = False,
    has_monsoon: bool | np.ndarray = False,
    c_sentinel: np.ndarray | pd.Series | float = 1.00,
) -> tuple[np.ndarray | float, str | np.ndarray]:
    """
    Compute calibrated Confidence Index and categorical tier.

    Returns
    -------
    tuple of (confidence_index, confidence_tier)
    """
    c_obs = compute_obs_multiplier(obs_count)
    c_qa = compute_qa_multiplier(qa_uncertainty_k)
    c_season = compute_season_multiplier(has_summer, has_winter, has_post_monsoon, has_monsoon)
    c_sent = np.asarray(c_sentinel, dtype=np.float64)

    ci = np.clip(c_obs * c_qa * c_season * c_sent, 0.0, 1.0)
    tier = classify_confidence_tier(ci)

    if np.ndim(ci) == 0:
        return float(ci), str(tier)
    return ci, tier
