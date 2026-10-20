# HEATSENSE AI — Machine Learning Model Registry

**Project:** HEATSENSE AI — AI-Powered GIS-Based Urban Heat Mitigation & Cooling Decision-Support Platform
**Target Area:** Surat Municipal Corporation (SMC), Gujarat, India (EPSG:4326 / EPSG:32643)
**Document Version:** 1.0
**Status:** **FROZEN (ML/QC SCIENTIFIC FREEZE)**
**Date:** September 2026

---

## 1. Registry Overview

This registry maintains the formal specification, lineage, hyperparameter configurations, spatial validation design, evaluation metrics, and operational limitations for all machine learning models developed within HEATSENSE AI.

In accordance with HEATSENSE scientific principles:
1. **Spatial Independence:** Models are trained and evaluated under strict spatial block separation (zero spatial leakage: $\text{train\_blocks} \cap \text{val\_blocks} = \emptyset$).
2. **Policy Lineage:** Models are evaluated against defined pixel quality and eligibility policies (authoritative baseline: Policy D).
3. **Reproducibility:** All seeds, dependencies, environments, and data hashes are explicitly tracked.
4. **Policy Status:** Policy D and the ML/QC pipeline are **FROZEN**. All 19 production analytical COGs are validated.

---

## 2. Global Experimental Setup & Environment

| Environment Property | Specification / Version |
|---|---|
| **Python Version** | 3.12.10 (64-bit) |
| **XGBoost Version** | 3.4.1 |
| **Scikit-Learn Version** | 1.9.1 |
| **Optuna Version** | 5.0.0 |
| **SHAP Version** | 0.52.0 |
| **NumPy / Pandas** | 2.5.3 / 3.0.6 |
| **Target Variable ($y$)** | `LST_C` (Land Surface Temperature in Celsius, 100m ground resolution) |
| **Feature Predictors ($X$)** | `NDVI`, `NDBI`, `NDWI`, `LST_OBS_COUNT`, `LST_QA_MEDIAN_K` (`LST_QA_MEDIAN_K` is the seasonal median of the per-scene Landsat ST_QA uncertainty indicator, expressed in Kelvin; provides radiometric retrieval context) |
| **Predictor Exclusions** | Geographic coordinates (`latitude`, `longitude`, `row`, `col`) are strictly excluded to avoid spatial memorization. |
| **Spatial Validation Design** | 165 spatial blocks (2 km × 2 km); 132 development blocks (5-fold spatial CV + Optuna) and 33 locked test blocks (independent spatial holdout). |
| **Random Seed** | 42 (fixed across all splits, samplers, and model seeds) |
| **Dataset Path** | `data/processed/sensitivity/policy_d/analysis.parquet` |
| **Dataset Observations** | 924,731 pixel-season records (19 seasons across 2022–2026) |
| **Policy D Status** | **FROZEN** |

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

- **Model Identifier:** `xgb_tuned_policy_d_v1`
- **Architecture:** XGBoost `XGBRegressor` (`tree_method='hist'`)
- **Purpose:** Hyperparameter-optimized gradient boosted decision tree discovered via 30-trial Tree-structured Parzen Estimator (TPE) spatial CV search strictly on 132 development blocks and validated once on 33 untouched test blocks.
- **Search Optimization Strategy:** Optuna `TPESampler(seed=42)` across 30 trials evaluated strictly with 5-fold spatial block cross-validation on 132 development blocks (720,973 rows) with zero test leakage.
- **Hyperparameters (Best Trial #25):**
  ```json
  {
    "n_estimators": 900,
    "max_depth": 9,
    "learning_rate": 0.03662937937931856,
    "min_child_weight": 3.253330265581497,
    "subsample": 0.6539539403049981,
    "colsample_bytree": 0.6285481356546664,
    "gamma": 1.2827623793054954,
    "reg_alpha": 6.448517630611331e-06,
    "reg_lambda": 12.086733674708716,
    "objective": "reg:squarederror",
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": -1
  }
  ```
- **Spatial Validation Performance:**
  - **Development 5-Fold Spatial CV (132 Blocks / 720,973 rows):**
    - **Best Dev-CV RMSE:** $1.8478^\circ\text{C}$
  - **Independent Spatial Holdout (Untouched 33 Blocks / 203,758 rows, Evaluation Count = 1):**
    - **MAE:** **$1.2726^\circ\text{C}$**
    - **RMSE:** **$1.7524^\circ\text{C}$**
    - **$R^2$:** **$0.9006$**
- **Training Time:** ~37.7 s on full development dataset (720,973 rows)
- **Empirical Prediction Latency (CPU Batch Inference):**
  - 203,758 samples (test holdout): 1.093 s (~5.36 s per 1M rows under linear extrapolation).
  - *Note:* In dedicated benchmarks on 924,731 rows, Random Forest demonstrated lower CPU batch inference latency (2.1132 s) than XGBoost (6.5477 s). XGBoost is the frozen operational model based on the tuned development workflow, independent locked test evaluation, and explainability workflow. RF remains an active benchmark. The currently reported RF 5-fold development CV RMSE and XGBoost locked-test RMSE are not directly comparable.
- **Status:** **FROZEN (CERTIFIED OPERATIONAL MODEL)**

---

## 4. Known Scientific & Sensor Limitations

All registered models operate under explicit geospatial, temporal, and sensor constraints:

1. **Validation Scope & Spatial Generalization:**
   The final independent evaluation uses 33 previously locked spatial blocks withheld from development and model selection. The reported performance therefore measures spatial generalization within the sampled temporal distribution. It explicitly does **NOT** establish:
   - future-year forecasting accuracy
   - transferability to cities outside Surat
   - real-time operational prediction
   - sub-100 m thermal prediction
   - intervention cooling effects from the regression model alone
2. **Temporal Coverage Limitation (2022–2026):**
   - The year 2026 is temporally incomplete.
   - 2026 post-monsoon is not represented because that seasonal period had not occurred at data generation time.
   - 2026 must not be interpreted as a complete annual climatological representation.
   - The spatial holdout protocol must not be conflated with a future-year forecasting holdout ($\text{spatial holdout} \neq \text{future-year holdout}$).
3. **Thermal Spatial Resolution (~100m Footprint):**
   Landsat Collection 2 Level-2 Band 10 thermal data is acquired at ~100m native resolution (resampled by USGS to 30m, aggregated to 100m analytical grid cells). Micro-scale urban features smaller than $100\text{ m} \times 100\text{ m}$ (individual trees, building courtyards, narrow asphalt roads) are radiometrically integrated into cell-average brightness temperature.
4. **Chronic Industrial Hotspot Under-Prediction:**
   Predictive error increases for recurrent/chronic hotspot classes (holdout RMSE increases from $1.6715^\circ\text{C}$ for non-hotspots to $4.8413^\circ\text{C}$ for chronic hotspots). The observed cold bias is consistent with sub-pixel thermal heterogeneity within the approximately 100 m thermal footprint, where high-radiance industrial surfaces (e.g. metal roofing in Pandesara/Sachin GIDC) are averaged with cooler surrounding background.
5. **Architectural Guardrail — Observed LST as Primary Thermal Evidence:**
   For downstream analysis, **observed satellite LST remains the authoritative primary thermal evidence**. Model predictions are supplementary predictive and error-context information, used for counterfactual scenario evaluation and uncertainty context, never as a replacement for observed thermal evidence.
6. **Non-Causal Nature of Feature Attributions:**
   SHAP values quantify numerical attribution within the fitted decision-tree ensembles, not physical causality. `LST_QA_MEDIAN_K` is the seasonal median of the per-scene Landsat ST_QA uncertainty indicator, expressed in Kelvin (not the formal uncertainty of the seasonal median LST composite). It provides a strong retrieval-quality and atmospheric-retrieval context signal that improves predictive performance in the evaluated feature configurations; its predictive contribution must not be interpreted as physical causation.
7. **Canonical Hotspot Persistence Terminology:**
   `IS_PERSISTENT_HOTSPOT` is a recurrence-based persistence indicator derived from the canonical hotspot-frequency policy, using $\text{frequency} \ge 0.25$ OR the authoritative existing persistent-hotspot flag. It denotes recurrence persistence under Policy D screening, not proof of continuous sub-daily thermal elevation.
