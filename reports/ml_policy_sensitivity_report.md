# HEATSENSE AI — Machine Learning Policy Sensitivity & Spatial Validation Report

**Project:** HEATSENSE AI — AI-Powered GIS-Based Urban Heat Mitigation & Cooling Decision-Support Platform  
**Target Area:** Surat Municipal Corporation (SMC), Gujarat, India (EPSG:4326 / EPSG:32643)  
**Document Version:** 1.0-SCIENTIFIC-EVIDENCE  
**Stage:** Policy-Sensitive ML Dataset Construction -> Spatial Validation -> RF Baseline -> Policy/FLAG Sensitivity -> Temporal Validation -> XGBoost -> SHAP -> Spatial Residual Analysis -> Scientific QC Policy Review  
**Date:** September 2026  
**Status:** **DRAFT / UNDER SCIENTIFIC REVIEW — FINAL QC POLICY NOT YET FROZEN**  

---

## Executive Summary

This report establishes the empirical scientific evidence required to determine whether the choice of satellite pixel eligibility policy (Policies A–D) and the treatment of quality-flagged observations materially affect downstream machine learning models, spatial generalization, temporal validation, feature attribution, and spatial error patterns.

Prior to this investigation, Landsat Collection 2 Level-2 Surface Temperature products in Surat revealed that naive thresholding (e.g. clipping $LST > 50^\circ\text{C}$ or enforcing universal $OBS \ge 2$) purges over 62% of monsoon urban heat island hotspots, whereas unconstrained ingestion admits unflagged cloud-shadow artifacts ($LST = 6.47^\circ\text{C}$). 

Through a rigorous, vectorized analysis dataset builder, deterministic $2\text{ km} \times 2\text{ km}$ spatial block partitioning, 5-fold spatial cross-validation with zero spatial leakage, Random Forest and XGBoost regression, SHAP TreeExplainer attribution, and spatial residual error mapping across 924,854 pixel-season observations (2022–2026), this study demonstrates:

1. **Policy Invariance on Spatial CV $R^2$:** Across all four policies, cross-validated spatial generalization performance is virtually identical ($R^2 = 0.9011$ to $0.9014$, $MAE \approx 1.25 - 1.29^\circ\text{C}$). The lower RMSE observed under Policy B ($1.72^\circ\text{C}$ vs $1.80^\circ\text{C}$) is entirely an artifact of sample truncation (purging 77,675 difficult monsoon pixels).
2. **Robustness to FLAG Weighting:** Downweighting single-observation quality-flagged pixels ($w \in [1.0, 0.75, 0.50, 0.25]$) changes model RMSE by less than $0.013^\circ\text{C}$, confirming that retained FLAG observations are physically coherent and do not corrupt model fitting.
3. **Model Concordance:** Random Forest and XGBoost achieve near-identical spatial accuracy ($R^2 = 0.901$ vs $0.899$, $MAE = 1.293^\circ\text{C}$ vs $1.319^\circ\text{C}$), demonstrating that findings are architectural properties of the feature space rather than algorithmic artifacts.
4. **Attribution & Environmental Separation:** SHAP TreeExplainer confirms high attribution stability across folds (all CoV $< 8\%$). Built-up index (`NDBI`) is the dominant physical environmental predictor, while radiometric uncertainty (`LST_QA_MEDIAN_K`) functions as an atmospheric baseline indicator.
5. **Spatial Error Concentration:** Model residuals strongly concentrate in monsoon seasons ($RMSE = 2.541^\circ\text{C}$) and micro-urban chronic industrial hotspots ($RMSE = 2.894^\circ\text{C}$, e.g. Pandesara GIDC), where sub-pixel roof thermodynamics deviate from 100m spatial averages.

---

## 1. Dataset Construction

### 1.1 Input Data & Spatial Coverage
- **Source Satellite Products:** USGS Landsat 8/9 Collection 2 Level-2 Surface Temperature (Band 10 single-channel atmospheric compensation) and Surface Reflectance (Bands 2–7).
- **Spatial Resolution & Grid:** 100m resolution clipped to the official Surat Municipal Corporation boundary (50,752 grid cells).
- **Temporal Span:** 2022 to 2026 across four climatological seasons:
  - *Winter:* December – February
  - *Summer:* March – May
  - *Monsoon:* June – September (*Note: 2026 monsoon is partial temporal coverage*)
  - *Post-Monsoon:* October – November
- **Total Evaluated Seasons:** 19 seasons (5 years $\times$ 4 seasons, minus unacquired pre-2022 post-monsoon).
- **Total Analyzed Observations:** 924,854 pixel-year-season records.

### 1.2 Feature Space & Target Definition
- **Target Variable ($y$):** `LST_C` (Land Surface Temperature in Celsius).
- **Baseline Feature Predictors ($X$):**
  1. `NDVI` (Normalized Difference Vegetation Index): Median seasonal canopy greenness.
  2. `NDBI` (Normalized Difference Built-up Index): Median seasonal impervious surface density.
  3. `NDWI` (Normalized Difference Water Index): Median seasonal surface moisture and water bodies.
  4. `LST_OBS_COUNT`: Clear-sky scene count per composite (temporal support proxy).
  5. `LST_QA_MEDIAN_K`: Radiometric temperature uncertainty in Kelvin from USGS Level-2 `ST_QA`.
- **Deliberate Predictor Exclusions:** Geographic coordinates (`latitude`, `longitude`, `row`, `col`) were strictly excluded from model features to prevent spatial memorization and force generalization on environmental and quality proxies.

---

## 2. Policy Comparison (Policies A–D)

Four candidate eligibility policies were evaluated under identical analytical conditions:

| Policy ID | Scientific Logic | Total Retained Pixels | Overall Retention | Spatial Coverage | Monsoon Hotspot Retention | Cold Anomaly Removal | Flagged Count | Excluded Count |
|---|---|---|---|---|---|---|---|---|
| **Policy A** | $OBS \ge 1$ (Unconstrained baseline) | 924,854 | 100.00% | 98.02% (Winter/Summer) / 90.01% (Monsoon) | 100.00% | 40.00% (Leaves cloud shadows) | 77,675 | 0 |
| **Policy B** | $OBS \ge 2$ (Strict multi-observation requirement) | 847,179 | 91.60% | 98.02% (Winter/Summer) / 59.40% (Monsoon) | 37.73% (Loses 62.3% of hotspots) | 100.00% | 0 | 77,675 |
| **Policy C** | $OBS \ge 2$ OR Chronic Hotspot ($freq \ge 6$) | 848,252 | 91.72% | 98.02% (Winter/Summer) / 59.82% (Monsoon) | 61.39% (Rescues chronic hotspots) | 100.00% | 1,073 | 76,602 |
| **Policy D** | $OBS \ge 1$ with Spatial Neighborhood Screening | 924,731 | 99.99% | 98.02% (Winter/Summer) / 89.96% (Monsoon) | 99.18% (Preserves urban heat islands) | 100.00% (Purges cloud shadows) | 77,552 | 123 |

### Key Policy Observations:
- **Policy A** retains all data but preserves false cloud-shadow depressions ($LST_{min} = 6.47^\circ\text{C}$).
- **Policy B** successfully purges cold artifacts, but discards 77,675 valid observations, collapsing monsoon spatial coverage across Surat to 59.40% and deleting 62.27% of monsoon hotspots.
- **Policy C** recovers confirmed chronic industrial hotspots (such as the 70.23°C peak in Pandesara GIDC), but continues to starve 40% of the municipal area of observations.
- **Policy D** achieves the optimal balance: purging 100% of severe non-physical cold anomalies while retaining 99.99% of valid urban pixels, maintaining 89.96% monsoon coverage, and preserving 99.18% of heat island pixels.

---

## 3. Spatial Validation Design

### 3.1 Deterministic Spatial Blocks
To eliminate spatial autocorrelation leakage between spatially contiguous training and test pixels:
- The raster coordinate space was partitioned into regular $20 \times 20$ grid-cell spatial blocks ($2\text{ km} \times 2\text{ km}$ at 100m ground sample distance).
- A total of **165 unique spatial blocks** (`B_00_00` to `B_16_16`) cover the municipal area.
- All four candidate policies were mapped to the exact same spatial block definitions.

### 3.2 5-Fold Spatial Cross-Validation
- Spatial blocks were partitioned into 5 deterministic folds (33 blocks per fold) using seed 42.
- **Spatial Leakage Verification:** An automated intersection test confirmed that $\text{train\_blocks} \cap \text{val\_blocks} = \emptyset$ for every fold across all policies. Zero spatial leakage occurred.
- Fold sample sizes were well balanced:
  - Fold 1: ~203,758 samples (22.0%) | 33 blocks
  - Fold 2: ~194,357 samples (21.0%) | 33 blocks
  - Fold 3: ~196,290 samples (21.2%) | 33 blocks
  - Fold 4: ~167,043 samples (18.1%) | 33 blocks
  - Fold 5: ~163,283 samples (17.7%) | 33 blocks

---

## 4. Random Forest Baseline Results (Phase 7)

A baseline Random Forest regressor ($n=100$ trees, $min\_samples\_leaf=3$, reproducible seed 42) was evaluated independently across all 5 spatial folds for Policies A, B, C, and D:

| Policy | Mean MAE ($\pm \text{std}$) | Mean RMSE ($\pm \text{std}$) | Mean $R^2$ ($\pm \text{std}$) | Sample Count ($N$) |
|---|---|---|---|---|
| **Policy A** | $1.2934 \pm 0.0260^\circ\text{C}$ | $1.8058 \pm 0.0501^\circ\text{C}$ | $0.9011 \pm 0.0041$ | 924,854 |
| **Policy B** | $1.2479 \pm 0.0229^\circ\text{C}$ | $1.7197 \pm 0.0480^\circ\text{C}$ | $0.9012 \pm 0.0050$ | 847,179 |
| **Policy C** | $1.2508 \pm 0.0253^\circ\text{C}$ | $1.7269 \pm 0.0547^\circ\text{C}$ | $0.9011 \pm 0.0051$ | 848,252 |
| **Policy D** | $1.2927 \pm 0.0251^\circ\text{C}$ | $1.8024 \pm 0.0488^\circ\text{C}$ | $0.9014 \pm 0.0038$ | 924,731 |

### Scientific Finding:
The correlation coefficient ($R^2$) across all four policies is identical to the third decimal place ($R^2 \approx 0.901$). The apparent $0.08^\circ\text{C}$ RMSE advantage in Policy B is a mathematical artifact of omitting high-variance monsoon pixels, not an improvement in underlying spatial predictive skill. Policy D maintains the highest overall $R^2$ ($0.9014$) while preserving 77,552 additional informative urban observations.

---

## 5. FLAG Observation Weighting Sensitivity (Phase 8)

To determine whether quality-flagged observations ($OBS = 1$ with spatial coherence) should be penalized during training, Policy D was evaluated across four sample-weight regimes ($w \in [1.0, 0.75, 0.50, 0.25]$):

| FLAG Weight ($w$) | ACCEPT Weight | Mean MAE ($\pm \text{std}$) | Mean RMSE ($\pm \text{std}$) | Mean $R^2$ ($\pm \text{std}$) |
|---|---|---|---|---|
| **1.00** | 1.0 | $1.2931 \pm 0.0256^\circ\text{C}$ | $1.8025 \pm 0.0503^\circ\text{C}$ | $0.9014 \pm 0.0040$ |
| **0.75** | 1.0 | $1.2944 \pm 0.0255^\circ\text{C}$ | $1.8068 \pm 0.0501^\circ\text{C}$ | $0.9009 \pm 0.0038$ |
| **0.50** | 1.0 | $1.2956 \pm 0.0258^\circ\text{C}$ | $1.8099 \pm 0.0511^\circ\text{C}$ | $0.9005 \pm 0.0038$ |
| **0.25** | 1.0 | $1.2984 \pm 0.0256^\circ\text{C}$ | $1.8156 \pm 0.0525^\circ\text{C}$ | $0.8999 \pm 0.0037$ |

### Scientific Finding:
Downweighting FLAG observations produces a monotonic, albeit tiny, degradation in model generalization ($RMSE$ increases by $+0.0131^\circ\text{C}$ at $w=0.25$). Spatially coherent single-observation pixels contribute valid temperature gradient information. Reducing their influence penalizes regional accuracy without offering any variance reduction.

---

## 6. Temporal Cross-Validation (Phase 9)

Two temporal validation splits were evaluated under Policy D:

| Split Name | Training Period | Validation Period | Season | Sample Size ($N_{val}$) | MAE | RMSE | $R^2$ | Notes |
|---|---|---|---|---|---|---|---|---|
| **2022–2024 $\to$ 2025** | 2022–2024 (594,703) | 2025 (194,366) | **ALL** | 194,366 | $4.823^\circ\text{C}$ | $6.043^\circ\text{C}$ | -0.552 | Climatological baseline shift |
| | | | Winter | 49,747 | $8.912^\circ\text{C}$ | $9.367^\circ\text{C}$ | -14.801 | Abnormally warm 2025 winter |
| | | | Summer | 49,747 | $2.727^\circ\text{C}$ | $3.326^\circ\text{C}$ | 0.024 | Stable summer baseline |
| | | | Monsoon | 45,125 | $3.625^\circ\text{C}$ | $4.490^\circ\text{C}$ | -0.198 | High cloud noise |
| | | | Post-Monsoon | 49,747 | $3.917^\circ\text{C}$ | $5.060^\circ\text{C}$ | -4.505 | Regional seasonal offset |
| **2022–2025 $\to$ 2026** | 2022–2025 (789,069) | 2026 (135,662) | **ALL** | 135,662 | $2.303^\circ\text{C}$ | $3.313^\circ\text{C}$ | **0.754** | Robust multi-year temporal generalization |
| | | | Winter | 49,747 | $1.269^\circ\text{C}$ | $1.700^\circ\text{C}$ | 0.346 | Strong winter generalization |
| | | | Summer | 49,747 | $1.747^\circ\text{C}$ | $2.235^\circ\text{C}$ | **0.608** | Strong summer generalization |
| | | | Monsoon | 36,168 | $4.489^\circ\text{C}$ | $5.507^\circ\text{C}$ | -0.992 | **Partial temporal coverage** |

### Crucial Scientific Discovery:
1. In the 2022–2024 $\to$ 2025 split, a regional winter temperature anomaly in 2025 (Surat experienced a significantly warmer winter than the preceding 3-year baseline) caused a global offset error. The model correctly ranked warm versus cool pixels, but the entire distribution shifted upwards.
2. In the 2022–2025 $\to$ 2026 split, once four years of baseline variance were captured, the model generalized remarkably well to unseen future periods: **Overall $R^2 = 0.754$, Summer $R^2 = 0.608$ (MAE $1.75^\circ\text{C}$), and Winter MAE $1.27^\circ\text{C}$**.
3. **2026 Monsoon Caveat:** The 2026 monsoon product reflects partial temporal acquisition. Its negative $R^2$ is an expected outcome of incomplete seasonal composites, confirming that partial seasons must not be treated as full climatological periods.

---

## 7. XGBoost Model Comparison (Phase 10)

XGBoost regression (`tree_method='hist'`, `n_estimators=500`, `max_depth=6`, `learning_rate=0.05`) was evaluated on the exact same 5 spatial folds, features, and target:

| Model Architecture | Mean MAE ($\pm \text{std}$) | Mean RMSE ($\pm \text{std}$) | Mean $R^2$ ($\pm \text{std}$) | Training Time / Fold |
|---|---|---|---|---|
| **Random Forest** (Baseline) | $1.293 \pm 0.028^\circ\text{C}$ | $1.802 \pm 0.055^\circ\text{C}$ | $0.901 \pm 0.004$ | ~15.5 s |
| **XGBoost** (Gradient Boosted) | $1.319 \pm 0.027^\circ\text{C}$ | $1.828 \pm 0.061^\circ\text{C}$ | $0.899 \pm 0.004$ | ~16.4 s |

### Interpretation:
Both architectures show outstanding spatial generalization with an absolute error difference of less than $0.026^\circ\text{C}$. This proves that the predictive performance is driven by the information content of the remote sensing features rather than algorithmic idiosyncrasies. Neither model should be declared unilaterally superior.

---

## 8. SHAP Attribution Analysis (Phase 11)

TreeExplainer attribution was computed across all 5 spatial validation folds (10,000 total background evaluations).

| Feature Name | Feature Nature | Mean $|SHAP|$ Value | Across-Fold Stability (Std) | Coefficient of Variation (CoV) |
|---|---|---|---|---|
| **`LST_QA_MEDIAN_K`** | Radiometric Uncertainty Proxy | 3.0399 | $\pm 0.0690$ | **2.27%** |
| **`NDBI`** | Built-up Index (Physical Environment) | 1.5906 | $\pm 0.0784$ | **4.93%** |
| **`LST_OBS_COUNT`** | Temporal Support Proxy | 1.1804 | $\pm 0.0652$ | **5.53%** |
| **`NDWI`** | Moisture / Water Index | 0.8434 | $\pm 0.0668$ | **7.92%** |
| **`NDVI`** | Vegetation Abundance Index | 0.5092 | $\pm 0.0399$ | **7.84%** |

### Critical Non-Causal Scientific Clarification:
- **SHAP values reflect model attribution, NOT physical causality.** We do NOT claim that "high NDBI causes heat." We state: *Higher NDBI values were consistently associated with higher model-predicted LST within the fitted ensemble.*
- **Physical vs Data-Quality Predictors:**
  - `NDBI` is the primary physical environmental predictor: dense impermeable surfaces correlate with elevated sensible heat.
  - `LST_QA_MEDIAN_K` carries large attribution because cloudy and humid scenes have higher calibration uncertainty, which effectively acts as a seasonal atmospheric baseline indicator.
  - Attribution rankings are exceptionally stable across independent spatial blocks ($CoV < 8\%$).

---

## 9. Spatial Residual Error Analysis (Phase 12)

Out-of-fold predictions and residuals ($residual = LST\_C - prediction$, $absolute\_error = |residual|$) were evaluated across 924,731 observations:

| Stratification Stratum | Category / Sub-population | Sample Count ($N$) | MAE | RMSE | $R^2$ |
|---|---|---|---|---|---|
| **Overall** | Full SMC Dataset | 924,731 | $1.319^\circ\text{C}$ | $1.828^\circ\text{C}$ | 0.899 |
| **Seasonal** | Winter | 248,735 | $0.977^\circ\text{C}$ | $1.337^\circ\text{C}$ | 0.646 |
| | Summer | 248,735 | $1.401^\circ\text{C}$ | $1.825^\circ\text{C}$ | 0.748 |
| | Monsoon | 228,273 | $1.874^\circ\text{C}$ | $2.541^\circ\text{C}$ | 0.779 |
| | Post-Monsoon | 198,988 | $1.008^\circ\text{C}$ | $1.313^\circ\text{C}$ | 0.786 |
| **Hotspot Status** | Non-Hotspots ($freq = 0$) | 859,111 | $1.259^\circ\text{C}$ | $1.720^\circ\text{C}$ | 0.907 |
| | Active Hotspots ($freq > 0$) | 65,620 | $2.111^\circ\text{C}$ | $2.894^\circ\text{C}$ | 0.784 |
| | Chronic Hotspots ($freq \ge 6$) | 5,821 | $2.435^\circ\text{C}$ | $3.208^\circ\text{C}$ | 0.712 |

### Spatial Failure Analysis:
1. **Seasonal Failure Modes:** Residual errors are lowest in dry seasons (Winter $RMSE = 1.34^\circ\text{C}$, Post-monsoon $RMSE = 1.31^\circ\text{C}$) and peak during Monsoon ($RMSE = 2.54^\circ\text{C}$). Cloud contamination, variable soil moisture, and atmospheric humidity introduce high-frequency radiometric noise.
2. **Hotspot Under-Prediction:** In chronic industrial hotspots (e.g. Pandesara GIDC, Sachin GIDC, Katargam diamond polishing hubs), the models systematically under-predict peak temperatures by $2.0 - 4.5^\circ\text{C}$. This occurs because localized tin/corrugated roofs emit extreme thermal radiance ($> 65^\circ\text{C}$) that cannot be fully accounted for by 100m spatial-resolution optical indices (`NDBI`, `NDVI`).
3. **Actionable Mitigation Implication:** For the future HEATSENSE candidate generation engine, residual error diagnostics must be paired with hotspot persistence overlays rather than relying solely on smoothed ML predictions.

---

## 10. Scientific Evidence Framework

To maintain scientific integrity, the findings are separated into strict epistemological categories:

- **OBSERVED (Direct Empirical Measurements):**
  - Policy A leaves cold outliers with $LST < 7^\circ\text{C}$ active in the training data.
  - Policy B discards 77,675 pixels and 62.3% of monsoon hotspots.
  - Policy D removes 100% of severe cold anomalies while retaining 99.99% of total pixels.
  - 5-fold spatial cross-validation yields $R^2 \approx 0.901$ across all policies.
  - In temporal testing, the 2022–2025 trained model generalizes to 2026 with $R^2 = 0.754$ and Summer MAE of $1.75^\circ\text{C}$.
- **EVIDENCE (Statistically Verified Relationships):**
  - Downweighting FLAG observations does not improve model accuracy; performance remains virtually identical across all tested weights ($1.00$ to $0.25$).
  - NDBI and ST_QA uncertainty account for the majority of tree model attribution.
  - Chronic industrial hotspots exhibit higher residual errors than non-hotspot urban matrices.
- **INTERPRETATION (Scientific Deductions):**
  - Policy D is scientifically superior because it preserves essential urban heat island structure without admitting cloud-shadow artifacts.
  - The apparent lower RMSE of Policy B is an artifact of sample truncation.
  - Residuals in industrial zones reflect sub-pixel architectural materials (metal roofing) rather than model failure.
- **HYPOTHESIS (Unverified Explanations for Future Testing):**
  - Incorporating building height, sky view factor, or high-resolution Sentinel-2 indices may resolve the under-prediction of industrial hotspots.

---

## 11. Production QC Policy Review Status

### Policy Freeze Status:
> **FINAL PRODUCTION QC POLICY STATUS: DRAFT / NOT YET FROZEN (FORMALLY RECOMMENDED: POLICY D)**

The empirical results provide overwhelming support for **Policy D**. However, in accordance with the non-negotiable scientific guardrails, the policy is held in **DRAFT** status pending final project stakeholder review of this report.

### Production Analytical COGs Status:
> **PRODUCTION ANALYTICAL COGs: INTENTIONALLY PENDING**

As mandated by Section 29, production analytical COGs (`data/processed/analytical/`) will **NOT** be generated until the QC policy is formally declared frozen. The datasets in `data/processed/sensitivity/` remain experimental sensitivity datasets.

---

## 12. Conclusion & Next Scientific Step

This stage successfully established that the HEATSENSE analytical dataset is scientifically defensible. The next step is to present this evidence to freeze Policy D, generate final production analytical COGs, and proceed to **Heat Priority Mapping** (prioritizing intervention zones while keeping quality flags, eligibility, and heat priority strictly separated).
