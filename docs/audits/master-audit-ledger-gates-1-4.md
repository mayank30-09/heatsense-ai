# HEATSENSE AI — MASTER AUDIT LEDGER (GATES 1–4)

**Target System:** HEATSENSE AI — Urban Heat Mitigation Decision Support Platform  
**Target Region:** Surat Municipal Corporation (SMC), Gujarat, India  
**Scope:** Pre-Heat-Priority Audit (Stage A & Stage B Implementation & Release Verification)  
**Evaluator:** Senior Software Architect, GIS/Remote-Sensing Engineer & ML Validation Specialist  
**Status Date:** 2026-10-04  

---

## 1. Summary of Gate Outcomes

| Gate | Description | Items | PASS | FAIL | PARTIAL | BLOCKED | Final Gate Status |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Gate 1** | Repository Baseline & Artifact Protection | 4 | 4 | 0 | 0 | 0 | **PASS** |
| **Gate 2** | Stage A: Data Acquisition, GIS, Raster Semantics & Policy D | 9 | 9 | 0 | 0 | 0 | **PASS** |
| **Gate 3** | Stage B: Splits, Models, Metrics, SHAP & Optical Sentinel Sensitivity | 8 | 8 | 0 | 0 | 0 | **PASS** |
| **Gate 4 (Historical)** | Integration & Regression (Docker Service Stopped) | 6 | 5 | 0 | 0 | 1 | **PASS WITH INFRASTRUCTURE QUALIFICATION** |
| **Gate 4 (Reconciled)** | Integration & Regression (PostGIS Recovered on Port 5433) | 6 | 6 | 0 | 0 | 0 | **PASS (READY FOR SIGN-OFF)** |
| **TOTAL (Current)** | All Evaluated Architectural Requirements | **27** | **27** | **0** | **0** | **0** | **PASS (READY FOR SIGN-OFF)** |

*Historical vs Current Note:* In the initial run, `test_resolve_area_name_postgis_contains` was blocked because the Docker Desktop engine was stopped. Upon engine recovery, the intended `heatsense-postgis` container on port 5433 became healthy. The full test suite was independently re-executed: **114 passed, 0 failed, 0 skipped**.

---

## 2. Protected Artifact Baseline Ledger (Gate 1)

| Artifact Name | Path | Canonical Expected SHA-256 | Verified SHA-256 | Status |
|---|---|---|---|:---:|
| Tuned Operational Model | `artifacts/ml_freeze/xgb_tuned_policy_d.joblib` | `e1aedd4946b1b29823bdea66ea3ec7b9ba5f20c4ddbfdf6920c2e62e6b30b7c9` | `e1aedd4946b1b29823bdea66ea3ec7b9ba5f20c4ddbfdf6920c2e62e6b30b7c9` | **PASS** |
| Policy D Analysis Dataset | `data/processed/sensitivity/policy_d/analysis.parquet` | `e824794e5ba2e26937ac40f55f5fd788adad70b1a6b23c6ab435b08223dd9997` | `e824794e5ba2e26937ac40f55f5fd788adad70b1a6b23c6ab435b08223dd9997` | **PASS** |
| Locked Spatial Holdout Split | `artifacts/ml_freeze/holdout_split.json` | `8a04b20c97b088ffc7d3f513ecd3e41007adea51ad16401f104529f40d8c1a2d` | `8a04b20c97b088ffc7d3f513ecd3e41007adea51ad16401f104529f40d8c1a2d` | **PASS** |
| All 41 Frozen Artifacts | `artifacts/ml_freeze/checksums.sha256` | 41 registered files match checksum manifest | 41 matches, 0 mismatches | **PASS** |

---

## 3. Persistent Requirement Audit Ledger

### Gate 1: Repository Baseline and Artifact Protection

- **REQ-G1-01: Immutable Frozen Core ML Artifact Protection**
  - **Path & Function:** `artifacts/ml_freeze/{xgb_tuned_policy_d.joblib, holdout_split.json}`, `data/processed/sensitivity/policy_d/analysis.parquet`
  - **Reproduction Command:** `.venv/Scripts/python.exe -c "import hashlib; [print(p, hashlib.sha256(open(p, 'rb').read()).hexdigest()) for p in ['artifacts/ml_freeze/xgb_tuned_policy_d.joblib', 'data/processed/sensitivity/policy_d/analysis.parquet', 'artifacts/ml_freeze/holdout_split.json']]"`
  - **Status:** PASS
  - **Severity:** P0 (Release Blocker if failed)
  - **Evidence:** All 3 files present on disk; SHA-256 match expected 64-char hashes exactly.
  - **Remaining Limitations:** None. Artifacts remain immutable.

- **REQ-G1-02: Complete Checksum Manifest Verification (41 Artifacts)**
  - **Path & Function:** `artifacts/ml_freeze/checksums.sha256`
  - **Reproduction Command:** `.venv/Scripts/python.exe -c "import hashlib, pathlib; [hashlib.sha256(open(line.split()[1], 'rb').read()).hexdigest() == line.split()[0] for line in open('artifacts/ml_freeze/checksums.sha256') if line.strip()]"`
  - **Status:** PASS
  - **Severity:** P0
  - **Evidence:** 41/41 files verified on disk with 0 hash discrepancies.
  - **Remaining Limitations:** None.

- **REQ-G1-03: Execution Environment & Dependency Alignment**
  - **Path & Function:** `.venv` runtime packages
  - **Reproduction Command:** `.venv/Scripts/python.exe -c "import sys, sklearn, xgboost, shap, pandas, numpy, geopandas, rasterio; print(sys.version, sklearn.__version__, xgboost.__version__, shap.__version__, pandas.__version__, numpy.__version__, geopandas.__version__, rasterio.__version__)"`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** Python 3.12.10, scikit-learn 1.9.1, xgboost 3.4.1, shap 0.52.0, pandas 3.0.6, numpy 2.5.3, geopandas 1.1.4, rasterio 1.5.1.
  - **Remaining Limitations:** None.

- **REQ-G1-04: Git Working Tree Preservation & Non-Destructive Operation**
  - **Path & Function:** Working directory `e:\FINAL YEAR PROJECT\heatsense-ai`
  - **Reproduction Command:** `git status --short`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** Zero untracked files discarded; no destructive git resets performed.
  - **Remaining Limitations:** None.

---

### Gate 2: Stage A: Data Acquisition, GIS, Raster Semantics & Policy D

- **REQ-G2-01: Landsat Collection 2 Tier-1 L2SP Source Validation & Scene Accounting**
  - **Path & Function:** `gis/gee/seasonal_features.py` (`build_landsat_collection`)
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_01`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** Landsat LC08 and LC09 Tier-1 Level-2 (L2SP) verified in GEE for Surat boundary. 329 retained scenes (162 L8, 167 L9) verified through 2026-06-01. 7 supplemental scenes identified in 2026 monsoon window documented separately.
  - **Remaining Limitations:** Post-monsoon 2026 absent by design as production freeze preceded acquisition window.

- **REQ-G2-02: Radiative Transfer LST Conversion Formula**
  - **Path & Function:** `gis/gee/landsat_lst.py` (`scale_lst`)
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_02`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** Evaluated against 50 randomly sampled production pixels: USGS scale factor (0.00341802) and offset (149.0 K) verified with Kelvin-to-Celsius conversion (-273.15). Maximum difference < 1e-5 °C. Phrasing strictly calibrated to USGS Collection 2 specification.
  - **Remaining Limitations:** None.

- **REQ-G2-03: QA Mask Bitwise Logic Verification**
  - **Path & Function:** `gis/gee/seasonal_features.py` (`create_seasonal_composite`)
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_02b`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** 100% of synthetic test cases for `QA_PIXEL` bits (0: fill, 1: dilated, 2: cirrus, 3: cloud, 4: shadow, 5: snow) and `QA_RADSAT == 0` pass. Designated "QA Mask Logic Validation".
  - **Remaining Limitations:** Logic tests bitwise filter operations, not external ground-truth imagery.

- **REQ-G2-04: Seasonal Boundaries and Temporal Window Definitions**
  - **Path & Function:** `gis/gee/seasonal_features.py` (`get_season_windows`)
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_03`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** Winter: Dec 1 (prior year) to Feb 28/29; Summer: Mar 1 to May 31; Monsoon: Jun 1 to Sep 30; Post-Monsoon: Oct 1 to Nov 30. Total 19 seasonal composites (2022–2026).
  - **Remaining Limitations:** None.

- **REQ-G2-05: Analytical Cloud-Optimized GeoTIFFs (COGs) Structural Integrity**
  - **Path & Function:** `data/processed/analytical/*.tif`, `gis/production/analytical_cog.py`
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_04`
  - **Status:** PASS
  - **Severity:** P0
  - **Evidence:** 19 COGs verified: EPSG:4326, 318x324 dimensions, 10 Float32 bands, tiled 256x256, 4 overviews (2, 4, 8, 16), NoData = -9999.0.
  - **Remaining Limitations:** None.

- **REQ-G2-06: COG Semantic Integrity & Hotspot Persistence Rules**
  - **Path & Function:** `gis/quality/hotspot_definitions.py` (`persistent_hotspot_mask`)
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_04b`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** Evaluated across all 19 COGs. Canonical rule `(frequency >= 0.25) or flag` verified with 0 differing pixels.
  - **Remaining Limitations:** None.

- **REQ-G2-07: Policy D Pixel Eligibility Decision Engine Reproduction & Non-Finite Guard**
  - **Path & Function:** `gis/quality/eligibility.py` (`evaluate_policy_d`, `evaluate_policy_a`, `evaluate_policy_b`, `evaluate_policy_c`)
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_05` & `.venv/Scripts/pytest.exe backend/tests/test_policy_d_spec.py`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** Evaluated on 50,000-row sample (0 mismatches) and vectorized full-dataset evaluation over 924,731 rows (0 mismatches). Identified and resolved an edge-case defect where non-finite `obs_count` (e.g. `NaN`, `Inf`) could bypass `< 1` comparisons and fall through to `ACCEPT` or `FLAG`; introduced `_is_invalid_or_zero_obs` helper to strictly enforce `EXCLUDE` for all non-finite observation counts. Added 2 regression tests in `backend/tests/test_policy_d_spec.py` covering boundary edges and non-finite values (all 4 tests passing).
  - **Remaining Limitations:** None.

- **REQ-G2-08: Extreme Pixel Quality Control (Cold Artifact vs Spatially Coherent Hot Extreme)**
  - **Path & Function:** `gis/quality/eligibility.py`, `artifacts/pre_heat_priority_validation/09_extreme_pixel_validation.json`
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_05b`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** 6.47 °C cold cloud-shadow artifact successfully purged from ACCEPT pool. Spatially coherent 70.23 °C observed LST extreme retained for downstream review without equating spatial coherence with physical ground truth.
  - **Remaining Limitations:** Downstream candidate generation must treat 70.23 °C pixel as observed radiometric extreme subject to microclimate verification.

- **REQ-G2-09: Authoritative Operational Dataset Validation & Feature Leakage Audit**
  - **Path & Function:** `data/processed/sensitivity/policy_d/analysis.parquet`
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_06`
  - **Status:** PASS
  - **Severity:** P0
  - **Evidence:** Exactly 924,731 rows, 165 spatial blocks. Target `LST_C` [6.47, 70.23] °C. Features: `NDVI`, `NDBI`, `NDWI`, `LST_OBS_COUNT`, `LST_QA_MEDIAN_K`. Coordinates (`x`, `y`, `longitude`, `latitude`, `block_id`) strictly excluded from feature matrix. 0 nulls, NaNs, or Infs in valid rows.
  - **Remaining Limitations:** None.

---

### Gate 3: Stage B: Splits, Models, Metrics, SHAP & Optical Sentinel Sensitivity

- **REQ-G3-01: Spatial Train/Test Block Partitioning**
  - **Path & Function:** `artifacts/ml_freeze/holdout_split.json`
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_07`
  - **Status:** PASS
  - **Severity:** P0
  - **Evidence:** 165 blocks partitioned into 132 development blocks (720,973 observations, 77.97%) and 33 locked test blocks (203,758 observations, 22.03%). Zero block overlap, zero coordinate overlap.
  - **Remaining Limitations:** None.

- **REQ-G3-02: 5-Fold Spatial CV & Optuna Hyperparameter Isolation**
  - **Path & Function:** `artifacts/ml_freeze/tuning/{spatial_fold_definition.json, study_summary.json, trial_results.csv}`
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_07b`
  - **Status:** PASS
  - **Severity:** P0
  - **Evidence:** 5 spatial folds defined strictly within 132 development blocks. All 30 Optuna trials executed strictly on development folds. Locked test set (33 blocks) isolated from tuning and cross-validation.
  - **Remaining Limitations:** None.

- **REQ-G3-03: Frozen Model Parameters & Locked Holdout Reproduction**
  - **Path & Function:** `artifacts/ml_freeze/xgb_tuned_policy_d.joblib`, `artifacts/final_holdout/holdout_performance.json`
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_08` & `run_gate_08b`
  - **Status:** PASS
  - **Severity:** P0
  - **Evidence:** Frozen hyperparameters: 900 estimators, max depth 9, learning rate 0.036629. Holdout reproduction on 203,758 rows matches authoritative targets exactly: MAE = 1.2726 °C, RMSE = 1.7524 °C, R² = 0.9006, Model Bias = -0.0521 °C, Residual Mean = +0.0521 °C (discrepancy < 1e-4).
  - **Remaining Limitations:** None.

- **REQ-G3-04: Seasonal Performance Reproduction**
  - **Path & Function:** `artifacts/ml_freeze/holdout_season_performance.csv`
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_09`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** Winter RMSE = 1.2136 °C, Summer RMSE = 1.7944 °C, Monsoon RMSE = 2.4353 °C, Post-Monsoon RMSE = 1.2772 °C. All reproduce targets exactly.
  - **Remaining Limitations:** Higher error during monsoon is physically expected due to cloud cover attenuation and sparser observations.

- **REQ-G3-05: Hotspot Error Stratification & RF Comparison Protocol**
  - **Path & Function:** `artifacts/ml_freeze/holdout_hotspot_performance.csv`
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_09b`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** Error escalates from Non-hotspot (RMSE 1.6715 °C) to Active (2.7228 °C), Persistent (3.9896 °C), and Chronic (4.8413 °C). Stale comparison claiming XGBoost beat RF removed; documentation explicitly notes RF development-CV RMSE (1.8024 °C) and XGBoost locked-test RMSE (1.7524 °C) use distinct protocols.
  - **Remaining Limitations:** Observed LST must remain primary thermal evidence; modeled LST must not replace observed LST.

- **REQ-G3-06: Residual Distribution & Bias Standardization**
  - **Path & Function:** `artifacts/ml_freeze/holdout_spatial_residuals.geojson`
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_09d`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** Standardized definitions: residual = observed - predicted (+0.0521 °C); model bias = predicted - observed (-0.0521 °C). Standard deviation = 1.7516 °C.
  - **Remaining Limitations:** Heteroscedasticity confirmed at extreme temperatures.

- **REQ-G3-07: SHAP Additivity Verification & Non-Causal Attribution Language**
  - **Path & Function:** `artifacts/pre_heat_priority_validation/18_shap_validation.json`
  - **Reproduction Command:** `verify_pre_heat_priority.py::run_gate_10`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** Local additivity verified: max |sum(phi) + base - margin| = 0.000107 <= 0.001. SHAP values confirmed as predictive attribution, not physical intervention causality.
  - **Remaining Limitations:** SHAP explanations must not be interpreted as physical cooling efficacy.

- **REQ-G3-08: Optical Sentinel (-9999.0) Sensitivity & Spatial Proximity Characterization (Issue 1)**
  - **Path & Function:** `scripts/analyze_optical_sentinel_spatial_proximity.py`, `scripts/analyze_optical_sentinel_local_effect.py`, `backend/tests/test_optical_sentinel_audit.py`
  - **Reproduction Command:** `.venv/Scripts/python.exe scripts/analyze_optical_sentinel_spatial_proximity.py` & `.venv/Scripts/pytest.exe backend/tests/test_optical_sentinel_audit.py -q`
  - **Status:** PASS
  - **Severity:** P0
  - **Evidence:**
    - 8 unique development observations contain -9999.0 optical values; locked test set contains 0.
    - Aggregate 5-fold spatial CV: MAE delta 0.0001 °C, RMSE delta 0.0001 °C, R² delta 0.0001.
    - Row-level local delta over 720,973 rows: P95 = 0.2494 °C, P99 = 0.4302 °C, Max = 4.9487 °C; 398 obs > 1.0 °C, 8 obs > 2.0 °C, 1 obs > 4.0 °C.
    - Proximity diagnostics: distance bins include `percentage`, `gt_1C_pct`, `gt_2C_pct`, `gt_4C_pct` with safe zero-observation handling.
    - Outcome designated **Outcome B: Observed Distributed Prediction Sensitivity**.
    - Unsupported claims of causal spatial propagation or tree split thresholds removed; evidence-calibrated wording applied.
    - 14 dedicated unit tests pass in `backend/tests/test_optical_sentinel_audit.py`.
  - **Remaining Limitations:** Sentinel values represent development-data quality limitation; production model and dataset remain unchanged.

---

### Gate 4: Integration, Regression Testing and Final Release Decision

- **REQ-G4-01: Non-Integration Backend Test Suite Execution**
  - **Path & Function:** `backend/tests`
  - **Reproduction Command:** `.venv/Scripts/pytest.exe backend/tests -m "not integration" -q`
  - **Status:** PASS
  - **Severity:** P0
  - **Evidence:** 112 passed, 2 deselected in 14.18s. 0 failures.
  - **Remaining Limitations:** None.

- **REQ-G4-02: Integration Test Execution & PostGIS Service Verification**
  - **Path & Function:** `backend/tests/test_analysis.py::test_resolve_area_name_postgis_contains`, `backend/tests/test_health.py::test_health_endpoint_requires_postgis`
  - **Reproduction Command:** `.venv/Scripts/pytest.exe backend/tests -m "integration" -v`
  - **Status:** PASS (Recovered from BLOCKED)
  - **Severity:** P0 (Release Requirement)
  - **Evidence:** 
    - Historical: Docker engine stopped; 1 skipped (`test_health`), 1 failed (`test_analysis`).
    - Recovered: Docker container `heatsense-postgis` verified running and healthy on port 5433 (`PostGIS 3.4`, 44 rows in `osm_places`).
    - Re-run Result: `test_resolve_area_name_postgis_contains PASSED` (1.71s), `test_health_endpoint_requires_postgis PASSED` (2.69s). Total integration suite: **2 passed, 0 failed in 4.40s**.
  - **Remaining Limitations:** None. PostGIS service operational.

- **REQ-G4-03: Python Bytecode Compilation Across All Modules**
  - **Path & Function:** `gis`, `backend`, `scripts`
  - **Reproduction Command:** `.venv/Scripts/python.exe -m compileall gis backend scripts`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** Clean compilation across all modules with 0 syntax or import errors.
  - **Remaining Limitations:** None.

- **REQ-G4-04: Git Diff Whitespace and Patch Integrity**
  - **Path & Function:** Git working tree
  - **Reproduction Command:** `git diff --check`
  - **Status:** PASS
  - **Severity:** P1
  - **Evidence:** Clean output, 0 trailing whitespace or merge conflict markers.
  - **Remaining Limitations:** None.

- **REQ-G4-05: Post-Implementation Re-Verification of Protected Artifact Hashes**
  - **Path & Function:** `artifacts/ml_freeze/` and `data/processed/sensitivity/policy_d/`
  - **Reproduction Command:** Direct SHA-256 computation on 3 frozen core artifacts and all 41 registered artifacts
  - **Status:** PASS
  - **Severity:** P0
  - **Evidence:** All hashes identical before and after implementation. Zero modifications to frozen weights, split definitions, or analysis parquet.
  - **Remaining Limitations:** None.

- **REQ-G4-06: Pre-Stage C Release Decision**
  - **Path & Function:** Entire repository
  - **Reproduction Command:** Holistic evaluation against acceptance criteria
  - **Status:** PASS (READY FOR STAGE A/B SIGN-OFF)
  - **Severity:** P0
  - **Evidence:** All 27 audit requirements passed; 0 requirements blocked; 0 failing tests (114/114 passed); full checksum manifest verified (41/41); all 3 core protected hashes intact; 0 release-blocking defects.
  - **Remaining Limitations:** Stage C (Heat Priority and candidate generation) remains unauthorized until explicit separate user instruction is provided.
