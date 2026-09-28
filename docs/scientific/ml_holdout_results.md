# HEATSENSE AI — Independent Spatial Holdout Evaluation Results

## 1. Executive Summary

This report documents the final, independent spatial holdout evaluation for the **HEATSENSE AI** machine learning pipeline under **Policy D** (spatially coherent, physically bounded pixel eligibility).

Following the strict scientific protocol:
1. The 165 spatial blocks (2 km × 2 km) covering Surat, India, were partitioned into **132 development blocks (80%)** and **33 locked test blocks (20%)** using a deterministic random seed (`seed=42`).
2. Hyperparameter optimization (30 Optuna TPE trials) and model selection were executed **strictly across the 132 development blocks** using 5-fold spatial cross-validation.
3. The 33 test blocks were strictly isolated and never accessed during Optuna search, feature selection, or model tuning.
4. The final candidate model (`xgb_tuned_policy_d`) was trained on all 720,973 development rows and evaluated **exactly once** on the 203,758 untouched test rows.

---

## 2. Spatial Holdout Methodology

- **Total Spatial Blocks**: 165 blocks across Surat municipal and peri-urban area.
- **Partition Ratio**: 80% Development (132 blocks) / 20% Test (33 blocks).
- **Partition Algorithm**: Deterministic stratified spatial hash (`gis/ml/holdout_split.py`, `random_state=42`).
- **Disjointness**: $\text{Development} \cap \text{Test} = \emptyset$ (strictly verified by automated unit tests).
- **Completeness**: $\text{Development} \cup \text{Test} = \text{All 165 Blocks}$.
- **Locked Test Set**: 33 block identifiers (`B_01_11`, `B_01_14`, `B_02_08`, ..., `B_15_09`) persisted in `artifacts/ml_freeze/holdout_split.json`.

---

## 3. Model Architecture & Locked Feature Schema

- **Model**: Tuned Extreme Gradient Boosting (`XGBRegressor`) with histogram-based tree method (`tree_method='hist'`).
- **Target Variable**: $LST\_C$ (Landsat Level-2 Land Surface Temperature, °C).
- **Canonical Feature Schema**:
  1. `NDVI` — Normalized Difference Vegetation Index (vegetation density).
  2. `NDBI` — Normalized Difference Built-Up Index (built surface density).
  3. `NDWI` — Normalized Difference Water Index (surface water/moisture).
  4. `LST_OBS_COUNT` — Clear-sky seasonal observation count (temporal support).
  5. `LST_QA_MEDIAN_K` — Pixel-level radiometric uncertainty / atmospheric retrieval context (Kelvin).
- **Coordinate Columns Excluded**: `latitude`, `longitude`, `row`, `col`, `x`, `y` are strictly prohibited from the feature matrix to prevent spatial memorization and coordinate shortcut learning.
- **Hyperparameters (Trial #25)**:
  - `n_estimators`: 900
  - `max_depth`: 9
  - `learning_rate`: 0.0366
  - `min_child_weight`: 3.2533
  - `subsample`: 0.6540
  - `colsample_bytree`: 0.6285
  - `gamma`: 1.2828
  - `reg_alpha`: 6.45e-06
  - `reg_lambda`: 12.0867

---

## 4. Overall Independent Test Metrics

The final evaluation was conducted on **September 27, 2026** against the 33 locked test blocks.

| Metric | Measured Value | Notes |
|:---|---:|:---|
| **Test Blocks** | 33 | Untouched during development |
| **Test Samples ($N$)** | 203,758 | Pixels across 2022–2026 seasons |
| **Mean Absolute Error (MAE)** | **1.2726 °C** | Across all seasons and land types |
| **Root Mean Squared Error (RMSE)** | **1.7524 °C** | Independent spatial generalization |
| **Coefficient of Determination ($R^2$)** | **0.9006** | Explains 90.06% of spatial-temporal variance |
| **CPU Batch Inference Latency** | 1.093 s | Measured on 203,758 test rows (~5.36 s / 1M rows under linear extrapolation) |
| **Evaluation Count** | 1 | Single independent evaluation |

*Note: Historical development re-evaluation metrics (1.7840 °C RMSE / 0.9033 $R^2$) represent cross-validation results across all folds, whereas 1.7524 °C RMSE represents the true independent holdout generalization.*

---

## 5. Seasonal Breakdown on Independent Holdout

Evaluation broken down by seasonal context in the locked test partition:

| Season | Samples ($N$) | Share (%) | MAE (°C) | RMSE (°C) | $R^2$ | Mean Bias (°C) |
|:---|---:|---:|---:|---:|---:|---:|
| **Winter** | 54,930 | 26.96% | 0.9139 | 1.2136 | 0.6512 | +0.0032 |
| **Summer** | 54,930 | 26.96% | 1.3734 | 1.7944 | 0.7119 | -0.1916 |
| **Monsoon** | 49,954 | 24.52% | 1.8024 | 2.4353 | 0.7718 | +0.0866 |
| **Post-Monsoon** | 43,944 | 21.57% | 0.9926 | 1.2772 | 0.7855 | -0.1047 |

### Scientific Observations by Season:
1. **Winter & Post-Monsoon Precision**: Winter exhibits the lowest MAE ($0.9139^\circ\text{C}$) and minimal bias ($+0.0032^\circ\text{C}$) among evaluated seasons. The result is consistent with comparatively stable retrieval conditions and higher clear-sky sample support, although the model evaluation alone does not establish atmospheric transmission as the causal explanation.
2. **Summer Heat Extremes**: Summer exhibits MAE of $1.3734^\circ\text{C}$ with a slight negative bias ($-0.1916^\circ\text{C}$). The result is consistent with wider surface thermal heterogeneity over dry non-vegetated soils and industrial rooftops, though localized emissivity dynamics cannot be directly separated without ground instrumentation.
3. **Monsoon Cloud Attenuation**: Monsoon exhibits the highest observed error (RMSE $2.4353^\circ\text{C}$). This observed pattern is consistent with cloud-mask boundary effects and reduced temporal clear-sky support ($LST\_OBS\_COUNT$), representing an operational observational limitation under cloud-restricted conditions rather than an intrinsic model failure.

---

## 6. Canonical Hotspot Performance on Independent Holdout

Hotspot tier breakdown across the 33 locked test blocks based on multi-season recurrence frequency ($f$):

| Tier | Definition | Samples ($N$) | Share (%) | MAE (°C) | RMSE (°C) | $R^2$ | Mean Bias (°C) |
|:---|:---|---:|---:|---:|---:|---:|---:|
| **Non-Hotspot** | $f = 0.0$ | 191,545 | 94.01% | 1.2251 | 1.6715 | 0.9076 | +0.0165 |
| **Active Hotspot** | $f > 0.0$ | 12,213 | 5.99% | 2.0170 | 2.7228 | 0.7809 | -1.1281 |
| **Persistent Hotspot** | $f \ge 0.25$ or flag | 2,177 | 1.07% | 3.0959 | 3.9896 | 0.4941 | -1.3041 |
| **Chronic Hotspot** | $f \ge 0.50$ | 405 | 0.20% | 3.9077 | 4.8413 | 0.2118 | -1.5264 |

### Critical Architectural Implication:
- As hotspot severity increases from non-hotspot to chronic, the model's RMSE increases from $1.67^\circ\text{C}$ to $4.84^\circ\text{C}$, with an increasing cold bias (underpredicting chronic hotspots by $-1.5264^\circ\text{C}$).
- **Interpretation**: The observed cold bias is consistent with sub-pixel thermal heterogeneity within the approximately 100m thermal footprint. Landsat's ~100m native thermal radiometer footprint resampled to 30m blends localized high-radiance industrial surfaces with cooler surrounding background.
- **Architectural Decision**: **Observed satellite LST must remain Primary Thermal Evidence** in HEATSENSE AI's Heat Priority engine. Model predictions serve exclusively as supplementary evidence and counterfactual simulation baselines, never as a replacement for observed thermal reality.

---

## 7. Scientific Interpretations & Non-Causal Grounding

1. **Retrieval-Quality Context Feature ($LST\_QA\_MEDIAN\_K$)**:
   `LST_QA_MEDIAN_K` provides a strong retrieval-quality and atmospheric-retrieval context signal that improves predictive performance in the evaluated feature configurations. Its predictive contribution must not be interpreted as physical causation.
2. **Model Attribution vs. Causality (SHAP)**:
   SHAP values quantify numerical feature attribution within the fitted decision-tree ensembles, not physical causality. Under cloud-restricted monsoon conditions, `LST_OBS_COUNT` has the largest reported mean absolute SHAP contribution among the evaluated features ($2.5202^\circ\text{C}$). The result indicates that observation support is particularly informative for the model during monsoon conditions. This is a model-attribution result, not evidence of physical causation.
3. **Inference Latency Benchmark**:
   In dedicated CPU batch inference benchmarks on 924,731 rows, Scikit-Learn Random Forest required approximately 2.1132 s, whereas XGBoost required approximately 6.5477 s. Separately, the final holdout evaluation required approximately 1.093 s for 203,758 rows, equivalent to approximately 5.36 s per million rows under linear extrapolation. Random Forest demonstrates faster measured CPU inference, while XGBoost was selected based on predictive performance ($1.7524^\circ\text{C}$ vs $1.8024^\circ\text{C}$ RMSE) and its native tree-based explanation workflow.

---

## 8. Limitations & Boundary Conditions

1. **Sub-Pixel Heterogeneity**: Predictions in dense industrial clusters (e.g., Pandesara, Sachin GIDC) are smoothed by the ~100m thermal footprint. Sub-100m rooftop temperatures cannot be inferred without high-resolution airborne or drone thermal sensing.
2. **Monsoon Observation Sparsity**: Coastal monsoon cloud cover reduces valid clear-sky Landsat scenes in some seasons, causing higher prediction variance in August–September.
3. **Operational Boundary**: The model is validated strictly within the Surat municipal and peri-urban boundary for the years 2022–2026. Generalization to other climatic zones (e.g., arid inland or mountainous regions) requires regional retraining.

---

## 9. Authoritative Artifact References

Every number in this document corresponds to an automated, cryptographically hashed artifact persisted in `artifacts/ml_freeze/checksums.sha256`:

- `artifacts/ml_freeze/holdout_split.json` (SHA-256: `8a04b20c97b088ffc7d3f513ecd3e41007adea51ad16401f104529f40d8c1a2d`)
- `artifacts/ml_freeze/feature_schema.json` (SHA-256: `e7c94e8c4a527a13d7b9538d491c8e27125fb5a1c245b565df2d390113c2c7e5`)
- `artifacts/ml_freeze/holdout_performance.json` (SHA-256: `93db2435970ea68b0e18c61abeebb0622a793a6026770973a534efd70a29ac3a`)
- `artifacts/ml_freeze/holdout_season_performance.csv` (SHA-256: `1158e56ba4e1a22cd44e6d92d614cc635db20be06415e902db99807cdf5291af`)
- `artifacts/ml_freeze/holdout_hotspot_performance.csv` (SHA-256: `3990946de0616a2d4e20457278c09c6c39268aab59756dee72501bcb1097e539`)
- `artifacts/ml_freeze/holdout_spatial_residuals.geojson` (SHA-256: `4b4d3d59e2f0c2b27e479f157d355d745bcb65c49c61aac077ffd5179cc27327`)
- `artifacts/ml_freeze/evaluation_manifest.json` (SHA-256: `0ca65f2e840f3a73a9c7ea6bee7c2c985925886704c31167d22d4d7e28011b0b`)
- `artifacts/ml_freeze/xgb_tuned_policy_d.json` (SHA-256: `8c4aad26e2a56867e327aeae0cd758f9b2b1105bf8d35c0ec8f6774f4ef38377`)
