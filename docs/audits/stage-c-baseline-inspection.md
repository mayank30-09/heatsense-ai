# HEATSENSE AI — Stage C Baseline Inspection & Spatial/Scientific Audit Report

**Document ID:** `AUDIT-STAGE-C-BASELINE-01`  
**Target Region:** Surat Municipal Corporation (SMC), Gujarat, India  
**Date of Execution:** 2026-10-04  
**Evaluator:** Senior GIS Engineer, Geospatial Data Architect, Urban Heat Researcher, ML Engineer, PostgreSQL/PostGIS Engineer, Scientific Validation Engineer  
**Status:** **PHASE 1 COMPLETE — VERIFIED EMPIRICAL BASELINE RECORDED**  

---

## 1. Executive Summary & Audit Authority

This baseline audit establishes the verified empirical ground truth of the **HEATSENSE AI** repository, database, GIS vector layers, multi-band raster composites, machine learning artifacts, and existing test suites prior to the implementation of **Stage C: LST-Based Heat Priority Index (HPI)**.

Every statement in this report is grounded in direct, reproducible inspections executed on the repository files, running Docker containers, and active PostGIS databases. No schema details, artifact hashes, pixel counts, or test outcomes have been fabricated or assumed.

---

## 2. Repository and Git Baseline

### 2.1 Git Repository Status
- **Repository Root:** `e:\FINAL YEAR PROJECT\heatsense-ai`
- **Active Branch:** `feature/scientific-freeze-correction`
- **HEAD Commit:** `5dc4d74` (*chore(validation): complete pre-heat-priority real-working verification loop*)
- **Upstream Branches:**
  - `main`
  - `develop`
  - `feature/day1-bootstrap`
  - `origin/feature/day1-bootstrap`
- **Working Tree State:** Dirty (untracked and modified files preserved).
  - Tracked modifications: Audit logs, validation JSON artifacts, session configurations, and pre-heat-priority verification files.
  - Untracked files: Optical sentinel sensitivity scripts/artifacts and pre-existing draft inspection scripts.
  - **Preservation Assurance:** In strict adherence to Section 16 of the execution rules, zero working-tree resets, stashes, or destructive git commands were executed.

### 2.2 Environment & Runtime Alignment
- **Operating System:** Windows 10/11 x86_64
- **Python Runtime:** Python 3.12.10 (`.venv\Scripts\python.exe`)
- **Key Installed Scientific Packages:**
  - `rasterio`: 1.5.1
  - `geopandas`: 1.1.4
  - `shapely`: 2.0.7
  - `pandas`: 3.0.6
  - `numpy`: 2.5.3
  - `scikit-learn`: 1.9.1
  - `xgboost`: 3.4.1
  - `shap`: 0.52.0
  - `psycopg` (v3): 3.2.5
  - `sqlalchemy`: 2.0.38
  - `pytest`: 8.4.2

---

## 3. Database & PostGIS Baseline

### 3.1 Connection Configuration
- **Container Name:** `heatsense-postgis` (Image: `postgis/postgis:16-3.4`, Container ID: `82495a69f08e`)
- **Container Status:** Up 11+ hours (healthy)
- **Port Mapping:** `0.0.0.0:5433 -> 5432/tcp` (Host port: `5433`)
- **Database Engine:** PostgreSQL 16.4 on x86_64-pc-linux-musl
- **PostGIS Extension:** `POSTGIS="3.4.3 e365945" [EXTENSION] PGSQL="160" GEOS="3.9.0-CAPI-1.16.2" PROJ="7.2.1"`
- **Alembic Version in Database:** `e39ad56b8ec7` (Migration: `e39ad56b8ec7_add_osm_places.py`)

### 3.2 Table Inventory & Geometry Inspection
Querying `information_schema.tables`, `geometry_columns`, and `ST_GeometryType`:

| Table Name | Geometry Column | Geometry Type | SRID | Feature Count | Validity (`ST_IsValid`) | Extent / Envelope |
|---|---|---|:---:|:---:|:---:|---|
| **`study_areas`** | `geometry` | `POLYGON` | 4326 | 1 | **100% Valid (True)** | `POLYGON((72.68375 21.03399, 72.68375 21.32409, 72.96866 21.32409, 72.96866 21.03399, 72.68375 21.03399))` |
| **`admin_boundaries`** | `geometry` | `POLYGON` | 4326 | 0 | N/A (Empty table) | N/A |
| **`osm_places`** | `geometry` | `POINT` | 4326 | 44 | **100% Valid (True)** | Bounding Box: `[72.66528, 21.01368, 72.98766, 21.34829]` |
| **`alembic_version`** | None | None | None | 1 | N/A | Current version: `e39ad56b8ec7` |

### 3.3 Detailed Examination of Target Tables
1. **`study_areas`:**
   - Single row: `id = 1`, `name = "Surat Municipal Corporation"`, `code = "SURAT_SMC"`.
   - Stored attribute `area_km2`: `461.63079085086207 km²`.
   - Projected `EPSG:32643` (UTM Zone 43N) geometric area: **`461.630791 km²`**.
   - Geodesic ellipsoidal area (`ST_Area(geometry::geography) / 1e6`): **`461.418649 km²`**.
   - Geometric equality check: Exactly identical to `data/raw/boundaries/surat_smc_boundary.geojson` (`ST_AsText` match = `True`).
2. **`admin_boundaries`:**
   - Table exists with columns (`id`, `name`, `boundary_type`, `geometry`), but row count is **0**. No official administrative zone polygons (e.g. Athwa, Udhana) have been ingested into this table.
3. **`osm_places`:**
   - 44 OpenStreetMap locality points (21 with `inside_smc = True`, 23 peripheral settlements).
   - **Crucial Observation:** Geometry type is strictly `POINT`. Point geometries have **0 area** (`ST_Area = 0.0`). They cannot be used as administrative zone boundaries or for vector-polygon aggregation.

---

## 4. Raster Inventory & Analytical Grid Metadata

### 4.1 Multi-Band Analytical COG Inventory
Across `data/processed/analytical/`, exactly **19 multi-band Cloud Optimized GeoTIFFs (COGs)** exist:
- **2022:** `winter`, `summer`, `monsoon`, `post_monsoon` (4 COGs)
- **2023:** `winter`, `summer`, `monsoon`, `post_monsoon` (4 COGs)
- **2024:** `winter`, `summer`, `monsoon`, `post_monsoon` (4 COGs)
- **2025:** `winter`, `summer`, `monsoon`, `post_monsoon` (4 COGs)
- **2026:** `winter`, `summer`, `monsoon` (3 COGs)
*(Note: Post-monsoon 2026 is absent by design as production freeze preceded the acquisition window.)*

### 4.2 Structural Grid Alignment & Raster Metadata
Inspection of all 19 analytical COGs confirms 100% invariant spatial alignment:
- **Coordinate Reference System (CRS):** `EPSG:4326` (WGS84 Geodetic)
- **Raster Dimensions:** $318 \text{ columns} \times 324 \text{ rows} = 103,032 \text{ total grid cells}$
- **Pixel Grid Resolution:**
  - $\Delta \lambda = 0.0008983152841195215^\circ \text{ (Easting)}$
  - $\Delta \phi = 0.0008983152841195215^\circ \text{ (Northing)}$
- **Raster Origin (Top-Left Corner):**
  - $x_0 = 72.68358795339460^\circ\text{ E}$
  - $y_0 = 21.32420821442920^\circ\text{ N}$
- **Spatial Bounds:** `[72.6835879533946, 21.03315406237448, 72.96925221374461, 21.324208214429202]`
- **Band Count:** 10 bands per COG:
  1. `LST_C` (Float32, NoData = -9999.0)
  2. `NDVI` (Float32, NoData = -9999.0)
  3. `NDBI` (Float32, NoData = -9999.0)
  4. `NDWI` (Float32, NoData = -9999.0)
  5. `LST_OBS_COUNT` (Float32, NoData = -9999.0)
  6. `LST_QA_MEDIAN_K` (Float32, NoData = -9999.0)
  7. `QUALITY_FLAG` (Float32, NoData = -9999.0)
  8. `ELIGIBILITY` (Float32, NoData = -9999.0)
  9. `HOTSPOT_FREQUENCY` (Float32, NoData = -9999.0)
  10. `IS_PERSISTENT_HOTSPOT` (Float32, NoData = -9999.0)
- **Pixel Ground Dimensions (in EPSG:32643 UTM Zone 43N):**
  - Width: $\approx 93.25\text{ m}$
  - Height: $\approx 99.54\text{ m}$
  - Ground Area: $\approx 9,282.07\text{ m}^2 = 0.009282\text{ km}^2$ per nominal grid cell.

---

## 5. Protected Artifact Hashes & Scientific Freeze Manifest

The SHA-256 cryptographic hashes for the frozen ML and analysis artifacts were recalculated directly on disk:

| Protected Artifact Path | Canonical Expected SHA-256 | Verified Active SHA-256 | Audit Status |
|---|---|---|:---:|
| `artifacts/ml_freeze/xgb_tuned_policy_d.joblib` | `e1aedd4946b1b29823bdea66ea3ec7b9ba5f20c4ddbfdf6920c2e62e6b30b7c9` | `e1aedd4946b1b29823bdea66ea3ec7b9ba5f20c4ddbfdf6920c2e62e6b30b7c9` | **MATCH (PASS)** |
| `data/processed/sensitivity/policy_d/analysis.parquet` | `e824794e5ba2e26937ac40f55f5fd788adad70b1a6b23c6ab435b08223dd9997` | `e824794e5ba2e26937ac40f55f5fd788adad70b1a6b23c6ab435b08223dd9997` | **MATCH (PASS)** |
| `artifacts/ml_freeze/holdout_split.json` | `8a04b20c97b088ffc7d3f513ecd3e41007adea51ad16401f104529f40d8c1a2d` | `8a04b20c97b088ffc7d3f513ecd3e41007adea51ad16401f104529f40d8c1a2d` | **MATCH (PASS)** |
| `artifacts/ml_freeze/checksums.sha256` | 41 registered files | 41/41 verified matching on disk | **MATCH (PASS)** |

**Zero hash drift** has occurred. All protected Stage A/B inputs remain pristine and locked.

---

## 6. Spatial Coverage & Area Reconciliation Metrics

A rigorous spatial intersection calculation was executed between the 103,032 raster grid cells and the authoritative Surat boundary polygon in `EPSG:32643` (UTM Zone 43N):

| Metric # | Spatial Dimension / Parameter | Verified Value | Physical Meaning & Scientific Source |
|:---:|---|:---:|---|
| **1** | Total Authoritative SMC Boundary Area | **`461.630791 km²`** | True vector polygon area of `surat_smc_boundary.geojson` projected in `EPSG:32643`. |
| **2** | Cells whose footprints intersect the boundary | **`50,871 cells`** | Rasterization with `all_touched = True`. Includes boundary-straddling fringe cells. |
| **3** | Cells completely inside boundary (interior) | **`48,588 cells`** | Cells whose bounding box does not intersect the boundary perimeter line ($w_{ik} = 1.0$). |
| **4** | Boundary-clipped perimeter cells | **`2,283 cells`** | Cells intersected by the boundary perimeter line ($0 < w_{ik} < 1.0$). |
| **5** | Active Study Area Cells (`centroid_inside`) | **`49,747 cells`** | Rasterization with `all_touched = False` (centroid strictly inside municipal polygon). |
| **6** | Total nominal area of all 50,871 intersecting cells | **`472.207020 km²`** | Unclipped sum of cell footprints ($50,871 \times \text{area}$). Overestimates SMC by +2.29%. |
| **7** | Total nominal area of 49,747 centroid-inside cells | **`461.772581 km²`** | Unclipped sum of centroid-inside footprints. Differs from vector polygon by **+0.03%**. |
| **8** | Sum of clipped cell-footprint intersections | **`461.630791 km²`** | **Exact Area Conservation:** $\sum_{i=1}^{50871} \text{Area}(\text{cell}_i \cap \text{SMC}) \equiv \text{Area}(\text{SMC})$. Error = **0.000000%**! |
| **9** | Fractional weight range ($w_{ik}$) | **`[0.000009, 1.000000]`** | Fractional allocation strictly bounded within $[0, 1]$. |
| **10** | Sum of clipped area for 49,747 centroid-inside cells | **`459.550167 km²`** | Covers 99.55% of municipal territory (remaining 0.45% is in fringe cells where centroid fell outside). |

### 6.1 Reconciliation of Historical Inconsistencies
- **The "326 km²" Mystery:** Earlier exploratory scripts referenced ~326 km², which was the municipal extent of Surat prior to the 2020 urban expansion. The post-2020 official boundary is **461.63 km²**.
- **The "463.90 km²" Figure:** In previous draft documents, 49,747 cells were multiplied by a simplified nominal factor of $9,325.2\text{ m}^2 = 0.0093252\text{ km}^2$, producing $463.90\text{ km}^2$. Under exact UTM projection, the 49,747 cells have a nominal unclipped area of **461.77 km²**, and when exact geometric boundary intersection weighting is applied, the area conservation is **461.630791 km²** with zero error.

---

## 7. Temporal Data Model & Seasonal Observation Profile

Inspection of `data/processed/sensitivity/policy_d/analysis.parquet` (924,731 rows) across the 5-year monitoring period (2022–2026):

| Year | Season | Total Cell Rows | Valid Observed LST | Policy D ACCEPT | Policy D FLAG | Policy D EXCLUDE | $OBS \ge 4$ | $OBS \in [1, 3]$ | Optical Sentinels |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 2022 | Winter | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,747 | 0 | 0 |
| 2022 | Summer | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,747 | 0 | 0 |
| 2022 | Monsoon | 49,726 | 49,726 | 46,365 | 3,361 | 21 | 22,268 | 27,458 | **5** |
| 2022 | Post-Monsoon | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,745 | 2 | 0 |
| 2023 | Winter | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,746 | 1 | 0 |
| 2023 | Summer | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,747 | 0 | 0 |
| 2023 | Monsoon | 49,477 | 49,477 | 34,865 | 14,612 | 270 | 12,294 | 37,183 | 0 |
| 2023 | Post-Monsoon | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,747 | 0 | 0 |
| 2024 | Winter | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,747 | 0 | 0 |
| 2024 | Summer | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,747 | 0 | 0 |
| 2024 | Monsoon | 47,777 | 47,777 | 24,897 | 22,880 | 1,970 | 4,313 | 43,464 | **1** |
| 2024 | Post-Monsoon | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,747 | 0 | 0 |
| 2025 | Winter | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,746 | 1 | 0 |
| 2025 | Summer | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,747 | 0 | 0 |
| 2025 | Monsoon | 45,125 | 45,125 | 28,276 | 16,849 | 4,622 | 7,103 | 38,022 | **2** |
| 2025 | Post-Monsoon | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,743 | 4 | 0 |
| 2026 | Winter | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,745 | 2 | 0 |
| 2026 | Summer | 49,747 | 49,747 | 49,747 | 0 | 0 | 49,747 | 0 | 0 |
| 2026 | Monsoon | 36,168 | 36,168 | 16,318 | 19,850 | 13,579 | 4,370 | 31,798 | 0 |
| 2026 | Post-Monsoon | 0 | 0 | 0 | 0 | 49,747 | 0 | 0 | 0 |

### 7.1 Key Scientific Findings from the Temporal Inspection
1. **100% Complete Summer Observation Coverage:** In every single summer from 2022 to 2026, **all 49,747 cells** have valid observed LST, $OBS \ge 4$, zero optical sentinels, and 100% Policy D `ACCEPT` status. There are zero missing summer cells in the operational historical dataset.
2. **Monsoon Cloud Masking:** The monsoon season is the sole season exhibiting missing data (cloud mask exclusions: 21 in 2022, 270 in 2023, 1,970 in 2024, 4,622 in 2025, 13,579 in 2026).
3. **Location of Optical Sentinels:** All 8 optical sentinel rows in the 924,731-row archive occurred exclusively in the monsoon season (5 in 2022, 1 in 2024, 2 in 2025). Zero optical sentinels exist in summer, winter, or post-monsoon.

---

## 8. Existing Codebase & Pre-Stage-C Test Status

### 8.1 Existing Heat Priority Code Inspection
- `gis/heat_priority/scoring.py`: Contains a legacy 2-component formulation ($w_1 \cdot \text{severity} + w_2 \cdot \text{persistence}$) with weights (0.60, 0.40).
- `gis/heat_priority/lst_priority.py`: Calculates percentile ranking of observed LST.
- `gis/heat_priority/persistence.py`: Normalizes recurrence frequency.
- `gis/heat_priority/quality.py`: Evaluates observation quality confidence.
- *Status:* These files represent prototype stubs. They must be upgraded to the approved 4-component formulation ($T_{norm}, P_{persist}, V_{deficit}, B_{density}$) with explicit confidence multipliers and spatial/temporal schemas.

### 8.2 Pre-Stage-C Test Suite Execution
Running the full backend test suite (`pytest -v backend/tests`):
- **Tests Collected:** 114 tests
- **Tests Passed:** **114 passed**
- **Tests Failed:** **0 failed**
- **Warnings:** 24 deprecation warnings (rasterio matrix multiplication syntax).
- **Execution Time:** 38.29 seconds.

---

## 9. Identified Specification Contradictions & Proposed Corrections

| # | Topic | Identified Draft Contradiction | Root Cause | Proposed Definitive Correction |
|:---:|---|---|---|---|
| **1** | **Spatial Boundary & Area** | Draft mixed 461.63 km², 463.90 km², 49,747 cells, and 50,752 cells without explaining the difference. | Inconsistent denominator definitions (vector area vs nominal cell count vs raster bounding mask). | Formally separate: (a) Official Vector SMC Area = `461.630791 km²`, (b) Canonical Grid Cells = `49,747` (`all_touched=False`), (c) Exact Vector Intersection Area = `461.630791 km²` ($0.00\%$ error). |
| **2** | **Administrative Hierarchy** | Draft implied 100 m cells fall inside `osm_places` polygons. | `osm_places` table contains 44 `POINT` geometries, not polygons. `admin_boundaries` is empty (0 rows). | Clarify that point lookup is via nearest-neighbor distance (`ST_Distance`). Vector zonal aggregation requires polygon boundaries (once ingested into `admin_boundaries`). |
| **3** | **Confidence Index Math** | Test #3 expected $CI \ge 0.75$ (`HIGH`) for Summer-only, $OBS=10, ST\_QA=2.37\text{ K}$, but formula gave $1.0 \times 0.80 \times 0.80 = 0.64$. | In tropical Surat, nominal clear-sky $ST\_QA \approx 2.37\text{ K}$. Penalizing $ST\_QA > 1.5\text{ K}$ with 0.80 while also penalizing Summer-only with 0.80 made $CI \ge 0.75$ mathematically impossible. | Calibrate $C_{qa}$: Nominal clear-sky $ST\_QA \le 2.50\text{ K} \to 1.00$. Calibrate $C_{season}$: Summer+Winter complete $\to 0.90$, Summer-only $\to 0.70$. Summer-only with clear sky achieves $CI = 0.70$ (`MODERATE`); multi-season dry achieves $CI = 0.90$ (`HIGH`). |
| **4** | **Temporal Storage Grain** | Draft proposed storing single-valued `observed_lst_c` alongside multi-year persistence in a single unversioned table. | Mixed observation-level data with multi-year aggregated metrics. | Adopt a 3-table normalized schema: `stage_c_grid_cells` (geometry once), `stage_c_grid_observations` (temporal observations), and `stage_c_heat_priority_scores` (versioned HPI runs). |
| **5** | **Chronic Hotspot Multi-Year Support** | Draft required hot recurrence across seasons but did not enforce distinct calendar years. | 4 hot observations in a single year could have qualified. | Formally require: $f_{hot} \ge 0.50$, $N_{hot} \ge 3$, spanning at least **2 distinct calendar years**, with $N_{valid} \ge 4$ and at least 2 observations with $OBS \ge 2$. |
| **6** | **Optical Imputation Scope** | Draft vaguely mentioned "sentinel present". | Did not specify neighborhood rules, fallbacks, or downstream model guardrails. | Specify 8-connected Moore neighborhood: $\ge 4$ valid $\to$ median ($C_{sentinel}=0.70$); $1\text{–}3$ valid $\to$ mean ($C_{sentinel}=0.50$); $0$ valid $\to$ neutral fallback ($C_{sentinel}=0.30$). All imputed cells strictly disqualified from ML counterfactual cooling simulations. |

---

## 10. Verification Sign-Off

The baseline inspection confirms:
1. All protected ML and analysis hashes match the frozen manifest.
2. Exact spatial area conservation holds at **461.630791 km²** ($0.000000\%$ error).
3. The 114 existing backend tests are 100% green.
4. The codebase is fully prepared for Phase 2 specification finalization.
