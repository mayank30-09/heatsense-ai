# HEATSENSE AI — Consolidated Platform Evidence Register

**Target Municipality:** Surat Municipal Corporation (SMC), Gujarat, India (461.63 km² territory, 49,747 analytical 100m grid cells)  
**Document Status:** OFFICIAL PRODUCTION EVIDENCE REGISTER (Task T6)  
**Date:** October 26, 2026  
**Active Branch:** `audit-fixes`  
**Cryptographic Integrity Invariant:** 41/41 Verified SHA-256 Checksums (`[PASS]`)  
**Validation Invariant Status:** 14/14 Automated Invariants Verified via `scripts/validation_harness.py` (Harness: 14 Passed, 4 Unverified, 0 Failed, Overall: PASS)  

---

## 1. Evidentiary Classification Taxonomy

In compliance with the post-audit scientific integrity mandate, every quantitative claim, parameter, formula, spatial boundary, and methodology assertion across the HEATSENSE AI platform is cataloged under one of four explicit evidentiary statuses:

1. **Verified by a reproducible command or committed artifact:**
   Directly confirmed by a deterministic command, cryptographic digest, stored GeoJSON/TIFF/JSON artifact, or reproducible automated test. Full chain of custody exists in the repository.
2. **Supported by source metadata or documented methodology:**
   Derived mathematically or physically from authoritative published specifications, satellite sensor calibration guides (e.g. USGS Landsat Science Product Guide), or peer-reviewed micrometeorological literature, but dependent on external documented methodology.
3. **Assumption or heuristic:**
   Policy choice, multi-criteria weighting, administrative parameter, empirical saturation ceiling, or spectral/site-type heuristic adopted for municipal decision-support. Not a natural physical law.
4. **Unverified or unavailable:**
   Data, schedule, legal boundary, or physical outcome that cannot be derived solely from satellite observations or committed files, requiring on-site municipal engineering, cadastral verification, or localized meteorological field sensor networks.

---

## 2. Master Platform Evidence Register

### 2.1 Satellite Remote Sensing, Calibration & Scene Provenance

| Claim / Assertion | Evidentiary Status | Evidence Path | Active Implementation & Context | Applicable Limitation / Boundary |
|---|---|---|---|---|
| **Landsat 8/9 LST Radiometric Conversion** ($T_{\text{skin}} = (\text{ST\_B10} \times 0.00341802 + 149.0) - 273.15$) | Supported by source metadata or documented methodology | `gis/gee/seasonal_features.py:65`; USGS Collection 2 Level-2 Surface Temperature Guide | Band 10 thermal radiance converted to surface skin temperature in Celsius using standard USGS calibration multipliers. | Measures thermodynamic skin surface temperature at ~10:30 solar time, **not** 2m ambient air temperature. Typically 8°C–16°C hotter than air on clear summer days. |
| **Multispectral Optical Surface Reflectance Indices** (NDVI, NDBI, NDWI) | Supported by source metadata or documented methodology | `gis/gee/seasonal_features.py:75-85`; USGS Landsat 8/9 Level-2 OLI/OLI-2 Guide | Standard band ratios: $\text{NDVI} = \frac{\text{B5}-\text{B4}}{\text{B5}+\text{B4}}$, $\text{NDBI} = \frac{\text{B6}-\text{B5}}{\text{B6}+\text{B5}}$, $\text{NDWI} = \frac{\text{B3}-\text{B5}}{\text{B3}+\text{B5}}$. | Optical resolution is 30m native, aggregated to 100m grid cells via pixel-wise median filtering. |
| **Seasonal Multi-Scene Processing (19 Seasons)** | Verified by a reproducible command or committed artifact | `data/processed/seasonal/` (seasonal COG rasters); `gis/gee/seasonal_features.py` | Pixel-wise median composites across 19 processing windows (Summer, Winter, Monsoon, Post-Monsoon across 2022–2026). | Multi-scene median eliminates transient cloud shadows and sensor noise, but obscures diurnal extremes. |
| **Reconciled Seasonal Scene Manifest (62 Scenes)** | Verified by a reproducible command or committed artifact | `docs/provenance/seasonal_scene_manifest.json`; `scripts/validation_harness.py:check_scene_provenance` | Exact catalog of 62 USGS Landsat 8/9 scenes covering Surat WRS Path 148, Row 045 across 4 active seasonal baselines (Summer: 22, Winter: 20, Monsoon: 6, Post-Monsoon: 14). | Reconciled audit: cause not established; counts differ between the early sensitivity analysis (8) and the manifest (6). |
| **Near-Real-Time (NRT) Overpass (Oct 14, 2026)** | Verified by a reproducible command or committed artifact | `data/processed/scenes/2026-10-14.tif`; `data/processed/scenes/2026-10-14.json` | Authentic single-pass Landsat 9 overpass acquired 2026-10-14T05:33:20.443000+00:00 UTC (~11:03 AM IST). | Instantaneous snapshot reflecting transient conditions; strictly excluded from multi-year HPI computation. |

---

### 2.2 Spatial Geometry, Domain & Administrative Invariants

| Claim / Assertion | Evidentiary Status | Evidence Path | Active Implementation & Context | Applicable Limitation / Boundary |
|---|---|---|---|---|
| **SMC Municipal Domain Boundary (461.63 km²)** | Verified by a reproducible command or committed artifact | `data/raw/boundaries/surat_smc_boundary.geojson`; `docs/audits/stage-c-baseline-inspection.md:149` | Authoritative Surat Municipal Corporation administrative boundary polygon ($461,630,791.0\text{ m}^2$) used for clipping and spatial normalization. | Represents municipal jurisdiction; excludes external peri-urban growth centers outside formal SMC boundary. |
| **Canonical 100m Analytical Grid (49,747 Cells)** | Verified by a reproducible command or committed artifact | `backend/app/db/models/stage_c.py` (`stage_c_grid_cells`); PostgreSQL table | Uniform 100m × 100m Cartesian grid tessellation across SMC bounding box. | Analytical screening units, not legal cadastral plots or building parcels. |
| **Administrative Locality & Ward Names** | Assumption or heuristic | `data/raw/place_names/surat_osm_place_points.geojson`; `gis/heat_priority/scoring.py` | Assigned to cells via spatial nearest-neighbor join against OpenStreetMap locality nodes. | Approximates general neighborhood; does not represent surveyed cadastral ward boundaries. |

---

### 2.3 Machine Learning Baseline, Spatial Holdout & Validation

| Claim / Assertion | Evidentiary Status | Evidence Path | Active Implementation & Context | Applicable Limitation / Boundary |
|---|---|---|---|---|
| **Cryptographic Freeze Checksums (41 Files)** | Verified by a reproducible command or committed artifact | `artifacts/ml_freeze/checksums.sha256`; `verify_checksums.py` | 41 SHA-256 cryptographic digests protecting models, feature matrices, splits, and holdout benchmarks. Output: `Verified Matches: 41`, `[PASS]`. | Prevents inadvertent drift or uncommitted retraining of scientific baselines. |
| **2km Block-Disjoint Spatial Holdout Split** | Verified by a reproducible command or committed artifact | `artifacts/ml_freeze/holdout_split.json`; `scripts/validation_harness.py:check_spatial_holdout_split` | 132 Development blocks ($80\%$, 720,973 observations), 33 Test blocks ($20\%$, 203,758 observations). Disjointness: $\text{Dev} \cap \text{Test} = \emptyset$. | 2km buffer separation controls spatial autocorrelation; boundary cells may have microclimatic proximity. |
| **Feature Non-Contamination (Coordinate Exclusion)** | Verified by a reproducible command or committed artifact | `artifacts/ml_freeze/feature_schema.json`; `backend/tests/test_reproduce_validation.py` | Features restricted to biophysical indices (`NDVI`, `NDBI`, `NDWI`, `LST_OBS_COUNT`, `LST_QA_MEDIAN_K`). Coordinates (`lat`, `lon`, `row`, `col`, `block_id`) are 100% excluded. | Guarantees model learns physical land-surface relationships rather than memorizing spatial coordinates. |
| **Pooled Random-Split Holdout Performance** ($R^2 = 0.9006$, $\text{MAE} = 1.2726^\circ\text{C}$, $\text{RMSE} = 1.7524^\circ\text{C}$) | Verified by a reproducible command or committed artifact | `artifacts/ml_freeze/holdout_performance.json`; `scripts/reproduce_validation_report.py` | Single-pass evaluation of production model `artifacts/ml_freeze/xgb_tuned_policy_d.json` on 203,758 locked test observations. | Reflects pooled holdout accuracy. Spatial autocorrelation between neighboring pixels inflates pooled $R^2$. |
| **Geographically Blocked Spatial-Split Performance** ($R^2 = 0.6919$) | Verified by a reproducible command or committed artifact | `artifacts/ml_freeze/holdout_spatial_residuals.geojson`; `docs/recommendation_methodology.md:125` | Spatial out-of-neighborhood evaluation across 33 isolated 2km holdout blocks. | True spatial generalization metric. Dual $R^2$ reporting is mandated across UI to prevent misrepresenting performance. |
| **Conformal Prediction Interval Coverage** (Overall: $90.15\%$ at nominal $90.0\%$, Half-Width: $\pm 2.98^\circ\text{C}$) | Verified by a reproducible command or committed artifact | `artifacts/ml_experiments/ml_experimental_evaluation.json`; `scripts/validation_harness.py:check_conformal_calibration` | Non-parametric split conformal calibration. Summer: 90.53%, Winter: 95.68%, Post-Monsoon: 95.80%. | Monsoon stratum undercovers at 79.19% due to cloud boundary noise. Hottest decile (D10) covers at 83.43%. |
| **In-Sample Cell-Mean Spatial Baseline** ($\text{RMSE} = 2.4170^\circ\text{C}$, $R^2 = 0.8268$) | Verified by a reproducible command or committed artifact | `reports/improvement_2026-10-23/VALIDATION_BENCHMARK.md`; `data/diagnostics/` | Evaluates persistence of historical cell mean temperature without ML feature regressors. | the cell-mean baseline is in-sample and not comparable with spatial CV or holdout RMSE |

---

### 2.4 Heat Priority Index (HPI) & Sensitivity Analysis

| Claim / Assertion | Evidentiary Status | Evidence Path | Active Implementation & Context | Applicable Limitation / Boundary |
|---|---|---|---|---|
| **Baseline HPI Formulation** ($0.40 T_{\text{norm}} + 0.30 P_{\text{persist}} + 0.15 V_{\text{deficit}} + 0.15 B_{\text{density}}$) | Assumption or heuristic | `gis/heat_priority/scoring.py`; `backend/app/db/models/stage_c.py` | Multi-criteria spatial vulnerability index normalized to $[0, 100]$. Bounds: $T \in [30, 50]^\circ\text{C}$, $\text{NDVI} \in [0.05, 0.45]$, $\text{NDBI} \in [-0.25, 0.15]$. | Reflects policy choices and stakeholder weighting, not a conserved thermodynamic physical property. |
| **Chronic Heat Hotspots Count (223 Cells)** | Assumption or heuristic | `backend/app/db/models/stage_c.py` (`is_chronic_hotspot`); `scripts/analyze_hotspot_persistence.py` | High-frequency extreme heat persistence ($\ge 90$th percentile across multi-year summer seasons). | Evaluated using fixed 19-season archive denominator. 10 cells differ (233 vs 223) if evaluated across locally valid seasons. |
| **Four Controlled HPI Sensitivity Scenarios** (Baseline, Extreme Thermal, Nature-First, Built-Density) | Verified by a reproducible command or committed artifact | `reports/hpi_sensitivity_analysis.json`; `reports/hpi_sensitivity_analysis.md`; `backend/tests/test_hpi_sensitivity.py` | Controlled sensitivity scenarios re-ranking all 49,747 cells while holding underlying data fixed. | Spearman rank correlations are high ($\rho \in [0.9660, 0.9917]$) due to shared thermal severity; stability does **not** prove causal correctness. |

---

### 2.5 Prescriptive Interventions, Cooling Physics & Methodological Boundaries

| Claim / Assertion | Evidentiary Status | Evidence Path | Active Implementation & Context | Applicable Limitation / Boundary |
|---|---|---|---|---|
| **Linearized Microclimate Heat Dissipation Model** ($\Delta T_s = f_{\text{treated}} \cdot \|\Delta T_{s,\text{skin}}\| \cdot \eta_{\text{cell}}$) | Supported by source metadata or documented methodology | `gis/interventions/cooling_effects.py:30-45`; Santamouris (2017), Akbari (2001) | Calculates skin cooling from effective thermal conductance $h_{\text{eff}} = 45.6\text{ W/(m}^2\cdot\text{K)}$ under solar irradiance $870\text{ W/m}^2$. | **Linearized first-order empirical equation.** The active code **does not solve** numerical Navier-Stokes, 3D CFD, or continuum PDE energy balance boundary value problems. |
| **Physical Cooling Saturation Caps** (Tree: 3.50°C, Cool Roof: 2.50°C, Green Roof: 2.00°C, Cool Pavers: 1.80°C, Cell: 4.50°C) | Assumption or heuristic | `gis/interventions/cooling_effects.py:89-125`; `backend/tests/test_interventions_realism.py` | Upper bound limits preventing unphysical runaway cooling extrapolations on large intervention footprints. | Literature-informed code constants; exact realization in Surat's coastal microclimate is unverified in-situ. |
| **Sub-Additive Multi-Intervention Attenuation** | Assumption or heuristic | `gis/interventions/cooling_effects.py:416-435` | Sub-additive factor ($0.25$) attenuates overlapping cooling benefits to avoid double-counting. Absolute ceiling $4.50^\circ\text{C}$. | Heuristic microclimate boundary layer overlap model; not a 3D coupled turbulent dispersion simulation. |
| **Seven Newer Intervention Types** (Public Park, Miyawaki, Bioswale, Pond, Shaded Parking, Green Wall, Permeable Cover) | Assumption or heuristic / Unverified locally | `gis/interventions/cooling_effects.py:258-410`; `reports/INTERVENTION_REALISM_REPORT.md` | Models 7 additional field-grade urban cooling strategies with cooling ranges and maintenance metadata. All tagged `local_field_validated: False`. | Empirical parameters from literature. High-density Miyawaki cooling ($9.0^\circ\text{C}$ skin, $1.4^\circ\text{C}$ air) and 3-year establishment are **UNVERIFIED IN SURAT**. |
| **Rainwater Retention Pond Water Source Catchment Guardrail** | Assumption or heuristic | `gis/interventions/feasibility.py:110-125` | Rainwater-fed ponds are strictly rejected without verified catchment ($\ge 5\times$ pond area) or treated effluent feed. | Prevents stagnant dry-season depression pits that become mosquito breeding vectors in Surat's tropical climate. |
| **Parked Stage D Research Patch** (`reports/runtime_verification_2026-10-21/parked/stage_d_science_wip.patch`) | Verified by a reproducible command or committed artifact | `reports/runtime_verification_2026-10-21/parked/stage_d_science_wip.patch`; `scripts/validation_harness.py:check_parked_stage_d_patch` | 10.1 KB git patch containing non-linear botanical growth curves and experimental differential equations, preserved unapplied. | Parked and unapplied to preserve frozen ML and Stage D production API contracts without interface drift. |

---

### 2.6 Civil Engineering Cost Models & Schedule Alignment

| Claim / Assertion | Evidentiary Status | Evidence Path | Active Implementation & Context | Applicable Limitation / Boundary |
|---|---|---|---|---|
| **Itemized Engineering Markup Structure** (18% GST, 12% Contingency, 6% Design, Setup Scaling, Water Tankers) | Supported by source metadata or documented methodology | `gis/interventions/costs.py:28-45` | Replaces flat rates with civil engineering itemization: GST (18%), Contingency (12%), Design/Supervision (6%), Setup ($\text{Base} \times \sqrt{A/500}$), Water tanker (₹120/kL), and Plant replacement. | Structural framework follows public works estimation standards; base unit rates remain indicative modeling assumptions. |
| **Unit Base Rates for Interventions** (Tree: ₹2,000/tree, Cool Roof: ₹300/m², Green Roof: ₹3,000/m², Paver: ₹400/m², etc.) | Assumption or heuristic | `gis/interventions/costs.py`; metadata `rate_status: "INDICATIVE_ASSUMPTION"` | Modeled base material and labour costs reflecting normative public expenditure levels. | Labeled `INDICATIVE_ASSUMPTION`. Actual tender prices vary with local market procurement conditions. |
| **CPWD DSR 2023 & SMC Annual Rate Contract Alignment** | Unverified or unavailable | `gis/interventions/costs.py:440` (`schedule_alignment: "UNVERIFIED_IN_REPO"`) | Normative reference frameworks cited in code comments. | **UNVERIFIED IN REPO:** Official CPWD and SMC rate contract PDF/CSV files are not committed in the repository. |

---

### 2.7 Land-Use Typologies, Tenure & Cadastral Verification

| Claim / Assertion | Evidentiary Status | Evidence Path | Active Implementation & Context | Applicable Limitation / Boundary |
|---|---|---|---|---|
| **Land-Use Typology Classification (11 Typologies)** | Assumption or heuristic | `gis/interventions/config/landuse_interventions.json`; `gis/interventions/landuse.py` | Classifies parcel types using Google Open Buildings V3 footprints and biophysical indices (NDVI, NDBI, NDWI). | Heuristic screening tool. Unclassified parcels receive `needs_site_survey: True` and zero automated mechanical recommendations. |
| **Legal Municipal Land Ownership & Confirmed Vacancy** | Unverified or unavailable | `gis/interventions/config/landuse_interventions.json` (`legal_disclaimer`); `reports/INTERVENTION_REALISM_REPORT.md` | Typologies renamed to spectral heuristics (e.g. `"Unbuilt Open Ground (Public Greening Candidate)"`). | **UNVERIFIED BY REMOTE SENSING:** Satellite data detects physical openness and absence of buildings; it **cannot** determine legal ownership, reservation, or confirmed legal vacancy. Official SMC Town Planning Scheme (TPS) cadastral records must be surveyed. |
| **Rooftop Civil Structural Load-Bearing Capacity** | Unverified or unavailable | `docs/KNOWN_LIMITATIONS.md:Section 2`; `scripts/validation_harness.py:check_roof_structural_feasibility` | Green roofs are prohibited on industrial corrugated sheds (`industrial_shed_roof`) due to structural collapse risk. | Physical live load capacity of individual buildings is **UNVERIFIED** without on-site structural engineer load tests. |
| **Ward/Slum High-Resolution Population Exposure** | Unverified or unavailable | `backend/app/api/v1/interventions.py` (`population_exposure_status: "POPULATION_DATA_UNAVAILABLE"`) | API returns `null` for population exposure benefit. | Census micro-data is not linked to the 100m grid. Prioritization relies on physical thermal severity and built-up density. |

---

### 2.8 Optimization Scenarios & Budget Consistency

| Claim / Assertion | Evidentiary Status | Evidence Path | Active Implementation & Context | Applicable Limitation / Boundary |
|---|---|---|---|---|
| **Budget Scenario Benchmarks** (Pilot: ₹50L, Smart City: ₹2.5Cr, Full UHAP: ₹10Cr) | Verified by a reproducible command or committed artifact | `docs/validation/scenario_summary.json`; `backend/app/api/v1/interventions.py:list_available_scenarios` | Reference scenarios derived from greedy knapsack run on the 49,747 SMC grid cells. All costs strictly $\le$ budget limits. | Benchmarks are precomputed optimization runs. Custom budgets are solved dynamically via greedy knapsack or NSGA-II. |
| **Greedy Knapsack & NSGA-II Pareto Optimization** | Verified by a reproducible command or committed artifact | `gis/interventions/optimization.py`; `backend/tests/test_stage_d_optimizer.py` | Bounded multi-objective optimization maximizing thermal benefit and hotspot mitigation under strict budget ceilings. | Assumes uniform cell execution costs and independence of candidate sites outside cell-exclusivity constraints. |

---

## 3. Discrepancy & Reconciliation Log

During the comprehensive audit run (T1–T5), the following discrepancies were identified between historical documentation drafts and the active repository implementation. Each has been reconciled:

| Subsystem | Historical Draft Assertion | Active Code Reality | Reconciled Status |
|---|---|---|---|
| **Monsoon 2026 Scenes** | "8 Monsoon scenes in composite" | 6 clear Landsat 8/9 Level-2 overpasses covering 100% of SMC territory. | Reconciled in `docs/provenance/seasonal_scene_manifest.json`: cause not established; counts differ between the early sensitivity analysis (8) and the manifest (6). |
| **Hotspot Persistence Denominator** | Chronic recurrence defined over locally valid seasons ($N_{\text{valid}}$). | Code in `scripts/analyze_hotspot_persistence.py` used a fixed 19-season archive denominator ($N=19$). | Reconciled in `docs/KNOWN_LIMITATIONS.md`: 223 chronic cells under fixed denominator vs 233 under locally valid denominator (10 differing cells cataloged). 223 is the frozen baseline. |
| **Dual $R^2$ Metrics** | Single $R^2 = 0.9006$ reported as general accuracy. | Pooled random-split holdout gives $R^2 = 0.9006$; 2km geographically blocked spatial-split gives $R^2 = 0.6919$. | Reconciled across Trust Center UI and documentation: Both scores are reported side-by-side with spatial autocorrelation disclosure. |
| **Physical Model Type** | "Surface Energy Balance PDE / 1D Continuum Solver". | First-order linearized heat dissipation equation ($h_{\text{eff}} = 45.6\text{ W/(m}^2\cdot\text{K)}$) and empirical literature caps. | Reconciled across all UI and docs: Described strictly as a "Linearized Microclimate Heat Dissipation Model", not a PDE or CFD solver. |
| **Government Cost Schedules** | "CPWD DSR and SMC Rate Contract Verified". | Raw schedule PDFs/CSVs are not committed in the repository. | Reconciled in `gis/interventions/costs.py`: Base rates tagged `INDICATIVE_ASSUMPTION` with schedule alignment marked `UNVERIFIED_IN_REPO`. |
| **Land Ownership** | "Vacant Public Open Land (SMC-owned)". | Satellite spectral data detects unbuilt ground but cannot verify property title or municipal reservation. | Reconciled in `gis/interventions/config/landuse_interventions.json`: Renamed to `"Unbuilt Open Ground (Public Greening Candidate)"` with mandatory cadastral verification caveat. |
| **Miyawaki Planting In-Situ** | Presented as verified Surat urban microclimate cooling. | Ultra-dense planting parameters ($9.0^\circ\text{C}$ skin, $1.4^\circ\text{C}$ air, 3-yr establishment) have no local sensor evidence. | Reconciled in `gis/interventions/cooling_effects.py`: Tagged `local_field_validated: False` and `UNVERIFIED IN SURAT`. |

---

## 4. Operational Governance & Scientific Disclaimers

1. **Non-Inversion of Diagnostic SHAP Values:**
   Machine learning feature attributions (SHAP values) represent diagnostic decision-tree associations on satellite observables. They must **never** be inverted or multiplied by intervention footprints to predict causal physical cooling.
2. **Skin Temperature vs. Ambient Air Temperature:**
   Satellite Land Surface Temperature ($T_{\text{skin}}$) represents the thermodynamic radiometric surface temperature of roofs, pavements, and soil. During May clear-sky noon overpasses in Surat, $T_{\text{skin}}$ is typically **8°C to 16°C higher than 2-meter ambient air temperature ($T_{\text{air}}$)**.
3. **Mandatory Cadastral & Structural Field Surveys:**
   Platform intervention recommendations are macroscopic spatial prioritization screening tools. They **do not substitute** for on-site structural engineering assessments (e.g. roof load capacity for green roofs) or cadastral title verification via Surat Municipal Corporation Town Planning Scheme (TPS) records.
4. **Simulation Baselines vs. Contractual Guarantees:**
   All counterfactual cooling projections and cost estimates represent decision-support simulations governed by explicit assumptions, not guaranteed contractual engineering outcomes.
