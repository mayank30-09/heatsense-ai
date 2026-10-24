# HEATSENSE AI
# Machine Learning / Quality-Control Freeze Record

**Document Version:** 1.0-FROZEN
**Target Area:** Surat Municipal Corporation (SMC), Gujarat, India (EPSG:4326 / EPSG:32643)
**Date:** September 2026
**Status:** **FROZEN**

---

## 1. Freeze Status

The HEATSENSE AI Machine Learning and Quality-Control pipeline is **FROZEN**.
All scientific gates, including independent spatial block holdout isolation, development-only Optuna hyperparameter optimization, test holdout evaluation protocol, automated leakage rejection tests, and cryptographic checksum generation, have passed with zero failures.

---

## 2. Repository Commit

- **Branch:** `feature/scientific-freeze-correction`
- **Git Commit:** `c91bc69038d1796c568772a5bce9fba900be7e96`
- **Working Tree:** Verified clean and passing `git diff --check`.

---

## 3. Dataset

- **Dataset Identifier:** Policy D Analysis Dataset
- **File Path:** `data/processed/sensitivity/policy_d/analysis.parquet`
- **Total Validated Rows:** 924,731
- **Spatial Blocks:** 165 blocks (each 2 km × 2 km tile across Surat)
- **Target Variable:** `LST_C` (Landsat Collection 2 Level-2 Surface Temperature, °C)
- **Non-Finite Target Count:** 0
- **Null Counts:** 0 nulls across target, features, quality flags, and eligibility columns.
- **Seasonal Distribution:**
  - Winter: 248,735 rows
  - Summer: 248,735 rows
  - Monsoon: 228,273 rows
  - Post-Monsoon: 198,988 rows
- **Temporal Span:** 2022–2026

---

## 4. Quality Policy

- **Policy ID:** `Policy D`
- **Specification:** `config/quality_policy_d.yaml`
- **Implementation:** `gis/quality/eligibility.py` (`evaluate_policy_d`)
- **Philosophy:** Spatially coherent, physically bounded pixel eligibility.
- **Screening Rules:**
  - Neighborhood: $3 \times 3$ matrix (minimum 4 valid neighbors required for interior unflagged evaluation).
  - Spatial Anomaly Threshold: $|\Delta_{\text{med}}| = 10.0^\circ\text{C}$ relative to neighborhood median.
  - Multi-observation pixels ($OBS \ge 2$) with coherent spatial neighborhood: ACCEPT (Weight 1.0).
  - Multi-observation pixels with spatial anomaly: FLAG (Weight 0.5).
  - Single-observation pixels ($OBS = 1$) with coherent spatial neighborhood: FLAG (Weight 0.5).
  - Single-observation severe spatial anomalies ($OBS = 1 \land |\Delta_{\text{med}}| > 10.0^\circ\text{C}$): EXCLUDE.
  - Zero-observation pixels ($OBS < 1$) or non-finite values: EXCLUDE.
- **Retention Rate:** 99.99% (924,731 of 924,854 rows retained; exactly 123 severe unphysical artifacts purged).

---

## 5. Feature Schema

- **Artifact:** `artifacts/ml_freeze/feature_schema.json` (SHA-256: `e7c94e8c4a527a13d7b9538d491c8e27125fb5a1c245b565df2d390113c2c7e5`)
- **Target:** `LST_C`
- **Canonical Feature List:**
  1. `NDVI`: Normalized Difference Vegetation Index (surface greenness)
  2. `NDBI`: Normalized Difference Built-Up Index (built density/impervious surface)
  3. `NDWI`: Normalized Difference Water Index (surface water/moisture)
  4. `LST_OBS_COUNT`: Clear-sky seasonal observation count (temporal support)
  5. `LST_QA_MEDIAN_K`: Landsat Level-2 radiometric uncertainty / atmospheric retrieval context (Kelvin)
- **Feature Order Locked:** Yes
- **Coordinate Columns Excluded:** Yes (`latitude`, `longitude`, `row`, `col`, `x`, `y` are strictly prohibited).

---

## 6. Spatial Validation Design

Spatial validation is designed to prevent spatial autocorrelation leakage between adjacent pixels.
- The entire Surat domain is divided into 165 discrete, non-overlapping $2\text{ km} \times 2\text{ km}$ spatial blocks (`block_id`).
- All validation, partitioning, and cross-validation operations operate strictly at the block level rather than pixel level.

---

## 7. Development/Test Split

- **Artifact:** `artifacts/ml_freeze/holdout_split.json` (SHA-256: `8a04b20c97b088ffc7d3f513ecd3e41007adea51ad16401f104529f40d8c1a2d`)
- **Total Blocks:** 165
- **Split Ratio:** 80% Development / 20% Test
- **Random State:** 42
- **Development Partition:** 132 blocks (720,973 rows, 77.97% of dataset)
- **Locked Test Partition:** 33 blocks (203,758 rows, 22.03% of dataset)
- **Disjointness:** $\text{Development} \cap \text{Test} = \emptyset$ (strictly verified)
- **Conservation:** $\text{Development} \cup \text{Test} = \text{All 165 Blocks}$

---

## 8. Development Cross-Validation

- **Implementation:** `gis/ml/development_cv.py` (`development_spatial_folds`)
- **Artifact:** `artifacts/ml_freeze/tuning/spatial_fold_definition.json` (SHA-256: `6836471bc503e7c9aeadcbf86907f1a10baa8def6607925cb27c0b0bf84b3418`)
- **Folds:** 5 spatial folds.
- **Population:** 132 development blocks only.
- **Properties:**
  - In every fold: $\text{Train} \cap \text{Validation} = \emptyset$.
  - In every fold: $\text{Train} \cup \text{Validation} = \text{132 Development Blocks}$.
  - Test blocks never enter fold generation ($\text{Test} \cap \text{Train} = \emptyset$, $\text{Test} \cap \text{Validation} = \emptyset$).

---

## 9. Hyperparameter Optimization

- **Script:** `scripts/tune_xgb.py`
- **Search Engine:** Optuna TPE (Tree-structured Parzen Estimator)
- **Optimization Metric:** 5-fold spatial cross-validation RMSE across 132 development blocks.
- **Input Data:** `development_df` only ($N = 720,973$ rows; test blocks structurally excluded).
- **Search Budget:** 30 trials (`random_state=42`).
- **Best Trial:** Trial #25
- **Best Development CV RMSE:** **1.8478 °C**
- **Discovered Best Hyperparameters:**
  - `n_estimators`: 900
  - `max_depth`: 9
  - `learning_rate`: 0.03662937937931856
  - `min_child_weight`: 3.253330265581497
  - `subsample`: 0.6539539403049981
  - `colsample_bytree`: 0.6285481356546664
  - `gamma`: 1.2827623793054954
  - `reg_alpha`: 6.448517630611331e-06
  - `reg_lambda`: 12.086733674708716
- **Artifacts:**
  - `artifacts/ml_freeze/tuning/best_params.json` (SHA-256: `0ca76e50933d35783596274467247dfa5936678ada0ef7dd7e8003c827026512`)
  - `artifacts/ml_freeze/tuning/study_summary.json` (SHA-256: `664d9710d4c99bb8897c0c6adde6e75aadf3f09495c8c824e905876130dc6564`)
  - `artifacts/ml_freeze/tuning/trial_results.csv` (SHA-256: `9cfea58f72e805c6c3abe09fdbd6b5fdaaff31475dfdedd1daa1426baf149a11`)

---

## 10. Final Model Training

- **Algorithm:** `xgboost.XGBRegressor` (`tree_method='hist'`)
- **Training Population:** All 132 development blocks (720,973 rows)
- **Training Duration:** 37.74 seconds on CPU
- **Test Exposure During Training:** 0 rows (strictly verified)
- **Model Artifacts:**
  - Native JSON: `artifacts/ml_freeze/xgb_tuned_policy_d.json` (SHA-256: `8c4aad26e2a56867e327aeae0cd758f9b2b1105bf8d35c0ec8f6774f4ef38377`)
  - Joblib Bundle: `artifacts/ml_freeze/xgb_tuned_policy_d.joblib` (SHA-256: `e1aedd4946b1b29823bdea66ea3ec7b9ba5f20c4ddbfdf6920c2e62e6b30b7c9`)

---

## 11. Independent Holdout Evaluation

- **Script:** `scripts/final_holdout_evaluation.py`
- **Evaluation Count:** **1 (Exactly Once)**
- **Test Set Population:** 33 locked test blocks (203,758 rows)
- **Test Evaluation Latency:** 1.093 seconds for 203,758 rows (equivalent to ~5.36 s per million rows under linear extrapolation). Dedicated benchmarks on 924,731 rows measured Random Forest at 2.1132 s and XGBoost at 6.5477 s.
- **Evaluation Manifest:** `artifacts/ml_freeze/evaluation_manifest.json` (SHA-256: `0ca65f2e840f3a73a9c7ea6bee7c2c985925886704c31167d22d4d7e28011b0b`)

---

## 12. Overall Test Metrics

Measured on the 33 locked test blocks ($N = 203,758$):

| Metric | Measured Value | Unit |
|:---|---:|:---|
| **Mean Absolute Error (MAE)** | **1.2726** | °C |
| **Root Mean Squared Error (RMSE)** | **1.7524** | °C |
| **Coefficient of Determination ($R^2$)** | **0.9006** | — |
| **Mean Bias** | **-0.0520** | °C |

*Note: Historical development re-evaluation figures (1.7840 °C RMSE / 0.9033 $R^2$) represent cross-validation results across all folds, whereas 1.7524 °C RMSE is the true independent holdout generalization.*

---

## 13. Seasonal Test Metrics

- **Artifact:** `artifacts/ml_freeze/holdout_season_performance.csv` (SHA-256: `1158e56ba4e1a22cd44e6d92d614cc635db20be06415e902db99807cdf5291af`)

| Season | Samples ($N$) | Share (%) | MAE (°C) | RMSE (°C) | $R^2$ | Mean Bias (°C) |
|:---|---:|---:|---:|---:|---:|---:|
| **Winter** | 54,930 | 26.96% | 0.9139 | 1.2136 | 0.6512 | +0.0032 |
| **Summer** | 54,930 | 26.96% | 1.3734 | 1.7944 | 0.7119 | -0.1916 |
| **Monsoon** | 49,954 | 24.52% | 1.8024 | 2.4353 | 0.7718 | +0.0866 |
| **Post-Monsoon** | 43,944 | 21.57% | 0.9926 | 1.2772 | 0.7855 | -0.1047 |

---

## 14. Hotspot Test Metrics

- **Artifact:** `artifacts/ml_freeze/holdout_hotspot_performance.csv` (SHA-256: `3990946de0616a2d4e20457278c09c6c39268aab59756dee72501bcb1097e539`)

| Hotspot Tier | Definition | Samples ($N$) | Share (%) | MAE (°C) | RMSE (°C) | $R^2$ | Mean Bias (°C) |
|:---|:---|---:|---:|---:|---:|---:|---:|
| **Non-Hotspot** | $f = 0.0$ | 191,545 | 94.01% | 1.2251 | 1.6715 | 0.9076 | +0.0165 |
| **Active Hotspot** | $f > 0.0$ | 12,213 | 5.99% | 2.0170 | 2.7228 | 0.7809 | -1.1281 |
| **Persistent Hotspot** | $f \ge 0.25$ or flag | 2,177 | 1.07% | 3.0959 | 3.9896 | 0.4941 | -1.3041 |
| **Chronic Hotspot** | $f \ge 0.50$ | 405 | 0.20% | 3.9077 | 4.8413 | 0.2118 | -1.5264 |

---

## 15. Spatial Residual Diagnostics

- **Artifact:** `artifacts/ml_freeze/holdout_spatial_residuals.geojson` (SHA-256: `4b4d3d59e2f0c2b27e479f157d355d745bcb65c49c61aac077ffd5179cc27327`)
- **Observed Residual Pattern:**
  - Predictions across residential, agricultural, and mixed commercial areas exhibit low errors (RMSE $\approx 1.2\text{--}1.7^\circ\text{C}$).
  - In chronic industrial hotspots, the model exhibits an under-prediction bias (mean bias $-1.5264^\circ\text{C}$).
- **Scientific Interpretation:**
  - Under-prediction is consistent with sub-pixel thermal heterogeneity. The ~100m native thermal resolution of Landsat integrates high-radiance industrial metal roofs with cooler surrounding gaps and shadow.
  - The model fits the spatial-statistical mean, dampening localized extremes.
- **Architectural Guardrail:**
  - **Observed satellite LST is mandated as Primary Thermal Evidence.** Downstream Heat Priority calculations directly utilize observed composited LST, while ML predictions are utilized strictly for counterfactual scenarios and supplementary evidence.

---

## 16. Scientific Interpretation

1. **Retrieval-Quality Context (`LST_QA_MEDIAN_K`):**
   `LST_QA_MEDIAN_K` is the seasonal median of the per-scene Landsat ST_QA uncertainty indicator, expressed in Kelvin (not the formal uncertainty of the seasonal median LST composite). It provides a strong retrieval-quality and atmospheric-retrieval context signal that improves predictive performance in the evaluated feature configurations. Its predictive contribution must not be interpreted as physical causation.
2. **SHAP Attribution (Non-Causal):**
   SHAP values quantify numerical feature attribution within the fitted decision-tree ensembles, not physical causality. Under monsoon conditions, `LST_OBS_COUNT` becomes the most influential predictor ($2.5202^\circ\text{C}$ mean absolute attribution), indicating that temporal observation support becomes particularly informative under cloud-restricted conditions. This is a model-attribution result, not evidence of physical causation.
3. **Inference Latency & Model Comparison Benchmark:**
   In dedicated CPU batch inference benchmarks on 924,731 rows, Random Forest achieved lower latency (2.1132 s) than XGBoost (6.5477 s). Separately, the final holdout evaluation required approximately 1.093 s for 203,758 rows, equivalent to approximately 5.36 s per million rows under linear extrapolation. Random Forest demonstrates faster measured CPU inference. On development CV, RF (1.8024) was slightly better than default XGBoost (1.8280); tuned frozen XGBoost reported 1.8478 in its own tuning study (different folds, not directly comparable); XGBoost was retained for the tuned workflow and holdout evaluation; RF was not evaluated on holdout.
4. **Feature Ablation:**
   Physical-only predictors (`NDVI+NDBI+NDWI`, Config A) retain coarse spatial structure ($R^2 = 0.1915, \text{RMSE} = 4.9967^\circ\text{C}$ on holdout), but performance improves substantially when observation count and retrieval quality context are incorporated. Config D ($R^2 = 0.9006, \text{RMSE} = 1.7524^\circ\text{C}$) provides the best observed predictive performance and is retained as the operational configuration.

---

## 17. Implementation Blockers and Known Limitations

### Remaining Implementation Blockers

**None.** All implementation gates, data pipelines, regression suites, and production COG validations have completed and passed without blocking defects.

### Known Scientific Limitations

1. **Approximately 100 m Analytical Thermal Footprint:**
   Landsat Collection 2 Level-2 Band 10 thermal radiometer data has an acquisition resolution of ~100m (resampled to 30m, aggregated to 100m analytical grid cells). Micro-scale urban features (individual trees, cool roofs, narrow road corridors) are radiometrically integrated into cell-average brightness temperature.
2. **Partial 2026 Temporal Coverage:**
   The year 2026 is temporally incomplete; 2026 post-monsoon is not represented because that seasonal period had not occurred at generation time. The year 2026 must not be interpreted as a complete annual climatological representation. Spatial holdout evaluation must not be conflated with future-year forecasting holdout ($\text{spatial holdout} \neq \text{future-year holdout}$).
3. **Reduced Predictive Performance in Persistent/Chronic Hotspots:**
   Predictive error increases for recurrent/chronic hotspot classes (holdout RMSE increases from $1.6715^\circ\text{C}$ for non-hotspots to $4.8413^\circ\text{C}$ for chronic hotspots). The observed cold bias is consistent with sub-pixel thermal heterogeneity within the ~100m thermal footprint. For downstream analysis, **observed LST remains the authoritative primary thermal evidence**. Model predictions provide supplementary predictive and error-context information.
4. **No Future-Year Forecasting Validation:**
   The evaluation protocol uses 33 previously locked spatial blocks to measure spatial generalization within the sampled temporal distribution; it does not validate multi-year future forecasting accuracy.
5. **No Cross-City Transfer Validation:**
   Parameters and relationships are calibrated specifically to the coastal urban regime of Surat, Gujarat, India; generalization to other cities or climatic regimes is unvalidated and requires local retraining.
6. **No Direct Intervention Cooling Inference:**
   The regression model evaluates observational correlations and associations between land-cover indices and surface temperature. It does not establish direct mechanistic or causal cooling effects of physical urban interventions.

---

## 18. Scientific Boundaries: Established vs. Not Established

### Established Findings
- **Independent Spatial Generalization:** High spatial predictive accuracy across 33 previously locked spatial blocks withheld from all model tuning and selection (MAE = 1.2726°C, RMSE = 1.7524°C, $R^2$ = 0.9006).
- **Seasonal Variation in Predictive Error:** Distinct seasonal error patterns, with winter/post-monsoon showing lowest errors (RMSE ~1.21–1.28°C) and monsoon showing highest error (RMSE = 2.4353°C).
- **Elevated Hotspot Class Errors:** Systematic escalation in predictive error with multi-season recurrence, consistent with sub-pixel thermal heterogeneity in dense industrial zones.
- **Predictive Value of Retrieval-Quality Variables:** Ingestion of temporal clear-sky support (`LST_OBS_COUNT`) and radiometric retrieval quality (`LST_QA_MEDIAN_K`) substantially improves predictive performance across spatial cross-validation.
- **Observed Satellite LST as Primary Thermal Evidence:** Invariant architectural rule establishing observed satellite measurements as the authoritative thermal evidence for all downstream decision-support workflows.

### Not Established
- **Causal Effects of Spectral Indices or QA on LST:** SHAP attributions and regression weights reflect model associations, not physical causation.
- **Future-Year Forecasting Accuracy:** Spatial holdout performance does not establish predictive skill on future unobserved years.
- **Cross-City Transferability:** Model transferability to urban areas outside Surat is not established.
- **Sub-100 m Industrial Rooftop Temperatures:** Fine-scale rooftop radiance cannot be directly inferred from the 100m analytical footprint.
- **Intervention Cooling Effects from Regression Alone:** Land-cover cooling effects cannot be causally deduced from the observational regression model alone.

---

## 18. Leakage Controls

- **Zero Partition Overlap:** $\text{Development} \cap \text{Test} = \emptyset$.
- **Structural Optuna Isolation:** `run_tuning(development_df=..., folds=...)` structurally rejects test rows.
- **Code-Level Assertions:** Explicit runtime assertions (`assert development_blocks.isdisjoint(test_blocks)`) enforced at all pipeline stages.
- **Evaluation Gate:** Test blocks evaluated once on the frozen model after final parameter selection and training on development data (preliminary tuning studies conducted before the holdout split existed used all 165 blocks; `evaluation_count: 1` is recorded by `scripts/final_holdout_evaluation.py`).
- **Automated Regression Suite:** 10 leakage and protocol unit tests in `backend/tests/test_holdout_protocol.py` verify isolation before any training.

---

## 19. Automated Test Results

- **Artifact:** `artifacts/ml_freeze/test_results.json` (SHA-256: `a4fe0b3e2c3ed59de5dafdbc7b9867bafd018f603b17cad3f40597c5bc0a80c1`)
- **Pytest Command:** `.venv\Scripts\pytest.exe backend/tests -q`
  - Exit Code: `0`
  - Tests Passed: `98`
  - Tests Failed: `0`
  - Warnings: `24` (rasterio deprecation notices)
- **Compile Command:** `.venv\Scripts\python.exe -m compileall gis backend scripts`
  - Exit Code: `0`
- **Code Formatting & Git Diff:** `git diff --check` passed with exit code `0`.
- **Frontend Build:** `npm run build` passed with exit code `0`.

---

## 20. Artifact Hashes

Authoritative SHA-256 cryptographic digests persisted in `artifacts/ml_freeze/checksums.sha256`:

| Artifact | File Path | SHA-256 Hex Digest |
|---|---|---|
| **Pre-Implementation Audit** | `artifacts/ml_freeze/pre_implementation_audit.json` | `d22623275bbab2c62c28125f8270534b832a6621e852243f970fd500bd35d0bb` |
| **Dataset Validation** | `artifacts/ml_freeze/dataset_validation.json` | `1b20895a2e1d020c80b8daef1652cf21e7b060e22ff507abb9b480fa70366d63` |
| **Quality Policy Spec** | `config/quality_policy_d.yaml` | `5f122e6104cc2772de1d6fc6daef64de170b68d4ed74d2a8e8182144b4c21363` |
| **Authoritative Dataset** | `data/processed/sensitivity/policy_d/analysis.parquet` | `e824794e5ba2e26937ac40f55f5fd788adad70b1a6b23c6ab435b08223dd9997` |
| **Locked Spatial Holdout** | `artifacts/ml_freeze/holdout_split.json` | `8a04b20c97b088ffc7d3f513ecd3e41007adea51ad16401f104529f40d8c1a2d` |
| **Spatial 5-Fold Map** | `artifacts/ml_freeze/tuning/spatial_fold_definition.json` | `6836471bc503e7c9aeadcbf86907f1a10baa8def6607925cb27c0b0bf84b3418` |
| **Best Hyperparameters** | `artifacts/ml_freeze/tuning/best_params.json` | `0ca76e50933d35783596274467247dfa5936678ada0ef7dd7e8003c827026512` |
| **Study Summary** | `artifacts/ml_freeze/tuning/study_summary.json` | `664d9710d4c99bb8897c0c6adde6e75aadf3f09495c8c824e905876130dc6564` |
| **Trial Results** | `artifacts/ml_freeze/tuning/trial_results.csv` | `9cfea58f72e805c6c3abe09fdbd6b5fdaaff31475dfdedd1daa1426baf149a11` |
| **Locked Feature Schema** | `artifacts/ml_freeze/feature_schema.json` | `e7c94e8c4a527a13d7b9538d491c8e27125fb5a1c245b565df2d390113c2c7e5` |
| **Model Metadata** | `artifacts/ml_freeze/model_metadata.json` | `ee51f60ab3b956b1a4294d9cebb495069c8ba5fd5e7ed1a937bafc13778a2b15` |
| **Final Candidate Model (JSON)** | `artifacts/ml_freeze/xgb_tuned_policy_d.json` | `8c4aad26e2a56867e327aeae0cd758f9b2b1105bf8d35c0ec8f6774f4ef38377` |
| **Final Candidate Model (Joblib)** | `artifacts/ml_freeze/xgb_tuned_policy_d.joblib` | `e1aedd4946b1b29823bdea66ea3ec7b9ba5f20c4ddbfdf6920c2e62e6b30b7c9` |
| **Final Holdout Performance** | `artifacts/ml_freeze/holdout_performance.json` | `93db2435970ea68b0e18c61abeebb0622a793a6026770973a534efd70a29ac3a` |
| **Holdout Seasonal Metrics** | `artifacts/ml_freeze/holdout_season_performance.csv` | `1158e56ba4e1a22cd44e6d92d614cc635db20be06415e902db99807cdf5291af` |
| **Holdout Hotspot Metrics** | `artifacts/ml_freeze/holdout_hotspot_performance.csv` | `3990946de0616a2d4e20457278c09c6c39268aab59756dee72501bcb1097e539` |
| **Holdout Spatial Residuals** | `artifacts/ml_freeze/holdout_spatial_residuals.geojson` | `4b4d3d59e2f0c2b27e479f157d355d745bcb65c49c61aac077ffd5179cc27327` |
| **Evaluation Manifest** | `artifacts/ml_freeze/evaluation_manifest.json` | `0ca65f2e840f3a73a9c7ea6bee7c2c985925886704c31167d22d4d7e28011b0b` |
| **QC Summary** | `artifacts/ml_freeze/qc_summary.json` | `387a1725ece353ffb095faa2de34aa7fa5fc48ef3454a020e0a7ec2bd13c5e50` |
| **Test Results** | `artifacts/ml_freeze/test_results.json` | `a4fe0b3e2c3ed59de5dafdbc7b9867bafd018f603b17cad3f40597c5bc0a80c1` |
| **Production COG Validation** | `artifacts/ml_freeze/production_cog_validation.json` | `07ce6181fab7b97a9188cf44c7e0130fae7541989697f4faa795ec6b69291ecf` |

---

## 21. Reproducibility Information

- **Operating System:** Windows 11 (AMD64)
- **Python Version:** 3.12.10
- **Key Libraries:**
  - `xgboost`: 3.4.1
  - `scikit-learn`: 1.9.1
  - `pandas`: 3.0.6
  - `numpy`: 2.5.3
  - `optuna`: 5.0.0
- **Deterministic Verification:** Executed holdout partitioning twice independently; partitions A and B are bitwise identical ($132/33$ blocks).

---

## 24. Freeze Decision

```text
ML METHODOLOGY:
FROZEN

ML/QC ARTIFACTS:
FROZEN

SCIENTIFIC DOCUMENTATION:
FROZEN

PRODUCTION ANALYTICAL COGs:
COMPLETE

HEATSENSE AI DOWNSTREAM DECISION-SUPPORT:
NOT STARTED
```

All conditions of the Scientific Freeze Gate are satisfied:
1. Repository audited and baseline recorded.
2. Dataset verified (924,731 rows, 165 blocks, 0 nonfinite targets).
3. Locked development/test split generated (132 dev / 33 test).
4. Development/test overlap is 0.
5. All 165 blocks conserved.
6. 5-fold CV uses development blocks only.
7. Test blocks strictly excluded from Optuna, feature selection, and model training.
8. Test holdout evaluation on locked blocks executed.
9. Scientific language audited and causal interpretations corrected.
10. All automated unit and regression tests passing.
11. Cryptographic SHA-256 hashes generated and verified.
12. All 19 production analytical COGs verified for 10-band structure and canonical hotspot persistence.
13. Observed satellite LST mandated as Primary Thermal Evidence.
14. No downstream Heat Priority, Candidate Generation, or Optimization implemented.
