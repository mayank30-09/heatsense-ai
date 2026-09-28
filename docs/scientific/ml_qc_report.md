# HEATSENSE AI — Quality-Control and Scientific Validation Report

## 1. Quality Control Overview

This document provides the formal Quality Control (QC) summary for the HEATSENSE AI Land Surface Temperature (LST) machine learning pipeline. It certifies dataset integrity, spatial partition independence, leakage prevention, model training rigor, and independent test evaluation.

---

## 2. Dataset Integrity

- **Path**: `data/processed/sensitivity/policy_d/analysis.parquet`
- **Total Validated Rows**: 924,731
- **Spatial Blocks**: 165 (2 km × 2 km tiles across Surat)
- **Target Variable**: `LST_C` (Landsat Collection 2 Level-2 Surface Temperature, °C)
- **Non-Finite Target Count**: 0 (all values are finite floats)
- **Null Value Assessment**:
  - Target and primary features (`NDVI`, `NDBI`, `NDWI`, `LST_OBS_COUNT`, `LST_QA_MEDIAN_K`): 0 nulls.
  - Quality flags and eligibility masks: 0 nulls.
- **Coordinate Exclusion**: `latitude`, `longitude`, `row`, `col`, `x`, `y` are strictly excluded from the regression feature space to prevent coordinate overfitting and spatial memorization.

---

## 3. Spatial Split & Leakage Verification

- **Partition**: 132 Development Blocks (80%) / 33 Test Blocks (20%).
- **Split File**: `artifacts/ml_freeze/holdout_split.json` (`random_state=42`).
- **Mathematical Disjointness**:
  $$\text{Development} \cap \text{Test} = \emptyset$$
- **Block Conservation**:
  $$\text{Development} \cup \text{Test} = \text{All 165 Blocks}$$
- **Automated Verification**:
  - `backend/tests/test_holdout_protocol.py` (Tests 1 through 10) explicitly validates disjointness, coverage, and fold isolation.
  - Zero test block rows were exposed to Optuna hyperparameter optimization or candidate model selection.
  - 5-fold cross-validation during tuning operated exclusively across the 132 development blocks.

---

## 4. Model Training Protocol

- **Algorithm**: `xgboost.XGBRegressor` with histogram-based tree splitting (`tree_method='hist'`).
- **Hyperparameter Selection**: 30 Optuna TPE trials strictly on development folds.
  - Best trial: Trial #25 (Development 5-fold CV RMSE = $1.8478^\circ\text{C}$).
- **Final Training Set**: All 132 development blocks ($N = 720,973$ rows).
- **Final Model Artifacts**:
  - Native JSON: `artifacts/ml_freeze/xgb_tuned_policy_d.json`
  - Python Joblib: `artifacts/ml_freeze/xgb_tuned_policy_d.joblib`

---

## 5. Independent Holdout Evaluation

The locked model was evaluated **exactly once** on the 33 untouched test blocks ($N = 203,758$ rows):

- **Mean Absolute Error (MAE)**: **1.2726 °C**
- **Root Mean Squared Error (RMSE)**: **1.7524 °C**
- **Coefficient of Determination ($R^2$)**: **0.9006**
- **Inference Speed**: 1.093 seconds for 203,758 rows (equivalent to ~5.36s per million rows under linear extrapolation). In dedicated benchmarks on 924,731 rows, Random Forest achieved lower CPU latency (2.1132 s) than XGBoost (6.5477 s).

---

## 6. Seasonal and Hotspot Diagnostics

### Seasonal Performance:
- **Winter**: $\text{MAE} = 0.9139^\circ\text{C}, \text{RMSE} = 1.2136^\circ\text{C}, R^2 = 0.6512$
- **Summer**: $\text{MAE} = 1.3734^\circ\text{C}, \text{RMSE} = 1.7944^\circ\text{C}, R^2 = 0.7119$
- **Monsoon**: $\text{MAE} = 1.8024^\circ\text{C}, \text{RMSE} = 2.4353^\circ\text{C}, R^2 = 0.7718$
- **Post-Monsoon**: $\text{MAE} = 0.9926^\circ\text{C}, \text{RMSE} = 1.2772^\circ\text{C}, R^2 = 0.7855$

### Hotspot Tier Error Escalation:
- **Non-Hotspot ($f=0$)**: $\text{RMSE} = 1.6715^\circ\text{C}$, Bias = $+0.0165^\circ\text{C}$
- **Active Hotspot ($f>0$)**: $\text{RMSE} = 2.7228^\circ\text{C}$, Bias = $-1.1281^\circ\text{C}$
- **Persistent Hotspot ($f \ge 0.25$)**: $\text{RMSE} = 3.9896^\circ\text{C}$, Bias = $-1.3041^\circ\text{C}$
- **Chronic Hotspot ($f \ge 0.50$)**: $\text{RMSE} = 4.8413^\circ\text{C}$, Bias = $-1.5264^\circ\text{C}$

### Scientific Error Pattern & Architectural Guardrail:
The elevated prediction error in chronic hotspots is consistent with sub-pixel thermal heterogeneity within Landsat's ~100m thermal radiometer footprint over highly heterogeneous industrial roofs. Consequently:
**Observed satellite LST is mandated as Primary Thermal Evidence in HEATSENSE AI's Heat Priority engine.** The ML model provides supplementary evidence and counterfactual scenario modeling, but never replaces observed measurements.

---

## 7. Quality Gate Conclusion

The ML scientific pipeline satisfies all quality and reproducibility criteria:
- [x] Zero spatial leakage between development and test partitions.
- [x] Hyperparameters selected exclusively on development CV.
- [x] Test set evaluated exactly once.
- [x] Full automated test suite passing (88/88 tests).
- [x] Comprehensive cryptographic artifact hashes recorded.

**Status: QUALITY CONTROL APPROVED / FREEZE COMPLETE**
