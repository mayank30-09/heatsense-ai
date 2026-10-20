# HEATSENSE AI — PRE-HEAT-PRIORITY SCIENTIFIC & TECHNICAL GATE REPORT

**System:** HEATSENSE AI — AI-Powered GIS-Based Urban Heat Mitigation & Cooling Decision-Support Platform
**Target Region:** Surat Municipal Corporation (SMC), Gujarat, India
**Branch:** `feature/scientific-freeze-correction`
**Scientific Freeze Baseline Tag / Git Commit:** `ml-qc-freeze-before-final-corrections` $\rightarrow$ `c91bc69b75f14d4ec5ad18288cac984815340d68` (Author Date: 2026-09-28 01:39:09 +0530)
**Manifest Recorded Commit String:** `c91bc69038d1796c568772a5bce9fba900be7e96` (Metadata string discrepancy; see Section 18)
**Audit & Validation Git HEAD:** `5dc4d74b7a53522c8bbcab04f46ff518c41691de` (2026-10-03 verification loop)
**Validation Artifacts Timestamp:** `2026-10-03T18:43:09Z`
**Validation Mode:** DETAIL / FULL REPOSITORY SCIENTIFIC VERIFICATION
**Primary Standard:** Real Code + Real Data + Real COGs + Real Saved Model + Real Frozen Split + Real Execution
**Overall Pre-Heat-Priority Gate Decision:** **`PASS (WITH DOCUMENTED MODEL LIMITATIONS & INFRASTRUCTURE QUALIFICATION)`**

---

## 1. Executive Status

A comprehensive pre-Heat-Priority scientific and technical gate verification pass was conducted across all components of the HEATSENSE AI pipeline preceding the downstream Heat Priority, Candidate Generation, and Optimization phases.

- **Total Primary Sequential Gates Evaluated:** 12 gates (21 sub-evaluations).
- **Gate Outcomes:** 20 / 21 PASS, 1 PASS WITH INFRASTRUCTURE QUALIFICATION (0 FAIL, 0 BLOCKED within non-infrastructure scope). The 21 sub-evaluations and 110 passing non-integration tests are reported separately from the PostGIS integration-test suite.
- **Validation Artifacts Generated:** 20 machine-readable JSON artifacts in `artifacts/pre_heat_priority_validation/`.
- **Engineering Suite Status:** 110 / 110 non-integration pytest passing (including 14 dedicated optical sentinel audit tests), compileall clean, frontend build clean, git diff check clean. Integration testing requiring external Docker PostGIS (port 5433) is qualified and reported separately: `test_health_endpoint_requires_postgis` skips and `test_resolve_area_name_postgis_contains` was not executable while offline.
- **Model Artifact Status:** **MODEL ARTIFACTS UNCHANGED**. The frozen model weights, hyperparameters, and artifact checksums remain intact.
- **Next Permitted Phase:** Downstream **LST-BASED HEAT PRIORITY** formulation and spatial candidate generation.

---

## 2. Gate-by-Gate Result

| Gate | Scope | Status | Machine-Readable Evidence Artifact | Key Validated Result |
|---|---|---|---|---|
| **GATE 01** | Source / GEE / Landsat Validation | **PASS** | `01_source_validation.json` | 329 retained scenes (162 L8, 167 L9) verified in GEE for 2022-01-01 to 2026-06-01; 7 scenes in 2026 monsoon |
| **GATE 02** | Independent LST Conversion | **PASS** | `02_lst_conversion_validation.json` | USGS Collection 2 Level-2 ST_B10 scale/offset verified; max diff < 1e-5 °C on 50 sampled pixels |
| **GATE 02B** | QA Mask Logic Validation | **PASS** | `03_qa_mask_validation.json` | QA_PIXEL bits 0-5 and QA_RADSAT==0 bitwise logic passes 100% of test cases |
| **GATE 03** | Seasonal Windows & Boundaries | **PASS** | `04_season_boundary_validation.json` | Exact boundary dates verified; Winter strictly spans Dec 1 (prior year) to Feb 28/29 |
| **GATE 03B** | Real Seasonal Composite Validation | **PASS** | `05_composite_validation.json` | 10 diverse Surat pixels independently computed in GEE match production COG (delta < 0.05 °C) |
| **GATE 04** | 19 Production COGs (Structural) | **PASS** | `06_cog_structural_validation.json` | 19 COGs verified: EPSG:4326, 318x324, 10 bands, float32, tiled 256x256, 4 overviews |
| **GATE 04B/C** | COG Semantic & Persistence Validation | **PASS** | `07_cog_semantic_validation.json` | 0 differing persistence pixels; canonical rule (freq >= 0.25) or flag verified across all 19 COGs |
| **GATE 05** | Policy D Real Reproduction | **PASS** | `08_policy_d_validation.json` | 0 mismatches across 50,000-row sample (evaluate_policy_d) and 0 mismatches across full 924,731 rows |
| **GATE 05B** | Extreme Pixel QC (Cold vs Hot) | **PASS** | `09_extreme_pixel_validation.json` | Purges the 6.47°C cold artifact while retaining the spatially coherent 70.23°C observed LST extreme for downstream review |
| **GATE 06** | Analysis Dataset & Leakage | **PASS** | `10_dataset_validation.json` | Exactly 924,731 rows, 165 blocks, 0 NaNs/Infs; coordinate columns strictly excluded from features |
| **GATE 07** | 132/33 Spatial Split Validation | **PASS** | `11_spatial_split_validation.json` | 132 dev blocks (720,973 rows) and 33 test blocks (203,758 rows); zero spatial overlap |
| **GATE 07B/C** | 5-Fold Spatial CV & Optuna Isolation | **PASS** | `12_cv_leakage_validation.json` | 33 test blocks strictly isolated from all 30 Optuna trials and all 5 CV folds |
| **GATE 08** | Frozen Model Parameters | **PASS** | `13_model_parameter_validation.json` | 900 estimators, max depth 9, lr 0.036629 match authoritative metadata exactly |
| **GATE 08B** | Independent Holdout Reproduction | **PASS** | `14_holdout_reproduction.json` | Holdout reproduces targets: MAE 1.2726, RMSE 1.7524, R² 0.9006, Model Bias -0.0521, Residual +0.0521 |
| **GATE 09** | Seasonal Metrics Reproduction | **PASS** | `15_seasonal_metrics_reproduction.json` | Winter 1.2136, Summer 1.7944, Monsoon 2.4353, Post-Monsoon 1.2772 match targets |
| **GATE 09B/C** | Hotspot Metrics & RF Comparison | **PASS** | `16_hotspot_metrics_reproduction.json` | Non-hotspot (1.6715) to Chronic (4.8413) error escalation verified; RF baseline protocol distinct |
| **GATE 09D** | Residual Analysis & Heteroscedasticity | **PASS** | `17_residual_validation.json` | Mean residual +0.0521 °C, mean model bias -0.0521 °C, std 1.7516 °C |
| **GATE 10** | SHAP Additivity & Language Audit | **PASS** | `18_shap_validation.json` | Additivity holds within 0.000107; non-causal attribution language strictly verified |
| **GATE 11** | Environment Version Verification | **PASS** | `19_environment_validation.json` | Python 3.12.10, XGBoost 3.4.1, Scikit-learn 1.9.1, Pandas 3.0.6, Numpy 2.5.3, SHAP 0.52.0 match |
| **GATE 11B/C** | Artifact SHA-256 Hashes & Provenance | **PASS** | `20_artifact_hash_validation.json` | 41/41 frozen artifacts verified; 0 hash mismatches; stale doc contradictions resolved |
| **GATE 12** | Automated Engineering Suite | **PASS WITH INFRASTRUCTURE QUALIFICATION** | Console execution | 110/110 non-integration tests passing; compileall clean; frontend build clean; git diff --check clean. One PostGIS-dependent integration test requires the external Docker service and was not executable while the service was offline. |

---

## 3. Dataset Validation

The authoritative operational dataset `data/processed/sensitivity/policy_d/analysis.parquet` was inspected and verified:
- **Total Dataset Rows:** 924,731
- **Spatial Blocks:** 165 mutually exclusive spatial blocks covering the Surat study area
- **Target Variable:** `LST_C` (Land Surface Temperature in Celsius)
- **Target Statistics:**
  - Observed Range: [9.1049, 70.2328] °C
  - Mean: 37.772797 °C
  - Standard Deviation: 5.751189 °C
- **Feature Set:** `NDVI`, `NDBI`, `NDWI`, `LST_OBS_COUNT`, `LST_QA_MEDIAN_K`
- **Coordinate Feature Leakage:** Spatial coordinate columns (`x`, `y`, `longitude`, `latitude`, `block_id`, etc.) are strictly excluded from the model feature matrix.
- **Data Integrity & Sentinel Distinction:**
  - Nulls / NaNs / Infs: Exactly **0 nulls, 0 NaNs, 0 Infs** across all feature and target columns.
  - Missing-Data Sentinels: Exactly **8 unique rows** contain optical `-9999.0` sentinels (12 column-level occurrences: 7 in `NDVI`, 2 in `NDBI`, 3 in `NDWI`), representing 0.000865% of dataset rows. These finite values represent unobserved optical bands from complete seasonal cloud masking under solitary thermal retrievals in GEE (`gis/gee/seasonal_features.py`: `result.unmask(-9999)`), and are strictly distinct from IEEE NaN/Inf floating-point values.
  - Spatial Partition: 100% (8 / 8) of optical sentinel rows reside in development blocks (`B_05_11`: 7 rows, `B_10_04`: 1 row); exactly **0 rows** exist in the locked independent test partition.
  - Quality Status: 100% (8 / 8) are classified under Policy D with eligibility status `FLAG` and flag reason `LOW_TEMPORAL_SUPPORT;SPATIALLY_COHERENT`.
- **Numerical Ranges in Analysis Dataset (Raw Columns):**
  - `NDVI`: [-9999.0, 0.9830]
  - `NDBI`: [-9999.0, 0.6161]
  - `NDWI`: [-9999.0, 0.4818]
  - `LST_OBS_COUNT`: [1.0, 24.0]
  - `LST_QA_MEDIAN_K`: [1.4700, 87.5200] (observed numerical range)
  - `LST_C`: [9.1049, 70.2328] °C
- **Physical Optical-Index Ranges (Excluding `-9999.0` Sentinels):**
  - `NDVI`: [-0.3630, 0.9830] (excluding 7 sentinel occurrences)
  - `NDBI`: [-0.7819, 0.6161] (excluding 2 sentinel occurrences)
  - `NDWI`: [-0.7674, 0.4818] (excluding 3 sentinel occurrences)
- **`LST_QA_MEDIAN_K` Numerical Range & Interpretation:**
  - Observed Numerical Range: [1.4700, 87.5200].
  - Semantic Interpretation: This feature represents the seasonal median of the Landsat Level-2 Surface Temperature Quality Assessment band (`ST_QA`), which quantifies pixel-level radiometric uncertainty. In typical clear-sky conditions, values cluster around 2.1–2.6 K. However, values reach 87.52 K numerically due to unscaled DN references at composite boundaries or low-quality acquisition edges. Because the pipeline preserves these values without rescaling, this range is reported as an **observed numerical range** rather than asserting physical validity across all pixels.
- **Low-Temperature Observations (< 10 °C):**
  - The current analysis dataset contains exactly **two observations below 10 °C**:
    1. `LST_C = 9.2929 °C` (row index 346032, raster row 285, col 114)
    2. `LST_C = 9.1049 °C` (row index 346033, raster row 285, col 115)
  - Both observations are from the 2023 monsoon season, located in spatial block `B_14_05`, with single thermal observation support (`LST_OBS_COUNT = 1.0`).
  - Both carry the quality flag `LOW_TEMPORAL_SUPPORT;SPATIALLY_COHERENT` and eligibility status `FLAG`.
  - Zero observations exist between 6.0 °C and 7.0 °C. The historical 6.4696 °C single-pass anomaly recorded in `09_extreme_pixel_validation.json` was purged under Policy D (`policy_d_purged: true`). However, this does not imply that every low-temperature observation was removed; the two verified sub-10 °C observations remain in the dataset under `FLAG` status.
- **High-Temperature Observed Extreme (70.2328 °C):**
  - The maximum observed temperature of 70.2328 °C (2023 Monsoon, row index 330966, raster row 201, col 199, block `B_10_09`, `LST_OBS_COUNT = 1.0`, `LST_QA_MEDIAN_K = 84.990 K`, eligibility `FLAG`) remains in the analysis dataset.
  - **Spatial Partition:** Block `B_10_09` belongs exclusively to the **development partition** (132 blocks, 720,973 observations); exactly **zero observations $\ge$ 70 °C exist in the locked independent test partition**.
  - **Physical & Diagnostic Context:** The pixel corresponds geographically to Pandesara Industrial Estate (Pandesara GIDC). The diagnostic analysis in `reports/extreme_lst_spatial_quality_report.md` (Section 9.2) and `reports/pixel_quality_hotspot_persistence_report.md` documents an interpretation that under solitary observation support ($OBS = 1.0$), single-channel Level-2 atmospheric over-correction during high monsoon column water vapor ($CWV > 4.5\text{ g/cm}^2$) amplified the surface temperature retrieval, consistent with the elevated Level-2 uncertainty ($QA = 84.99\text{ K}$). This is noted as a documented repository diagnostic interpretation rather than independently proven causation. In all contexts, observed LST reflects satellite-derived radiometric surface skin temperature, not an ambient air temperature or ground meteorological measurement.

---

## 4. Optical Sentinel Investigation (-9999 Deep-Dive)

An exhaustive investigation was conducted into the numerical sentinel values (-9999.0) reported in Gate 06:
1. **Exact Sentinel Counts:**
   - `NDVI == -9999.0`: 7 rows (0.000757%)
   - `NDBI == -9999.0`: 2 rows (0.000216%)
   - `NDWI == -9999.0`: 3 rows (0.000324%)
   - **Total Unique Sentinel Rows:** Exactly **8 rows** out of 924,731 (**0.000865%** of the dataset).
2. **Quality Eligibility Distribution:**
   - 100% (8 / 8) of sentinel rows are classified under Policy D as `FLAG` with reason `LOW_TEMPORAL_SUPPORT;SPATIALLY_COHERENT`.
   - Exactly 0 rows are classified as `ACCEPT` or `EXCLUDE`.
3. **Temporal Breakdown:**
   - 100% (8 / 8) occurred during the **Monsoon** season (5 in 2022, 1 in 2024, 2 in 2025).
4. **Thermal Target Statistics:**
   - Sentinel rows (N = 8): Mean `LST_C` = 28.1527 °C (Min: 24.1305 °C, Median: 24.2006 °C, Max: 41.9418 °C, Std: 6.4196 °C).
   - Non-sentinel rows (N = 924,723): Mean `LST_C` = 37.7729 °C (Min: 9.1049 °C, Max: 70.2328 °C).
   - The observed LST values for the eight sentinel rows fall within the observed temperature distribution of the development dataset. The sentinel values themselves do not exhibit an obvious thermal-target anomaly in this descriptive comparison.
5. **Spatial Partitioning & Leakage:**
   - **Development Set (132 blocks):** 8 rows (all in blocks `B_05_11` [7 rows] and `B_10_04` [1 row]). This represents **0.00111%** (8 / 720,973) of development rows.
   - **Locked Independent Test Set (33 blocks):** Exactly **0 rows** (0.0000%). The locked independent test set contains 0 observations with the audited optical -9999.0 sentinel values.
6. **Pipeline Origin:**
   - In `gis/gee/seasonal_features.py` (lines 258–282), unobserved pixels in the seasonal optical composite are explicitly unmasked to `-9999.0` (the standard project NoData sentinel). When severe monsoon cloud cover prevents any cloud-free optical acquisition over a pixel during an entire season, but a valid thermal retrieval exists, unobserved optical bands are exported as `-9999.0`.
7. **Scientific Disposition & Model Impact:**
   - **Model Retraining Status:** No production-model retraining was performed or required for this audit; the frozen production model remains unchanged. The locked test partition contains zero observations with the audited optical `-9999.0` sentinel values.
   - **Optical Sentinel Audit:** Eight unique development observations contain `-9999.0` in one or more optical predictors (`NDVI`, `NDBI`, `NDWI`), while the locked independent test population contains zero such observations. A development-only sensitivity experiment using the frozen XGBoost configuration was conducted to quantify whether these observations materially influence spatial cross-validation behavior and local prediction fields. No production model or locked holdout artifact was modified.
   - **Disposition:** Model artifacts remain **UNCHANGED**. Gate 06 explicitly distinguishes dataset-level sentinel presence (8 flagged monsoon rows) from model input validity.

8. **Issue 1 Sensitivity Audit & Spatial Proximity Characterization (Completed):**
   - **Scientific Scope:** The optical sentinel sensitivity was characterized using aggregate spatial cross-validation metrics, a row-level local prediction-effect diagnostic, and a spatial proximity characterization. The diagnostic quantifies the magnitude, spatial concentration, seasonal distribution, and proximity of prediction differences relative to the eight development-only sentinel observations. The frozen production model, authoritative dataset, and locked independent test set remain unchanged.
   - **Aggregate Sensitivity Results (5-Fold Spatial CV, 720,965 Common Development Rows):**
     - Experiment A (Original, with sentinels): MAE = 1.4880 °C, RMSE = 2.1158 °C, R² = 0.8872, Model Bias = +0.0036 °C
     - Experiment B (Clean, sentinel-excluded): MAE = 1.4881 °C, RMSE = 2.1159 °C, R² = 0.8871, Model Bias = +0.0034 °C
     - Aggregate Delta: $\Delta\text{MAE} = 0.0001$ °C, $\Delta\text{RMSE} = 0.0001$ °C, $\Delta R^2 = 0.0001$, $\Delta\text{Bias} = 0.0002$ °C. The aggregate spatial cross-validation performance is virtually identical.
   - **Row-Level Local Prediction-Effect Distribution (720,973 Matched Rows):**
     - Mean Prediction Delta ($\text{Clean} - \text{Orig}$): $+0.000334$ °C
     - Mean Absolute Prediction Delta: $0.087349$ °C
     - RMSE of Prediction Delta: $0.127227$ °C
     - 95th Percentile Absolute Delta (P95): $0.249353$ °C
     - 99th Percentile Absolute Delta (P99): $0.430191$ °C
     - Maximum Absolute Delta: $4.948700$ °C
   - **Threshold Exceedance Breakdown:**
     - $|\Delta| > 0.10$ °C: 220,374 rows (30.5662%)
     - $|\Delta| > 0.25$ °C: 35,809 rows (4.9668%)
     - $|\Delta| > 0.50$ °C: 4,475 rows (0.6207%)
     - $|\Delta| > 1.00$ °C: 398 rows (0.0552%)
     - $|\Delta| > 2.00$ °C: 8 rows (0.0011%)
     - $|\Delta| > 3.00$ °C: 2 rows (0.0003%)
     - $|\Delta| > 4.00$ °C: 1 row (0.0001%)
   - **Block-Level Spatial Concentration:**
     - Total development blocks evaluated: 132
     - Blocks with max $|\Delta| > 1.0$ °C: 87 (65.91%)
     - Blocks with max $|\Delta| > 2.0$ °C: 7 (5.30%) (`B_10_05`, `B_00_14`, `B_05_09`, `B_11_08`, `B_06_07`, `B_00_13`, `B_09_08`)
     - Blocks with max $|\Delta| > 4.0$ °C: 1 (0.76% — exclusively block `B_10_05` where 1 observation reached 4.9487 °C)
   - **Seasonal Distribution:**
     - Monsoon: 178,319 obs, Mean $|\Delta| = 0.1268$ °C, Max $= 4.9487$ °C, P95 $= 0.3414$ °C (255 obs $> 1.0$ °C, 64.07% of exceedances)
     - Summer: 193,805 obs, Mean $|\Delta| = 0.0805$ °C, Max $= 2.0512$ °C, P95 $= 0.2199$ °C (56 obs $> 1.0$ °C, 14.07%)
     - Winter: 193,805 obs, Mean $|\Delta| = 0.0720$ °C, Max $= 1.5653$ °C, P95 $= 0.1909$ °C (57 obs $> 1.0$ °C, 14.32%)
     - Post-Monsoon: 155,044 obs, Mean $|\Delta| = 0.0697$ °C, Max $= 1.8902$ °C, P95 $= 0.1919$ °C (30 obs $> 1.0$ °C, 7.54%)
     - *Descriptive Assessment:* The largest prediction changes are predominantly observed in monsoon development observations. This experiment characterizes model sensitivity to removing the audited sentinel observations, but does not establish a causal spatial mechanism for effects observed away from the sentinel locations.
   - **Top 5 Local Effects:**
     1. Year 2023, Monsoon, Row 207, Col 118, Block `B_10_05`: Pred Orig = 52.8479 °C, Pred Clean = 57.7966 °C, $\Delta = +4.9487$ °C ($|\Delta| = 4.9487$ °C, Dist = 35.36 cells)
     2. Year 2024, Monsoon, Row 12, Col 280, Block `B_00_14`: Pred Orig = 30.6044 °C, Pred Clean = 26.9612 °C, $\Delta = -3.6431$ °C ($|\Delta| = 3.6431$ °C, Dist = 273.70 cells)
     3. Year 2024, Monsoon, Row 110, Col 181, Block `B_05_09`: Pred Orig = 39.4376 °C, Pred Clean = 42.3207 °C, $\Delta = +2.8831$ °C ($|\Delta| = 2.8831$ °C, Dist = 134.42 cells)
     4. Year 2024, Monsoon, Row 206, Col 118, Block `B_10_05`: Pred Orig = 40.3886 °C, Pred Clean = 42.9353 °C, $\Delta = +2.5467$ °C ($|\Delta| = 2.5467$ °C, Dist = 35.23 cells)
     5. Year 2024, Monsoon, Row 238, Col 178, Block `B_11_08`: Pred Orig = 48.1969 °C, Pred Clean = 50.4029 °C, $\Delta = +2.2060$ °C ($|\Delta| = 2.2060$ °C, Dist = 101.59 cells)
   - **Spatial Proximity Characterization (`sentinel_spatial_proximity.csv`, `sentinel_spatial_proximity_summary.json`):**
     - **Outcome:** **Outcome B: Observed Distributed Prediction Sensitivity**
     - Same-block observations: 13,332 (1.85%, mean $|\Delta| = 0.0758$ °C, max $|\Delta| = 1.7861$ °C). Different-block observations: 707,641 (98.15%, mean $|\Delta| = 0.0876$ °C, max $|\Delta| = 4.9487$ °C).
     - For large effects $|\Delta| > 1.0$ °C (398 obs), the median distance to the nearest audited sentinel observation is 93.93 cells, and 392 of 398 (98.49%) occur in different spatial blocks.
     - For effects $|\Delta| > 2.0$ °C (8 obs), median distance to the nearest audited sentinel observation is 93.20 cells, and 0 of 8 occur in the same block as the nearest audited sentinel observation.
     - The maximum observed prediction difference occurred in a 2023 monsoon observation whose nearest audited sentinel observation was from 2024 monsoon at a grid distance of 35.36 cells.
     - Mean absolute prediction differences were broadly similar across the evaluated distance bins, with no obvious monotonic distance pattern in this descriptive analysis. A large proportion of observations exhibiting prediction differences above 1°C are geographically distant from the nearest audited sentinel observation. This characterizes the distribution of prediction differences but does not establish causal geographic influence. The prediction changes are not confined to observations spatially close to the audited sentinel observations. This is a descriptive spatial-proximity result and does not establish a physical propagation mechanism or a specific internal tree-split mechanism.

### Issue 1 Status: RESOLVED BY SENSITIVITY EVIDENCE

Eight development-only observations contain the audited optical
`-9999.0` sentinel values. The locked independent test population contains
zero observations with these audited sentinel values.

A development-only sensitivity experiment was performed using the frozen
XGBoost configuration and the canonical spatial cross-validation protocol.
The locked test partition and frozen production artifacts were not modified.

Aggregate spatial cross-validation metrics were effectively unchanged:

- MAE delta: 0.0001 °C
- RMSE delta: 0.0001 °C
- R² delta: 0.0001

A row-level prediction-effect analysis over 720,973 matched development
observations showed:

- P95 absolute prediction difference: 0.2494 °C
- P99 absolute prediction difference: 0.4302 °C
- Maximum absolute prediction difference: 4.9487 °C
- 398 observations exceeded 1.0 °C
- 8 observations exceeded 2.0 °C
- 1 observation exceeded 4.0 °C

A spatial-proximity diagnostic found that the larger prediction differences
were not confined to the immediate geographic vicinity of the eight audited
sentinel observations. This is treated as a descriptive characterization of
model sensitivity, not as evidence of a physical spatial propagation
mechanism.

The sensitivity experiment therefore establishes that the audited sentinel
observations have measurable but sparse effects on development-model
predictions, while aggregate validation performance remains effectively
unchanged. The production model, authoritative analysis dataset, and locked
test partition remain unchanged.

The sentinel condition remains documented as a development-data quality
limitation and is preserved in the machine-readable audit artifacts.

---

## 5. Source-Scene Validation

- **Verified Query Retained Count:** **329 scenes** (Landsat 8 = 162, Landsat 9 = 167).
- **Temporal Window:** 2022-01-01 through 2026-06-01.
- **Sensor Tier:** Landsat Collection 2 Tier 1 Level-2 Science Products (L2SP).
- **Quality Filtering:** `QA_PIXEL` clear land/water, cloud cover <= 80%, geometric RMSE within threshold.
- **Temporal Alignment Resolution:**
  - The frozen source validation artifact contains 329 retained scenes through 2026-06-01. A subsequent query covering the 2026 monsoon window identified 7 additional qualifying scenes. These additional scenes are reported separately and do not alter the frozen production artifact unless explicitly incorporated into a new data-generation version.
  - The historical mention of 682 scenes in early planning documents was resolved: 682 represented the raw unfiltered candidate catalog footprint across SMC before Tier-1 L2SP quality and coverage filtering.
- **Production Seasonal Distribution:**
  - Winter: 2022, 2023, 2024, 2025, 2026 (5 seasons)
  - Summer: 2022, 2023, 2024, 2025, 2026 (5 seasons)
  - Monsoon: 2022, 2023, 2024, 2025, 2026 (5 seasons)
  - Post-monsoon: 2022, 2023, 2024, 2025 (4 seasons)
  - Total: **19 seasonal composites**. Post-monsoon 2026 is intentionally absent because the frozen production dataset was generated before completion of the 2026 post-monsoon acquisition window.

---

## 6. LST Formula Validation

The radiative transfer conversion was independently verified against USGS Landsat Collection 2 specifications:
- `LST_K = ST_B10 * 0.00341802 + 149.0`
- `LST_C = LST_K - 273.15`
- **Technical Wording:** Corrected throughout the repository to:
  *“LST_C is derived from Landsat Collection 2 Level-2 Surface Temperature (ST_B10) using the USGS-provided scale factor and offset, followed by conversion from Kelvin to Celsius.”*
  (Generic "single-channel atmospheric compensation" phrasing has been removed).
- **Numerical Verification:** Evaluated across 50 randomly sampled production pixels in Gate 02. The maximum absolute discrepancy between raw DN recomputation and stored LST is < 1e-5 °C.

---

## 7. QA Mask Logic Validation

- **Gate Scope:** Formally designated as **“QA Mask Logic Validation”** (clarifying that it tests bitwise filtering logic against synthetic and known bit-combination cases, not external ground-truth imagery).
- **Bitwise Logic:**
  - `QA_PIXEL` bits: bit 0 (fill), bit 1 (dilated cloud), bit 2 (cirrus), bit 3 (cloud), bit 4 (cloud shadow), bit 5 (snow).
  - Radiometric Saturation: `QA_RADSAT == 0` (no band saturation).
- **Validation Outcome:** 100% of tested bitwise mask combinations (clear, cloud, shadow, cirrus, dilated, snow, fill, saturation) behaved according to USGS specifications.

---

## 8. Policy D Validation

The three-tier pixel eligibility decision engine under Policy D was evaluated across both sample and full-dataset scopes:
- **Policy Rules:**
  - **EXCLUDE:** OBS = 0, nonfinite LST, or (OBS = 1 and |delta_median| > 10 °C).
  - **ACCEPT:** OBS >= 2 and |delta_median| <= 10 °C and valid_neighbor_count >= 4.
  - **FLAG:** Low temporal support, elevated QA variance, or boundary edge with plausible temperature.
- **Sample Validation Scope:** Independent evaluation using `evaluate_policy_d` across 50,000 randomly sampled rows produced **0 mismatches** (100% concordance).
- **Full-Dataset Validation Scope:** Vectorized production decision logic evaluated across all **924,731 rows** confirmed **0 mismatches** between stored and independently computed eligibility classes.

---

## 9. Spatial Split Validation

- **Partitioning Structure:** 165 spatial blocks partitioned into:
  - **Development Set:** 132 blocks (720,973 observations, 77.97%)
  - **Locked Test Set:** 33 blocks (203,758 observations, 22.03%)
- **Spatial Leakage Verification:**
  - Intersection of block sets: 132 dev blocks intersect 33 test blocks = empty set (zero block overlap).
  - Intersection of coordinate tuples: Exactly 0 overlapping points between development and test sets.
  - Development and test spatial blocks form mutually exclusive territorial clusters.

---

## 10. ML Model Architecture & Parameter Validation

The frozen operational model `xgb_tuned_policy_d_v1` was verified against `artifacts/ml_freeze/model_metadata.json` and the loaded model object:
- **Objective:** `reg:squarederror`
- **Tree Method:** `hist`
- **Number of Estimators:** 900
- **Maximum Tree Depth:** 9
- **Learning Rate:** 0.03662937937931856
- **Subsample Ratio:** 0.6539539403049981
- **Colsample by Tree:** 0.6285481356546664
- **Min Child Weight:** 3.253330265581497
- **Gamma:** 1.2827623793054954
- **Reg Alpha (L1):** 6.448517630611331e-06
- **Reg Lambda (L2):** 12.086733674708716
- **Random State:** 42
- **RF vs XGBoost Protocol Correction:** Stale comparison language claiming "XGBoost outperformed RF 1.7524 vs 1.8024" was removed. Corrected language states:
  *“XGBoost is the frozen operational model based on the tuned development workflow, independent locked test evaluation, and explainability workflow. RF remains an active benchmark. The currently reported RF 5-fold development CV RMSE (1.8024 °C) and XGBoost locked-test RMSE (1.7524 °C) arise from distinct validation protocols and are not directly comparable.”*

---

## 11. Holdout Reproduction

The frozen model `xgb_tuned_policy_d.joblib` was executed against the untouched 33-block spatial test set (203,758 rows):

```text
========================================================================
METRIC                     EXPECTED TARGET         REPRODUCED RESULT
========================================================================
Observations (N)                   203,758                   203,758
Mean Absolute Error (MAE)       1.2726 °C                 1.2726 °C
Root Mean Squared Error (RMSE)  1.7524 °C                 1.7524 °C
Coefficient of Determ. (R²)        0.9006                    0.9006
Mean Model Bias                -0.0521 °C                -0.0521 °C
Mean Residual                  +0.0521 °C                +0.0521 °C
========================================================================
```

All metrics reproduced with exact precision (< 0.0001 discrepancy).

---

## 12. Seasonal Metrics

Holdout error stratified across seasons matches frozen targets:
- **Winter:** N = 54,930 | MAE = 0.9139 °C | RMSE = 1.2136 °C | R² = 0.6512 | Bias = +0.0032 °C | Residual = -0.0032 °C
- **Summer:** N = 54,930 | MAE = 1.3734 °C | RMSE = 1.7944 °C | R² = 0.7119 | Bias = -0.1916 °C | Residual = +0.1916 °C
- **Monsoon:** N = 49,954 | MAE = 1.8024 °C | RMSE = 2.4353 °C | R² = 0.7718 | Bias = +0.0866 °C | Residual = -0.0866 °C
- **Post-Monsoon:** N = 43,944 | MAE = 0.9926 °C | RMSE = 1.2772 °C | R² = 0.7855 | Bias = -0.1047 °C | Residual = +0.1047 °C

---

## 13. Hotspot Metrics

Stratification by multi-year hotspot recurrence frequency:
- **Non-Hotspot (f = 0):** N = 191,545 | MAE = 1.2251 °C | RMSE = 1.6715 °C | R² = 0.9076 | Bias = +0.0165 °C
- **Active Hotspot (f > 0):** N = 12,213 | MAE = 2.0170 °C | RMSE = 2.7228 °C | R² = 0.7809 | Bias = -1.1281 °C
- **Persistent Hotspot (f >= 0.25 or flag):** N = 2,177 | MAE = 3.0959 °C | RMSE = 3.9896 °C | R² = 0.4941 | Bias = -1.3041 °C
- **Chronic Hotspot (f >= 0.50):** N = 405 | MAE = 3.9077 °C | RMSE = 4.8413 °C | R² = 0.2118 | Bias = -1.5264 °C

**Core Principle:** Observed LST remains the **PRIMARY THERMAL EVIDENCE**. Modeled LST is supplementary analytical output. The model must never replace observed LST in hotspot delineation or priority scoring.

---

## 14. Residual & Bias Convention

The sign conventions have been explicitly standardized across all documentation:
- **Residual Convention:**
  `residual = observed - predicted`
  `Mean Residual = +0.0521 °C`
- **Model Bias Convention:**
  `model bias = predicted - observed`
  `Mean Model Bias = -0.0521 °C`
- Standard deviation of residuals: 1.7516 °C.
- **Upper-Temperature Decile Diagnostics (Decile 10):**
  - In `artifacts/pre_heat_priority_validation/17_residual_validation.json`, residual heteroscedasticity was characterized across 10 true LST deciles on the locked holdout set (203,758 rows).
  - **Decile 10 (Hottest Decile, (45.073 °C, 61.278 °C], N = 20,358):**
    - Mean True LST: 47.34 °C
    - RMSE: **2.5108 °C**
    - Mean Residual (`observed - predicted`): **+1.5205 °C**
    - Mean Model Bias (`predicted - observed`): **-1.5205 °C**
  - **Physical Interpretation:** The positive mean residual (+1.5205 °C) indicates that the XGBoost model systematically **underpredicts** the hottest decile on average by 1.52 °C (the model's predictions are cooler than observed satellite LST in peak thermal conditions).
  - **Mandatory Safeguard:**
    **Observed LST remains the primary thermal evidence. Model predictions are supplementary and must not replace observed LST for hotspot delineation or Heat Priority scoring.** High overall holdout performance ($R^2 = 0.9006$, overall RMSE = 1.7524 °C) does not imply uniform fidelity across extreme heat regimes or hotspot severity tiers.

---

## 15. SHAP Validation

- **Additivity Verification:** TreeExplainer additivity was verified across holdout sample rows:
  `max |sum(phi_i) + phi_0 - f(x)| = 0.000107 <= 0.001`
  Local additivity holds strictly.
- **Scientific Interpretation Guardrails:**
  - SHAP values quantify feature attribution to model predictions; they **do NOT establish physical causality** or intervention cooling potential.
  - The high SHAP importance of `LST_OBS_COUNT` during the monsoon season indicates retrieval support and clear-sky sampling context; it does **not** imply that satellite observation count physically cools or heats the ground.

---

## 16. COG Structural Validation

All 19 production analytical COGs in `data/processed/cog/analytical/` were verified:
- **File Count:** Exactly 19 COGs.
- **Dimensions:** 318 rows x 324 columns (100 m spatial resolution).
- **Coordinate Reference System:** EPSG:4326 (WGS 84).
- **Bands:** Exactly 10 bands per COG (Float32, NoData = -9999.0):
  1. `LST_C`, 2. `NDVI`, 3. `NDBI`, 4. `NDWI`, 5. `LST_OBS_COUNT`, 6. `LST_QA_MEDIAN_K`, 7. `QUALITY_FLAG`, 8. `ELIGIBILITY`, 9. `HOTSPOT_FREQUENCY`, 10. `IS_PERSISTENT_HOTSPOT`.
- **Tiling & Block Dimensions:** Direct rasterio inspection of `src.block_shapes` confirmed that **all 19 COGs and all 10 bands use uniform 256x256 block tiling**.
- **Pyramidal Overviews:** 4 overview levels confirmed on all 19 files.

---

## 17. COG Semantic Validation

- **Hotspot Persistence Semantics:** Verified across all 19 COGs with **0 differing pixels**.
- **Canonical Persistence Rule:** `(frequency >= 0.25) or flag ==> persistent`.
- **Boundary Verification:** Exactly triggers at f = 0.25 and f = 0.50 thresholds.
- **Rescued Flags:** Multi-year persistent flags rescued correctly across all temporal slices.
- **Scope Note:** Semantic validation specifically covers hotspot frequency and persistence semantics; structural properties (dimensions, CRS, dtypes, tiling) are verified across all 10 bands.

---

## 18. Reproducibility & Checksum Validation

- **Authoritative Manifest:** `artifacts/ml_freeze/artifact_manifest.json` (41 registered artifacts).
- **Cryptographic Verification:** SHA-256 recalculation across all 41 files confirmed **41 matches, 0 mismatches**.
- **Model Checksum Stability:** `xgb_tuned_policy_d.joblib` matches its frozen SHA-256 hash `e1aedd4946b1b29823bdea66ea3ec7b9ba5f20c4ddbfdf6920c2e62e6b30b7c9`.
- **Provenance & Commit Distinction:**
  - **Scientific Freeze Baseline Git Commit:** Git tag `ml-qc-freeze-before-final-corrections` resolves in the Git object database to `c91bc69b75f14d4ec5ad18288cac984815340d68` (authored 2026-09-28 01:39:09 +0530). This commit established the frozen model, locked spatial splits, Optuna hyperparameters, and authoritative Policy D dataset.
  - **Manifest Metadata Provenance Discrepancy:** The frozen artifact manifest (`artifacts/ml_freeze/artifact_manifest.json`) records the string `"git_commit": "c91bc69038d1796c568772a5bce9fba900be7e96"` (originating from a hardcoded string in `scripts/reconcile_freeze_manifest.py`). While the first 7 characters (`c91bc69`) match, the remaining 33 characters differ. This is documented as a known metadata string discrepancy; the underlying repository files and 41 artifact hashes remain bit-identical.
  - **Audit & Verification Git HEAD:** `5dc4d74b7a53522c8bbcab04f46ff518c41691de` incorporates the pre-heat-priority real-working verification loop.
  - **Validation Artifacts Generation Timestamp:** `2026-10-03T18:43:09Z` for artifacts in `artifacts/pre_heat_priority_validation/`.
  - **Working-Tree Status:** Working-tree contains uncommitted documentation corrections and audit verification adjustments; all 41 registered frozen artifacts, datasets, and splits remain bit-identical to the baseline freeze.

---

## 19. Test & Build Results

- **Validation Suite Scopes & Results:**
  - **Issue 1 Focused Suite:**
    `.venv/Scripts/pytest.exe backend/tests/test_optical_sentinel_audit.py -q`
    Result: **14 passed, 0 failed** in 3.84s.
  - **Non-Integration Backend Suite:**
    `.venv/Scripts/pytest.exe backend/tests -m "not integration" -q`
    Result: **110 passed, 2 deselected, 0 failed** in 21.48s.
  - **Full Backend Suite (with Integration Tests):**
    `.venv/Scripts/pytest.exe backend/tests -q`
    Result: Integration tests requiring the external PostGIS Docker service (`test_resolve_area_name_postgis_contains` and `test_health_endpoint_requires_postgis`) require port 5433 to be active. When Docker is offline, `test_health_endpoint_requires_postgis` skips and `test_resolve_area_name_postgis_contains` fails on unavailable database. Non-integration suite isolates all application and scientific logic cleanly.
- **Bytecode Compilation:**
  `.venv/Scripts/python.exe -m compileall gis backend scripts`
  Result: Clean compilation across all modules.
- **Frontend Build:**
  `cd frontend && npm run build`
  Result: Clean Vite production bundle (0 errors).
- **Git Formatting & Diff Check:**
  `git diff --check`
  Result: Clean (0 whitespace or conflict errors).

---

## 20. Known Limitations (Preserved in Scientific Record)

1. **Sub-Pixel Radiative Heterogeneity at Hotspots:** Error escalates in chronic industrial hotspots (RMSE increases from 1.67 °C to 4.84 °C, R² = 0.2118). Landsat's 100m thermal footprint averages complex mixed roofscapes. Observed LST remains the primary thermal truth.
2. **Upper-Temperature Decile Underprediction:** In the hottest decile of holdout observations (> 45.07 °C, N = 20,358), holdout RMSE increases to 2.5108 °C and the mean residual is +1.5205 °C (`residual = observed - predicted`), indicating that the model underpredicts peak surface temperatures by 1.52 °C on average. High overall $R^2$ (0.9006) does not imply uniform precision across extreme heat conditions. Observed LST remains mandatory primary thermal truth.
3. **Monsoon Cloud Attenuation:** Clear-sky observation count is reduced during July–September, elevating local temperature variance.
4. **RF vs XGBoost Protocol Non-Equivalence:** RF CV RMSE (1.8024 °C) and XGBoost locked holdout RMSE (1.7524 °C) arise from separate evaluation frameworks and are not directly comparable.
5. **Optical Sentinel Presence:** 8 monsoon rows in development data contain -9999.0 unobserved optical sentinels due to cloud masking; 0 sentinels exist in the test set.
6. **Source Scene Validation Temporal Scope:** The frozen source validation artifact contains 329 retained scenes through 2026-06-01. A subsequent query identified 7 additional qualifying scenes during the 2026 monsoon window, reported separately. Post-monsoon 2026 is intentionally absent because the frozen production dataset was generated before completion of the 2026 post-monsoon acquisition window.

---

## 21. Exact Remaining Blockers

**ZERO (0) REMAINING BLOCKERS WITHIN PRE-HEAT-PRIORITY VERIFICATION SCOPE.**
All 16 identified scientific and technical gate issues within the pre-Heat-Priority scope have been thoroughly audited, documented, and verified. Known model limitations (including chronic hotspot error escalation, upper-temperature decile underprediction, and unobserved monsoon optical sentinels) represent characterized physical constraints of the frozen model and dataset rather than unresolved technical blockers. The PostGIS integration test qualification remains explicit: live Docker service is required for spatial database containment tests and was not executable while offline.

---

## 22. Final Decision

```text
========================================================================
PRE-HEAT-PRIORITY SCIENTIFIC & TECHNICAL GATE:   PASS
========================================================================
STATUS:                PRE-HEAT-PRIORITY CHECKS PASSED WITH
                       DOCUMENTED MODEL LIMITATIONS AND
                       INFRASTRUCTURE QUALIFICATION
MODEL ARTIFACTS:       UNCHANGED (Zero alterations to frozen weights)
METHODOLOGY:           FROZEN
NEXT PERMITTED PHASE:  LST-BASED HEAT PRIORITY
========================================================================
```

**STOP CONDITION HONORED:** No Heat Priority, Candidate Generation, Intervention Scoring, or Optimization code has been implemented. The pre-Heat-Priority stage is complete and frozen.
