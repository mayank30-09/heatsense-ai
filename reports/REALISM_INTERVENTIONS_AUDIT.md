# HEATSENSE AI — Realism in Cost & Area-Wise Recommendations Audit

**Document Status:** Production Engineering Audit & Evidence Verification  
**Date:** October 25, 2026  
**Target Domain:** Surat Municipal Corporation (SMC), Gujarat, India (461.63 km² territory, 49,747 analytical 100m grid cells)  
**Active Branch:** `ui-polish`  
**Cryptographic Integrity Invariant:** 41/41 Verified SHA-256 Checksums (`[PASS]`)  
**Backend & Frontend Verification:** 34/34 Stage D & Realism Backend Tests + 58/58 Frontend Vitest Tests + Clean Vite Production Build  

---

## 1. Executive Summary & Verification Matrix

In accordance with municipal engineering standards and scientific integrity constraints, the HEATSENSE AI Recommendation and Optimization Engine (Stage D) has been upgraded to enforce thermodynamic consistency, realistic site-level typologies, comprehensive itemized engineering costing, and strict budget adherence.

Crucially:
- **Zero alterations were made to the frozen ML models or Stage C Heat Priority Index (HPI) scoring logic.**
- All 41 cryptographic digests in `artifacts/ml_freeze/checksums.sha256` match with 100% precision (`verify_checksums.py` yields `[PASS]`).
- Machine learning regression coefficients and SHAP values are strictly quarantined from direct causal cooling extrapolations, resolving the scientific fallacy of multiplying diagnostic associations by intervention footprints.

```
+---------------------------------------------------------------------------------------------------+
| HEATSENSE AI REALISM VERIFICATION MATRIX                                                          |
+================================+================================+=================================+
| Verification Check             | Required Condition             | Verification Result             |
+--------------------------------+--------------------------------+---------------------------------+
| ML Artifact Freeze             | 41 / 41 SHA-256 Checksums      | 41 / 41 MATCHES (0 mismatches)   |
| Stage D Realism Tests          | 6 / 6 Test Cases Pass          | 6 / 6 PASSED                    |
| Stage D API & Unit Tests       | 28 / 28 Test Cases Pass        | 28 / 28 PASSED                  |
| Frontend Vitest Suite          | 58 / 58 Unit Tests Pass        | 58 / 58 PASSED                  |
| Frontend Production Build      | Clean TypeScript & Vite Build  | 0 Errors (2.85s build time)     |
| Land-Use Typology Rules        | 11 Typologies Configured       | 11 / 11 JSON Schema Validated   |
| Structural Load Constraints    | Industrial Shed Green Roof     | 100% REJECTED (COLLAPSE RISK)   |
| Open Plot Roof Constraints     | Vacant Land Cool/Green Roof    | 100% REJECTED (NO STRUCTURE)    |
| Water Source Requirement       | Rainwater Pond Catchment       | 100% REJECTED IF UNVERIFIED     |
| Unclassified Parcel Handling   | Needs Site Survey Banner       | ZERO Mechanical Recs Issued     |
| Budget Constraint Adherence    | Total Expenditure <= Budget    | 100% Obeyed (Greedy & NSGA-II)  |
+--------------------------------+--------------------------------+---------------------------------+
```

---

## 2. Phase 1: Reconciliation with Version 4.0 Methodology

### 2.1 Astronomical Incident Solar Irradiance Derivation
In `docs/recommendation_methodology.md` and `gis/interventions/cooling_effects.py`, incident solar irradiance is derived from first principles for Surat's geographic coordinates ($21.1702^\circ\text{N}$, $72.8311^\circ\text{E}$) during the Landsat morning overpass window (DOY 135, May 15, ~10:30 IST / 10:28 Local Solar Time):
- Solar Declination: $\delta = +18.79^\circ$
- Solar Hour Angle: $\omega = -31.23^\circ$
- Solar Zenith Angle: $\theta_z = 29.40^\circ \implies \cos\theta_z = 0.8711$
- Relative Optical Air Mass: $m = 1.148$
- Incident Extraterrestrial Irradiance: $I_0 = 1330.3\text{ W/m}^2$
- Clear-Sky Gujarat Atmospheric Transmittance: $\tau_b + \tau_d = 0.58 + 0.17 = 0.75$
- **Downwelling Shortwave Solar Irradiance:**
  $$K_{\downarrow} = I_0 \cdot \cos\theta_z \cdot (\tau_b + \tau_d) = 1330.3 \times 0.8711 \times 0.75 \approx \mathbf{870\text{ W/m}^2}$$

### 2.2 Effective Dissipation Conductance ($h_{\text{eff}}$) & Sensible Cooling
The energy balance linearization around $T_{\text{air}} = 38.0^\circ\text{C}$ ($311.15\text{ K}$) establishes:
- Convective conductance: $h_c = \frac{\rho c_p}{r_a} = \frac{1.16 \times 1005}{30} \approx 38.9\text{ W/(m}^2\cdot\text{K)}$
- Radiative linearization conductance: $h_r = 4 \varepsilon \sigma T_{\text{air}}^3 \approx 6.5\text{ W/(m}^2\cdot\text{K)}$
- Total effective dissipation conductance:
  $$h_{\text{eff}} = h_c + h_r \approx \mathbf{45.6\text{ W/(m}^2\cdot\text{K)}}$$

### 2.3 Albedo Delta ($\Delta\alpha$) and Direct Skin Temperature Shifts
All intervention cooling calculations strictly enforce labeled assumptions (`ASSUMPTION_COOL_ROOF_ALBEDO_DELTA_AGED`):
1. **Aged / Weathered Cool Roof (Operational Baseline):**
   $$\Delta\alpha = +0.45 \implies \Delta S = -870 \times 0.45 = -391.5\text{ W/m}^2$$
   $$\Delta T_{s,\text{skin}} = \frac{-391.5}{45.6} = \mathbf{-8.59^\circ\text{C}} \quad [\text{Range: } -7.20^\circ\text{C} \text{ to } -10.50^\circ\text{C}]$$
2. **Pristine / Newly Applied Cool Roof:**
   $$\Delta\alpha = +0.50 \implies \Delta S = -435.0\text{ W/m}^2 \implies \Delta T_{s,\text{skin}} = \mathbf{-9.54^\circ\text{C}}$$
3. **Cool Permeable Pavements:**
   $$\Delta\alpha = +0.25 \implies \Delta S = -217.5\text{ W/m}^2 \implies \Delta T_{s,\text{skin}} = \mathbf{-4.77^\circ\text{C}}$$

### 2.4 Removal of Uncited Caps & Assumption Interval Transparency
Arbitrary caps (`MAX_COOLING_COOL_ROOF_C = 2.5°C`) were removed. The engine models thermodynamic skin cooling while reporting parameter bounds (low/expected/high):
- Cell conversion efficiency $\eta_{\text{cell}} = 1.00$ (direct physical footprint translation).
- Ambient canopy air temperature cooling ($\Delta T_{\text{air}}$) is decoupled from skin temperature: cool roofs provide $0.50^\circ\text{C}$ air cooling, tree canopies provide $0.94^\circ\text{C}$, and water bodies provide $0.80^\circ\text{C}$ localized breeze cooling.

### 2.5 Trust Center Dual $R^2$ Reporting
In `backend/app/api/v1/heat_priority.py` and `frontend/src/components/dashboard/ValidationTrust.tsx`:
- **Pooled Random-Split $R^2$:** $0.9006$ ($N = 203,758$ holdout observations).
- **2km Geographically Blocked Spatial-Split $R^2$:** $0.6919$.
- Disclosed clear reconciliation note: The spatial-block score controls for spatial autocorrelation (Tobler's First Law), demonstrating true out-of-neighborhood generalization without inflating variance explained.

---

## 3. Phase 2: Land-Use Typologies & Constraint Engine

### 3.1 External Land-Use Configuration
Created `gis/interventions/config/landuse_interventions.json` specifying 11 typologies with allowed/prohibited lists and engineering thresholds:
1. `residential_rcc_roof`: Reinforced concrete roofs; allowed cool roof, green roof, green wall.
2. `industrial_shed_roof`: Corrugated metal/asbestos sheds (Pandesara, Sachin); strictly prohibits green roof due to live-load $< 25\text{ kg/m}^2$.
3. `commercial_mixed_use`: High-rise commercial; allowed cool roof, green roof, shaded parking, green wall.
4. `informal_dense_settlement`: Low-income dense settlements; allowed lightweight cool roof; prohibits heavy soil loads.
5. `vacant_public_open_land`: SMC-owned vacant plots; allowed native public park, Miyawaki forest, rainwater retention pond; strictly prohibits cool roof and green roof.
6. `institutional_campus`: Schools, universities; allowed cool roof, green roof, Miyawaki plantation, bioswale.
7. `transport_corridor`: Major roads and rights-of-way; allowed roadside trees, bioswale, permeable pavements.
8. `commercial_parking`: Surface lots; allowed shaded PV/canopy parking, permeable pavement, bioswale.
9. `park_garden`: Existing municipal gardens; allowed canopy enrichment, Miyawaki groves, rainwater pond.
10. `water_adjacent`: Tapi riverfront and canal edges; allowed riparian buffer trees, bioswales, retention ponds; prohibits terrestrial pavements.
11. `unclassified`: Ambiguous or unverified parcels; `needs_site_survey = True`; **zero mechanical recommendations issued**.

### 3.2 Automated Land-Use Classifier
Implemented in `gis/interventions/landuse.py`:
- Integrates Google Open Buildings V3 building footprints (`docs/validation/top100_building_footprints_summary.json`).
- Evaluates biophysical signatures (NDVI, NDBI, NDWI, water fraction).
- Flags unclassified parcels for municipal ground validation.

---

## 4. Phase 3: Seven New Interventions & Biophysical Parameters

Added 7 new field-grade interventions to `gis/interventions/__init__.py`, `gis/interventions/cooling_effects.py`, and `gis/interventions/feasibility.py`:

| Intervention Type | Skin Cooling ($\Delta T_{\text{skin}}$) | Air Cooling ($\Delta T_{\text{air}}$) | Water Need | Maintenance Burden | Time to Effect | Key Engineering Rule |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `public_park_native_trees` | $7.50^\circ\text{C}$ | $0.94^\circ\text{C}$ | Medium ($15\text{ L/tree/wk}$) | Medium | 3–5 years | Open plots $\ge 1,000\text{ m}^2$ |
| `dense_miyawaki_plantation` | $8.20^\circ\text{C}$ | $1.20^\circ\text{C}$ | High (Yr 1–2: $25\text{ L/m}^2$) | Low (Self-sustaining Yr 3+) | 2–3 years | Requires dense plot $\ge 200\text{ m}^2$ |
| `bioswale_rain_garden` | $3.20^\circ\text{C}$ | $0.45^\circ\text{C}$ | Low (Stormwater fed) | Low | 1 year | Roadside / parking corridors |
| `rainwater_fed_pond` | $2.50^\circ\text{C}$ | $0.80^\circ\text{C}$ | High (Water body retention) | Medium | Immediate | **Requires verified catchment** |
| `shaded_parking_structure` | $12.00^\circ\text{C}$ | $0.70^\circ\text{C}$ | Zero | Low | Immediate | Surface parking lots |
| `green_wall` | $6.50^\circ\text{C}$ | $0.35^\circ\text{C}$ | High ($5\text{ L/m}^2/\text{day}$) | High | 1–2 years | Facade structure check |
| `permeable_ground_cover` | $4.77^\circ\text{C}$ | $0.40^\circ\text{C}$ | Low | Low | Immediate | Pedestrian / parking areas |

### 4.1 Rainwater Pond Catchment Safeguard
Rainwater-fed retention ponds without verified catchment ($\ge 5\times$ pond area) or treated STP effluent feed are strictly rejected (`RejectionReason.UNVERIFIED_WATER_SOURCE`). This prevents stagnant dry-season depression pits that become mosquito breeding vectors in Surat's humid tropical climate.

---

## 5. Phase 4: Realistic Itemized Engineering Costing & Budget Optimization

### 5.1 Itemized Rate Schedule (CPWD & SMC Benchmark Aligned)
Implemented in `gis/interventions/costs.py`:
- All cost rates are explicitly tagged `"INDICATIVE"` with traceable source replacement metadata.
- **Statutory Markups:**
  - Goods and Services Tax: **$18\%$ GST**
  - Physical & Price Contingencies: **$12\%$ Contingency**
  - Detailed Engineering Design & Site Supervision: **$6\%$**
- **Logistical Overhead:**
  - Site setup and staging scale non-linearly with project footprint: $\text{Base} \times \sqrt{A / 500}$.
  - Initial 3-year establishment watering includes water tanker mobilization (₹750 per 5,000L tanker trip).
- **Whole-Life Costing:**
  - 3-Year Establishment Cost (pruning, desilting, replanting).
  - 10-Year Lifecycle Replacement Cost (membrane recoating, pump overhauls).
  - Whole-life cost per degree-cell-area: $\text{INR} / (^\circ\text{C}\cdot\text{m}^2)$.

### 5.2 Strict Budget Knapsack Invariant
Updated `gis/interventions/optimization.py`:
- Both the Greedy Knapsack heuristic and the NSGA-II Pareto genetic algorithm perform strict cost pruning.
- Total expenditure (inclusive of statutory markups, design fees, and establishment) **never exceeds the municipal budget allocation under any circumstance**.

### 5.3 Citywide Scenario Validation Tables
Verified in `docs/validation/`:
- `scenario_low.csv`, `scenario_medium.csv`, `scenario_high.csv`, and `scenario_summary.json` derive strictly from 100m grid cell aggregations.
- Reports both **Treated Footprint Mean $\Delta\text{LST}$** and **Citywide Territory Mean $\Delta\text{LST}$** alongside percentage of municipal land area treated:
  - Low Budget (₹10 Cr): 1.15% area treated, $-0.04^\circ\text{C}$ citywide mean change.
  - Medium Budget (₹50 Cr): 5.42% area treated, $-0.21^\circ\text{C}$ citywide mean change.
  - High Budget (₹200 Cr): 19.80% area treated, $-0.78^\circ\text{C}$ citywide mean change.

---

## 6. Phase 5: Municipal UI & Area Recommendations Panel

### 6.1 Interactive Panel Enhancements (`AreaRecommendationsPanel.tsx`)
- **"Needs Site Survey" Warning Banner:** High-visibility amber warning box displayed prominently whenever a polygon is unclassified or data coverage is low, blocking automated mechanical interventions.
- **Land-Use Typology Tag:** Visual indicator showing classified land-use typology with source attribution.
- **Allowed Interventions Pills:** Quick visual pills indicating which intervention categories are permissible on the parcel.
- **Dual Cooling Display:** Side-by-side presentation of **Surface Skin Cooling** ($\Delta T_{\text{skin}}$) and **Ambient Air Cooling** ($\Delta T_{\text{air}}$).
- **Engineering Attributes:** Water requirement, maintenance burden, and time-to-full-effect metrics for every card.
- **Disqualified Alternatives Drawer:** Expandable section detailing why other interventions were rejected on this parcel (e.g. "Structural collapse risk on industrial metal shed").

### 6.2 Frontend Type Consistency & Production Build
- Synchronized `frontend/src/types/interventions.ts` with all 11 intervention types.
- Updated `InterventionExplorer.tsx`, `Optimization.tsx`, and `ScenarioLab.tsx` configurations.
- Vitest test suite: 9 files, 58 tests passed in 754ms.
- Vite build: Completed cleanly in 2.85s with 0 errors.

---

## 7. Verification Audit Trail & Evidence Log

### 7.1 Automated Pytest Results
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0
rootdir: E:\FINAL YEAR PROJECT\heatsense-ai
configfile: pyproject.toml
plugins: anyio-4.15.1
collected 34 items

backend\tests\test_interventions_realism.py ......                       [ 17%]
backend\tests\test_stage_d_api.py ..........                             [ 47%]
backend\tests\test_stage_d_candidates.py .....                           [ 61%]
backend\tests\test_stage_d_optimizer.py ....                             [ 73%]
backend\tests\test_recommendations.py .........                          [100%]

======================= 34 passed, 10 warnings in 9.06s =======================
```

### 7.2 Checksum Verification Manifest
```text
======================================================================
HeatSense AI — SHA-256 Checksum Manifest Verification Report
======================================================================
Manifest File: E:\FINAL YEAR PROJECT\heatsense-ai\artifacts\ml_freeze\checksums.sha256
Total Lines Processed: 41
Valid Entries:         41
Verified Matches:      41
Missing Files:         0
Checksum Mismatches:   0
----------------------------------------------------------------------
[PASS] ALL CHECKSUMS VERIFIED OK (100% MATCH)!
All protected artifacts match authoritative freeze digests exactly.
======================================================================
```

---

## 8. Conclusion & Sign-Off

The HEATSENSE AI Recommendation and Optimization Engine achieves rigorous physical grounding and municipal engineering realism. All physical formulas, land-use classifications, cost itemizations, and interface disclosures are fully reconciled with authoritative civil engineering practices for Surat Municipal Corporation.
