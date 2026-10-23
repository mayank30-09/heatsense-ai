# HEATSENSE AI — Platform Execution and Verification Run Guide

**Project:** Geospatial AI/ML WebGIS for Urban Heat Island Mitigation & Physics-Informed Interventions  
**Target City:** Surat, Gujarat, India (Surat Municipal Corporation — SMC)  
**Spec Version:** v2.0 Operational (2026 Summer Baseline)  
**Document Purpose:** Complete, reproducible operational guide for environment setup, database services, API server, frontend development, testing suites, scientific freeze verification, and platform walkthrough across all 7 views.

---

## 1. System Architecture & Port Mapping

HEATSENSE AI consists of three synchronized micro-services:

| Service | Technology Stack | Host Binding | Container / Internal Port | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Spatial Database** | PostgreSQL 16 + PostGIS 3.4 | `127.0.0.1:5433` | `5432` | PostGIS spatial database containing 49,747 analytical 100m grid cells, multi-season LST observations, and SMC boundaries |
| **Backend API** | FastAPI, SQLAlchemy 2.0, Rasterio, XGBoost | `127.0.0.1:8000` | N/A | Geospatial REST API, raster tile renderer, zonal statistics engine, NSGA-II optimizer |
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
   Ensure `.env` exists in the repository root with the following parameters:
   ```env
   POSTGRES_USER=heatsense
   POSTGRES_PASSWORD=heatsense_dev
   POSTGRES_PORT=5433
   POSTGRES_DB=heatsense
   DATABASE_URL=postgresql+psycopg://heatsense:heatsense_dev@127.0.0.1:5433/heatsense
   JWT_SECRET_KEY=dev_secret_key_change_in_production_min_32_chars_long
   DEV_USER_PASSWORD=heatsense_dev
   ```

   > [!WARNING]
   > Never commit `.env` or production credentials to source control. The `.env` file is strictly ignored by `.gitignore`.

3. Python Virtual Environment:
   ```powershell
   # Activate existing virtual environment
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
   *Expected status: `heatsense-postgis` is `Up` and `healthy`, with port `5433->5432/tcp`.*

3. Quick connectivity test (optional):
   ```powershell
   docker exec -it heatsense-postgis pg_isready -U heatsense -d heatsense
   ```

---

## 4. Cryptographic Scientific Freeze Verification

Before starting application services, verify that all 41 mission-critical scientific artifacts (ML models, spatial holdout partitions, calibration matrices, and raster tiles) remain cryptographically intact:

```powershell
.venv\Scripts\python.exe verify_checksums.py
```
*Expected output:*
```
Total checked: 41
Matches: 41
Missing: 0
Mismatches: 0
ALL CHECKSUMS VERIFIED OK (100% MATCH)!
```

---

## 5. Starting the FastAPI Backend API

1. Start Uvicorn development server:
   ```powershell
   .venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

2. Verify operational endpoints:
   - **API Base:** `http://127.0.0.1:8000/api/v1`
   - **Health Check:** `http://127.0.0.1:8000/api/v1/health`
   - **Interactive OpenAPI Documentation (Swagger UI):** `http://127.0.0.1:8000/docs`
   - **ReDoc Documentation:** `http://127.0.0.1:8000/redoc`

### Key REST API Endpoints Inventory

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Service and database health check |
| `POST` | `/api/v1/auth/login` | Authenticates user credentials and issues JWT access token |
| `GET` | `/api/v1/heat-priority/summary` | Aggregate city-wide HPI metrics, chronic hotspot count, and confidence tiers |
| `GET` | `/api/v1/heat-priority/cells` | Bounding box spatial viewport query for 100m grid cells |
| `GET` | `/api/v1/heat-priority/cell/{pixel_id}` | Detailed multi-criteria breakdown for an individual grid cell |
| `GET` | `/api/v1/heat-priority/lst-stats` | Seasonal LST statistical distribution (Summer, Winter, Monsoon, Post-Monsoon) |
| `GET` | `/api/v1/heat-priority/model-validation` | Frozen ML model quality control, spatial holdout metrics, and sensor provenance |
| `GET` | `/api/v1/interventions/typologies` | Urban morphology classifications and allowable intervention types |
| `GET` | `/api/v1/interventions/candidates` | Candidate cooling interventions catalog with physics-based metrics |
| `GET` | `/api/v1/interventions/candidates/{candidate_id}` | Detailed candidate specification including species models and cooling radius |
| `GET` | `/api/v1/interventions/reference-scenarios` | Precomputed reference budgets (Low ₹50L, Medium ₹2.5Cr, High ₹10Cr) |
| `POST` | `/api/v1/interventions/optimize` | Constrained NSGA-II Pareto optimization or Greedy budget allocation |
| `POST` | `/api/v1/analysis/zonal-statistics` | Seasonal, SMC boundary-clipped zonal statistics for drawn polygons |
| `GET` | `/api/v1/rasters/lst/tiles/{z}/{x}/{y}.png` | Multi-season Cloud-Optimized GeoTIFF raster tile service |

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

The HEATSENSE AI WebGIS provides seven dedicated, fully integrated operational views accessible via the sidebar navigation:

### 1. Dashboard (`/`)
- **Key Metrics:** City-wide mean Heat Priority Index (52.4), total analytical cells (49,747), and identified chronic hotspots (223 cells).
- **Confidence Distribution:** High confidence (>49,000 cells) and Moderate confidence counts based on satellite data coverage.
- **Persistence Tiers:** Breakdown of cells by heat recurrence history across 2022–2026.
- **Quick Links:** Direct navigation to Heat Map and Area Analysis workflows.

### 2. Heat Map (`Heat Map`)
- **Interactive WebGIS Canvas:** High-resolution Leaflet map centered on Surat Municipal Corporation (`[21.1702, 72.8311]`).
- **Seasonal Raster Toggle:** Switch seamlessly between Summer Peak (☀️ April–May 2026) and Winter Baseline (❄️ January 2026) LST layers.
- **Aligned Thermal Scale:** Scientific 20°C–60°C thermal colormap reflecting true Landsat surface skin temperatures.
- **Physical Context Labeling:** Explanatory callouts distinguishing satellite skin surface temperature ($T_{\text{skin}}$) from 2m ambient air temperature ($T_{\text{air}}$) with typical 10–18°C thermal offsets on roofs and pavements.
- **Interactive Cell Inspector:** Click any 100m grid cell to inspect its exact coordinates, ward name, HPI score, LST value, vegetation deficit, built-up density, and confidence tier.

### 3. Area Analysis (`Area Analysis`)
- **Custom Polygon Drawing:** Interactive Leaflet Draw tools to sketch arbitrary assessment polygons across the city.
- **SMC Boundary Clipping:** Polygons extending into the Gulf of Khambhat or rural districts are automatically clipped to the official Surat Municipal Corporation boundary.
- **Multi-Season Statistics Table:** Calculates and displays zonal statistics across all four seasons (Summer, Winter, Monsoon, Post-Monsoon) including Min, Mean, Median (P50), P95, Max, and Cell Count.
- **Boundary & Water Warnings:** Contextual amber warning banners alert planners when drawn areas overlap water bodies (Tapi River / Arabian Sea) or extend outside municipal jurisdiction.

### 4. Intervention Explorer (`Intervention Explorer`)
- **Typology Filtering:** Browse candidates tailored to specific urban morphologies: *Dense Informal / Slums*, *Industrial Metal Roof Estates*, *Commercial RCC*, *Road Corridors*, and *Open Parks*.
- **Physics-Informed Cooling Effects:** Direct calculation of Surface Energy Balance cooling ($\Delta T_{\text{skin}}$ from $-9.8^\circ\text{C}$ to $-12.0^\circ\text{C}$, $\Delta T_{\text{cell}}$ from $0.8^\circ\text{C}$ to $2.5^\circ\text{C}$).
- **Species Models:** Native Surat urban forestry modeling with crown geometries, shading, and evapotranspiration (Neem, Peepal, Gulmohar).
- **Time-to-Maturity Curves:** Projected cooling progression from sapling establishment (Years 1–2) through canopy maturity (Year 10).
- **CapEx & Maintenance:** Itemized unit capital expenditure and annual operational maintenance costs.

### 5. Scenario Lab (`Scenario Lab`)
- **Reference Investment Tiers:** Pre-computed municipal intervention packages:
  - *Tier 1 — Low Effort:* ₹50 Lakhs (Fast tactical deployments in acute hotspots).
  - *Tier 2 — Medium Effort:* ₹2.5 Crores (Targeted ward cooling corridors).
  - *Tier 3 — High Effort:* ₹10 Crores (Comprehensive city-wide urban resilience program).
- **Interactive Budget Simulator:** Dynamic slider allowing municipal planners to simulate custom investment budgets (₹10 Lakhs to ₹20 Crores).
- **Ward-Level Allocation:** Geographic distribution of proposed cooling actions across Surat's 9 administrative zones.
- **Timeline Projections:** Immediate (Year 1 Cool Roofs), Intermediate (Year 3–5 Pavements), and Long-term (Year 10 Tree Canopies) cooling trajectories.

### 6. Optimization (`Optimization`)
- **Multi-Objective NSGA-II Pareto Optimization:** Explores non-dominated trade-offs between city-wide mean cooling benefit and total capital expenditure.
- **Greedy Knapsack Baseline:** High-speed greedy heuristic allocating budget based on marginal cost-effectiveness.
- **Interactive Pareto Trade-Off Curve:** Visual scatter plot allowing decision-makers to inspect and select specific investment compromises.
- **Candidate Spatial Map:** Geographic preview of prioritized intervention sites across Surat.
- **CSV Data Export:** One-click download of selected intervention plans for procurement and engineering review.

### 7. Validation / Trust Center (`Validation / Trust`)
- **Scientific Transparency Center:** Complete view into Stage C/D machine learning and spatial validation protocols.
- **Spatial Holdout Benchmarks:** Rigorous evaluation on 203,758 holdout observations ($R^2 = 0.9006$, $\text{MAE} = 1.27^\circ\text{C}$, $\text{RMSE} = 1.76^\circ\text{C}$) using block-disjoint cross-validation.
- **Leakage Controls Checklist:** Verification of spatial buffer disjointness, temporal ordering, and coordinate feature exclusion.
- **Seasonal Error Diagnostics:** Performance metrics across Summer, Winter, Monsoon, and Post-Monsoon test sets.
- **Hotspot Conformal Bounds:** Residual distributions in chronic hotspots with $90\%$ conformal prediction intervals ($0.97^\circ\text{C}$ to $2.15^\circ\text{C}$).
- **Sensor Chain of Custody:** Sensor specifications, calibration pipelines, and data provenance for Landsat 8/9 TIRS-2 thermal, Landsat 8/9 OLI-2 surface reflectance, and official SMC municipal boundaries.

---

## 8. Verification & Test Execution Suite

### Running Backend Tests (pytest)
Execute the comprehensive backend test suite inside the Python virtual environment:

```powershell
# Run full backend test suite (316 tests)
.venv\Scripts\python.exe -m pytest backend/tests/ -v

# Run specific domain test suites:
# 1. Zonal Analysis & Seasonal LST:
.venv\Scripts\python.exe -m pytest backend/tests/test_analysis.py backend/tests/test_seasonal_observations.py -v

# 2. Stage C Heat Priority Scoring & API:
.venv\Scripts\python.exe -m pytest backend/tests/test_stage_c_api.py backend/tests/test_stage_c_scoring.py -v

# 3. Stage D Interventions & NSGA-II Optimizer:
.venv\Scripts\python.exe -m pytest backend/tests/test_stage_d_api.py backend/tests/test_stage_d_optimizer.py backend/tests/test_stage_d_candidates.py -v

# 4. Security, Auth & RBAC Audit:
.venv\Scripts\python.exe -m pytest backend/tests/test_security_audit.py -v
```

### Running Frontend Tests (Vitest)
Execute all frontend unit and integration tests:

```powershell
cd frontend
npm test -- --run
```
*Expected result: 45 of 45 tests passing across `api.test.ts`, `scenesApi.test.ts`, `hpiColorScales.test.ts`, `heatPriorityApi.test.ts`, `authApi.test.ts`, and `interventionsApi.test.ts`.*

---

## 9. Troubleshooting & FAQ

### Port Conflict on 5433
If port 5433 is in use by a local PostgreSQL service:
1. Verify what is using the port: `Get-NetTCPConnection -LocalPort 5433`
2. Update `POSTGRES_PORT` in `.env` and `frontend/.env.local` to an alternate port (e.g., 5434).

### Raster Tile 404 / Missing TIF Warning
Ensure that the Cloud-Optimized GeoTIFFs (`data/cogs/`) are present and readable. The backend automatically handles season-to-file mapping with fallback to baseline tiles.

### 403 Forbidden on Optimization Endpoint
The optimization API requires `planner` or `admin` role. Planners authenticate via `/api/v1/auth/login` to obtain an authorized JWT session token.
