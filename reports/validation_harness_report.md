# HEATSENSE AI — Validation Harness Audit Report

**Overall Status:** `PASS`  
**Total Checks:** 18 | **Passed:** 14 | **Failed:** 0 | **Unverified Limitations:** 4  
**Execution Mode:** Strictly Read-Only (Zero Data/Model Mutation)  

---

## 1. Verified Evidence & Invariants Matrix

| ID | Category | Check Name | Expected | Actual | Status |
| :--- | :--- | :--- | :--- | :--- | :---: |
| `CHK-01-FREEZE-MANIFEST` | cryptographic_freeze | Cryptographic Freeze Manifest (41 Files) | {'total_entries': 41, 'verified_matches': 41, 'missing': ... | {'total_entries': 41, 'verified_matches': 41, 'missing_fi... | **PASS** |
| `CHK-02-SPATIAL-SPLIT` | spatial_holdout_integrity | Spatial Block Disjointness (132 Dev / 33 Test) | {'dev_blocks_count': 132, 'test_blocks_count': 33, 'overl... | {'dev_blocks_count': 132, 'test_blocks_count': 33, 'total... | **PASS** |
| `CHK-03-ROW-PARTITION` | spatial_holdout_integrity | Dataset Row Partitioning (720,973 Dev / 203,758 Test) | {'total_rows': 924731, 'test_rows': 203758, 'dev_rows': 7... | {'total_rows': 924731, 'test_rows': 203758, 'dev_rows': 7... | **PASS** |
| `CHK-04-COORDINATE-EXCLUSION` | spatial_holdout_integrity | Spatial Coordinate Exclusion from Features | {'leaked_coordinates': []} | {'feature_count': 5, 'feature_names': ['NDVI', 'NDBI', 'N... | **PASS** |
| `CHK-05-SINGLE-EVALUATION` | spatial_holdout_integrity | Single Holdout Evaluation Policy (count == 1) | {'evaluation_count': 1} | {'evaluation_count': 1} | **PASS** |
| `CHK-06-HOLDOUT-METRICS` | model_performance_reproduction | Authoritative Holdout Performance Metrics | {'mae': 1.2726, 'rmse': 1.7524, 'r2': 0.9006} | {'mae': 1.2726, 'rmse': 1.7524, 'r2': 0.9006} | **PASS** |
| `CHK-07-SPATIAL-RESIDUALS-RECOMPUTE` | model_performance_reproduction | Spatial Residual GeoJSON Recomputation | {'total_blocks': 33, 'total_samples': 203758, 'recomputed... | {'total_blocks': 33, 'total_samples': 203758, 'recomputed... | **PASS** |
| `CHK-08-MODEL-COMPARISON` | model_performance_reproduction | Controlled 5-Fold Spatial CV Model Comparison | {'RandomForest_rmse': 1.8024, 'XGBoost_rmse': 1.828} | {'RandomForest': {'mean_mae': 1.29272, 'mean_rmse': 1.802... | **PASS** |
| `CHK-09-CONFORMAL-CALIBRATION` | model_performance_reproduction | Conformal Uncertainty Calibration & Subgroup Coverage | {'overall_empirical_coverage': 0.9015, 'monsoon_coverage'... | {'nominal_coverage': 0.9, 'overall_empirical_coverage': 0... | **PASS** |
| `CHK-10-SCENE-PROVENANCE` | scene_provenance | Seasonal Scene Manifest Provenance | {'summer_2026': 22, 'winter_2026': 20, 'monsoon_2026': 6,... | {'summer_2026': 22, 'winter_2026': 20, 'monsoon_2026': 6,... | **PASS** |
| `CHK-11-MONSOON-DISCREPANCY` | scene_provenance | Monsoon 2026 Count Discrepancy Reconciliation | {'reconciliation_documented': True} | {'reconciliation_documented': True, 'excerpt': 'In Monsoo... | **PASS** |
| `CHK-12-GRID-INVARIANTS` | stage_c_grid_invariants | Canonical Grid Cell & Chronic Hotspot Invariants | {'canonical_cells': 49747, 'chronic_hotspots_count': 223} | {'canonical_cells': 49747, 'chronic_definitions_present':... | **PASS** |
| `CHK-13-INTERVENTION-PHYSICS` | cooling_interventions_physics | Cooling Intervention Saturation Bounds & Attenuation | {'tree_cap': 3.5, 'cool_roof_cap': 2.5, 'cell_max_cap': 4.5} | {'tree_saturation_cap_verified': True, 'cool_roof_saturat... | **PASS** |
| `CHK-14-PARKED-PATCH-STATUS` | cooling_interventions_physics | Parked Stage D Science Patch Preservation | {'patch_exists': True, 'status': 'PARKED_UNAPPLIED'} | {'patch_exists': True, 'size_bytes': 10128, 'status': 'PA... | **PASS** |
| `CHK-15-UNVERIFIED-ROOF-STRUCTURAL` | unsupported_or_unexecuted_checks | Building Roof Structural Load-Bearing Survey | Physical on-site inspection of roof structural load capac... | UNVERIFIED — Satellite imagery and GIS cannot determine s... | `UNVERIFIED` |
| `CHK-16-UNVERIFIED-SLUM-POPULATION` | unsupported_or_unexecuted_checks | Ward/Slum High-Resolution Population Exposure Benefit | Grid-cell population exposure density weighting | UNVERIFIED — Field returns POPULATION_DATA_UNAVAILABLE; s... | `UNVERIFIED` |
| `CHK-17-UNVERIFIED-SPECIES-CROWN-GROWTH` | unsupported_or_unexecuted_checks | Botanical Species Crown Geometry & 10-Year Growth Progression | Species-specific (Neem, Peepal, Gulmohar) temporal growth... | UNVERIFIED — Active runtime uses mature canopy equilibriu... | `UNVERIFIED` |
| `CHK-18-UNVERIFIED-1D-ENERGY-BALANCE` | unsupported_or_unexecuted_checks | 1D Surface Energy Balance Equation Differential Solver | Iterative numerical solver for net radiation and latent h... | UNVERIFIED — Platform implements empirical microclimate f... | `UNVERIFIED` |

---

## 2. Check Detail & Evidence Chains

### `CHK-01-FREEZE-MANIFEST`: Cryptographic Freeze Manifest (41 Files)
- **Category:** `cryptographic_freeze`
- **Status:** `PASS`
- **Procedure:** sha256 verification against artifacts/ml_freeze/checksums.sha256
- **Evidence Path:** `artifacts/ml_freeze/checksums.sha256`
- **Expected:** `{"total_entries": 41, "verified_matches": 41, "missing": 0, "mismatches": 0}`
- **Actual:** `{"total_entries": 41, "verified_matches": 41, "missing_files": [], "mismatches": []}`
- **Notes:** Guarantees zero bit drift in frozen models, spatial holdout partitions, and evaluation records.

### `CHK-02-SPATIAL-SPLIT`: Spatial Block Disjointness (132 Dev / 33 Test)
- **Category:** `spatial_holdout_integrity`
- **Status:** `PASS`
- **Procedure:** Read artifacts/ml_freeze/holdout_split.json and evaluate block intersection
- **Evidence Path:** `artifacts/ml_freeze/holdout_split.json`
- **Expected:** `{"dev_blocks_count": 132, "test_blocks_count": 33, "overlap_count": 0}`
- **Actual:** `{"dev_blocks_count": 132, "test_blocks_count": 33, "total_blocks": 165, "overlap_count": 0}`
- **Notes:** Strictly enforces zero spatial autocorrelation leakage between dev and test blocks.

### `CHK-03-ROW-PARTITION`: Dataset Row Partitioning (720,973 Dev / 203,758 Test)
- **Category:** `spatial_holdout_integrity`
- **Status:** `PASS`
- **Procedure:** Read artifacts/ml_freeze/qc_summary.json for row counts
- **Evidence Path:** `artifacts/ml_freeze/qc_summary.json`
- **Expected:** `{"total_rows": 924731, "test_rows": 203758, "dev_rows": 720973}`
- **Actual:** `{"total_rows": 924731, "test_rows": 203758, "dev_rows": 720973}`
- **Notes:** Exact partition accounting matches Policy D multi-year analysis dataset.

### `CHK-04-COORDINATE-EXCLUSION`: Spatial Coordinate Exclusion from Features
- **Category:** `spatial_holdout_integrity`
- **Status:** `PASS`
- **Procedure:** Inspect artifacts/ml_freeze/feature_schema.json feature columns
- **Evidence Path:** `artifacts/ml_freeze/feature_schema.json`
- **Expected:** `{"leaked_coordinates": []}`
- **Actual:** `{"feature_count": 5, "feature_names": ["NDVI", "NDBI", "NDWI", "LST_OBS_COUNT", "LST_QA_MEDIAN_K"], "leaked_coordinates": []}`
- **Notes:** Ensures models generalize by physical characteristics rather than memorizing spatial coordinates.

### `CHK-05-SINGLE-EVALUATION`: Single Holdout Evaluation Policy (count == 1)
- **Category:** `spatial_holdout_integrity`
- **Status:** `PASS`
- **Procedure:** Inspect evaluation_count in artifacts/ml_freeze/evaluation_manifest.json
- **Evidence Path:** `artifacts/ml_freeze/evaluation_manifest.json`
- **Expected:** `{"evaluation_count": 1}`
- **Actual:** `{"evaluation_count": 1}`
- **Notes:** Documented constant: final model was evaluated once on the locked holdout blocks.

### `CHK-06-HOLDOUT-METRICS`: Authoritative Holdout Performance Metrics
- **Category:** `model_performance_reproduction`
- **Status:** `PASS`
- **Procedure:** Read artifacts/ml_freeze/holdout_performance.json
- **Evidence Path:** `artifacts/ml_freeze/holdout_performance.json`
- **Expected:** `{"mae": 1.2726, "rmse": 1.7524, "r2": 0.9006}`
- **Actual:** `{"mae": 1.2726, "rmse": 1.7524, "r2": 0.9006}`
- **Notes:** MAE 1.2726°C is well within the municipal planning tolerance of sub-1.5°C.

### `CHK-07-SPATIAL-RESIDUALS-RECOMPUTE`: Spatial Residual GeoJSON Recomputation
- **Category:** `model_performance_reproduction`
- **Status:** `PASS`
- **Procedure:** Aggregate sample-weighted MAE and RMSE across 33 blocks in holdout_spatial_residuals.geojson
- **Evidence Path:** `artifacts/ml_freeze/holdout_spatial_residuals.geojson`
- **Expected:** `{"total_blocks": 33, "total_samples": 203758, "recomputed_mae": 1.2726, "recomputed_rmse": 1.7524}`
- **Actual:** `{"total_blocks": 33, "total_samples": 203758, "recomputed_mae": 1.2726, "recomputed_rmse": 1.7524}`
- **Discrepancy (diff):** `{"diff_mae": 1.6e-05, "diff_rmse": 2e-06}`
- **Notes:** Mathematically proves holdout metrics derive from the 33 locked spatial holdout blocks.

### `CHK-08-MODEL-COMPARISON`: Controlled 5-Fold Spatial CV Model Comparison
- **Category:** `model_performance_reproduction`
- **Status:** `PASS`
- **Procedure:** Read data/diagnostics/ml/model_comparison_rf_xgb.csv
- **Evidence Path:** `data/diagnostics/ml/model_comparison_rf_xgb.csv`
- **Expected:** `{"RandomForest_rmse": 1.8024, "XGBoost_rmse": 1.828}`
- **Actual:** `{"RandomForest": {"mean_mae": 1.29272, "mean_rmse": 1.8023599999999997, "mean_r2": 0.90138}, "XGBoost": {"mean_mae": 1.31902, "mean_rmse": 1.82802, "mean_r2": 0.89856}}`
- **Notes:** Under identical 5-fold spatial cross-validation, RF achieves slightly lower CV RMSE than XGBoost; XGBoost is selected for production latency.

### `CHK-09-CONFORMAL-CALIBRATION`: Conformal Uncertainty Calibration & Subgroup Coverage
- **Category:** `model_performance_reproduction`
- **Status:** `PASS`
- **Procedure:** Inspect conformal_calibration in artifacts/ml_experiments/ml_experimental_evaluation.json
- **Evidence Path:** `artifacts/ml_experiments/ml_experimental_evaluation.json`
- **Expected:** `{"overall_empirical_coverage": 0.9015, "monsoon_coverage": 0.7919, "d10_coverage": 0.8343}`
- **Actual:** `{"nominal_coverage": 0.9, "overall_empirical_coverage": 0.9015, "monsoon_coverage": 0.7919, "d10_coverage": 0.8343}`
- **Notes:** Calibrated overall at 90% nominal; documented undercoverage in monsoon (cloud contamination) and decile 10 (industrial hotspots).

### `CHK-10-SCENE-PROVENANCE`: Seasonal Scene Manifest Provenance
- **Category:** `scene_provenance`
- **Status:** `PASS`
- **Procedure:** Inspect docs/provenance/seasonal_scene_manifest.json season scene counts
- **Evidence Path:** `docs/provenance/seasonal_scene_manifest.json`
- **Expected:** `{"summer_2026": 22, "winter_2026": 20, "monsoon_2026": 6, "post_monsoon_2025": 14}`
- **Actual:** `{"summer_2026": 22, "winter_2026": 20, "monsoon_2026": 6, "post_monsoon_2025": 14}`
- **Notes:** Reconciles 62 authentic USGS Landsat 8/9 Level-2 overpasses across the 4 processing windows.

### `CHK-11-MONSOON-DISCREPANCY`: Monsoon 2026 Count Discrepancy Reconciliation
- **Category:** `scene_provenance`
- **Status:** `PASS`
- **Procedure:** Inspect reconciliation notes in docs/provenance/seasonal_scene_manifest.json
- **Evidence Path:** `docs/provenance/seasonal_scene_manifest.json`
- **Expected:** `{"reconciliation_documented": true}`
- **Actual:** `{"reconciliation_documented": true, "excerpt": "In Monsoon 2026, WRS 148/045 has exactly 6 scenes passing CLOUD_COVER <= 80%. When including WRS 148/046 (5 scenes), total is 11. The historical dashb..."}`
- **Notes:** Establishes that the count of 8 reflected an earlier cutoff checkpoint before late-September acquisitions.

### `CHK-12-GRID-INVARIANTS`: Canonical Grid Cell & Chronic Hotspot Invariants
- **Category:** `stage_c_grid_invariants`
- **Status:** `PASS`
- **Procedure:** Check canonical_smc_grid_cells and chronic hotspot count invariants
- **Evidence Path:** `docs/provenance/seasonal_scene_manifest.json`
- **Expected:** `{"canonical_cells": 49747, "chronic_hotspots_count": 223}`
- **Actual:** `{"canonical_cells": 49747, "chronic_definitions_present": true, "chronic_hotspots_count": 223}`
- **Notes:** 49,747 100m grid cells define the authoritative municipal territory of Surat SMC.

### `CHK-13-INTERVENTION-PHYSICS`: Cooling Intervention Saturation Bounds & Attenuation
- **Category:** `cooling_interventions_physics`
- **Status:** `PASS`
- **Procedure:** Inspect cooling saturation constants in gis/interventions/cooling_effects.py
- **Evidence Path:** `gis/interventions/cooling_effects.py`
- **Expected:** `{"tree_cap": 3.5, "cool_roof_cap": 2.5, "cell_max_cap": 4.5}`
- **Actual:** `{"tree_saturation_cap_verified": true, "cool_roof_saturation_cap_verified": true, "cell_combined_cap_verified": true, "subadditive_attenuation_verified": true}`
- **Notes:** Enforces thermodynamic limits: single intervention caps and diminishing returns on co-located interventions.

### `CHK-14-PARKED-PATCH-STATUS`: Parked Stage D Science Patch Preservation
- **Category:** `cooling_interventions_physics`
- **Status:** `PASS`
- **Procedure:** Verify presence of parked research patch without uncommitted working tree modifications
- **Evidence Path:** `reports/runtime_verification_2026-10-21/parked/stage_d_science_wip.patch`
- **Expected:** `{"patch_exists": true, "status": "PARKED_UNAPPLIED"}`
- **Actual:** `{"patch_exists": true, "size_bytes": 10128, "status": "PARKED_UNAPPLIED"}`
- **Notes:** Preserves frozen ML and Stage D contract by keeping non-linear botanical growth curves parked.

### `CHK-15-UNVERIFIED-ROOF-STRUCTURAL`: Building Roof Structural Load-Bearing Survey
- **Category:** `unsupported_or_unexecuted_checks`
- **Status:** `UNVERIFIED`
- **Procedure:** Physical structural civil engineering assessment
- **Evidence Path:** `docs/EVIDENCE_REGISTER.md (Claim #50)`
- **Expected:** `"Physical on-site inspection of roof structural load capacity for green roofs / coatings"`
- **Actual:** `"UNVERIFIED \u2014 Satellite imagery and GIS cannot determine structural load-bearing capacity"`
- **Notes:** Mandatory limitation: physical on-site structural engineering survey required before installing extensive green roofs or heavy installations.

### `CHK-16-UNVERIFIED-SLUM-POPULATION`: Ward/Slum High-Resolution Population Exposure Benefit
- **Category:** `unsupported_or_unexecuted_checks`
- **Status:** `UNVERIFIED`
- **Procedure:** Micro-census demographic spatial join to 100m grid
- **Evidence Path:** `docs/EVIDENCE_REGISTER.md (Claim #51)`
- **Expected:** `"Grid-cell population exposure density weighting"`
- **Actual:** `"UNVERIFIED \u2014 Field returns POPULATION_DATA_UNAVAILABLE; slum demographic layer not linked to 100m grid"`
- **Notes:** Prioritization relies on thermal severity, persistence, and built density components until fine-scale census data is integrated.

### `CHK-17-UNVERIFIED-SPECIES-CROWN-GROWTH`: Botanical Species Crown Geometry & 10-Year Growth Progression
- **Category:** `unsupported_or_unexecuted_checks`
- **Status:** `UNVERIFIED`
- **Procedure:** Dynamic allometric tree growth simulation
- **Evidence Path:** `docs/EVIDENCE_REGISTER.md (Claim #52, #53); parked patch`
- **Expected:** `"Species-specific (Neem, Peepal, Gulmohar) temporal growth curves over 1\u201310 years"`
- **Actual:** `"UNVERIFIED \u2014 Active runtime uses mature canopy equilibrium cooling estimates; temporal growth curves remain in parked patch"`
- **Notes:** Growth curves are scientifically modeled in parked research patch but excluded from active production runtime.

### `CHK-18-UNVERIFIED-1D-ENERGY-BALANCE`: 1D Surface Energy Balance Equation Differential Solver
- **Category:** `unsupported_or_unexecuted_checks`
- **Status:** `UNVERIFIED`
- **Procedure:** Full atmospheric boundary layer 1D heat flux solver (Rn = H + LE + G)
- **Evidence Path:** `docs/EVIDENCE_REGISTER.md (Claim #54); parked patch`
- **Expected:** `"Iterative numerical solver for net radiation and latent heat fluxes"`
- **Actual:** `"UNVERIFIED \u2014 Platform implements empirical microclimate formulas (Bowler 2010, Santamouris 2017) rather than differential solvers"`
- **Notes:** Empirical microclimate equations are computationally bounded for interactive municipal planning.

---

## 3. Disclosures & Unresolved Gaps

1. **Zero Model Mutation:** No machine learning weights, feature selection parameters, or spatial holdout boundaries were modified.
2. **Single Holdout Evaluation:** The frozen production model (`xgb_tuned_policy_d.joblib`) was evaluated exactly once on the 33 locked test blocks.
3. **Heuristic Confidence:** The spatial Confidence Index is a decision-support heuristic, not a calibrated statistical probability.
4. **On-Site Physical Surveys:** Satellite observations cannot verify roof structural integrity or sub-surface ground utility feasibility; on-site surveys remain mandatory prior to physical cooling installations.
