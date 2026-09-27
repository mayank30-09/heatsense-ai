# HEATSENSE AI — Systematic Feature Ablation Experiment Report

**Status:** VALIDATED SCIENTIFIC ABLATION  
**Model Architecture:** Tuned XGBoost (`tree_method='hist'`)  
**Validation Design:** 5-Fold Spatial Block CV on 132 Development Blocks + 1-time 33 Test Block Holdout  
**Total Analysis Rows:** 924,731 (Policy D)  

---

## 1. Experimental Overview

This experiment evaluates four nested feature configurations under strict spatial block separation:

1. **`A_physical_only`**: Strictly optical surface reflectances (`NDVI`, `NDBI`, `NDWI`).
2. **`B_physical_temporal`**: Optical surface reflectances + clear-sky scene support (`LST_OBS_COUNT`).
3. **`C_physical_qa`**: Optical surface reflectances + USGS radiometric quality / retrieval context (`LST_QA_MEDIAN_K`).
4. **`D_full`**: Complete operational set (`NDVI`, `NDBI`, `NDWI`, `LST_OBS_COUNT`, `LST_QA_MEDIAN_K`).

---

## 2. Performance Comparison Table

| Configuration ID | Features Included | Dev Spatial CV RMSE ($^\circ\text{C}$) | Dev Spatial CV $R^2$ | Test Holdout RMSE ($^\circ\text{C}$) | Test Holdout $R^2$ | Monsoon RMSE ($^\circ\text{C}$) | Chronic Hotspot RMSE ($^\circ\text{C}$) |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`A_physical_only`** | `NDVI+NDBI+NDWI` | $5.1455 \pm 0.1085$ | $0.2108 \pm 0.0241$ | **$4.9967$** | **$0.1915$** | $5.2912$ | $6.9289$ |
| **`B_physical_temporal`** | `NDVI+NDBI+NDWI+LST_OBS_COUNT` | $4.0787 \pm 0.1022$ | $0.5039 \pm 0.0240$ | **$3.9709$** | **$0.4894$** | $3.1449$ | $6.1146$ |
| **`C_physical_qa`** | `NDVI+NDBI+NDWI+LST_QA_MEDIAN_K` | $2.1420 \pm 0.0929$ | $0.8631 \pm 0.0104$ | **$2.0518$** | **$0.8637$** | $3.0449$ | $6.0398$ |
| **`D_full`** | `NDVI+NDBI+NDWI+LST_OBS_COUNT+LST_QA_MEDIAN_K` | $1.8224 \pm 0.0619$ | $0.9009 \pm 0.0062$ | **$1.7524$** | **$0.9006$** | $2.4353$ | $4.8413$ |

---

## 3. Scientific Findings & Interpretation

### 3.1 Contribution of Radiometric QA (`LST_QA_MEDIAN_K`)
- Adding `LST_QA_MEDIAN_K` to physical predictors provides a substantial reduction in both spatial cross-validation RMSE and holdout RMSE.
- **Context Signal vs Physical Cause:** As established in project guidelines, `LST_QA_MEDIAN_K` is not a causal driver of urban heat. It provides a strong retrieval-quality/context signal associated with seasonal atmospheric and observation conditions. Its high predictive contribution should not be interpreted as evidence that radiometric uncertainty itself causes surface heating.

### 3.2 Contribution of Temporal Observation Support (`LST_OBS_COUNT`)
- Clear-sky scene count (`LST_OBS_COUNT`) provides important temporal support information, particularly under cloud-restricted monsoon conditions.

### 3.3 Physical Surface Predictor Performance (Config A)
- The physical-only configuration retains some spatial predictive structure, but its absolute predictive performance is substantially weaker than configurations containing retrieval-context features, with holdout $R^2 = 0.1915$ and RMSE = 4.9967 °C.

### 3.4 Operational Recommendation
- Config D provides the best observed predictive performance among the evaluated feature configurations and is therefore retained as the operational feature configuration for this study.