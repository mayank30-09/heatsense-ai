# HEATSENSE AI — XGBoost Hyperparameter Tuning & Spatial Confirmation Report

**Project:** HEATSENSE AI — AI-Powered GIS-Based Urban Heat Mitigation & Cooling Decision-Support Platform  
**Target Area:** Surat Municipal Corporation (SMC), Gujarat, India (EPSG:4326 / EPSG:32643)  
**Document Version:** 1.0-SCIENTIFIC-EVIDENCE  
**Stage:** XGBoost Hyperparameter Tuning -> Spatial Confirmation -> Model Comparison -> SHAP Refresh -> Residual Analysis -> Scientific Model Selection  
**Date:** September 2026  
**Status:** **DRAFT / UNDER SCIENTIFIC REVIEW — NOT YET FROZEN**  

---

## 1. Objective

The objective of this investigation is to evaluate whether systematically optimizing the hyperparameters of the XGBoost Land Surface Temperature (`LST_C`) regression model via Bayesian Tree-structured Parzen Estimator (TPE) search produces a **reproducible, statistically meaningful improvement under strict spatial cross-validation**, or whether model generalization is primarily constrained by feature information content and remote sensing sensor physics.

In particular, the experiment resolves:
1. Whether hyperparameter tuning can close the minor gap between baseline XGBoost ($MAE = 1.319^\circ\text{C}, RMSE = 1.828^\circ\text{C}, R^2 = 0.899$) and the Random Forest baseline ($MAE = 1.293^\circ\text{C}, RMSE = 1.802^\circ\text{C}, R^2 = 0.901$).
2. Whether the optimal parameter configuration discovered on a spatially stratified search sample confirms on the full 924,731 observation Policy D dataset.
3. How tuning affects difficult thermal regimes, specifically high-humidity monsoon periods and chronic industrial urban heat island hotspots (e.g., Pandesara GIDC).
4. How feature attribution (SHAP TreeExplainer) behaves under the confirmed tuned architecture.
5. What the scientific model selection decision should be among Random Forest, Baseline XGBoost, and Tuned XGBoost.

---

## 2. Dataset

All experiments consume the authoritative Policy D analysis dataset:
- **File Path:** `data/processed/sensitivity/policy_d/analysis.parquet`
- **Total Records:** 924,731 pixel-year-season observations.
- **Temporal Span:** 19 climatological seasons across 2022–2026 (Winter, Summer, Monsoon, Post-Monsoon).
- **Spatial Extent:** Surat Municipal Corporation (50,752 100m grid cells).
- **Spatial Partitioning:** 165 deterministic $2\text{ km} \times 2\text{ km}$ spatial blocks (`block_id`: `B_00_00` to `B_16_16`).
- **Policy Lineage:** Policy D applies $OBS \ge 1$ clear-sky temporal ingestion combined with $3 \times 3$ neighborhood anomaly screening ($|\Delta_{\text{med}}| \le 10^\circ\text{C}$ for $OBS=1$). It purges 100% of non-physical cloud-shadow depressions while retaining 99.99% of valid urban pixels, maintaining 89.96% monsoon spatial coverage and 99.18% hotspot retention.
- **Policy D Status:** **DRAFT / NOT FROZEN**. Production analytical COGs are intentionally pending final policy freeze.

---

## 3. Feature Set

To ensure rigorous spatial and physical generalization, geographic coordinates are strictly excluded from the predictor space:

### Target Variable ($y$)
- **`LST_C`:** Land Surface Temperature in Celsius derived from Landsat 8/9 Collection 2 Level-2 Band 10 thermal infrared radiance via single-channel atmospheric correction (100m ground resolution).

### Feature Predictors ($X$)
1. **`NDVI`** (Normalized Difference Vegetation Index): Canopy greenness and vegetation fraction ($(\text{NIR}-\text{Red})/(\text{NIR}+\text{Red})$).
2. **`NDBI`** (Normalized Difference Built-up Index): Impervious surface density and built fabric ($(\text{SWIR1}-\text{NIR})/(\text{SWIR1}+\text{NIR})$).
3. **`NDWI`** (Normalized Difference Water Index): Surface moisture and open water ($(\text{Green}-\text{NIR})/(\text{Green}+\text{NIR})$).
4. **`LST_OBS_COUNT`**: Clear-sky scene count contributing to the seasonal composite (temporal support proxy).
5. **`LST_QA_MEDIAN_K`**: Pixel-level radiometric surface temperature uncertainty in Kelvin from USGS Level-2 `ST_QA`.

*Deliberate Predictor Exclusions:* `latitude`, `longitude`, `row`, `col`, and neighborhood summary metrics are excluded from training features to prevent spatial memorization and force generalization on environmental indicators.

---

## 4. Spatial Validation Design

Spatial autocorrelation causes standard random train/test splits or random K-fold CV to leak proximate pixels across splits, yielding overly optimistic evaluation metrics. To guarantee scientific integrity:

```text
SAME SPATIAL BLOCK
        ↓
MUST NEVER APPEAR IN BOTH
TRAINING AND VALIDATION
```

1. **Spatial Grid:** The Surat municipal raster is divided into 165 spatial blocks of $20 \times 20$ pixels (~$2\text{ km} \times 2\text{ km}$).
2. **Deterministic Partitioning:** Blocks are assigned to 5 balanced folds (33 blocks per fold) using deterministic seed `42`.
3. **Zero Spatial Leakage:** The invariant $\text{train\_blocks} \cap \text{val\_blocks} = \emptyset$ is formally verified for every fold.
4. **Fold Balance:**
   - Fold 1: 203,758 validation pixels (33 blocks)
   - Fold 2: 194,357 validation pixels (33 blocks)
   - Fold 3: 196,290 validation pixels (33 blocks)
   - Fold 4: 167,043 validation pixels (33 blocks)
   - Fold 5: 163,283 validation pixels (33 blocks)

The exact same fold partitioning is used across the RF baseline, XGBoost baseline, Optuna search, and full-data tuned confirmation.

---

## 5. Baseline XGBoost

The baseline XGBoost model utilized the repository's established default configuration:
- `objective`: `reg:squarederror`
- `tree_method`: `hist`
- `n_estimators`: 500
- `max_depth`: 6
- `learning_rate`: 0.05
- `min_child_weight`: 1.0
- `subsample`: 1.0
- `colsample_bytree`: 1.0
- `gamma`: 0.0
- `reg_alpha`: 0.0
- `reg_lambda`: 1.0
- `random_state`: 42

**Baseline 5-Fold Spatial CV Performance:**
- **MAE:** $1.3190 \pm 0.0270^\circ\text{C}$
- **RMSE:** $1.8280 \pm 0.0610^\circ\text{C}$
- **$R^2$:** $0.8990 \pm 0.0040$
- **Training Time:** ~16.4 s / fold

---

## 6. Optuna Search Configuration

Hyperparameter tuning was conducted using Optuna 5.0.0 with deterministic Tree-structured Parzen Estimator (TPE) sampling:
- **Sampler:** `optuna.samplers.TPESampler(seed=42)`
- **Pruning:** `optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=1)`
- **Trials:** 30 trials
- **Optimization Metric:** Mean 5-Fold Spatial Cross-Validation RMSE (minimization)
- **Evaluation Rule:** Every trial was evaluated strictly on spatial validation folds; training RMSE and random-split metrics were never optimized.

### Search Space Bounds:
| Parameter | Type | Range / Distribution | Baseline Value |
|---|---|---|---|
| `n_estimators` | Integer | $300 - 1500$ (step 50) | 500 |
| `max_depth` | Integer | $3 - 10$ | 6 |
| `learning_rate` | Float | $0.01 - 0.20$ (log scale) | 0.05 |
| `min_child_weight` | Float | $1.0 - 20.0$ | 1.0 |
| `subsample` | Float | $0.60 - 1.00$ | 1.0 |
| `colsample_bytree` | Float | $0.60 - 1.00$ | 1.0 |
| `gamma` | Float | $0.0 - 5.0$ | 0.0 |
| `reg_alpha` | Float | $10^{-8} - 10.0$ (log scale) | 0.0 |
| `reg_lambda` | Float | $10^{-3} - 20.0$ (log scale) | 1.0 |

---

## 7. Search Dataset

To ensure computational tractability while maintaining spatial rigor, a spatially stratified search sample of 250,004 observations was drawn:
- **Stratification Mechanism:** Grouped by `block_id`, sampling exactly ~27.03% of rows within each block.
- **Geographic Representation:** 165 of 165 spatial blocks (100.0%) were preserved in exact municipal proportions.
- **Baseline Metric on Search Sample:** The baseline model configuration on this search sample yielded a 5-fold spatial CV RMSE of $1.8815^\circ\text{C}$.

---

## 8. Best Candidate Configuration

Out of 30 evaluated trials, **Trial #23** achieved the lowest mean spatial CV RMSE on the search sample:
- **Search Sample Mean RMSE:** $1.8225^\circ\text{C}$ (an improvement of $-0.0590^\circ\text{C}$ over the baseline configuration on the same sample).

### Selected Best Hyperparameters:
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

### Parameter Dynamics Observed During Search:
1. **Deeper Trees with Moderate Regularization:** The search preferred `max_depth = 8` over the baseline 6, coupled with `min_child_weight = 5.41` and `gamma = 1.63` to prevent leaf overfitting.
2. **Lower Learning Rate with Extended Trees:** Learning rate decreased from $0.05$ to $0.0328$, compensated by expanding tree capacity from 500 to 1300 estimators.
3. **Stochastic Subsampling:** Row subsampling ($subsample \approx 0.76$) and feature subsampling ($colsample\_bytree \approx 0.97$) added de-correlating noise, improving spatial out-of-fold generalization.

---

## 9. Full-Data Spatial Confirmation

The candidate hyperparameters discovered in Trial #23 were confirmed on the **complete 924,731 observation Policy D dataset** across the authoritative 5 spatial folds.

### Individual Spatial Fold Results:
| Fold ID | Validation Block Count | Validation Sample Count ($N$) | MAE ($^\circ\text{C}$) | RMSE ($^\circ\text{C}$) | $R^2$ | Training Time |
|---|---|---|---|---|---|---|
| **Fold 1** | 33 blocks | 203,758 | 1.2595 | 1.7342 | 0.9033 | 48.8 s |
| **Fold 2** | 33 blocks | 194,357 | 1.2801 | 1.7369 | 0.9064 | 53.4 s |
| **Fold 3** | 33 blocks | 196,290 | 1.3301 | 1.8801 | 0.8963 | 60.4 s |
| **Fold 4** | 33 blocks | 167,043 | 1.2974 | 1.7801 | 0.9023 | 56.5 s |
| **Fold 5** | 33 blocks | 163,283 | 1.2604 | 1.7887 | 0.9095 | 56.0 s |

### Full-Data Aggregate Statistics:
- **Mean MAE:** $1.2855 \pm 0.0294^\circ\text{C}$ (min: $1.2595^\circ\text{C}$, max: $1.3301^\circ\text{C}$)
- **Mean RMSE:** $1.7840 \pm 0.0591^\circ\text{C}$ (min: $1.7342^\circ\text{C}$, max: $1.8801^\circ\text{C}$)
- **Mean $R^2$:** $0.9033 \pm 0.0050$ (min: $0.8963$, max: $0.9095$)

### Confirmation Verification:
The search-sample RMSE ($1.8225^\circ\text{C}$) successfully generalized to the full dataset, producing an even lower out-of-fold RMSE ($1.7840^\circ\text{C}$) due to the larger training fold size (~740k training pixels vs ~200k in the search sample).

---

## 10. RF vs XGBoost Baseline vs Tuned XGBoost

All three model configurations were evaluated using the exact same 5-fold spatial cross-validation design, features, and target:

| Model Architecture | Mean MAE ($\pm \text{std}$) | Mean RMSE ($\pm \text{std}$) | Mean $R^2$ ($\pm \text{std}$) | Training Time / Fold |
|---|---|---|---|---|
| **Random Forest Baseline** | $1.2927 \pm 0.0280^\circ\text{C}$ | $1.8024 \pm 0.0545^\circ\text{C}$ | $0.9014 \pm 0.0043$ | ~15.5 s |
| **XGBoost Baseline** | $1.3190 \pm 0.0274^\circ\text{C}$ | $1.8280 \pm 0.0607^\circ\text{C}$ | $0.8986 \pm 0.0045$ | ~16.4 s |
| **XGBoost Tuned** | **$1.2855 \pm 0.0294^\circ\text{C}$** | **$1.7840 \pm 0.0591^\circ\text{C}$** | **$0.9033 \pm 0.0050$** | ~55.0 s |

### Measured Differences:
1. **Tuned XGBoost vs XGBoost Baseline:**
   - MAE improved by **$-0.0335^\circ\text{C}$** (2.54% error reduction).
   - RMSE improved by **$-0.0440^\circ\text{C}$** (2.41% error reduction).
   - $R^2$ increased by **$+0.0047$** (from 0.8986 to 0.9033).
2. **Tuned XGBoost vs Random Forest Baseline:**
   - MAE improved by **$-0.0072^\circ\text{C}$** (0.56% error reduction).
   - RMSE improved by **$-0.0184^\circ\text{C}$** (1.02% error reduction).
   - $R^2$ increased by **$+0.0019$** (from 0.9014 to 0.9033).

### Scientific Significance Discussion:
While Tuned XGBoost achieves the lowest mean error across all three metrics, the difference relative to Random Forest ($-0.018^\circ\text{C}$ RMSE) is well within the spatial fold standard deviation ($\pm 0.059^\circ\text{C}$). Therefore, this represents a **modest, consistent refinement** rather than a transformative algorithmic breakthrough. It confirms that both ensemble families approach the empirical Bayes error rate governed by 100m optical/thermal remote sensing features.

---

## 11. Seasonal Performance

Out-of-fold spatial predictions were stratified across climatological seasons:

| Season | Sample Count ($N$) | MAE ($^\circ\text{C}$) | RMSE ($^\circ\text{C}$) | $R^2$ | Contains Partial Season | Scientific Context / Notes |
|---|---|---|---|---|---|---|
| **Winter** | 248,735 | 0.9547 | 1.3165 | 0.6564 | No | Complete 5-year series; minimal cloud interference |
| **Summer** | 248,735 | 1.3658 | 1.7860 | 0.7589 | No | Complete series; high dynamic range and peak urban heat |
| **Monsoon** | 228,273 | 1.8211 | 2.4689 | 0.7910 | Yes | **2026 monsoon contains partial temporal acquisitions** |
| **Post-Monsoon** | 198,988 | 0.9858 | 1.2852 | 0.7951 | No | Complete series; clear atmospheric windows |

### Key Seasonal Observations:
- **Tuning Reduces Seasonal Errors Across All Strata:**
  - Winter RMSE dropped from $1.337^\circ\text{C}$ (baseline) to $1.317^\circ\text{C}$ (tuned).
  - Summer RMSE dropped from $1.825^\circ\text{C}$ (baseline) to $1.786^\circ\text{C}$ (tuned).
  - Monsoon RMSE dropped from $2.541^\circ\text{C}$ (baseline) to $2.469^\circ\text{C}$ (tuned, an improvement of $-0.072^\circ\text{C}$).
  - Post-Monsoon RMSE dropped from $1.313^\circ\text{C}$ (baseline) to $1.285^\circ\text{C}$ (tuned).
- **Monsoon Cloud Attenuation:** Monsoon remains the highest-variance season ($RMSE = 2.469^\circ\text{C}$) due to persistent cloud contamination, variable soil moisture, and atmospheric moisture attenuation.
- **Partial 2026 Monsoon Note:** The 2026 monsoon data contains partial season acquisitions and must not be interpreted as a full 4-month climatological composite.

---

## 12. Hotspot Performance

Evaluation across urban heat island sub-populations confirms performance in critical high-risk zones:

| Hotspot Stratum | Operational Definition | Sample Count ($N$) | MAE ($^\circ\text{C}$) | RMSE ($^\circ\text{C}$) | $R^2$ | Baseline XGB RMSE | Change ($\Delta$) |
|---|---|---|---|---|---|---|---|
| **Non-Hotspot** | $hotspot\_frequency = 0$ | 859,111 | 1.2284 | 1.6790 | 0.9119 | 1.7200 | **-0.0410** |
| **Active Hotspot** | $hotspot\_frequency > 0$ | 65,620 | 2.0386 | 2.8222 | 0.7943 | 2.8940 | **-0.0718** |
| **Chronic Hotspot** | $hotspot\_frequency \ge 6 \lor persistent$ | 11,851 | 3.3601 | 4.3494 | 0.5122 | 4.4120 | **-0.0626** |

### Key Hotspot Findings:
1. **Substantial Error Reduction in Active Hotspots:** In active hotspots, tuned XGBoost reduced RMSE by $-0.072^\circ\text{C}$ (from $2.894^\circ\text{C}$ to $2.822^\circ\text{C}$), demonstrating that deeper trees (`max_depth=8`) better capture steep urban thermal gradients.
2. **Persistence of Chronic Hotspot Under-Prediction:** In chronic industrial hotspots (e.g., Pandesara GIDC metal fabricators, Sachin GIDC chemical plants), mean absolute error remains elevated ($MAE = 3.360^\circ\text{C}$, $RMSE = 4.349^\circ\text{C}$).
3. **Physical Explanation:** This residual error is not an algorithmic defect; it is a direct consequence of spatial scale. Corrugated industrial roofs reach skin temperatures exceeding $65^\circ\text{C}$ over $20\text{ m} \times 20\text{ m}$ footprints. When integrated into 100m grid cells with surrounding roads and vegetation, optical indices (`NDBI`, `NDVI`) reach asymptotic saturation, bounding the model's capacity to predict extreme local peaks.

---

## 13. Spatial Residual Analysis

Out-of-fold spatial residuals ($residual = LST\_C - prediction$) were calculated across all 924,731 observations and exported to:
- `artifacts/xgb_tuning/tuned_spatial_residuals.parquet` (full tabular records)
- `reports/xgb_spatial_residuals.geojson` (1,500 diagnostic sample points: 500 largest absolute errors + 1,000 spatial background samples).

### Spatial Anomaly Patterns:
1. **Zero Spatial Mean Bias:** The mean out-of-fold residual across Surat is $0.0018^\circ\text{C}$, confirming that the model exhibits no global directional bias.
2. **Geographic Concentration of Extreme Residuals:**
   - **Pandesara & Sachin GIDC:** Predominantly positive residuals ($LST_{\text{obs}} > LST_{\text{pred}}$ by $+3.0$ to $+6.5^\circ\text{C}$), indicating systematic under-prediction of extreme industrial rooftop skin temperatures.
   - **Tapi River & Dumas Coastal Edge:** Minor negative residuals ($LST_{\text{obs}} < LST_{\text{pred}}$ by $-1.5$ to $-3.0^\circ\text{C}$), where sub-pixel water-land interfaces cause spectral mixing.
   - **Dense Residential Wards (Central Surat / Rander):** Small, normally distributed residuals ($|residual| < 1.0^\circ\text{C}$), indicating excellent spatial fit in standard urban fabric.

---

## 14. SHAP Analysis

TreeExplainer attribution was refreshed for the confirmed tuned XGBoost model across all 5 spatial validation folds (10,000 background evaluations):

| Feature Name | Feature Role / Type | Mean $|SHAP|$ Value | Across-Fold Std | CoV (%) | Baseline XGB Mean $|SHAP|$ |
|---|---|---|---|---|---|---|
| **`LST_QA_MEDIAN_K`** | Radiometric Uncertainty / Context | **3.0481** | $\pm 0.0740$ | **2.43%** | 3.0399 |
| **`NDBI`** | Impervious Built-up Index (Physical) | **1.5538** | $\pm 0.0799$ | **5.14%** | 1.5906 |
| **`LST_OBS_COUNT`** | Clear-Sky Temporal Support (Quality) | **1.0880** | $\pm 0.1023$ | **9.41%** | 1.1804 |
| **`NDWI`** | Moisture / Water Index (Physical) | **0.7471** | $\pm 0.0435$ | **5.82%** | 0.8434 |
| **`NDVI`** | Vegetation Abundance Index (Physical) | **0.4891** | $\pm 0.0319$ | **6.52%** | 0.5092 |

### Critical Scientific Attribution Insights:
1. **Attribution Order Invariant:** The relative importance hierarchy is identical to the baseline model:
   $$\text{LST\_QA\_MEDIAN\_K} > \text{NDBI} > \text{LST\_OBS\_COUNT} > \text{NDWI} > \text{NDVI}$$
2. **Exceptionally High Spatial Stability:** The coefficient of variation across independent spatial folds is under $10\%$ for all features (and $2.43\%$ for `LST_QA_MEDIAN_K`), proving that feature attributions are consistent across Surat and not driven by local fold sampling.
3. **Non-Causal Interpretation Reminder:** SHAP values represent statistical attribution within the fitted tree ensemble, not physical causality.

---

## 15. Stability Analysis

Model stability across the 5 independent spatial blocks was rigorously evaluated:
- **RMSE Range:** $1.7342^\circ\text{C}$ (Fold 1) to $1.8801^\circ\text{C}$ (Fold 3).
- **RMSE Standard Deviation:** $\pm 0.0591^\circ\text{C}$ (CoV = $3.31\%$).
- **MAE Standard Deviation:** $\pm 0.0294^\circ\text{C}$ (CoV = $2.29\%$).
- **$R^2$ Range:** $0.8963$ (Fold 3) to $0.9095$ (Fold 5).

### Fold 3 Variance Driver:
Fold 3 exhibits slightly higher RMSE ($1.8801^\circ\text{C}$) because its spatial blocks encompass the core Pandesara industrial corridor and Surat's southern dense urban expansion, which possess the highest concentration of chronic thermal anomalies. Despite this regional difficulty, Fold 3 maintains an $R^2$ of $0.8963$, indicating excellent rank correlation.

---

## 16. Scientific Interpretation

### 16.1 Physical vs Radiometric Context Separation
- **`NDBI` as Primary Physical Driver:** Among direct surface property indicators, `NDBI` carries the highest attribution ($mean\ |SHAP| = 1.5538$). Densely paved urban surfaces systematically associate with elevated surface temperatures.
- **`NDVI` and `NDWI` Cooling Association:** Higher canopy greenness (`NDVI`) and surface moisture (`NDWI`) contribute negative SHAP values, reflecting the well-documented evaporative cooling effect of urban vegetation and water bodies.

### 16.2 Interpretation of `LST_QA_MEDIAN_K`
- `LST_QA_MEDIAN_K` exhibits the largest mean absolute SHAP value ($3.0481$).
- **Scientific Context:** USGS Level-2 `ST_QA` reports radiometric uncertainty derived from atmospheric transmission and water vapor models. In coastal, sub-tropical Surat, atmospheric column water vapor varies dramatically between hot dry summers and humid monsoons.
- **Role:** Rather than acting as a direct physical cause of surface heat, `LST_QA_MEDIAN_K` provides the decision trees with a powerful proxy for atmospheric background state, allowing the trees to conditionally shift the seasonal baseline temperature before applying optical corrections (`NDBI`, `NDVI`).

---

## 17. Limitations

The following scientific, sensor, and operational limitations must be preserved in all downstream analyses:

1. **Thermal Spatial Scale (~100m):**
   Landsat 8/9 Band 10 thermal observations have a native resolution of 100m. Micro-urban interventions (e.g. painting a single $15\text{ m} \times 15\text{ m}$ roof white) cannot be directly resolved by 100m raster pixels without spatial downscaling or sub-pixel endmember modeling.
2. **Under-Prediction in Chronic Industrial Hotspots:**
   Peak skin temperatures in chronic hotspots are systematically under-predicted by $2.0 - 4.5^\circ\text{C}$. The future Heat Priority engine must fuse persistent hotspot frequency masks with ML predictions rather than relying solely on regression outputs.
3. **Monsoon Temporal Truncation (2026):**
   The 2026 monsoon composite represents a partial temporal series. It is retained for completeness but must not be treated as a full 4-month climatological composite.
4. **Inter-Annual Atmospheric Shifts:**
   Unprecedented regional climate shifts (e.g., the abnormally warm 2025 winter) require temporal context adjustments when projecting future heat patterns.

---

## 18. Model Configuration Status

### Scientific Decision:
1. **Tuned XGBoost is Confirmed as the Primary Gradient Boosted Architecture:**
   The tuned configuration ($1300\text{ trees}, max\_depth=8, lr=0.0328$) is confirmed to be stable, reproducible, and superior to the XGBoost baseline across all metrics ($-0.044^\circ\text{C}$ RMSE reduction).
2. **Comparison with Random Forest Baseline:**
   Tuned XGBoost marginally outperforms Random Forest ($RMSE = 1.784^\circ\text{C}$ vs $1.802^\circ\text{C}$, $R^2 = 0.903$ vs $0.901$). Because both models demonstrate near-identical spatial generalization skill, Tuned XGBoost is selected as the operational model due to:
   - Faster vectorized batch inference on full rasters via `tree_method='hist'`.
   - Direct, native integration with fast C++ TreeExplainer for spatial SHAP generation.
   - Compact memory footprint for deployment in FastAPI backend services.
3. **Policy D Status:**
   Policy D remains **DRAFT / NOT FROZEN**. Model hyperparameter tuning establishes that the ML architecture is sound and stable under Policy D, but the formal policy freeze will be documented in the final QC configuration milestone.

---

## 19. Reproducibility Metadata

| Property | Value |
|---|---|
| **Git Commit Hash** | `21e6601` (feature/day1-bootstrap) |
| **Execution Date** | September 27, 2026 |
| **Python Version** | 3.12.10 |
| **XGBoost Version** | 3.4.1 |
| **Optuna Version** | 5.0.0 |
| **Scikit-Learn Version** | 1.9.1 |
| **SHAP Version** | 0.52.0 |
| **Random State / Seed** | 42 |
| **Tuning Script** | `scripts/tune_xgb.py` |
| **Validation Script** | `scripts/validate_tuned_xgb.py` |
| **Tuning Module** | `gis/ml/xgb_tuning.py` |
| **Primary Input Dataset** | `data/processed/sensitivity/policy_d/analysis.parquet` |
| **Generated Artifacts** | `artifacts/xgb_tuning/` |
| **Generated Reports** | `reports/xgb_model_comparison.csv`, `reports/xgb_season_errors.csv`, `reports/xgb_hotspot_errors.csv`, `reports/xgb_spatial_residuals.geojson` |

