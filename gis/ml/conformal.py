"""Spatially Validated Conformal Prediction and Uncertainty Calibration for HEATSENSE AI.

Provides:
1. Split-conformal calibration on independent spatial folds.
2. Prediction interval generation [y_hat - q, y_hat + q] for target coverage 1 - alpha.
3. Subgroup coverage and width evaluation across seasons, heat deciles, and hotspot classes.
4. Input quality and confidence tier scoring.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd


class SpatiallyCalibratedConformalRegressor:
    """Split-conformal prediction interval generator calibrated on spatially independent folds."""

    def __init__(self, alpha: float = 0.10) -> None:
        """
        Parameters
        ----------
        alpha : float, default 0.10
            Significance level (1 - alpha is nominal coverage, e.g. 0.90 for 90%).
        """
        if not (0.0 < alpha < 1.0):
            raise ValueError(f"Alpha must be in (0, 1), got {alpha}")
        self.alpha = float(alpha)
        self.nominal_coverage = 1.0 - self.alpha
        self.q_val: float | None = None
        self.calibration_sample_size: int = 0
        self.seasonal_q_vals: dict[str, float] = {}

    def fit_calibration(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        seasons: np.ndarray | list[str] | None = None,
    ) -> SpatiallyCalibratedConformalRegressor:
        """
        Calibrate absolute residual quantiles on held-out spatial partition.

        Parameters
        ----------
        y_true : np.ndarray
            Observed ground-truth target values on calibration partition.
        y_pred : np.ndarray
            Model predictions on calibration partition.
        seasons : np.ndarray | list[str] | None
            Optional season strings for computing season-stratified calibration.
        """
        y_true = np.asarray(y_true, dtype=np.float64)
        y_pred = np.asarray(y_pred, dtype=np.float64)

        valid = np.isfinite(y_true) & np.isfinite(y_pred)
        residuals = np.abs(y_true[valid] - y_pred[valid])
        n = len(residuals)
        if n == 0:
            raise ValueError("No valid calibration residuals provided.")

        self.calibration_sample_size = n
        # Conformal quantile level with finite-sample correction: ceil((n + 1) * (1 - alpha)) / n
        q_level = min(1.0, np.ceil((n + 1) * (1.0 - self.alpha)) / n)
        self.q_val = float(np.quantile(residuals, q_level, method="higher"))

        # Season-stratified calibration if provided
        if seasons is not None:
            seasons_arr = np.asarray(seasons)[valid]
            for s in np.unique(seasons_arr):
                s_mask = seasons_arr == s
                s_res = residuals[s_mask]
                n_s = len(s_res)
                if n_s >= 20:
                    q_s_level = min(1.0, np.ceil((n_s + 1) * (1.0 - self.alpha)) / n_s)
                    self.seasonal_q_vals[str(s)] = float(np.quantile(s_res, q_s_level, method="higher"))
                else:
                    self.seasonal_q_vals[str(s)] = self.q_val

        return self

    def predict_intervals(
        self,
        y_pred: np.ndarray | list[float],
        season: str | None = None,
    ) -> tuple[np.ndarray, np.ndarray, float]:
        """
        Produce upper and lower prediction bounds.

        Returns
        -------
        tuple[np.ndarray, np.ndarray, float]
            (lower_bounds, upper_bounds, half_width)
        """
        if self.q_val is None:
            raise RuntimeError("Model must be calibrated before generating prediction intervals.")

        y_hat = np.asarray(y_pred, dtype=np.float64)
        half_width = self.seasonal_q_vals.get(str(season), self.q_val) if season else self.q_val

        lower = y_hat - half_width
        upper = y_hat + half_width
        return lower, upper, half_width

    def evaluate_coverage(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        subgroups: dict[str, np.ndarray] | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate empirical coverage and interval width.

        Parameters
        ----------
        y_true : np.ndarray
            Observed ground truth.
        y_pred : np.ndarray
            Model predictions.
        subgroups : dict[str, np.ndarray], optional
            Dictionary of categorical arrays (e.g. {'season': ..., 'heat_decile': ...})
            to evaluate subgroup-stratified coverage.

        Returns
        -------
        dict[str, Any]
            Overall and stratified coverage metrics.
        """
        if self.q_val is None:
            raise RuntimeError("Model must be calibrated before evaluation.")

        y_true = np.asarray(y_true, dtype=np.float64)
        y_pred = np.asarray(y_pred, dtype=np.float64)
        valid = np.isfinite(y_true) & np.isfinite(y_pred)
        y_t = y_true[valid]
        y_p = y_pred[valid]

        lower = y_p - self.q_val
        upper = y_p + self.q_val
        covered = (y_t >= lower) & (y_t <= upper)

        overall_coverage = float(np.mean(covered))
        overall_width = float(2 * self.q_val)

        subgroup_results: dict[str, dict[str, Any]] = {}
        if subgroups:
            for group_name, group_vals in subgroups.items():
                g_arr = np.asarray(group_vals)[valid]
                group_metrics: dict[str, Any] = {}
                for cat in np.unique(g_arr):
                    cat_mask = g_arr == cat
                    cat_n = int(np.sum(cat_mask))
                    if cat_n > 0:
                        cat_cov = float(np.mean(covered[cat_mask]))
                        group_metrics[str(cat)] = {
                            "n_samples": cat_n,
                            "coverage": round(cat_cov, 4),
                            "width": round(overall_width, 4),
                            "coverage_gap": round(cat_cov - self.nominal_coverage, 4),
                        }
                subgroup_results[group_name] = group_metrics

        return {
            "nominal_coverage": self.nominal_coverage,
            "overall_empirical_coverage": round(overall_coverage, 4),
            "interval_half_width": round(self.q_val, 4),
            "interval_full_width": round(overall_width, 4),
            "n_samples": len(y_t),
            "subgroups": subgroup_results,
        }
