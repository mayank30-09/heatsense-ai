# HEATSENSE AI — Machine Learning & QC Policy Freeze Record

**Project:** HEATSENSE AI — AI-Powered GIS-Based Urban Heat Mitigation & Cooling Decision-Support Platform  
**Target Area:** Surat Municipal Corporation (SMC), Gujarat, India (EPSG:4326 / EPSG:32643)  
**Document Version:** 1.0-FROZEN  
**Date:** September 2026  
**Status:** **FROZEN (SCIENTIFIC QC + ML FREEZE GATE COMPLETED)**  
**Branch:** `feature/scientific-freeze-correction`  
**Git Commit:** `06a4c850893cb2656f9687c9ac3bc52cb03cdc3d`  

---

## 1. Freeze Lineage & Scientific Protocol Statement

This record establishes the authoritative, immutable cryptographic and procedural specification for the **HEATSENSE AI Pixel Quality Eligibility Policy (Policy D)** and the **Final Tuned XGBoost LST Regression Model (`xgb_tuned_policy_d_v1`)**.

### Critical Procedural Guarantees:
1. **Immutable Spatial Holdout:** The Surat analysis area was partitioned strictly by spatial block (`block_id`) into **132 development blocks** (720,973 rows, 77.97%) and **33 test blocks** (203,758 rows, 22.03%) with zero overlap ($\text{development\_blocks} \cap \text{test\_blocks} = \emptyset$).
2. **Strict Test Isolation:** The test blocks were NOT used for:
   - hyperparameter tuning
   - feature selection
   - model selection
   - threshold selection
   - model development
3. **Single Untouched Evaluation:** The final candidate model was trained on all 132 development blocks and evaluated **EXACTLY ONCE** on the locked test blocks.

```text
Policy D (Analysis Dataset)
    ↓
LOCKED SPATIAL HOLDOUT (132 Dev / 33 Test Blocks)
    ↓
5-FOLD SPATIAL CV (132 Dev Blocks Only)
    ↓
OPTUNA TPE TUNING (30 Trials strictly on Dev Blocks)
    ↓
FINAL CANDIDATE MODEL (Fit on all 132 Dev Blocks)
    ↓
33 UNTOUCHED TEST BLOCKS
    ↓
ONE FINAL HOLDOUT EVALUATION (MAE: 1.2726°C, RMSE: 1.7524°C, R²: 0.9006)
    ↓
REPRODUCIBILITY HASHES (SHA-256)
    ↓
QC + ML FREEZE
```

---

## 2. Certified Cryptographic Provenance (SHA-256 Hashes)

The following SHA-256 digests are authoritative and persisted in `artifacts/ml_freeze/checksums.sha256`:

| Artifact Category | File Path | SHA-256 Hex Digest |
|---|---|---|
| **Quality Policy Spec** | `config/quality_policy_d.yaml` | `5f122e6104cc2772de1d6fc6daef64de170b68d4ed74d2a8e8182144b4c21363` |
| **Authoritative Dataset** | `data/processed/sensitivity/policy_d/analysis.parquet` | `e824794e5ba2e26937ac40f55f5fd788adad70b1a6b23c6ab435b08223dd9997` |
| **Locked Spatial Holdout** | `artifacts/ml_freeze/holdout_split.json` | `0ee436cbb382c6b811c27331701b03fba8221f8f1b99baa5522e8b94f92deb5f` |
| **Spatial 5-Fold Map** | `artifacts/ml_freeze/tuning/spatial_fold_definition.json` | `6836471bc503e7c9aeadcbf86907f1a10baa8def6607925cb27c0b0bf84b3418` |
| **Tuned Hyperparameters** | `artifacts/ml_freeze/tuning/xgb_best_params.json` | `0ca76e50933d35783596274467247dfa5936678ada0ef7dd7e8003c827026512` |
| **Locked Feature Schema** | `artifacts/ml_freeze/feature_schema.json` | `15f1828a55d54d01997ae17109c3dbd57ef57257e5c790a76e3e476ae13d042c` |
| **Final Candidate Model (JSON)** | `artifacts/ml_freeze/xgb_tuned_policy_d.json` | `8c4aad26e2a56867e327aeae0cd758f9b2b1105bf8d35c0ec8f6774f4ef38377` |
| **Final Candidate Model (Joblib)** | `artifacts/ml_freeze/xgb_tuned_policy_d.joblib` | `e1aedd4946b1b29823bdea66ea3ec7b9ba5f20c4ddbfdf6920c2e62e6b30b7c9` |
| **Final Holdout Performance** | `artifacts/ml_freeze/holdout_performance.json` | `fc72fe6a22281b364c11f614dc9406a06c3c0291b4c29f89eea89e4531a93de5` |
| **Holdout Seasonal Metrics** | `artifacts/ml_freeze/holdout_season_performance.csv` | `1158e56ba4e1a22cd44e6d92d614cc635db20be06415e902db99807cdf5291af` |
| **Holdout Hotspot Metrics** | `artifacts/ml_freeze/holdout_hotspot_performance.csv` | `3990946de0616a2d4e20457278c09c6c39268aab59756dee72501bcb1097e539` |
| **Holdout Spatial Residuals** | `artifacts/ml_freeze/holdout_spatial_residuals.geojson` | `4b4d3d59e2f0c2b27e479f157d355d745bcb65c49c61aac077ffd5179cc27327` |
| **Model Metadata** | `artifacts/ml_freeze/model_metadata.json` | `8799b14fe3823ba84fd4efea90b8028c3aae0c2bda4eee8916f986b524743798` |

---

## 3. Dataset Reconciliation

| Dataset Identifier | Filter Logic | Total Rows | Total Spatial Blocks | Retention vs Raw | Severe Anomaly Removal | Status |
|---|---|---|---|---|---|---|
| **All-Policy Baseline** | $OBS \ge 1$ (Policy A unconstrained) | 924,854 | 165 | 100.00% | Retains unflagged cold shadows | Diagnostic Reference |
| **Policy D Dataset** | $OBS \ge 1$ + $3\times3$ screening ($|\Delta_{\text{med}}| \le 10^\circ\text{C}$ for $OBS=1$) | **924,731** | **165** | **99.99%** | **100.0%** (123 severe anomalies purged) | **CERTIFIED FROZEN BASELINE** |

- **Development Set (132 Blocks):** 720,973 rows (77.97%)
- **Independent Test Set (33 Blocks):** 203,758 rows (22.03%)
- **Spatial Block Size:** $20 \times 20$ pixels (~$2\text{ km} \times 2\text{ km}$)

---

## 4. Frozen Quality Policy Specification (Policy D)

- **Policy ID:** `D`
- **Policy Name:** `policy_d`
- **Version:** `1.0-FROZEN`
- **Implementation:** `gis/quality/eligibility.py` (`evaluate_policy_d`)
- **Specification:** `config/quality_policy_d.yaml`
- **Neighborhood Size:** $3 \times 3$ matrix (minimum 4 valid neighbors required for unflagged interior evaluation)
- **Anomaly Threshold:** $|\Delta_{\text{med}}| = 10.0^\circ\text{C}$
- **Operational Rules:**
  - $OBS < 1 \lor \text{non-finite}: \to \mathbf{EXCLUDE}$ (Reason: `no_temporal_support`)
  - $OBS \ge 2 \land \text{no spatial anomaly}: \to \mathbf{ACCEPT}$ (Reason: `robust_temporal_support_and_spatially_coherent`)
  - $OBS \ge 2 \land \text{SPATIAL\_ANOMALY}: \to \mathbf{FLAG}$ (Reason: `multi_observation_spatial_anomaly`)
  - $OBS = 1 \land (|\Delta_{\text{med}}| > 10.0^\circ\text{C} \lor \text{LOW\_SUPPORT\_SPATIAL\_EXTREME}): \to \mathbf{EXCLUDE}$ (Reason: `single_observation_severe_spatial_anomaly`)
  - $OBS = 1 \land \text{is\_boundary} \land valid\_neighbors < 4 \land |\Delta_{\text{med}}| \le 10.0^\circ\text{C}: \to \mathbf{FLAG}$ (Reason: `single_observation_boundary_context`)
  - $OBS = 1 \land |\Delta_{\text{med}}| \le 10.0^\circ\text{C}: \to \mathbf{FLAG}$ (Reason: `single_observation_spatially_coherent`)

---

## 5. Canonical Hotspot & Persistence Definitions

- **Implementation:** `gis/quality/hotspot_definitions.py`
- **Tiers (Normalized Seasonal Recurrence Frequency):**
  - `non_hotspot`: $hotspot\_frequency == 0.0$ ($N = 191,545$ in test holdout, 94.01%)
  - `active_hotspot`: $hotspot\_frequency > 0.0$ ($N = 12,213$ in test holdout, 5.99%)
  - `persistent_hotspot`: $hotspot\_frequency \ge 0.25 \lor is\_persistent\_hotspot$ ($N = 2,177$ in test holdout, 1.07%)
  - `chronic_hotspot`: $hotspot\_frequency \ge 0.50$ ($N = 405$ in test holdout, 0.20%)
- **Resolution:** Replaced outdated integer check `hotspot_frequency >= 6` with normalized float thresholds (`PERSISTENT = 0.25`, `CHRONIC = 0.50`).

---

## 6. Frozen Model Architecture & Hyperparameters

- **Model ID:** `xgb_tuned_policy_d_v1`
- **Architecture:** XGBoost `XGBRegressor` (`tree_method='hist'`)
- **Target Variable ($y$):** `LST_C` (100m ground resolution Land Surface Temperature in Celsius)
- **Predictor Features ($X$):**
  1. `NDVI` (Normalized Difference Vegetation Index)
  2. `NDBI` (Normalized Difference Built-up Index)
  3. `NDWI` (Normalized Difference Water Index)
  4. `LST_OBS_COUNT` (Clear-sky scene count per composite)
  5. `LST_QA_MEDIAN_K` (Radiometric surface temperature uncertainty in Kelvin from USGS Level-2 `ST_QA`)
- **Predictor Exclusions:** `latitude`, `longitude`, `row`, `col`, and spatial coordinates are strictly omitted.
- **Hyperparameters (Discovered in Development-Only Optuna Trial #25):**
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

---

## 7. Authoritative Performance Verification

### 7.1 Development 5-Fold Spatial Cross-Validation (132 Blocks / 720,973 rows)
- **Best Dev-CV RMSE:** $1.8478^\circ\text{C}$

### 7.2 Independent Spatial Holdout Evaluation (Untouched 33 Blocks / 203,758 rows, Evaluation Count = 1)
- **MAE:** **$1.2726^\circ\text{C}$**
- **RMSE:** **$1.7524^\circ\text{C}$**
- **$R^2$:** **$0.9006$**
- **Training Time:** 37.74 s (on 720,973 development rows)
- **Inference Latency:** 1.093 s (for 203,758 test rows)

### 7.3 Seasonal Holdout Breakdown
| Season | Samples ($N$) | Pct (%) | MAE ($^\circ\text{C}$) | RMSE ($^\circ\text{C}$) | $R^2$ | Mean Bias ($^\circ\text{C}$) |
|---|---|---|---|---|---|---|
| **Winter** | 54,930 | 26.96% | 0.9139 | 1.2136 | 0.6512 | +0.0032 |
| **Summer** | 54,930 | 26.96% | 1.3734 | 1.7944 | 0.7119 | -0.1916 |
| **Monsoon** | 49,954 | 24.52% | 1.8024 | 2.4353 | 0.7718 | +0.0866 |
| **Post-Monsoon** | 43,944 | 21.57% | 0.9926 | 1.2772 | 0.7855 | -0.1047 |

### 7.4 Hotspot Tier Breakdown
| Hotspot Tier | Samples ($N$) | Pct (%) | MAE ($^\circ\text{C}$) | RMSE ($^\circ\text{C}$) | $R^2$ | Mean Bias ($^\circ\text{C}$) |
|---|---|---|---|---|---|---|
| **Non-Hotspot** ($freq == 0.0$) | 191,545 | 94.01% | 1.2251 | 1.6715 | 0.9076 | +0.0165 |
| **Active Hotspot** ($freq > 0.0$) | 12,213 | 5.99% | 2.0170 | 2.7228 | 0.7809 | -1.1281 |
| **Persistent Hotspot** ($freq \ge 0.25$) | 2,177 | 1.07% | 3.0959 | 3.9896 | 0.4941 | -1.3041 |
| **Chronic Hotspot** ($freq \ge 0.50$) | 405 | 0.20% | 3.9077 | 4.8413 | 0.2118 | -1.5264 |

---

## 8. Feature Ablation & SHAP Attribution Summary

### 8.1 Systematic Feature Ablation (Strict 132-Dev / 33-Test Split)
| Configuration | Predictors | Dev CV RMSE ($^\circ\text{C}$) | Holdout RMSE ($^\circ\text{C}$) | Holdout $R^2$ |
|---|---|---|---|---|
| `A_physical_only` | `NDVI+NDBI+NDWI` | $5.1455 \pm 0.1085$ | 4.9967 | 0.1915 |
| `B_physical_temporal` | `NDVI+NDBI+NDWI+LST_OBS_COUNT` | $4.0787 \pm 0.1022$ | 3.9709 | 0.4894 |
| `C_physical_qa` | `NDVI+NDBI+NDWI+LST_QA_MEDIAN_K` | $2.1420 \pm 0.0929$ | 2.0518 | 0.8637 |
| **`D_full`** | `NDVI+NDBI+NDWI+LST_OBS_COUNT+LST_QA_MEDIAN_K` | **$1.8224 \pm 0.0619$** | **1.7524** | **0.9006** |

### 8.2 Seasonal Mean Absolute SHAP Attributions (|SHAP| $^\circ\text{C}$)
| Season | `LST_QA_MEDIAN_K` | `LST_OBS_COUNT` | `NDBI` | `NDWI` | `NDVI` |
|---|---|---|---|---|---|
| **Overall** | 2.9800 | 1.2879 | 1.3867 | 0.6981 | 0.5347 |
| **Winter** | 4.7802 | 1.2379 | 1.1056 | 0.7026 | 0.4461 |
| **Summer** | 4.4230 | 0.5449 | 1.5739 | 0.7442 | 0.5028 |
| **Monsoon** | 1.1709 | 2.5202 | 1.5900 | 0.7828 | 0.7365 |
| **Post-Monsoon** | 1.0171 | 0.7262 | 1.1810 | 0.5139 | 0.5030 |

---

## 9. Known Physical & Sensor Limitations

1. **Analytical Scale (~100m):**
   Landsat 8/9 Band 10 thermal observations possess an analytical scale of ~100m. Micro-urban features (single tree crowns, individual small rooftops) are radiometrically integrated into cell-average radiance. Downstream candidate generation operates at 100m scale.
2. **Elevated Prediction Error in Chronic Hotspots:**
   In chronic industrial hotspots ($freq \ge 0.50$), prediction RMSE rises to $4.8413^\circ\text{C}$, with mean negative bias of $-1.5264^\circ\text{C}$ (under-prediction of extreme rooftop skin radiance due to 100m sub-pixel thermal heterogeneity). Downstream Heat Priority MUST maintain observed LST as primary evidence rather than substituting ML predictions.
3. **Partial 2026 Monsoon Observation Record:**
   The 2026 monsoon period represents partial satellite acquisitions.
4. **Non-Causal Interpretative Nature of Features:**
   `LST_QA_MEDIAN_K` provides retrieval-quality and atmospheric context. It is not a physical driver of surface heating.

---

## 10. Software & Environment Stack

- **Operating System:** Windows 11 (AMD64)
- **Python Version:** 3.12.10
- **XGBoost:** 3.4.1
- **Scikit-Learn:** 1.9.1
- **Optuna:** 5.0.0
- **SHAP:** 0.52.0
- **NumPy / Pandas:** 2.4.3 / 3.0.1
