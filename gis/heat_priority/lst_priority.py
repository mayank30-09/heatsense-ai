"""LST Severity Layer for Heat Priority.

Evaluates empirical thermal severity grounded strictly in observed satellite LST.
Observed LST is the PRIMARY THERMAL EVIDENCE and is never replaced by model predictions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import rankdata


def compute_lst_severity(
    observed_lst: np.ndarray | pd.Series,
    valid_mask: np.ndarray | pd.Series | None = None,
) -> np.ndarray:
    """
    Compute empirical thermal severity percentile ranking [0.0, 1.0] from observed LST.

    Parameters
    ----------
    observed_lst : np.ndarray or pd.Series
        Array of observed Land Surface Temperatures (degC).
    valid_mask : np.ndarray or pd.Series, optional
        Boolean mask of valid pixels (excluding NoData). If None, finite values are used.

    Returns
    -------
    np.ndarray
        Percentile rank values in [0.0, 1.0] for valid pixels (NaN for invalid).
    """
    obs = np.asarray(observed_lst, dtype=np.float64)

    if valid_mask is None:
        mask = np.isfinite(obs) & (obs > -9000.0)
    else:
        mask = np.asarray(valid_mask, dtype=bool) & np.isfinite(obs) & (obs > -9000.0)

    severity = np.full(obs.shape, np.nan, dtype=np.float64)

    valid_vals = obs[mask]
    n_valid = len(valid_vals)

    if n_valid == 0:
        return severity

    if n_valid == 1:
        severity[mask] = 1.0
        return severity

    # Compute empirical percentile rank (0.0 to 1.0)
    ranks = rankdata(valid_vals, method="average")
    percentiles = (ranks - 1.0) / (n_valid - 1.0)
    severity[mask] = np.clip(percentiles, 0.0, 1.0)

    return severity
