"""SHAP Explainability Module for HEATSENSE AI.

Computes TreeExplainer SHAP attribution values for Random Forest and XGBoost models.
Enforces non-causal interpretative attribution reporting.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
import shap


def compute_tree_shap_values(
    model: Any,
    X_sample: np.ndarray | pd.DataFrame,
    feature_names: list[str],
) -> dict[str, Any]:
    """
    Compute SHAP values using TreeExplainer on a sample of observations.

    Parameters
    ----------
    model : Any
        Trained tree model (RandomForestRegressor or XGBRegressor).
    X_sample : np.ndarray | pd.DataFrame
        Background/evaluation feature matrix.
    feature_names : list[str]
        List of predictor feature names.

    Returns
    -------
    dict[str, Any]
        Dictionary containing:
        - 'shap_values': np.ndarray of shape (N, D)
        - 'mean_abs_shap': dict[str, float] mapping feature -> mean(|SHAP|)
        - 'feature_ranking': list[str] sorted from highest to lowest attribution
        - 'sample_size': int
    """
    if isinstance(X_sample, pd.DataFrame):
        X_mat = X_sample[feature_names].to_numpy()
    else:
        X_mat = np.asarray(X_sample)

    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(X_mat)

    # In case shap_vals is a list or has extra dimensions
    if isinstance(shap_vals, list):
        shap_vals = shap_vals[0]

    mean_abs = np.mean(np.abs(shap_vals), axis=0)
    feat_importance = {name: round(float(val), 4) for name, val in zip(feature_names, mean_abs)}

    sorted_features = sorted(feat_importance.keys(), key=lambda k: feat_importance[k], reverse=True)

    return {
        "shap_values": shap_vals,
        "mean_abs_shap": feat_importance,
        "feature_ranking": sorted_features,
        "sample_size": len(X_mat),
    }


def compare_shap_stability(
    shap_results_by_fold: list[dict[str, Any]],
    feature_names: list[str],
) -> pd.DataFrame:
    """
    Evaluate attribution stability across cross-validation folds.

    Returns
    -------
    pd.DataFrame
        Table with mean, std, and coefficient of variation for each feature's mean(|SHAP|).
    """
    fold_importances = []
    for r in shap_results_by_fold:
        fold_importances.append(r["mean_abs_shap"])

    df_imp = pd.DataFrame(fold_importances)
    summary_rows = []
    for f in feature_names:
        vals = df_imp[f]
        mean_v = float(vals.mean())
        std_v = float(vals.std())
        cov_v = round((std_v / mean_v) * 100.0, 2) if mean_v > 0 else 0.0
        summary_rows.append({
            "feature": f,
            "mean_shap": round(mean_v, 4),
            "std_shap": round(std_v, 4),
            "cov_percent": cov_v,
        })

    return pd.DataFrame(summary_rows).sort_values("mean_shap", ascending=False)
