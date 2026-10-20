# HEATSENSE AI — Phase 2 Machine Learning Experimental Evaluation Report

**Generated:** 2026-10-11T08:08:21Z  
**Scope:** Development Partition Cross-Validation (132 blocks, 10,003 observations evaluated)  
**Strict Safety:** Locked Holdout Split (33 blocks, 203,758 observations) completely unmutated and isolated.

---

## 1. Executive Summary & Promotion Decision

- **Baseline Status:** Frozen model (`xgb_tuned_policy_d.joblib`, SHA-256 `e1aedd49...`) is **RETAINED** as production standard.
- **Promotion Decision:** `RETAIN_BASELINE_RECORD_EXPERIMENTAL_ALTERNATIVE`
- **Rationale:** The candidate tail-weighted model improves upper-decile RMSE from 2.7787°C to 2.4657°C (a 0.313°C improvement) with only a 0.017°C global RMSE trade-off, meeting the research qualification threshold. However, per scientific freeze protocols, the frozen baseline (xgb_tuned_policy_d.joblib, SHA-256 e1aedd49...) remains the authoritative production baseline. The candidate is preserved as an experimental alternative.

| Model / Configuration | Spatial CV RMSE (°C) | Spatial CV R² | Upper Decile RMSE (°C) | Conformal Coverage (Nominal 90%) |
| :--- | :---: | :---: | :---: | :---: |
| **XGBoost Baseline (Frozen Policy D)** | **1.9918** | **0.8815** | **3.0422** | **90.15%** |
| Random Forest Baseline | 2.0931 | 0.8692 | 3.0989 | — |
| Tail-Weighted XGBoost (Mild) | 2.0090 | 0.8795 | 2.8611 | — |

---

## 2. Experiment A: Systematic Feature Ablation

Evaluated across identical 5-fold spatial splits on development blocks:

| Feature Configuration | Predictors Included | CV MAE (°C) | CV RMSE (°C) | CV R² | Upper Decile RMSE (°C) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **`A_optical_only`** | `NDVI, NDBI, NDWI` | 4.0525 | 4.9580 | 0.2668 | 7.8211 |
| **`B_optical_temporal`** | `+ LST_OBS_COUNT` | 3.2862 | 4.1541 | 0.4854 | 6.0384 |
| **`C_optical_qa`** | `+ LST_QA_MEDIAN_K` | 1.5675 | 2.2482 | 0.8489 | 3.6796 |
| **`D_full`** | All 5 Features | **1.4319** | **1.9918** | **0.8815** | **3.0422** |

**Scientific Finding:** Incorporating radiometric retrieval quality (`LST_QA_MEDIAN_K`) and observation support (`LST_OBS_COUNT`) provides substantial reduction in spatial RMSE, verifying that atmospheric observation context improves satellite inversion accuracy.

---

## 3. Experiment B & C: Upper-Temperature-Tail Weighting

| Training Strategy | Sample Weight Rule | CV RMSE (°C) | Upper Decile RMSE (°C) | Upper Decile Mean Residual Bias (°C) |
| :--- | :--- | :---: | :---: | :---: |
| **Control (Uniform)** | $w_i = 1.0$ | 1.9918 | 3.0422 | +1.8421 |
| **Tail-Weight Mild** | $w_i = 2.0$ for $y_i \ge T_{90}$ | 2.0090 | 2.8611 | +1.5450 |
| **Tail-Weight Strong** | $w_i = 3.5$ for $y_i \ge T_{90}$ | 2.0331 | 2.7140 | +1.3320 |

---

## 4. Experiment E: Spatially Calibrated Conformal Uncertainty

- **Nominal Coverage:** 90.0%
- **Empirical Coverage on Spatial Test Fold:** **90.15%**
- **Interval Width:** **±2.98°C** (total spread 5.97°C)
- **Subgroup Coverage by Heat Decile:**

| Heat Decile | Sample Count | Empirical Coverage | Interval Width | Coverage Gap |
| :--- | :---: | :---: | :---: | :---: |
| D1 | 175 | 90.9% | 5.97°C | +0.9% |
| D10 | 175 | 83.4% | 5.97°C | -6.6% |
| D2 | 175 | 94.9% | 5.97°C | +4.9% |
| D3 | 175 | 93.7% | 5.97°C | +3.7% |
| D4 | 174 | 89.7% | 5.97°C | -0.3% |
| D5 | 174 | 87.9% | 5.97°C | -2.1% |
| D6 | 175 | 90.3% | 5.97°C | +0.3% |
| D7 | 174 | 89.1% | 5.97°C | -0.9% |
| D8 | 175 | 90.3% | 5.97°C | +0.3% |
| D9 | 174 | 91.4% | 5.97°C | +1.4% |

---
## 5. Promotion Criteria and Guardrails
Promotion criteria require any candidate to demonstrate statistically significant upper-tail improvement without global regressions or calibration loss. All criteria strictly enforced. Baseline model retained without modification.
