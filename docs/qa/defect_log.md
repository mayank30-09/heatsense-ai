# HEATSENSE AI: Master Defect Log
**Document Version:** 2.0.0 (Post-Engineering Verification)  
**Date:** October 30, 2026  
**Auditor / QA Lead:** Antigravity QA Engineering Team  
**Severity Levels:** Critical (P0), High (P1), Medium (P2), Low (P3)  
**Status Lifecycle:** LOGGED -> IN_PROGRESS -> FIXED -> VERIFIED_PASS

---

## 1. Defect Summary Table

| Defect ID | Severity / Priority | Associated Req | Component / File | Title / Short Description | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DEF-001** | **Critical (P0)** | R7 | `gis/interventions/optimization.py` | Exact DP Knapsack hangs/times out on budgets $\ge \text{₹2.5 Cr}$ due to $O(n \cdot W)$ 64M+ loop iterations. | **VERIFIED_PASS** |
| **DEF-002** | **Critical (P0)** | R7 | `backend/app/api/v1/interventions.py` | `/optimize` endpoint executes Exact DP unconditionally on line 810 even for Greedy or NSGA-II requests. | **VERIFIED_PASS** |
| **DEF-003** | **High (P1)** | R8 | `frontend/src/components/interventions/ScenarioLab.tsx` | Scenario Lab "Run optimization" does not forward algorithm, typologies, or strategy, and requires redundant manual click. | **VERIFIED_PASS** |
| **DEF-004** | **High (P1)** | R1 | `frontend/src/components/map/CellInspector.tsx` | Cell inspector outer container `max-h-[85vh]` causes clipping of methodological, survey, and provenance sections. | **VERIFIED_PASS** |
| **DEF-005** | **Medium (P2)** | R1, C5 | `frontend/src/components/map/CellInspector.tsx` | Cell inspector text hardcodes "10,000 m² (1 ha)" instead of true planar projected cell area ($9,273\text{ m}^2$). | **VERIFIED_PASS** |
| **DEF-006** | **High (P1)** | R2 | `frontend/src/components/map/MapShell.tsx`, `AreaDrawing.tsx` | Area Analysis displays season buttons despite HPI baseline being fixed to Summer 2026. | **VERIFIED_PASS** |
| **DEF-007** | **High (P1)** | R3 | `frontend/src/components/map/AreaRecommendationsPanel.tsx` | Area Analysis confines detailed recommendations to cramped 380px drawer without dedicated full-width report. | **VERIFIED_PASS** |
| **DEF-008** | **Medium (P2)** | R4 | `frontend/src/components/interventions/InterventionExplorer.tsx` | Explorer displays filter chips for retired types (Rainwater Pond, Modular Green Wall) that have 0 candidates. | **VERIFIED_PASS** |
| **DEF-009** | **Low (P3)** | C4 | `frontend/src/components/interventions/InterventionExplorer.tsx` | Header states "23 administrative localities" when areas are spatial clusters indexed to nearest OSM place points. | **VERIFIED_PASS** |
| **DEF-010** | **Medium (P2)** | R6 | `frontend/src/components/interventions/Optimization.tsx` | UI shows bare "0 packages" without explaining what a package is or diagnosing why zero packages qualify. | **VERIFIED_PASS** |
| **DEF-011** | **High (P1)** | C2 | `gis/interventions/rules.py` | `rules.py` hardcoded $-2.05^\circ\text{C}\dots-2.5^\circ\text{C}$ skin cooling, diverging from `cooling_effects.py` ($8.59^\circ\text{C}$). | **VERIFIED_PASS** |
| **DEF-012** | **High (P1)** | R13 | `gis/interventions/recommendations.py` | Polygon recommendations headline presents full ₹43.61 Cr build-out instead of phased municipal Phase 1 plan. | **VERIFIED_PASS** |

---

## 2. Detailed Defect Resolution & Verification Reports

### DEF-001: Exact DP Knapsack Hangs on Large Budgets
- **Root Cause:** Discretization unit was hardcoded at ₹5,000, creating $W = 5,000$ steps at ₹2.5 Cr and $W = 20,000$ at ₹10 Cr. For citywide scope ($N = 12,816$ packages), the inner loop executed $12,816 \times 5,000 = 64,080,000$ iterations in interpreted Python, taking $> 300\text{ s}$ and exceeding the HTTP 30s timeout.
- **Resolution:**
  1. Applied adaptive discretization unit: $\text{unit} = \max(100.0, \text{discretization\_unit\_inr}, \max(25000.0, \text{budget} / 1000.0))$, bounding $W \le 1,000$.
  2. Implemented candidate pool pre-filtering by strategy density metric when $N > 400$, keeping the top 400 Pareto-competitive packages.
- **Verification:** Benchmarked directly on 12,816 PostGIS database packages: Exact DP execution dropped from $>300\text{ s}$ to **0.1264 s** (2,400x speedup). Live API test returned HTTP 200 in 5.22s.
- **Status:** **VERIFIED_PASS**

### DEF-002: `/optimize` Endpoint Executes Exact DP Unconditionally
- **Root Cause:** Line 810 of `backend/app/api/v1/interventions.py` called `run_exact_knapsack_optimizer` unconditionally to construct the 10-point budget curve, even when the user requested `greedy` or `nsga2`.
- **Resolution:** Decoupled line 810. For `greedy`, the 10-point budget curve is constructed directly from cumulative greedy points in $O(N \log N)$ (0.02s). For `exact`, the solution's pre-computed budget curve is reused.
- **Verification:** Greedy optimization endpoint execution verified at 0.021s algorithm runtime and 5.459s total HTTP turnaround with 10 budget curve points.
- **Status:** **VERIFIED_PASS**

### DEF-003: Scenario Lab Navigation Omits Parameters
- **Root Cause:** `onSwitchToOptimization` in `ScenarioLab.tsx` only passed `simBudget`, discarding focus strategy, algorithm, and enabled typology filters.
- **Resolution:**
  1. Extended `onSwitchToOptimization` signature to accept full `ScenarioOptimizationConfig`.
  2. Wired custom simulator to forward `simBudget`, `simFocus`, `enabledTypes`, `autoRun: true`, and `source`.
  3. Added `initialConfig` prop to `Optimization.tsx` with auto-run idempotency guard (`hasAutoRunRef`) and an `AUTO-CONFIGURED` notification banner.
- **Verification:** Unit tests passing; verified end-to-end parameter passing from custom simulator into Optimization view.
- **Status:** **VERIFIED_PASS**

### DEF-004 & DEF-005: Cell Inspector Layout Clipping & Projected Area
- **Root Cause:** Outer aside used `max-h-[85vh]` with single scroll container, clipping survey prerequisites and provenance. Area was textually stated as nominal "10,000 m² (1 ha)".
- **Resolution:**
  1. Restructured `CellInspector.tsx` into a flex-column layout: fixed header, scrollable body (`min-h-0 overflow-y-auto`), dedicated survey prerequisites and sensor provenance panels.
  2. Corrected planar projected cell area to $9,273\text{ m}^2$ ($0.927\text{ ha}$) based on UTM 32643 dimensions ($93.21\text{ m} \times 99.48\text{ m}$).
- **Verification:** Vitest tests pass; production bundle build succeeds; responsive across 1366×768, 1920×1080, and mobile viewports.
- **Status:** **VERIFIED_PASS**

### DEF-006 & DEF-007: Area Analysis Season Decoupling & Dedicated Full View
- **Root Cause:** Area Analysis displayed seasonal selection buttons despite authoritative HPI baseline being fixed to Summer 2026. Detailed polygon results were confined to a cramped 380px drawer.
- **Resolution:**
  1. Removed season buttons in Area Analysis mode in `LayerControls.tsx`; replaced with read-only notice: *"Analysis Baseline: Summer 2026 (Authoritative HPI Composite)"*.
  2. Added dedicated full-width modal spatial report (`max-w-5xl`) in `MapShell.tsx` triggered by *"View Full Spatial Report →"* button, preserving map selection upon return.
- **Verification:** `navigation.test.tsx` updated and passing (4/4 tests). Full modal report verified.
- **Status:** **VERIFIED_PASS**

### DEF-008 & DEF-009: Explorer Typology Pruning & Locality Clarity
- **Root Cause:** `InterventionExplorer.tsx` displayed filter chips for `rainwater_fed_pond` and `green_wall` which had 0 eligible packages due to missing DEM and facade data. Banner claimed "Surat's 23 administrative localities".
- **Resolution:**
  1. Removed unassessable typologies from `TYPE_CONFIG` and filter chips.
  2. Clarified banner text: *"across Surat's 23 spatial locality clusters (indexed to nearest OpenStreetMap place points in SMC domain)"*.
- **Verification:** `ClusterExplorer.test.tsx` passing; 9 assessable typologies displayed; 0 retired types rendered.
- **Status:** **VERIFIED_PASS**

### DEF-010: Package Definition & Diagnostic Reporting
- **Root Cause:** UI displayed bare "0 pkgs" without context, and lacked an explicit definition of what a package represents.
- **Resolution:**
  1. Added tooltip explainer: *"A package is a group of contiguous cells in one locality receiving the same intervention, funded as one municipal project. The optimizer chooses whole packages rather than isolated cells."*
  2. Replaced bare zero with diagnostic badge *"0 (requires site data)"* and added comprehensive empty-state diagnostic cards citing missing datasets.
- **Verification:** Vitest test suite passing; empty state diagnostics verified.
- **Status:** **VERIFIED_PASS**

### DEF-011: Cooling Thermodynamics Reconciliation
- **Root Cause:** `rules.py` hardcoded $-2.05^\circ\text{C}\dots-2.5^\circ\text{C}$ skin cooling from air temperature literature, diverging from `cooling_effects.py` first-principles energy balance ($8.59^\circ\text{C}$).
- **Resolution:** Updated `rules.py` cool roof rule to reference $-8.59^\circ\text{C}$ raw surface skin cooling on treated coating ($\Delta\alpha = 0.45, I = 870\text{ W/m}^2, h_{\text{eff}} = 45.6\text{ W/m}^2\text{K}$), noting cell-diluted equivalent ($-1.29^\circ\text{C}$ to $-2.20^\circ\text{C}$) and stating that ambient 2m air temperature is unmodeled.
- **Verification:** Unit tests and canonical optimization tests passing (36/36).
- **Status:** **VERIFIED_PASS**

### DEF-012: Phased Implementation Realism
- **Root Cause:** Polygon recommendation headline presented total unphased build-out cost across 100% of the polygon footprint.
- **Resolution:** Updated `gis/interventions/recommendations.py` to structure `cost_rollup` with `phase1_headline` (10% pilot plan) as the primary municipal recommendation alongside `full_potential_upper_bound` (100% theoretical envelope).
- **Verification:** Reconciled response structure tested; backwards compatibility preserved.
- **Status:** **VERIFIED_PASS**
