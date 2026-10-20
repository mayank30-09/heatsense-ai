# HEATSENSE AI — Stage D Feasibility, Candidate Generation & Optimization Report

**Date:** October 2026  
**Target Municipality:** Surat Municipal Corporation (SMC), Gujarat, India  
**System Status:** FULLY IMPLEMENTED, SCIENTIFICALLY RECONCILED & EMPIRICALLY VERIFIED  
**Test Suite:** 24 Automated Tests Passing (17 Unit + 7 FastAPI Integration Tests)

---

## 1. Executive Summary

Stage D completes the urban heat decision-support pipeline of HEATSENSE AI, transforming Stage C Heat Priority Index (HPI) scores and chronic hotspot classifications into actionable, cost-constrained, and evidence-grounded physical heat mitigation scenarios.

### Core Architectural Capabilities Implemented:

1. **Spatial Candidate Generation (`gis/interventions/candidates.py`):**
   - Synthesizes viable physical interventions across 4 supported intervention typologies: Urban Tree Canopy, Reflective Cool Roofs, Extensive Green Roofs, and Permeable Cool Pavements.
   - Binds candidates to authoritative 100m × 100m SMC analytical grid cells with stable geometric polygons in EPSG:4326.

2. **Hard Feasibility Constraints Engine (`gis/interventions/feasibility.py`):**
   - Enforces statutory SMC study boundary containment.
   - Filters out micro-slivers (< 100 m² usable area).
   - Eliminates water body and wetland conflicts ($NDWI > 0.05$).
   - Verifies land-cover suitability ($NDBI > -0.10$ for roofs; $NDVI < 0.55$ for open canopy additions).
   - Enforces structured rejection logging (`RejectionReason`) for all disqualified candidates.

3. **Traceable Municipal Cost Modeling (`gis/interventions/costs.py`):**
   - Calibrated against CPWD, Gujarat PWD, and Surat Municipal Corporation (SMC) schedule of rates (2024–2025).
   - Tree planting: ₹3,500 / tree (procurement ₹800, installation & tree guards ₹1,200, 3-year establishment maintenance ₹1,500).
   - Cool roof coatings: ₹350 / m² (material ₹250, labor ₹100, ₹5,000 fixed setup per site).
   - Extensive green roofs: ₹3,600 / m² (modular trays ₹2,800, waterproofing ₹800, ₹15,000 structural engineering).
   - Cool pavements: ₹450 / m² (reflective sealcoat ₹300, labor ₹150, ₹8,000 setup).
   - Explicit uncertainty bounds (±15% to ±25%) attached to every estimate.

4. **Calibrated Microclimate Cooling & Portfolio Metric Models (`gis/interventions/cooling_effects.py`):**
   - **Absolute Prohibition of SHAP-as-Multiplier Fallacy:** SHAP attributions represent decision-tree feature selection on satellite observables, not causal cooling physics.
   - Implements empirical peer-reviewed microclimate models (Bowler et al. 2010, Santamouris et al. 2017, Akbari et al. 2001).
   - Logarithmic diminishing returns for tree canopy additions (saturation cap: 3.50°C).
   - Albedo radiative displacement models for cool roofs (saturation cap: 2.50°C).
   - Sub-additive overlap attenuation for multi-intervention cells with an absolute physical cooling ceiling of 4.50°C.
   - **Rigorous Mathematical Formulation of Regional Portfolio Metrics:**
     - **Extensive Portfolio Thermal Benefit ($B_{\text{portfolio}}$, in °C·m²):**
       $$B_{\text{portfolio}} = \sum_{i=1}^{K} A_i \times \Delta T_i$$
       Extensive, partition-invariant thermal quantity that strictly conserves benefit under site subdivision or parcel re-aggregation.
     - **Treated-Area-Weighted Mean Local Cooling ($\overline{\Delta T}_{\text{treated}}$, in °C):**
       $$\overline{\Delta T}_{\text{treated}} = \frac{B_{\text{portfolio}}}{\sum_{i=1}^{K} A_i} = \frac{\sum_{i=1}^{K} A_i \Delta T_i}{\sum_{i=1}^{K} A_i}$$
       Represents the average estimated microclimatic surface temperature reduction within the directly treated footprint.
     - **Citywide Area-Average Direct-Footprint Cooling ($\Delta T_{\text{citywide}}$, in °C):**
       $$\Delta T_{\text{citywide}} = \frac{B_{\text{portfolio}}}{A_{\text{domain}}} = \frac{\sum_{i=1}^{K} A_i \Delta T_i}{461{,}630{,}791\text{ m}^2}$$
       Evaluated over the authoritative SMC statutory municipal domain area ($461.630791\text{ km}^2$ in EPSG:32643). Untreated urban cells contribute zero direct temperature delta ($\Delta T = 0.0^\circ\text{C}$) under the documented baseline assumption of zero regional advective coupling.
     - **Prohibition of Intensive Temperature Summation:** Temperature reductions are intensive variables and must never be summed across geographically disjoint sites.
     - **Population Exposure Status:** Explicitly set to `POPULATION_DATA_UNAVAILABLE` until an authoritative, verified census raster is integrated. Population exposures are never synthetically fabricated.

5. **Dual Optimization Engines (`gis/interventions/optimization.py`):**
   - **Baseline Constrained Greedy Knapsack Optimizer:** Ranks candidates by extensive thermal cost-effectiveness ratio:
     $$P_i = \frac{A_i \times \Delta T_i \times \text{HPI}_i \times (1.5 \text{ if chronic})}{\text{Cost}_i} \quad \left[\frac{\text{°C}\cdot\text{m}^2}{\text{INR}}\right]$$
     Greedily selects top-ranked interventions subject to budget constraints and strict 1-candidate-per-cell exclusivity.
   - **NSGA-II Multi-Objective Evolutionary Optimizer:** Generates true non-dominated Rank 1 Pareto fronts across 3 unit-consistent objectives:
     1. Minimize Total Investment Cost (INR ₹)
     2. Maximize Extensive Heat Priority-Weighted Thermal Benefit ($\sum A_i \Delta T_i \text{HPI}_i$ in °C·m²)
     3. Maximize Chronic Hotspot Mitigations (count)

6. **Full-Stack Persistence & API Integration:**
   - Database tables: `stage_d_intervention_candidates`, `stage_d_scenario_results`.
   - Alembic migration `b2c3d4e5f6a7` adds extensive and area-weighted metric columns (`portfolio_thermal_benefit_c_m2`, `treated_area_m2`, `mean_local_cooling_c`, `citywide_cooling_c`, `domain_area_m2`, `heat_priority_weighted_benefit_c_m2`, `population_exposure_status`) with server defaults and backwards-compatible legacy aliases.
   - FastAPI REST endpoints: `/api/v1/interventions/candidates`, `/candidates/{id}`, `/optimize`, `/scenarios`.

---

## 2. Empirical Validation Results

### 2.1 Optimization Benchmark Runs & Provenance Audit

During the initial Stage D development phase, benchmark runs were recorded using a prototype implementation. Below is the historical record alongside the scientific audit findings:

#### Historical Prototype Benchmark Record (Deprecated — Obsolete Cumulative Cooling Sums)

| Algorithm | Budget Limit (INR) | Total Cost (INR) | Interventions | Historical "Total Cooling" (Deprecated) | Historical "Heat-Weighted" (Deprecated) | Chronic Hotspots Mitigated | Budget Utilization |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline Greedy Knapsack** | ₹10,000,000 (1 Cr) | ₹9,870,000 | 48 | ~~84.60°C~~ *(Invalid)* | ~~52.45~~ *(Invalid)* | 16 | 98.7% |
| **NSGA-II Pareto Sol 1 (Max Cooling)** | ₹15,000,000 (1.5 Cr) | ₹14,750,000 | 68 | ~~126.80°C~~ *(Invalid)* | ~~81.20~~ *(Invalid)* | 24 | 98.3% |
| **NSGA-II Pareto Sol 2 (Balanced Trade-Off)** | ₹15,000,000 (1.5 Cr) | ₹11,200,000 | 52 | ~~98.40°C~~ *(Invalid)* | ~~64.10~~ *(Invalid)* | 21 | 74.7% |
| **NSGA-II Pareto Sol 3 (Low Budget Entry)** | ₹15,000,000 (1.5 Cr) | ₹6,450,000 | 31 | ~~59.20°C~~ *(Invalid)* | ~~39.80~~ *(Invalid)* | 14 | 43.0% |

#### Provenance and Scientific Audit Findings:
1. **Invalidity of Historical Temperature Sums:**
   The historical values `84.60°C` (mean $\approx 1.76^\circ\text{C}$ across 48 sites), `126.80°C` (mean $\approx 1.86^\circ\text{C}$ across 68 sites), `98.40°C` (mean $\approx 1.89^\circ\text{C}$ across 52 sites), and `59.20°C` (mean $\approx 1.91^\circ\text{C}$ across 31 sites) were computed by naively summing local temperature reductions ($\sum \Delta T_i$). Because temperature is an intensive thermodynamic state variable, adding temperatures across geographically disjoint parcels is physically meaningless and invalid for regional cooling interpretation.
2. **Missing Input Artifacts:**
   The exact candidate-level inputs for this historical prototype run—specifically, the selected candidate IDs, individual cell usable footprint areas ($A_i$), and local baseline LST values—were not persisted to the database (`stage_d_scenario_results` contains 0 rows) or to any versioned artifact manifest.
3. **Strict Non-Fabrication Protocol:**
   In accordance with rigorous scientific engineering standards, because the original candidate footprint areas are unavailable, corrected extensive values (°C·m²) or area-weighted citywide deltas (°C) cannot and must not be guessed or fabricated. The historical figures above are retained solely for traceability, with an explicit designation that **they are invalid and superseded**.
4. **Verified Mathematical Identities (Test Suite Demonstration):**
   The corrected engine implementation and its mathematical identities have been independently verified through reproducible scenarios in `backend/tests/test_stage_d_cooling_metrics.py`:
   - **Partition Invariance:** Splitting a 2,000 m² site with 2.40°C cooling into four 500 m² sub-candidates preserves the exact extensive benefit ($4{,}800\text{ °C}\cdot\text{m}^2$) and treated-area mean ($2.40^\circ\text{C}$), whereas naive summation would have erroneously quadrupled the metric to $9.60^\circ\text{C}$.
   - **Equal-Area Disjoint Cooling:** Two disjoint 1,500 m² cells each achieving 2.0°C local cooling yield an area-weighted treated mean of $2.0^\circ\text{C}$ (never $4.0^\circ\text{C}$), an extensive benefit of $6{,}000\text{ °C}\cdot\text{m}^2$, and a citywide domain cooling of $\approx 0.000013^\circ\text{C}$.
   - **Strict Constraint Enforcement:** All solutions guarantee $TotalCost \le BudgetLimit$, strict cell exclusivity (at most 1 intervention per 100m grid cell), and Pareto Rank = 1.

---

### 2.2 Scientific Assumptions, Metric Distinctions & Limitations

To ensure full transparency for municipal urban planners and researchers, the following distinctions and scientific limitations govern all Stage D outputs:

#### Metric Definitions & Distinctions:
1. **Area-Integrated Estimated LST Reduction ($B_{\text{portfolio}}$, °C·m²):**
   An extensive measure of total thermal mitigation capacity. It reflects the product of the treated surface area and the local estimated temperature drop. This metric is scale-consistent and partition-invariant.
2. **Mean Estimated LST Reduction Over Treated Area ($\overline{\Delta T}_{\text{treated}}$, °C):**
   The area-weighted average cooling within the physical footprint of the interventions. It indicates the localized microclimatic relief experienced directly within treated sites.
3. **Estimated Citywide Area-Average Direct-Footprint LST Reduction ($\Delta T_{\text{citywide}}$, °C):**
   The extensive benefit distributed across the entire $461.63\text{ km}^2$ municipal jurisdiction ($461{,}630{,}791\text{ m}^2$). Untreated grid cells contribute zero direct cooling ($\Delta T = 0.0^\circ\text{C}$). For municipal portfolios spanning several hectares, this value is naturally on the order of $10^{-4}$ to $10^{-2}\text{ }^\circ\text{C}$.

#### Scientific Assumptions & Operational Limitations:
- **Surface Temperature (LST) vs. Pedestrian-Level Air Temperature ($T_{\text{air}}$):**
  All modeled reductions represent estimated Land Surface Temperature (LST) deltas derived from satellite radiometric analogues and empirical boundary-layer equations. They **do not represent validated 2-meter ambient air temperature ($T_{\text{air}}$)**. Ambient air temperatures are mediated by 3D turbulent advection, atmospheric mixing, and wind corridors that require computational fluid dynamics (CFD) or meso-scale atmospheric models (e.g., WRF-UCM) to resolve.
- **Untreated Footprint Assumption:**
  The citywide metric assumes that unmitigated cells experience zero cooling benefit. Potential downwind microclimatic "park cool island" (PCI) advection plumes are not modeled, making citywide estimates conservative lower bounds of direct footprint mitigation.
- **Synthetic Candidate Geometries:**
  Until municipal parcel and cadastral GIS layers are ingested, candidate intervention areas are assigned based on empirical land-cover suitability assumptions (e.g., 1,500 m² for tree canopies, 2,000 m² for cool roofs) rather than field-surveyed boundary polygons.
- **Absence of Local Empirical Microclimate Calibration:**
  Cooling equations are grounded in published international meta-analyses (Bowler et al. 2010, Santamouris et al. 2017). They have not yet been empirically calibrated against a high-density microclimate sensor or eddy covariance tower network within Surat.
- **Demographic Exposure:**
  Population exposure metrics are reported as `None` with status `POPULATION_DATA_UNAVAILABLE` until official ward-level Census/SMC population data is formally joined.

---

## 3. Test Coverage

The complete Stage D test suite contains **24 automated tests** (17 unit and scientific regression tests + 7 FastAPI integration tests), all passing:

### Candidate Generation & Microclimate Physics (`backend/tests/test_stage_d_candidates.py`)
- `test_candidate_generation_all_types`: **PASS**
- `test_scientific_cooling_models_and_fallacy_prevention`: **PASS**
- `test_combined_cooling_sub_additivity`: **PASS**
- `test_cost_models_positive_and_detailed`: **PASS**
- `test_hard_feasibility_boundary_and_water_rejection`: **PASS**

### Optimization Engines (`backend/tests/test_stage_d_optimizer.py`)
- `test_baseline_greedy_optimizer_budget_and_exclusivity`: **PASS**
- `test_nsga2_pareto_front_generation`: **PASS**
- `test_optimizer_determinism_under_fixed_seed`: **PASS**

### API Integration & Scenarios (`backend/tests/test_stage_d_api.py`)
- `test_candidates_endpoint_basic`: **PASS**
- `test_candidates_endpoint_type_and_bbox_filtering`: **PASS**
- `test_candidate_detail_endpoint`: **PASS**
- `test_optimize_endpoint_greedy`: **PASS**
- `test_optimize_endpoint_nsga2`: **PASS**
- `test_optimize_endpoint_unsupported_algorithm`: **PASS**
- `test_reference_scenarios_endpoint`: **PASS**

### Scientific Cooling Metrics & Spatial Area Accounting (`backend/tests/test_stage_d_cooling_metrics.py`)
- `test_two_equal_area_cells_do_not_sum_temperatures`: **PASS**
- `test_unequal_area_cells_weighted_correctly`: **PASS**
- `test_untreated_area_handled_according_to_documented_domain`: **PASS**
- `test_duplicate_candidate_cannot_inflate_benefit`: **PASS**
- `test_splitting_candidate_preserves_aggregate_benefit`: **PASS**
- `test_greedy_and_nsga2_consistent_benefit_semantics`: **PASS**
- `test_budget_limits_feasibility_and_site_exclusivity`: **PASS**
- `test_api_responses_and_persisted_scenarios`: **PASS**
- `test_grid_coverage_and_area_conservation_reconciliation`: **PASS**

**Result: 24 / 24 Stage D Tests Passing.**
