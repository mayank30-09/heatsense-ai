# HEATSENSE AI — Intervention Realism and Scientific Guardrails Report (T5)

**Document Status:** OFFICIAL PRODUCTION AUDIT REPORT (Task T5)  
**Date:** October 26, 2026  
**Target Domain:** Surat Municipal Corporation (SMC), Gujarat, India (461.63 km² territory, 49,747 analytical 100m grid cells)  
**Active Branch:** `audit-fixes`  
**Cryptographic Integrity Invariant:** 41/41 Verified SHA-256 Checksums (`[PASS]`)  
**Test Suite Verification:** 10/10 Realism Tests + 10/10 Stage D API Tests + 72/72 Frontend Vitest Tests + Clean Vite Production Build  

---

## 1. Executive Summary

This report establishes the evidence basis, physical model definitions, cost provenance, land-use boundaries, and scientific guardrails for the Stage D Intervention and Optimization Engine in HEATSENSE AI.

In accordance with strict scientific integrity principles:
1. **Physical Modeling Transparency:** The active production code is verified to be a first-order **linearized heat dissipation model** ($h_{\text{eff}} = 45.6\text{ W/(m}^2\cdot\text{K)}$) with empirical literature saturation bounds, **not** a numerical CFD or PDE surface-energy-balance continuum solver. All UI and documentation claims attributing calculations to a continuum PDE solver have been corrected.
2. **Cost Provenance & Schedule Alignment:** Intervention costs incorporate itemized engineering markups ($18\%$ GST, $12\%$ contingency, $6\%$ design/supervision, non-linear setup scaling $\text{Base} \times \sqrt{A/500}$, water tanker ₹120/kL, and whole-life maintenance). Base unit rates are explicitly labeled `INDICATIVE_ASSUMPTION`. Schedule alignment with CPWD DSR and SMC annual rate contracts is tagged `UNVERIFIED_IN_REPO` because official government schedule PDFs/CSVs are not committed in the repository.
3. **Land Tenure & Vacancy Heuristics:** Satellite spectral features (vegetation deficit $V_{\text{def}} \ge 0.50$, low NDBI, absence of Google Open Buildings footprints) identify unbuilt, permeable ground. They **do not** determine legal municipal ownership or legal vacancy. Typology titles and descriptions have been updated to spectral/site-type heuristic terminology (`"Unbuilt Open Ground (Public Greening Candidate)"`), mandating cadastral record verification before municipal procurement.
4. **Newer Interventions & Miyawaki Plantation Guardrails:** All 7 newer intervention types are tagged with `local_field_validated: False`. Miyawaki ultra-dense afforestation cooling ($9.0^\circ\text{C}$ skin, $1.4^\circ\text{C}$ air) and 3-year establishment assumptions are documented as `UNVERIFIED IN SURAT` due to the lack of local in-situ microclimatic sensor network data in Surat's coastal semi-arid / humid tropical climate.
5. **Scenario Budget Consistency:** Reference planning scenarios (Pilot ₹50 Lakhs, Smart City Phase 1 ₹2.5 Crores, Full UHAP ₹10 Crores) are verified to match `docs/validation/scenario_summary.json` and originate from a reproducible greedy knapsack optimization run on the 49,747 SMC grid cells.
6. **Scientific Freeze Preserved:** No changes were made to `artifacts/ml_freeze/*`, `data/**`, COGs, trained models, or stored Stage C HPI scores. The checksum verifier passes with 41/41 matches.

---

## 2. Parameter Audit Matrix across All 11 Intervention Types

Each intervention parameter in the active production code is audited and classified into three distinct evidential categories:
- **DERIVED / SOURCED:** Parameter is mathematically derived from physical constants or directly traceable to peer-reviewed urban microclimate literature.
- **ASSUMPTION:** Parameter is an explicit engineering heuristic, empirical ceiling, or conservative design rule.
- **UNVERIFIED IN REPO / LOCAL CLIMATE:** Parameter reflects normative practice or literature from other regions, but raw official government schedules are not committed in the repo or local in-situ sensor validation in Surat is unavailable.

| # | Intervention Type | Skin Cooling ($\Delta T_s$) | Ambient Air Cooling ($\Delta T_{\text{air}}$) | Cost Rate Status | Schedule Alignment | Evidential Classification |
|---|---|---|---|---|---|---|
| 1 | `tree_canopy` (Neem / Native) | $7.50^\circ\text{C}$ | $0.94^\circ\text{C}$ | `INDICATIVE_ASSUMPTION` (₹3,500/tree all-in) | `UNVERIFIED_IN_REPO` (SMC Parks & Gardens) | **DERIVED:** Beer-Lambert LAI=3.2 + stomatal latent flux $LE=70\text{ W/m}^2$; cooling cap ($3.50^\circ\text{C}$) is `ASSUMPTION`. |
| 2 | `cool_roof` (High-SRI Acrylic) | $8.59^\circ\text{C}$ (aged) | $0.50^\circ\text{C}$ | `INDICATIVE_ASSUMPTION` (₹300/m² base) | `UNVERIFIED_IN_REPO` (CPWD DSR Item 12.58) | **DERIVED:** Solar irradiance $870\text{ W/m}^2 \times \Delta\alpha(+0.45) / 45.6\text{ W/(m}^2\cdot\text{K)}$; cooling cap ($2.50^\circ\text{C}$) is `ASSUMPTION`. |
| 3 | `green_roof` (Extensive RCC) | $6.20^\circ\text{C}$ | $0.35^\circ\text{C}$ | `INDICATIVE_ASSUMPTION` (₹3,000/m² base) | `UNVERIFIED_IN_REPO` (Specialized Vendor / IGBC) | **ASSUMPTION:** Substrate thermal mass + vegetation transpiration (Akbari 2001); cooling cap ($2.00^\circ\text{C}$) is `ASSUMPTION`. |
| 4 | `cool_pavement` (Reflective Pavers) | $4.77^\circ\text{C}$ | $0.40^\circ\text{C}$ | `INDICATIVE_ASSUMPTION` (₹400/m² base) | `UNVERIFIED_IN_REPO` (CPWD DSR Item 16.68) | **DERIVED:** Solar irradiance $870\text{ W/m}^2 \times \Delta\alpha(+0.25) / 45.6\text{ W/(m}^2\cdot\text{K)}$; cooling cap ($1.80^\circ\text{C}$) is `ASSUMPTION`. |
| 5 | `public_park_native_trees` | $8.20^\circ\text{C}$ | $1.10^\circ\text{C}$ | `INDICATIVE_ASSUMPTION` (₹600/m² base) | `UNVERIFIED_IN_REPO` (SMC Parks & Gardens) | **ASSUMPTION / DERIVED:** Multi-tier canopy + turf (Bowler 2010); local cooling in Surat is `UNVERIFIED IN SURAT`. |
| 6 | `dense_miyawaki_plantation` | $9.00^\circ\text{C}$ | $1.40^\circ\text{C}$ | `INDICATIVE_ASSUMPTION` (₹950/m² base) | `UNVERIFIED_IN_REPO` (SMC CSR Plantation) | **UNVERIFIED IN SURAT:** Ultra-dense planting (3–5 saplings/m²); cooling magnitude and 3-yr establishment unverified by local in-situ sensors. |
| 7 | `bioswale_rain_garden` | $4.50^\circ\text{C}$ | $0.45^\circ\text{C}$ | `INDICATIVE_ASSUMPTION` (₹800/m² base) | `UNVERIFIED_IN_REPO` (CPWD Road Drainage) | **ASSUMPTION:** Engineered sand-gravel filter media; dry-season performance and local Surat cooling effect is `UNVERIFIED IN SURAT`. |
| 8 | `rainwater_fed_pond` | $2.50^\circ\text{C}$ | $0.80^\circ\text{C}$ | `INDICATIVE_ASSUMPTION` (₹1,200/m² base) | `UNVERIFIED_IN_REPO` (SMC Water Works) | **ASSUMPTION / SOURCED:** Theeuwes et al. (2013) boundary-layer evaporative breeze; dry-season replenishment in Surat is `UNVERIFIED IN SURAT`. |
| 9 | `shaded_parking_structure` | $12.00^\circ\text{C}$ | $0.60^\circ\text{C}$ | `INDICATIVE_ASSUMPTION` (₹2,400/m² base) | `UNVERIFIED_IN_REPO` (CPWD DSR Item 10.25) | **DERIVED:** 100% direct solar irradiance interception over dark asphalt (Akbari 2001); local microclimate impact is `UNVERIFIED IN SURAT`. |
| 10 | `green_wall` (Exterior Trellis) | $5.80^\circ\text{C}$ | $0.40^\circ\text{C}$ | `INDICATIVE_ASSUMPTION` (₹3,300/m² base) | `UNVERIFIED_IN_REPO` (Commercial Vendor Quotes) | **ASSUMPTION:** Perez et al. (2014) vertical facade shading; summer maintenance and water survival in Surat is `UNVERIFIED IN SURAT`. |
| 11 | `permeable_ground_cover` | $4.00^\circ\text{C}$ | $0.35^\circ\text{C}$ | `INDICATIVE_ASSUMPTION` (₹270/m² base) | `UNVERIFIED_IN_REPO` (CPWD DSR Item 16.12) | **DERIVED:** Substrate conduction and porosity modification (Santamouris 2017); local field effect is `UNVERIFIED IN SURAT`. |

---

## 3. Physical Methodology Audit: Linearized Heat Dissipation vs PDE Solvers

### 3.1 Active Production Formulation
The active cooling engine in `gis/interventions/cooling_effects.py` implements a first-order linearized surface heat dissipation equation:

$$\Delta T_s = f_{\text{treated}} \times |\Delta T_{s,\text{skin}}| \times \eta_{\text{cell}} \times f_{\text{thermal\_contrast}}$$

where:
- $f_{\text{treated}} = \min(f_{\max}, A_{\text{usable}} / A_{\text{cell}})$ represents the fraction of the 100m cell treated.
- $|\Delta T_{s,\text{skin}}| = \frac{K_{\downarrow} \cdot \Delta\alpha}{h_{\text{eff}}}$ represents the maximum direct skin cooling at solar noon.
- $K_{\downarrow} = 870\text{ W/m}^2$ is the astronomical clear-sky solar irradiance for Surat (May 15, ~10:30 IST).
- $h_{\text{eff}} = h_c + h_r = 38.9 + 6.5 = 45.6\text{ W/(m}^2\cdot\text{K)}$ is the linearized effective surface conductance.
- $\eta_{\text{cell}} = 1.00$ is the cell radiometric coupling factor (range $[0.75, 1.00]$).
- $f_{\text{thermal\_contrast}} = \text{clamp}(0.85, 1.15, 1.0 + 0.02 \times (T_{\text{baseline}} - 40.0))$.

### 3.2 Correction of Scientific Descriptions
The system **does not solve** the transient coupled Navier-Stokes equations, 3D Reynolds-Averaged Navier-Stokes (RANS) computational fluid dynamics, or partial differential surface-energy-balance boundary value problems (e.g., ENVI-met or SOLWEIG). Describing the active code as a "Surface Energy Balance PDE Solver" was scientifically misleading.

All instances across:
- `frontend/src/components/interventions/ScenarioLab.tsx`
- `frontend/src/components/interventions/InterventionExplorer.tsx`
- `frontend/src/components/common/ScienceGlossaryModal.tsx`
- `frontend/src/App.tsx`
- `gis/interventions/cooling_effects.py`

have been corrected to specify **"Linearized Microclimate Heat Dissipation Model"** with effective conductance $h_{\text{eff}} = 45.6\text{ W/(m}^2\cdot\text{K)}$.

---

## 4. Cost Engineering Audit & Itemized Markups

### 4.1 Cost Breakdown Structure
Flat-rate multipliers have been replaced with a transparent civil engineering itemization in `gis/interventions/costs.py`:
1. **Materials Procurement:** Unit costs for containers, pavers, elastomeric coatings, drainage mats, tensile fabric, or basalt aggregates.
2. **Labour & Surface Preparation:** Earthwork, surface pressure washing, primer application, or structural erection.
3. **Statutory Taxes:** Goods and Services Tax (**GST at 18.0%** statutory rate).
4. **Physical & Price Contingency:** **12.0%** expected contingency (range 10–15%).
5. **Engineering Design & Supervision:** **6.0%** (range 5–8% depending on complexity).
6. **Non-Linear Setup & Mobilization:** Scaled with site area:
   $$\text{Setup}(A) = \text{Base} \times \max\left(1.0, \sqrt{\frac{A}{A_{\text{ref}}}}\right)$$
   (e.g., Base ₹2,500 for trees, ₹5,000 for cool roofs, ₹15,000 for green roofs and parks).
7. **Water Supply Provision:** Dedicated non-potable water tanker trips modeled at ₹120 per 1,000 L (m³) for initial establishment.
8. **Plant Mortality Replacement:** 15% mortality replacement provision for tree canopy and public parks (85% survival rate); 10% provision for Miyawaki (90% survival rate).
9. **Whole-Life Cost Horizons:** 3-year establishment maintenance and 10-year major recoat / overhaul lifecycle cost.

### 4.2 Disclaimer on Schedule Alignment
While the itemized structure reflects standard public works estimation methodology:
- Official CPWD Delhi Schedule of Rates (DSR 2023–2024) and SMC Parks and Gardens annual rate contract schedules **are not committed as raw files in the repository**.
- All cost rates are returned with metadata:
  ```json
  {
    "rate_status": "INDICATIVE_ASSUMPTION",
    "schedule_alignment": "UNVERIFIED_IN_REPO (Model estimates based on published public norms; official schedule PDFs/CSVs not in repo)"
  }
  ```
- Before municipal procurement, tender schedules must be populated with current prevailing SMC Schedule of Rates (SoR).

---

## 5. Land-Use, Ownership, and Vacancy Guardrails

### 5.1 Spectral Heuristic Limitations
Satellite spectral indices and remote sensing features:
- High vegetation deficit ($V_{\text{def}} \ge 0.50$)
- Low normalized difference built index ($\text{NDBI} \le 0.10$)
- Absence of Google Open Buildings footprints ($N_{\text{buildings}} = 0, A_{\text{roof}} = 0$)

indicate **unbuilt, low-canopy, permeable or bare ground**. They **cannot verify legal ownership, parcel tenure, municipal reservation status, or confirmed legal vacancy**.

### 5.2 Typology Name & Description Adjustments
To prevent users from mistaking spectral classifications for legal title:
- `vacant_public_open_land`: Renamed from *"Vacant Public Open Land"* to **"Unbuilt Open Ground (Public Greening Candidate)"**. Added legal disclaimer: *"Satellite data identifies spectral openness and lack of structures; it does NOT confirm legal municipal ownership or legal vacancy, which must be verified via municipal cadastral records."*
- `vacant_private_land`: Renamed from *"Vacant Private Land"* to **"Unbuilt Open Ground (Private / Non-Municipal)"**.
- `institutional_campus`: Renamed to **"Institutional Campus (Heuristic)"** to indicate OSM amenity tag origin.
- Added top-level `"legal_disclaimer"` to `gis/interventions/config/landuse_interventions.json`.
- Updated `TYPOLOGY_LABELS` in `frontend/src/components/map/AreaRecommendationsPanel.tsx`.

---

## 6. Seven Newer Interventions & Miyawaki Planting Review

### 6.1 Functionality Preserved
All 7 newer interventions remain available in the prescriptive catalog, optimization search space, and scenario lab:
1. `public_park_native_trees`
2. `dense_miyawaki_plantation`
3. `bioswale_rain_garden`
4. `rainwater_fed_pond`
5. `shaded_parking_structure`
6. `green_wall`
7. `permeable_ground_cover`

### 6.2 Explicit Guardrails Applied
1. In `gis/interventions/cooling_effects.py`, each of the 7 types has `"local_field_validated": False`.
2. For `dense_miyawaki_plantation`, the provenance string explicitly warns:
   `"UNVERIFIED IN SURAT: High-density Miyawaki planting microclimate cooling values (9.0°C skin, 1.4°C air) and 3-year establishment assumptions are unverified by in-situ sensors in Surat's coastal semi-arid / humid tropical climate."`
3. Catchment constraint on `rainwater_fed_pond` is maintained: ponds without verified stormwater catchment ($\ge 5\times$ pond area) or treated effluent feed are rejected (`RejectionReason.UNVERIFIED_WATER_SOURCE`), preventing stagnant dry-season depression pits that become mosquito breeding vectors.

---

## 7. Scenario Benchmarks & Optimizer Consistency

### 7.1 Provenance Verification
The three reference scenarios returned by `GET /api/v1/interventions/scenarios`:
- **Pilot Tier (₹50 Lakhs):** 39 cells, 36,915 m² treated, 585 trees, 7,500 m² cool roof. Cost: ₹49,72,500 (99.45% budget utilization).
- **Smart City Phase 1 (₹2.5 Crores):** 138 cells, 152,130 m² treated, 2,208 trees, 30,240 m² cool roof, 10,800 m² cool pavers. Cost: ₹2,49,72,000 (99.89% budget utilization).
- **Full UHAP (₹10 Crores):** 371 cells, 465,355 m² treated, 6,678 trees, 86,800 m² cool roof, 36,000 m² cool pavers, 6,800 m² green roof. Cost: ₹9,99,63,000 (99.96% budget utilization).

derive from `docs/validation/scenario_summary.json` and represent a precomputed run of the baseline greedy knapsack optimizer on the 49,747 SMC grid cells.

### 7.2 API Enrichment
`GET /api/v1/interventions/scenarios` now dynamically reads `scenario_summary.json` when available, returning explicit provenance metadata:
```json
{
  "provenance": "PRECOMPUTED_OPTIMIZER_BENCHMARK",
  "optimizer_algorithm": "BASELINE_GREEDY_KNAPSACK",
  "optimization_basis": "Derived from greedy knapsack run on Stage C HPI priority grid under physical feasibility constraints"
}
```

---

## 8. Test Evidence Log

### 8.1 Backend Realism Test Suite (`backend/tests/test_interventions_realism.py`)
```text
backend/tests/test_interventions_realism.py::test_open_public_plot_never_receives_cool_or_green_roof PASSED [ 10%]
backend/tests/test_interventions_realism.py::test_industrial_shed_never_receives_green_roof_due_to_structural_collapse PASSED [ 20%]
backend/tests/test_interventions_realism.py::test_rainwater_pond_rejected_without_verified_water_source PASSED [ 30%]
backend/tests/test_interventions_realism.py::test_optimizer_total_cost_never_exceeds_budget PASSED [ 40%]
backend/tests/test_interventions_realism.py::test_unclassified_parcel_requires_site_survey_and_returns_zero_recommendations PASSED [ 50%]
backend/tests/test_interventions_realism.py::test_itemized_engineering_cost_model_breakdown PASSED [ 60%]
backend/tests/test_interventions_realism.py::test_landuse_typologies_no_unsupported_ownership_claims PASSED [ 70%]
backend/tests/test_interventions_realism.py::test_newer_interventions_unverified_local_field_guardrails PASSED [ 80%]
backend/tests/test_interventions_realism.py::test_cooling_caps_and_saturation_bounds PASSED [ 90%]
backend/tests/test_interventions_realism.py::test_scenario_budget_consistency_and_provenance PASSED [100%]
============================= 10 passed in 0.15s ==============================
```

### 8.2 Stage D API Test Suite (`backend/tests/test_stage_d_api.py`)
```text
backend/tests/test_stage_d_api.py::test_candidates_endpoint_basic PASSED [ 10%]
backend/tests/test_stage_d_api.py::test_candidates_endpoint_type_and_bbox_filtering PASSED [ 20%]
backend/tests/test_stage_d_api.py::test_candidate_detail_endpoint PASSED [ 30%]
backend/tests/test_stage_d_api.py::test_optimize_endpoint_greedy PASSED  [ 40%]
backend/tests/test_stage_d_api.py::test_optimize_endpoint_nsga2 PASSED   [ 50%]
backend/tests/test_stage_d_api.py::test_optimize_endpoint_unsupported_algorithm PASSED [ 60%]
backend/tests/test_stage_d_api.py::test_reference_scenarios_endpoint PASSED [ 70%]
backend/tests/test_stage_d_api.py::test_optimize_endpoint_auth_and_dev_token_removal PASSED [ 80%]
backend/tests/test_stage_d_api.py::test_candidates_filtering_sorting_and_caching PASSED [ 90%]
backend/tests/test_stage_d_api.py::test_diminishing_returns_endpoint PASSED [100%]
============================= 10 passed in 8.62s ==============================
```

### 8.3 Frontend Vitest Suite
```text
Test Files  12 passed (12)
     Tests  72 passed (72)
  Duration  936ms
```

### 8.4 Frontend Vite Production Build
```text
✓ built in 2.69s
dist/assets/ScenarioLab-DskQh8g0.js            24.89 kB │ gzip:  5.95 kB
dist/assets/InterventionExplorer-CMYhGrYT.js   31.42 kB │ gzip:  7.46 kB
dist/assets/MapShell-BAIuGEHZ.js              360.83 kB │ gzip: 92.96 kB
```

---

## 9. Remaining Unverified Items Summary

In compliance with the scientific audit mandate, the following items remain explicitly marked **UNVERIFIED**:
1. **Local In-Situ Microclimate Cooling:** Actual in-situ skin and air temperature cooling from implemented interventions in Surat has not been validated against localized weather station / sensor networks. All cooling figures remain simulation estimates governed by stated parameter assumptions.
2. **Official Schedule PDFs/CSVs in Repo:** Raw CPWD Delhi Schedule of Rates (DSR 2023) and SMC Parks and Gardens annual rate contract documents are not committed in the repository. Unit base rates are modeled engineering heuristics.
3. **Cadastral Land Ownership & Tenure:** Satellite spectral characteristics identify physical ground openness, but legal municipal ownership and zoning title remain unverified in the platform and require official SMC Town Planning Scheme (TPS) cadastral records.
4. **Miyawaki 3-Year Establishment in Surat:** Multi-tier sapling survival (90%) and rapid 36-month canopy self-sufficiency under coastal semi-arid / monsoon conditions in Surat are unverified by empirical municipal longitudinal studies.
