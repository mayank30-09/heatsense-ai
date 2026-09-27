"""Quality Confidence Layer for Heat Priority.

Evaluates observational and radiometric reliability to distinguish high-confidence
thermal signals from low-support or boundary artifacts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_quality_confidence(
    obs_count: np.ndarray | pd.Series,
    eligibility_code: np.ndarray | pd.Series | None = None,
    qa_uncertainty_k: np.ndarray | pd.Series | None = None,
    valid_mask: np.ndarray | pd.Series | None = None,
) -> np.ndarray:
    """
    Compute observation quality confidence score [0.0, 1.0].

    Parameters
    ----------
    obs_count : np.ndarray or pd.Series
        Clear-sky scene count contributing to the seasonal composite.
    eligibility_code : np.ndarray or pd.Series, optional
        Policy D eligibility code (1.0=ACCEPT, 2.0=FLAG, 0.0=EXCLUDE).
    qa_uncertainty_k : np.ndarray or pd.Series, optional
        USGS ST_QA radiometric surface temperature uncertainty in Kelvin.
    valid_mask : np.ndarray or pd.Series, optional
        Boolean mask of valid pixels.

    Returns
    -------
    np.ndarray
        Quality confidence scores in [0.0, 1.0].
    """
    obs = np.asarray(obs_count, dtype=np.float64)

    if valid_mask is None:
        mask = np.isfinite(obs) & (obs >= 0.0)
    else:
        mask = np.asarray(valid_mask, dtype=bool) & np.isfinite(obs) & (obs >= 0.0)

    confidence = np.full(obs.shape, np.nan, dtype=np.float64)
    obs_v = obs[mask]

    # Base temporal support scoring
    # OBS >= 3: 1.0; OBS == 2: 0.90; OBS == 1: 0.65; OBS == 0: 0.0
    c_temporal = np.where(
        obs_v >= 3.0,
        1.0,
        np.where(obs_v == 2.0, 0.90, np.where(obs_v == 1.0, 0.65, 0.0)),
    )

    # Adjust for Policy D eligibility if available
    if eligibility_code is not None:
        elig = np.asarray(eligibility_code, dtype=np.float64)[mask]
        # FLAG reduces confidence slightly (-0.15), EXCLUDE drops to 0.0
        c_temporal = np.where(elig == 0.0, 0.0, np.where(elig == 2.0, c_temporal * 0.85, c_temporal))

    # Adjust for QA uncertainty if available (higher uncertainty K reduces confidence)
    if qa_uncertainty_k is not None:
        qa = np.asarray(qa_uncertainty_k, dtype=np.float64)[mask]
        valid_qa = np.isfinite(qa) & (qa > 0.0)
        # Typical QA is ~1.5 - 3.5 K. Scale penalty: QA > 4.0 K reduces score
        qa_penalty = np.where(valid_qa & (qa > 4.0), np.clip(1.0 - (qa - 4.0) * 0.1, 0.5, 1.0), 1.0)
        c_temporal = c_temporal * qa_penalty

    confidence[mask] = np.clip(c_temporal, 0.0, 1.0)
    return confidence
