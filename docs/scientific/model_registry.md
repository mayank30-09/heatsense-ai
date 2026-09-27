# HEATSENSE AI — Machine Learning Model Registry

**Project:** HEATSENSE AI — AI-Powered GIS-Based Urban Heat Mitigation & Cooling Decision-Support Platform  
**Target Area:** Surat Municipal Corporation (SMC), Gujarat, India (EPSG:4326 / EPSG:32643)  
**Document Version:** 1.0  
**Status:** **DRAFT / UNDER SCIENTIFIC REVIEW — NOT YET FROZEN**  
**Date:** September 2026  

---

## 1. Registry Overview

This registry maintains the formal specification, lineage, hyperparameter configurations, spatial validation design, evaluation metrics, and operational limitations for all machine learning models developed within HEATSENSE AI.

In accordance with HEATSENSE scientific principles:
1. **Spatial Independence:** Models are trained and evaluated under strict spatial block separation (zero spatial leakage: $\text{train\_blocks} \cap \text{val\_blocks} = \emptyset$).
2. **Policy Lineage:** Models are evaluated against defined pixel quality and eligibility policies (current evaluation baseline: Policy D Draft).
3. **Reproducibility:** All seeds, dependencies, environments, and data hashes are explicitly tracked.
4. **Policy Status:** Policy D remains **DRAFT / NOT FROZEN**. Production analytical COG generation is intentionally pending final freeze.

---

## 2. Global Experimental Setup & Environment

| Environment Property | Specification / Version |
|---|---|
| **Python Version** | 3.12.10 (64-bit) |
| **XGBoost Version** | 3.4.1 |
| **Scikit-Learn Version** | 1.9.1 |
| **Optuna Version** | 5.0.0 |
| **SHAP Version** | 0.52.0 |
| **NumPy / Pandas** | 2.4.3 / 3.0.1 |
| **Target Variable ($y$)** | `LST_C` (Land Surface Temperature in Celsius, 100m ground resolution) |
| **Feature Predictors ($X$)** | `NDVI`, `NDBI`, `NDWI`, `LST_OBS_COUNT`, `LST_QA_MEDIAN_K` |
| **Predictor Exclusions** | Geographic coordinates (`latitude`, `longitude`, `row`, `col`) are strictly excluded to avoid spatial memorization. |
| **Spatial Validation Design** | 5-Fold Spatial Cross-Validation over 165 deterministic blocks (~$2\text{ km} \times 2\text{ km}$, $20 \times 20$ pixels). |
| **Random Seed** | 42 (fixed across all splits, samplers, and model seeds) |
| **Dataset Path** | `data/processed/sensitivity/policy_d/analysis.parquet` |
| **Dataset Observations** | 924,731 pixel-season records (19 seasons across 2022–2026) |
| **Policy D Status** | **DRAFT / NOT FROZEN** |

---

## 3. Registered Models

### 3.1 Model: `RandomForest_Baseline`

- **Model Identifier:** `rf_baseline_v1`
- **Architecture:** Scikit-Learn `RandomForestRegressor`
- **Purpose:** Primary ensemble baseline establishing non-linear spatial generalization benchmark for urban LST regression under spatial block cross-validation.
- **Hyperparameters:**
  ```json
  {
    "n_estimators": 100,
    "max_depth": null,
    "min_samples_split": 2,
    "min_samples_leaf": 3,
    "max_features": 1.0,
    "random_state": 42,
    "n_jobs": -1
  }
  ```
- **Spatial Validation Performance (5-Fold Mean $\pm$ Std):**
  - **MAE:** $1.2927 \pm 0.0251^\circ\text{C}$
  - **RMSE:** $1.8024 \pm 0.0488^\circ\text{C}$
  - **$R^2$:** $0.9014 \pm 0.0038$
- **Training Time:** ~15.5 s / fold
- **Status:** **ACTIVE BENCHMARK**

---

### 3.2 Model: `XGBoost_Baseline`

- **Model Identifier:** `xgb_baseline_v1`
- **Architecture:** XGBoost `XGBRegressor` (`tree_method='hist'`)
- **Purpose:** Gradient-boosted tree baseline establishing comparison against Random Forest prior to automated hyperparameter optimization.
- **Hyperparameters:**
  ```json
  {
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05,
    "min_child_weight": 1.0,
    "subsample": 1.0,
    "colsample_bytree": 1.0,
    "gamma": 0.0,
    "reg_alpha": 0.0,
    "reg_lambda": 1.0,
    "objective": "reg:squarederror",
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": -1
  }
  ```
- **Spatial Validation Performance (5-Fold Mean $\pm$ Std):**
  - **MAE:** $1.3190 \pm 0.0270^\circ\text{C}$
  - **RMSE:** $1.8280 \pm 0.0610^\circ\text{C}$
  - **$R^2$:** $0.8990 \pm 0.0040$
- **Training Time:** ~16.4 s / fold
- **Status:** **SUPERSEDED BY TUNED CONFIGURATION (KEPT FOR PROVENANCE)**

---

### 3.3 Model: `XGBoost_Tuned`

- **Model Identifier:** `xgb_tuned_optuna_tpe_v1`
- **Architecture:** XGBoost `XGBRegressor` (`tree_method='hist'`)
- **Purpose:** Hyperparameter-optimized gradient boosted decision tree discovered via 30-trial Tree-structured Parzen Estimator (TPE) spatial CV search and confirmed on full Policy D dataset.
- **Search Optimization Strategy:** Optuna `TPESampler(seed=42)` on 250,004 spatially-stratified search sample across 165 spatial blocks (preserving geographic representation).
- **Hyperparameters (Best Trial #23):**
  ```json
  {
    "n_estimators": 1300,
    "max_depth": 8,
    "learning_rate": 0.03279127013273231,
    "min_child_weight": 5.407238106447656,
    "subsample": 0.7645658245026288,
    "colsample_bytree": 0.9688977790657431,
    "gamma": 1.6307304358159391,
    "reg_alpha": 1.6949358907768442e-08,
    "reg_lambda": 0.775738584617916,
    "objective": "reg:squarederror",
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": -1
  }
  ```
- **Spatial Validation Performance:**
  - **Development 5-Fold Spatial CV (Full Dataset Mean $\pm$ Std):**
    - **MAE:** $1.2855 \pm 0.0294^\circ\text{C}$ (min: $1.2595$, max: $1.3301$)
    - **RMSE:** $1.7840 \pm 0.0591^\circ\text{C}$ (min: $1.7342$, max: $1.8801$)
    - **$R^2$:** $0.9033 \pm 0.0050$ (min: $0.8963$, max: $0.9095$)
  - **Independent Spatial Holdout (Untouched 20% Blocks, N = 203,758):**
    - **MAE:** **$1.2595^\circ\text{C}$**
    - **RMSE:** **$1.7342^\circ\text{C}$**
    - **$R^2$:** **$0.9026$**
- **Training Time:** ~55.0 s / fold
- **Empirical Prediction Latency (CPU Batch Inference):**
  - 10k samples: 0.099 s (RF: 0.058 s)
  - 100k samples: 0.764 s (RF: 0.256 s)
  - Full Dataset (924,731 rows): 6.548 s (RF: 2.113 s)
  - *Note:* Random Forest is ~3.1x faster at CPU batch prediction than the 1,300-tree depth-8 XGBoost ensemble. Tuned XGBoost is selected due to slightly superior spatial accuracy and native TreeExplainer acceleration.
- **Status:** **FROZEN (CERTIFIED OPERATIONAL MODEL)**

---

## 4. Known Scientific & Sensor Limitations

All registered models operate under explicit geospatial and sensor constraints:

1. **Thermal Spatial Resolution (~100m):**
   Landsat Collection 2 Level-2 Band 10 thermal data is acquired at 100m native resolution (resampled by USGS to 30m, aggregated to 100m analytical grid cells). Micro-scale urban features smaller than $100\text{ m} \times 100\text{ m}$ (individual trees, building courtyards, narrow asphalt roads) are radiometrically integrated into cell-average brightness temperature.
2. **Partial 2026 Monsoon Observation Record:**
   The 2026 monsoon period represents partial satellite acquisitions. Models evaluated on temporal splits involving 2026 monsoon must account for truncated scene counts ($OBS \approx 1-2$) and elevated cloud-edge variance.
3. **Chronic Industrial Hotspot Under-Prediction:**
   In chronic high-temperature industrial zones (e.g. Pandesara GIDC, Sachin GIDC), localized industrial surfaces and structural materials exhibit elevated thermal skin radiance. When integrated into 100m grid cells, optical indices (`NDBI`, `NDVI`) reach asymptotic saturation, bounding the model's ability to predict localized thermal extremes (mean under-prediction of $2.0 - 4.5^\circ\text{C}$, holdout RMSE = $4.746^\circ\text{C}$). Sub-pixel building material emissivity effects remain an active hypothesis for future high-resolution sensor investigation.
4. **Temporal / Inter-Annual Climatological Shifts:**
   Inter-annual macro-climatic anomalies (e.g. the abnormally warm winter of 2025 across western India) introduce global offset biases in multi-year zero-shot projections if baseline seasonal temperatures are not normalized or context-adjusted.
5. **Non-Causal Nature of Feature Attributions:**
   SHAP values quantify statistical contribution within the fitted decision-tree ensembles. They do not constitute proof of physical causality (`LST_QA_MEDIAN_K` acts as an atmospheric quality/context indicator, not a direct physical driver of surface temperature).

