# HEATSENSE AI — Platform Execution and Verification Run Guide

**Project:** Geospatial AI/ML WebGIS for Urban Heat Island Mitigation & Physics-Informed Interventions  
**Target City:** Surat, Gujarat, India (Surat Municipal Corporation — SMC)  
**Spec Version:** v2.0 Operational (2026 Summer Baseline)  
**Document Purpose:** Complete, reproducible operational guide for environment setup, database services, API server, frontend development, testing suites, scientific freeze verification, platform walkthrough across all 7 views, and evidentiary classification.

---

## 1. System Architecture & Port Mapping

HEATSENSE AI consists of three synchronized services:

| Service | Technology Stack | Host Binding | Container / Internal Port | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Spatial Database** | PostgreSQL 16 + PostGIS 3.4 | `127.0.0.1:5433` | `5432` | PostGIS spatial database containing 49,747 analytical 100m grid cells, multi-season LST observations, and SMC boundaries |
| **Backend API** | FastAPI, SQLAlchemy 2.0, Rasterio, XGBoost | `127.0.0.1:8000` | N/A | Geospatial REST API (24 endpoints), raster tile renderer, zonal statistics engine, greedy and NSGA-II optimizers |
| **Frontend WebGIS** | React 18, TypeScript, Vite, Tailwind CSS, Leaflet | `http://localhost:5173` | N/A | Interactive 7-tab WebGIS dashboard for municipal climate planners and researchers |

---

## 2. Prerequisites & Environment Setup

### Required Runtimes
- **Python:** 3.12+ (tested on Python 3.12.10)
- **Node.js:** v20+ (tested on Node.js v26.3.0 and npm 12.0.0)
- **Docker Engine & Docker Compose:** For running the spatial database container
- **Git:** Configured with LF line-ending preservation

### Initial Setup
1. Clone the repository and navigate to root:
   ```bash
   cd "E:\FINAL YEAR PROJECT\heatsense-ai"
   ```

2. Configure environment file:
   Ensure `.env` exists in the repository root. Configure your local configuration using non-default passwords:
   ```env
   POSTGRES_USER=heatsense
   POSTGRES_PASSWORD=<CHOOSE_YOUR_POSTGRES_PASSWORD>
   POSTGRES_PORT=5433
   POSTGRES_DB=heatsense
   DATABASE_URL=postgresql+psycopg://heatsense:<CHOOSE_YOUR_POSTGRES_PASSWORD>@127.0.0.1:5433/heatsense
   JWT_SECRET_KEY=<GENERATE_MIN_32_CHAR_SECRET_KEY>
   DEV_USER_PASSWORD=<CHOOSE_YOUR_DEV_USER_PASSWORD>
   ```

   > [!IMPORTANT]
   > Readers must choose their own secure values for `POSTGRES_PASSWORD` and `DEV_USER_PASSWORD`, and generate a 32+ character random string for `JWT_SECRET_KEY`. Never use `heatsense_dev` or placeholder credentials in shared or production environments. The `.env` file is strictly ignored by `.gitignore`.

3. Python Virtual Environment:
   ```powershell
   # Activate virtual environment
   .\.venv\Scripts\Activate.ps1
   ```

4. Install Frontend Dependencies:
   ```powershell
   cd frontend
   npm install
   cd ..
   ```

---

## 3. Starting the PostGIS Spatial Database

1. Launch the PostGIS container in the background:
   ```powershell
   docker compose up -d
   ```

2. Confirm container health status:
   ```powershell
   docker compose ps
   ```
   *Expected status: `heatsense-postgis` is `Up` and `healthy`, with port mapping `5433->5432/tcp`.*

3. Quick connectivity test (optional):
   ```powershell
   docker exec -it heatsense-postgis pg_isready -U heatsense -d heatsense
   ```

---

## 4. Cryptographic Scientific Freeze Verification

Before starting application services or executing model queries, verify that all 41 mission-critical scientific artifacts (ML models, spatial holdout partitions, calibration matrices, and baseline datasets) remain cryptographically intact:

```powershell
.\.venv\Scripts\python.exe verify_checksums.py
```

*Expected authoritative output format:*
```
======================================================================
HeatSense AI — SHA-256 Checksum Manifest Verification Report
======================================================================
Manifest File: E:\FINAL YEAR PROJECT\heatsense-ai\artifacts\ml_freeze\checksums.sha256
Total Lines Processed: 41
Comment/Blank Lines:   0
Valid Entries:         41
Verified Matches:      41
Missing Files:         0
Checksum Mismatches:   0
Duplicate Paths:       0
Malformed Lines:       0
Empty Manifest:        False
----------------------------------------------------------------------

[PASS] ALL CHECKSUMS VERIFIED OK (100% MATCH)!
All protected artifacts match authoritative freeze digests exactly.
======================================================================
```

---

## 5. Starting the FastAPI Backend API

1. Start Uvicorn development server:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

2. Service documentation routes:
   - **Interactive Swagger UI:** `http://127.0.0.1:8000/docs`
   - **Swagger OAuth2 Redirect:** `http://127.0.0.1:8000/docs/oauth2-redirect`
   - **OpenAPI Schema JSON:** `http://127.0.0.1:8000/openapi.json`
   - **ReDoc Documentation:** `http://127.0.0.1:8000/redoc`

### Authoritative REST API Route Inventory (24 Endpoints)

| Method | Endpoint Path | Description | Access Role |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Service and database health check | Public |
| `POST` | `/api/v1/auth/login` | Authenticates user credentials and returns JWT bearer token | Public |
| `GET` | `/api/v1/auth/me` | Returns current authenticated user record and assigned role | Authenticated |
| `POST` | `/api/v1/auth/refresh` | Refreshes existing active JWT access token | Authenticated |
| `GET` | `/api/v1/heat-priority/summary` | Aggregate city-wide HPI metrics, chronic hotspot count, and confidence tiers | Public |
| `GET` | `/api/v1/heat-priority/cells` | Bounding box spatial viewport query for 100m grid cells | Public |
| `GET` | `/api/v1/heat-priority/cell/{pixel_id}` | Detailed multi-criteria breakdown for an individual grid cell | Public |
| `GET` | `/api/v1/heat-priority/lst-stats` | Seasonal LST statistical distribution (Summer, Winter, Monsoon, Post-Monsoon) | Public |
| `GET` | `/api/v1/heat-priority/model-validation` | Frozen ML model quality control, spatial holdout metrics, and sensor provenance | Public |
| `GET` | `/api/v1/interventions/candidates` | Candidate cooling interventions catalog with server-side filtering and sorting | Public |
| `GET` | `/api/v1/interventions/candidates/{candidate_id}` | Detailed candidate specification including cooling bounds and unit costs | Public |
| `GET` | `/api/v1/interventions/scenarios` | Precomputed reference budget scenarios (Low ₹50L, Medium ₹2.5Cr, High ₹10Cr) | Public |
| `POST` | `/api/v1/interventions/optimize` | Constrained NSGA-II Pareto optimization or Greedy budget allocation | Planner, Admin |
| `POST` | `/api/v1/interventions/diminishing-returns` | Multi-budget diminishing returns curve solver across investment tiers | Public |
| `POST` | `/api/v1/analysis/zonal-stats` | Seasonal, SMC boundary-clipped zonal statistics for drawn polygons | Public |
| `POST` | `/api/v1/analysis/resolve-area-name` | Fast bounding-box/heuristic reverse-geocoding for drawn areas | Public |
| `POST` | `/api/v1/analysis/resolve-area-name-postgis` | PostGIS-backed spatial reverse geocoding against SMC grid / places | Public |
| `POST` | `/api/v1/analysis/recommendations` | Rule-based cooling intervention recommendations for drawn area polygons | Public |
| `GET` | `/api/v1/rasters/lst/tiles/{z}/{x}/{y}.png` | Multi-season Cloud-Optimized GeoTIFF raster tile service | Public |
| `GET` | `/api/v1/scenes` | Satellite catalog scenes listing (real Landsat acquisitions, excluding synthetic) | Public |
| `GET` | `/api/v1/admin/audit-logs` | Security audit trail logs with filtering by action, outcome, and date range | Admin |
| `PUT` | `/api/v1/admin/cost-parameters` | Updates configurable intervention cost and maintenance parameters | Admin |
| `POST` | `/api/v1/admin/ingest` | Data ingestion pipeline trigger for new satellite scenes | Admin |
| `GET` | `/api/v1/admin/model-metadata` | Model metadata, hyperparameters, and feature weights | Admin |

---

## 6. Starting the Vite React Frontend

1. Navigate to the `frontend/` directory and run the Vite dev server:
   ```powershell
   cd frontend
   npm run dev
   ```

2. Open `http://localhost:5173` in a modern web browser (Chrome, Edge, Firefox).

3. Production bundle build and validation:
   ```powershell
   npm run build
   ```
   *Executes TypeScript compiler (`tsc -b`) and Vite production bundler, producing optimized chunks in `frontend/dist/` with 0 type errors.*

---

## 7. Platform Walkthrough & Feature Verification

The HEATSENSE AI WebGIS provides seven dedicated, operational views accessible via the sidebar navigation:

### 1. Dashboard (`/`)
- **Key Metrics:** City-wide mean Heat Priority Index (52.4), total analytical cells (49,747), and identified chronic hotspots (223 cells).
- **Confidence Distribution:** Cell count distribution across High and Moderate confidence tiers based on multi-year cloud-free satellite coverage.
- **Persistence Tiers:** Breakdown of cells by heat recurrence history across 2022–2026 summer overpasses.
- **Quick Navigation:** Direct links to Heat Map exploration and Area Analysis workflows.

### 2. Heat Map (`Heat Map`)
- **Interactive WebGIS Canvas:** High-resolution Leaflet map anchored to Surat Municipal Corporation (`[21.1702, 72.8311]`).
- **Seasonal Raster Toggle:** Switch between Summer Peak (☀️ April–May 2026) and Winter Baseline (❄️ January 2026) LST layers.
- **Thermal Scale:** Scientific 20°C–60°C thermal colormap reflecting true Landsat surface skin temperatures ($T_{\text{skin}}$).
- **Physical Context Labeling:** Explanatory callouts distinguishing satellite skin surface temperature ($T_{\text{skin}}$) from 2m ambient air temperature ($T_{\text{air}}$), with typical 10–18°C thermal offsets on roofs and pavements.
- **Cell Inspector:** Click any 100m grid cell to inspect its coordinates, nearest OSM locality name, HPI score, LST value, vegetation deficit, built-up density, and confidence tier (with explicit non-calibrated heuristic disclaimer).

### 3. Area Analysis (`Area Analysis`)
- **Custom Polygon Drawing:** Interactive Leaflet Draw tools to sketch arbitrary assessment polygons across Surat.
- **SMC Boundary Clipping:** Polygons extending into the Gulf of Khambhat or rural districts are automatically clipped to the official Surat Municipal Corporation boundary (461.63 km²).
- **Multi-Season Statistics Table:** Calculates and displays zonal statistics across all four seasons (Summer, Winter, Monsoon, Post-Monsoon) including Min, Mean, Median (P50), P95, Max, and Cell Count via `POST /api/v1/analysis/zonal-stats`.
- **Cooling Recommendations Panel:** Displays automated, rule-based intervention advice via `POST /api/v1/analysis/recommendations` based on area thermal severity, built-up density, and green deficit, with explicit evidence badges (MEASURED/MODELLED/ASSUMPTION/UNVERIFIED).
- **Boundary & Water Warnings:** Contextual amber warning banners alert planners when drawn areas overlap water bodies (Tapi River / Arabian Sea) or extend outside municipal jurisdiction.

### 4. Intervention Explorer (`Intervention Explorer`)
- **Typology Filtering:** Browse candidates tailored to urban morphologies: *Dense Informal / Slums*, *Industrial Metal Roof Estates*, *Commercial RCC*, *Road Corridors*, and *Open Parks*.
- **Empirical Microclimate Cooling Bounds:** Cooling calculations grounded in peer-reviewed empirical literature models (`gis/interventions/cooling_effects.py` lines 22–105):
  - Tree Canopy: Bowler et al. (2010) logarithmic scaling, capped at 3.50°C.
  - Cool Roof: Santamouris et al. (2017) albedo shift model, capped at 2.50°C.
  - Green Roof: Akbari et al. (2001) heat flux model, capped at 2.00°C.
  - Cool Pavement: Reflective permeable model, capped at 1.80°C.
  - Combined saturation ceiling: Maximum 4.50°C per 100m cell with sub-additive attenuation.
- **CapEx & Maintenance:** Itemized unit capital expenditure and 3-year operational maintenance estimates.
- **Structural Caveats:** Explicit warning badges noting: *"Roof structure unverified — requires on-site structural engineering survey."*
- **Candidate Comparison & Export:** Side-by-side comparison of up to 3 candidates and one-click CSV catalog export.

### 5. Scenario Lab (`Scenario Lab`)
- **Reference Investment Tiers:** Precomputed municipal intervention packages via `GET /api/v1/interventions/scenarios`:
  - *Tier 1 — Low Effort:* ₹50 Lakhs (Tactical deployments in acute chronic hotspots).
  - *Tier 2 — Medium Effort:* ₹2.5 Crores (Targeted ward cooling corridors).
  - *Tier 3 — High Effort:* ₹10 Crores (Comprehensive city-wide urban resilience program).
- **Interactive Budget Simulator:** Dynamic slider allowing municipal planners to simulate custom investment budgets (₹10 Lakhs to ₹20 Crores).
- **Diminishing Returns Solver:** Backend-computed diminishing returns curve via `POST /api/v1/interventions/diminishing-returns`, plotting thermal benefit vs. capital expenditure.
- **Extensive Thermal Benefit:** Reports extensive cooling benefit in °C·m² ($B = \sum A_i \times \Delta T_i$), treated footprint mean cooling, and citywide area-weighted reduction over the 461.63 km² SMC domain.

### 6. Optimization (`Optimization`)
- **Dual Optimization Engines:**
  - *NSGA-II Multi-Objective Optimizer:* Genetic algorithm discovering true non-dominated Rank 1 Pareto fronts balancing Cost (min), Thermal Benefit (max), and Chronic Hotspot Mitigations (max).
  - *Greedy Knapsack Baseline:* High-speed heuristic allocating budget based on extensive thermal benefit per rupee ($B_i / \text{Cost}_i$) subject to strict 1-intervention-per-cell exclusivity.
- **Pareto Trade-Off Frontier:** Interactive scatter plot allowing decision-makers to inspect and select specific investment trade-offs.
- **Candidate Spatial Map:** Geographic preview of prioritized intervention sites across Surat.
- **CSV Data Export:** One-click download of selected intervention plans for procurement and engineering review.

### 7. Validation / Trust Center (`Validation / Trust`)
- **Scientific Transparency Center:** Complete view into Stage C/D machine learning and spatial validation protocols.
- **Spatial Holdout Benchmarks:** Evaluated on 203,758 holdout observations ($R^2 = 0.9006$, $\text{MAE} = 1.2726^\circ\text{C}$, $\text{RMSE} = 1.7524^\circ\text{C}$) across 33 block-disjoint test partitions.
- **Baseline Comparison Hierarchy:** Comparison against Global Mean, Seasonal Mean, In-Sample Cell Persistence, and Random Forest 5-fold CV baselines (`data/diagnostics/ml/model_comparison_rf_xgb.csv`).
- **Conformal Uncertainty Coverage:** Stratified coverage table: Summer 90.53%, Winter 95.68%, Post-Monsoon 95.80%, Monsoon 79.19% (undercoverage due to cloud masking), and D10 hottest decile 83.43%. Verbatim disclaimer: *"Confidence index is a heuristic, not a calibrated probability."*
- **Sensor Chain of Custody:** Data provenance for Landsat 8/9 TIRS-2 thermal, Landsat 8/9 OLI-2 surface reflectance (30m resampled to 100m), and official SMC municipal boundaries.
- **Evidence Register:** Full evidentiary classification table available in `docs/EVIDENCE_REGISTER.md`.

---

## 8. Verification & Test Execution Suite

### Running Backend Tests (pytest)
Execute the backend test suite inside the Python virtual environment:

```powershell
# Run full unit and API test suite (340 tests)
.\.venv\Scripts\python.exe -m pytest backend/tests/ -v

# Run with integration tests excluded (skips external DB service integration tests):
.\.venv\Scripts\python.exe -m pytest backend/tests/ -m "not integration" -v

# Run specific domain test suites:
# 1. Zonal Analysis & Recommendations:
.\.venv\Scripts\python.exe -m pytest backend/tests/test_analysis.py backend/tests/test_recommendations.py -v

# 2. Stage C Heat Priority Scoring & API:
.\.venv\Scripts\python.exe -m pytest backend/tests/test_stage_c_api.py backend/tests/test_stage_c_scoring.py -v

# 3. Stage D Interventions & Optimizers:
.\.venv\Scripts\python.exe -m pytest backend/tests/test_stage_d_api.py backend/tests/test_stage_d_optimizer.py backend/tests/test_stage_d_candidates.py -v

# 4. Security, Auth & RBAC Audit:
.\.venv\Scripts\python.exe -m pytest backend/tests/test_security_audit.py -v

# 5. Scientific Validation Report Reproduction:
.\.venv\Scripts\python.exe -m pytest backend/tests/test_reproduce_validation.py -v
```

*Expected test results:*
- Full test run: **340 passed**, **140 warnings** in ~400 seconds.
- When running with `-m "not integration"`: **336 passed**, 4 deselected (integration tests requiring live external services/deep fixtures).

### Running Frontend Tests (Vitest)
Execute all frontend unit and integration tests:

```powershell
cd frontend
npm test -- --run
```
*Expected result:*
- **8 test files passed**, **55 tests passed** in ~1.7 seconds across:
  1. `frontend/src/utils/__tests__/hpiColorScales.test.ts` (9 tests)
  2. `frontend/src/services/__tests__/api.test.ts` (3 tests)
  3. `frontend/src/services/__tests__/scenesApi.test.ts` (4 tests)
  4. `frontend/src/services/__tests__/heatPriorityApi.test.ts` (6 tests)
  5. `frontend/src/services/__tests__/recommendationsApi.test.ts` (4 tests)
  6. `frontend/src/services/__tests__/interventionsApi.test.ts` (13 tests)
  7. `frontend/src/services/__tests__/authApi.test.ts` (12 tests)
  8. `frontend/src/components/map/__tests__/navigation.test.tsx` (4 tests)

---

## 9. Troubleshooting & FAQ

### Port Conflict on 5433
If port 5433 is in use by another local service:
1. Identify the blocking process: `Get-NetTCPConnection -LocalPort 5433`
2. Update `POSTGRES_PORT` in `.env` to an alternate open port (e.g., 5434).

### Raster Tile 404 / Missing TIF Warning
Ensure that the Cloud-Optimized GeoTIFFs (`data/processed/seasonal/`) are present and readable. The backend automatically handles season-to-file mapping with fallback to baseline tiles.

### 403 Forbidden on Optimization Endpoint
The optimization API (`POST /api/v1/interventions/optimize`) requires `planner` or `admin` role. Authenticate via `/api/v1/auth/login` to obtain an authorized JWT session token.

### Evidence & Truth Audit
For complete classification of all scientific, geospatial, statistical, and engineering assertions across the platform into MEASURED, MODELLED, ASSUMPTION, or UNVERIFIED, refer to [`docs/EVIDENCE_REGISTER.md`](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/docs/EVIDENCE_REGISTER.md).

---

## 10. Near-Real-Time (NRT) Landsat Pipeline & Automation

The HEATSENSE AI NRT pipeline automatically discovers, ingests, quality-masks, and evaluates new Landsat 8/9 Level-2 thermal scenes over Surat (WRS-2 Path 148, Row 45) every morning, ensuring operational freshness while strictly preserving frozen science baselines.

### Architectural Guardrails
1. **Scientific Freeze Protection:** Daily discovery NEVER modifies files in `artifacts/ml_freeze/` or the authoritative 223 chronic hotspots.
2. **Idempotency:** Scene IDs are uniquely tracked in `stage_c_scene_registry`. Re-running discovery on identical scenes never duplicates database records.
3. **Quality Gate:** Scenes with less than 40% clear pixels across the 49,747 canonical SMC cells are marked `rejected` with an explicit reason (e.g. `Excessive cloud contamination: 15.1% clear over SMC boundary (< 40.0% threshold)`).
4. **Provisional Hotspots:** Provisional hotspots are flagged in `stage_c_provisional_hotspots` with label `"Provisional NRT hotspot, single scene"` and are never conflated with multi-year chronic hotspots or composite HPI scores.

### Manual / Test Execution
```powershell
# Run discovery in dry-run mode (no database writes)
.\.venv\Scripts\python.exe scripts/discover_nrt_scenes.py --dry-run

# Run offline mock discovery (simulates synthetic overpass)
.\.venv\Scripts\python.exe scripts/discover_nrt_scenes.py --mock

# Run live Earth Engine discovery for a specific date window
.\.venv\Scripts\python.exe scripts/discover_nrt_scenes.py --start-date 2026-10-01 --end-date 2026-10-27
```

### Automated Scheduling

#### Windows Task Scheduler (PowerShell)
To register the automated discovery job to execute daily at 06:00 IST:
```powershell
$Action = New-ScheduledTaskAction -Execute "E:\FINAL YEAR PROJECT\heatsense-ai\.venv\Scripts\python.exe" `
    -Argument "scripts\discover_nrt_scenes.py" `
    -WorkingDirectory "E:\FINAL YEAR PROJECT\heatsense-ai"

$Trigger = New-ScheduledTaskTrigger -Daily -At 6:00AM

$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "HeatSense_NRT_Discovery" `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "HEATSENSE AI Daily Landsat 8/9 NRT Discovery over Surat SMC (WRS 148/45)"
```

#### Linux Cron Configuration
On Linux production or container host environments, install the following cron entry (`crontab -e`):
```bash
# HeatSense AI Daily Landsat 8/9 NRT Discovery over Surat SMC (06:00 IST / 00:30 UTC)
30 0 * * * cd /opt/heatsense-ai && /opt/heatsense-ai/.venv/bin/python scripts/discover_nrt_scenes.py >> /var/log/heatsense_nrt.log 2>&1
```

### Experimental Candidate Model Retraining Workflow
Candidate retraining is strictly experimental research and never modifies production or frozen baseline models.
```powershell
.\.venv\Scripts\python.exe scripts/experimental/retrain_candidate.py --output-dir tmp/candidate_eval
```
- **EXPERIMENTAL Notice:** Prints `"EXPERIMENTAL - does not modify frozen artifacts"`.
- **Mandatory Output Directory:** Strictly requires an explicit `--output-dir` argument located outside `artifacts/ml_freeze/` and `data/`.
- **Holdout Contamination Guard:** Strictly asserts that the 33 locked test blocks are never loaded into candidate training data.
- **Evidence Boundary:** Candidate model outputs are isolated research artifacts and are never cited as platform verification evidence.
- **Freeze Promotion Policy:** Model updates are never auto-promoted; freeze updates require explicit municipal lead authorization and independent cryptographic manifest regeneration.

