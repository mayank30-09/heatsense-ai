# 08 — Machine Learning Model Integrity & Conformal Calibration Audit

**Project:** HeatSense AI — Surat Urban Heat Mitigation & Decision Support System  
**Audit Scope:** Model Artifact Integrity, Zero Leakage Spatial Holdout, Feature Ordering, Conformal Uncertainty Calibration, and Promotion Decisions  
**Date:** October 2026  
**Auditor Classification:** Machine Learning & Data Provenance Engineer  
**Model Artifact:** `artifacts/ml_freeze/xgb_tuned_policy_d.joblib` (SHA-256: `e1aedd4946b1b29823bdea66ea3ec7b9ba5f20c4ddbfdf6920c2e62e6b30b7c9`)  
**Status:** **VERIFIED (PASS)**  

---

## 1. Machine Learning Model Architecture & Specification

The core predictive model estimates seasonal Land Surface Temperature (`LST_C`) at 100m pixel resolution across Surat:

| Parameter | Specification | Verification |
| :--- | :--- | :--- |
| **Model Class** | XGBoost Regressor (`XGBRegressor`) | Frozen artifact loaded via `joblib.load()` |
| **Target Variable** | `LST_C` (Land Surface Temperature in °C) | Single target regression |
| **Input Features (5)** | `['NDVI', 'NDBI', 'NDWI', 'LST_OBS_COUNT', 'LST_QA_MEDIAN_K']` | Strict feature order preserved via `feature_schema.json` |
| **Hyperparameters** | `n_estimators=900, max_depth=9, learning_rate=0.0366, subsample=0.654, colsample_bytree=0.629` | Derived from 30 Optuna trials strictly on development partition |
| **Holdout Performance** | $\text{MAE} = 1.2726^\circ\text{C}, \text{RMSE} = 1.7524^\circ\text{C}, R^2 = 0.9006$ | Evaluated once on locked test partition |

---

## 2. Zero-Leakage Spatial Holdout Protocol

To prevent optimistic bias and spatial autocorrelation leakage between contiguous cells, the study area was divided into **165 spatial blocks (2km × 2km)**:

```text
                  ┌──────────────────────────────────────────────┐
                  │ Total SMC Area Partition: 165 Spatial Blocks │
                  └──────────────────────┬───────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │                                               │
                 ▼                                               ▼
  ┌─────────────────────────────┐                 ┌─────────────────────────────┐
  │ Development Partition (80%) │                 │ Locked Test Partition (20%) │
  │   132 Blocks / 720,973 Rows │                 │   33 Blocks / 203,758 Rows  │
  │  (Used for Optuna CV & Exp) │                 │  (STRICTLY UNSEEN / LOCKED) │
  └─────────────────────────────┘                 └─────────────────────────────┘
```

### Invariants Verified:
1. **Zero Spatial Overlap:** Test blocks are structurally excluded from development cross-validation folds (`gis/ml/development_cv.py`).
2. **Zero Contamination:** Test observations were never exposed to Optuna hyperparameter searches, feature ablation, or threshold tuning.
3. **Partition Immutability:** Preserved via cryptographic hash in `artifacts/ml_freeze/holdout_split.json`.

Verified via automated test: [backend/tests/test_holdout_protocol.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/tests/test_holdout_protocol.py).

---

## 3. Controlled Experimental Evaluation & Comparison

Controlled experiments were conducted on the development partition without touching the locked test partition (`scripts/run_ml_experiments.py`):

### 3.1 Feature Ablation Comparison:
- **Optical Only (`NDVI, NDBI, NDWI`):** CV RMSE = 4.7620°C, $R^2 = 0.3192$, Upper Decile RMSE = 7.5427°C.
- **Optical + Temporal (`+ LST_OBS_COUNT`):** CV RMSE = 3.9986°C, $R^2 = 0.5197$.
- **Optical + QA (`+ LST_QA_MEDIAN_K`):** CV RMSE = 2.1152°C, $R^2 = 0.8656$.
- **Full 5 Features:** CV RMSE = 1.8868°C, $R^2 = 0.8930$, Upper Decile RMSE = 2.7787°C.

### 3.2 Model Architecture Comparison:
- **Random Forest Baseline (100 trees):** CV RMSE = 1.9014°C, $R^2 = 0.8914$.
- **XGBoost Tuned Baseline:** CV RMSE = 1.8868°C, $R^2 = 0.8930$ (optimal performance).

---

## 4. Spatially Calibrated Conformal Uncertainty (`gis/ml/conformal.py`)

In production municipal planning, point predictions must be paired with rigorous uncertainty bounds. Split-conformal prediction intervals with finite-sample correction were implemented:

- **Target Nominal Coverage:** 90.0% ($1 - \alpha = 0.90$).
- **Overall Empirical Spatial Coverage (Holdout):** **90.02%** (passing nominal standard with $< 0.1\%$ margin error).
- **Overall Empirical Spatial Coverage (Spatial CV Fold):** **90.15%** (interval width: $\pm 2.98^\circ\text{C}$).
- **Mean Prediction Interval Half-Width:** $\pm 2.86^\circ\text{C}$ to $\pm 2.98^\circ\text{C}$.

### Critical Distinction: Overall Coverage vs. Hottest-Decile Undercoverage:

While overall marginal conformal coverage rigorously satisfies the 90% nominal guarantee across the full municipal distribution, conditional coverage across temperature deciles reveals significant heterogeneity:

| Decile Subgroup | Temperature Regime | Empirical Coverage | Nominal Target | Coverage Gap | Uncertainty State |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **D1** (Coolest 10%) | Water bodies, dense vegetation | 90.9% | 90.0% | +0.9% | Well-calibrated |
| **D2 – D3** | Intermediate suburban / vegetative | 93.7% – 94.9% | 90.0% | +3.7% to +4.9% | Conservative / Overcovered |
| **D4 – D9** | Typical urban fabric / core built | 87.9% – 91.4% | 90.0% | -2.1% to +1.4% | Centrally calibrated |
| **D10** (Hottest 10%) | High-impervious industrial / dense core | **83.4%** | 90.0% | **-6.6%** | **Undercoverage Gap** |

**Scientific Assessment:**
1. *Root Cause:* Extreme upper-tail temperatures ($> 38^\circ\text{C}$) are subject to non-linear localized thermal turbulence and micro-surface emissivity variations, causing wider error residuals than the global quantile estimate $\hat{q}_{\text{val}}$.
2. *Decision Guidance for SMC Planners:* Because the hottest decile exhibits an empirical coverage of 83.4% (undercovering nominal 90% by 6.6%), planners must strictly use the upper prediction bound ($y + \hat{q}$) rather than the point estimate when sizing critical cooling interventions in chronic hotspot zones.

Verified via automated test: [backend/tests/test_ml_experiments_and_conformal.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/tests/test_ml_experiments_and_conformal.py).

---

## 5. Model Promotion Decision & Production Invariants

1. **Promotion Evaluation:** While upper-tail sample weighting improved hot-tail error by 0.313°C, the frozen baseline maintains optimal global calibration and historical holdout reproducibility. **Decision: RETAIN AUTHORITATIVE BASELINE.**
2. **Prohibition of Synthetic Outputs:** Production inference code is strictly prohibited from returning random values, synthetic heuristics, or uncalibrated multipliers.
3. **SHAP Multiplication Prohibition:** Multiplying TreeSHAP values by intervention square meters to estimate cooling is explicitly banned; all cooling derives from empirical microclimate field literature (Bowler et al. 2010, Santamouris et al. 2017).
