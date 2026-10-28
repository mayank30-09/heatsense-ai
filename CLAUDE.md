6# CLAUDE.md — HEATSENSE AI Project Master Context & Agent Protocol

> **Target Audience:** Claude AI Agent (Claude Code CLI, Claude Desktop, Claude Web Project)  
> **Project:** HEATSENSE AI — AI-Powered GIS-Based Urban Heat Mitigation & Cooling Decision-Support Platform  
> **Target Municipality:** Surat Municipal Corporation (SMC), Gujarat, India  
> **Policy Context:** Surat Urban Heat Action Plan (UHAP 2026)  
> **Spatial Domain:** 461.63 km² official SMC boundary · 49,747 canonical 100m analytical grid cells  
> **Operational Baseline:** Summer 2026 Operational Baseline (19 multi-temporal Landsat seasons, 2022–2026)  
> **Cryptographic Freeze Status:** 41/41 Verified SHA-256 Digests (`[PASS]`)  
> **Current Git Branch:** `fix/runtime-working`

---

## 1. Executive Summary & Mission

**HEATSENSE AI** is an enterprise geospatial artificial intelligence (GeoAI) and physical decision-support platform engineered specifically for the **Surat Municipal Corporation (SMC)** in Gujarat, India.

The platform ingests multi-temporal Landsat 8/9 thermal observations across Surat, trains spatially blocked and conformalized machine learning models, evaluates a multi-criteria Heat Priority Index (HPI), and optimizes field-grade municipal cooling interventions (urban forestry, cool roofs, green roofs, cool pavements, water bodies) subject to strict municipal budget limits and physical saturation constraints.

### Core Municipal Purpose
1. **Identify Chronic Vulnerability:** Pinpoint where heat persistently threatens dense, unshaded, built-up neighborhoods (223 chronic summer hotspots).
2. **Prescribe Realistic Interventions:** Calculate physical skin and microclimate cooling based on surface energy dissipation, bounded empirical literature models, and itemized engineering cost schedules (including 18% GST, 12% contingency, and 3-year establishment maintenance).
3. **Optimize Public Expenditure:** Use Greedy Knapsack and NSGA-II multi-objective genetic algorithms to allocate municipal funds (₹50 Lakhs to ₹20+ Crores) without exceeding budget caps, enforcing a strict 1-intervention-per-cell exclusivity rule.

---

## 2. System Architecture & Port Mapping

HEATSENSE AI runs as three tightly integrated services:

```
                      ┌────────────────────────────────────────┐
                      │            Frontend WebGIS             │
                      │  React 18 + Vite + TS + Tailwind + Leaflet  │
                      │         Host: http://localhost:5173    │
                      └───────────────────▲────────────────────┘
                                          │ HTTP REST / Tiles
                                          ▼
                      ┌────────────────────────────────────────┐
                      │          Backend REST API Server       │
                      │      FastAPI + SQLAlchemy 2.0 + Uvicorn│
                      │      Rasterio + GeoPandas + XGBoost    │
                      │         Host: 127.0.0.1:8000           │
                      └───────────────────▲────────────────────┘
                                          │ SQL + PostGIS queries
                                          ▼
                      ┌────────────────────────────────────────┐
                      │         Spatial Database (Docker)      │
                      │         PostgreSQL 16 + PostGIS 3.4    │
                      │   Host: 127.0.0.1:5433 (Internal: 5432)│
                      │        Database: 'heatsense'           │
                      └────────────────────────────────────────┘
```

| Service | Technology Stack | Host Binding | Container Port | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Spatial Database** | PostgreSQL 16, PostGIS 3.4 (Docker) | `127.0.0.1:5433` | `5432` | Stores 49,747 100m grid cells, 19-season LST observations, HPI scores, intervention candidates, and SMC vector boundaries. |
| **Backend REST API** | FastAPI, Python 3.12, SQLAlchemy 2.0, Rasterio, XGBoost | `127.0.0.1:8000` | N/A | 24 REST endpoints, Cloud-Optimized GeoTIFF (COG) raster tile streamer, zonal statistics engine, greedy and NSGA-II optimizers. |
| **Frontend WebGIS** | React 18, TypeScript, Vite, Tailwind CSS, Leaflet | `http://localhost:5173` | N/A | Interactive 7-tab WebGIS dashboard for municipal climate planners, engineers, researchers, and public citizens. |

---

## 3. Directory Layout

```
heatsense-ai/
├── CLAUDE.md                   # THIS FILE: Master briefing and operating protocol for Claude AI
├── README.md                   # Human-facing project overview and quickstart
├── verify_checksums.py         # Mandatory cryptographic verifier (41 SHA-256 artifacts)
├── docker-compose.yml          # PostGIS 16 container definition (port 5433:5432)
├── alembic.ini                 # Database migration configuration
├── pyproject.toml              # Python build configuration and dependencies
├── .env                        # Local credentials (DO NOT COMMIT SECRETS)
│
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app initialization, middleware, router mounts
│   │   ├── config.py           # Pydantic v2 settings & production security validators
│   │   ├── api/v1/             # REST API routers:
│   │   │   ├── health.py       # GET /health
│   │   │   ├── auth.py         # POST /login, GET /me, POST /refresh
│   │   │   ├── heat_priority.py# /summary, /cells, /cell/{id}, /lst-stats, /model-validation
│   │   │   ├── interventions.py# /candidates, /scenarios, /optimize, /diminishing-returns
│   │   │   ├── analysis.py     # /zonal-stats, /resolve-area-name, /recommendations
│   │   │   ├── rasters.py      # /rasters/lst/tiles/{z}/{x}/{y}.png (XYZ tile server)
│   │   │   ├── scenes.py       # /scenes (authentic Landsat overpass listing)
│   │   │   └── admin.py        # /admin/audit-logs, /cost-parameters, /ingest, /model-metadata
│   │   ├── core/               # Auth (JWT, passwords, rate limiters, security guards)
│   │   ├── db/                 # SQLAlchemy database session, models, and spatial schemas
│   │   └── raster/             # GeoTIFF sampling, window reading, and tile generation
│   └── tests/                  # 343 backend pytest tests (unit, integration, API, security)
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # Main layout, route-level code splitting (React.lazy), nav
│   │   ├── components/
│   │   │   ├── dashboard/      # HPIDashboardView.tsx, ValidationTrust.tsx
│   │   │   ├── map/            # MapShell.tsx, HPIViewportGrid.tsx, CellInspector.tsx,
│   │   │   │                   # LayerControls.tsx, HPILegend.tsx, AreaRecommendationsPanel.tsx
│   │   │   ├── interventions/  # InterventionExplorer.tsx, ScenarioLab.tsx, Optimization.tsx
│   │   │   ├── auth/           # LoginModal.tsx, UserMenu.tsx
│   │   │   └── common/         # ScienceGlossaryModal.tsx, UI primitives
│   │   ├── services/           # Axios/fetch API clients (heatPriorityApi, interventionsApi, etc.)
│   │   ├── context/            # AuthContext.tsx (in-memory JWT management)
│   │   ├── types/              # Full TypeScript schemas for API contracts
│   │   └── styles.css          # Tailwind CSS and Leaflet map overrides
│   └── package.json            # Vite, React 18, Leaflet, Vitest dependencies
│
├── gis/                        # Core scientific and spatial computation engines:
│   ├── gee/                    # Google Earth Engine & Landsat Level-2 ingestion pipelines
│   ├── heat_priority/          # HPI scoring, thermal persistence, and normalization
│   ├── interventions/          # Bounded cooling models, costing, knapsack, and NSGA-II
│   ├── ml/                     # Model inference, spatial CV, and conformal prediction
│   └── spatial/                # Grid generation, bounding boxes, and geometry utilities
│
├── artifacts/
│   └── ml_freeze/              # 41 FROZEN ARTIFACTS (CHECKSUM PROTECTED - DO NOT MODIFY)
│       ├── checksums.sha256    # Authoritative SHA-256 hashes
│       ├── xgb_tuned_policy_d.json / .joblib # Authoritative frozen XGBoost model
│       ├── holdout_split.json  # 132 dev blocks / 33 test blocks partition
│       ├── holdout_performance.json # Evaluated test set performance
│       └── ...
│
├── docs/                       # Comprehensive specifications:
│   ├── RUN_GUIDE.md            # Platform run and walkthrough guide
│   ├── AUTH.md                 # RBAC specification and seeded account table
│   ├── EVIDENCE_REGISTER.md    # MEASURED/MODELLED/ASSUMPTION/UNVERIFIED classification
│   ├── KNOWN_LIMITATIONS.md    # 8 operational and physical disclosures
│   └── specifications/         # Stage C HPI spec, Stage D interventions spec
│
└── reports/                    # Complete audits, benchmark reports, and improvement records
```

---

## 4. Immutable Scientific Guardrails & Core Principles

> [!CAUTION]
> **ZERO-TOLERANCE RULES FOR ALL CODE MODIFICATIONS & MODELING**  
> Claude AI must strictly uphold these physical and scientific invariants. Violating them introduces unscientific claims or breaks cryptographic verifications.

### 1. The Non-Inversion Principle (SHAP is Diagnostic, Not Causal)
- Machine learning feature attributions (SHAP values) reflect observational diagnostic correlations across the Landsat archive.
- **Under NO circumstance should SHAP values be multiplied by proposed intervention area or fraction to compute cooling.**
- All cooling projections must use the bounded microclimate equations in `gis/interventions/cooling_effects.py`.

### 2. Linearized Heat Dissipation (No Fake PDE/CFD Claims)
- Active Stage D cooling calculations use a first-order linearized microclimate heat dissipation formula:
  $$\Delta T_s = f_{\text{treated}} \times |\Delta T_{s,\text{skin}}| \times \eta_{\text{cell}}$$
  with effective thermal conductance $h_{\text{eff}} = 45.6\text{ W/(m}^2\cdot\text{K)}$ under clear summer solar irradiance ($870\text{ W/m}^2$).
- The system **does not** solve continuum partial differential equations (PDE) or 3D computational fluid dynamics (CFD). Never claim or generate code claiming CFD/PDE simulation unless a genuine solver is being introduced with user approval.

### 3. Empirical Saturation Ceilings & Sub-Additive Attenuation
Individual cell cooling is strictly capped by literature-derived physical saturation limits:
- **Tree Canopy:** Maximum **3.50°C** (Bowler et al. logarithmic diminishing returns: $\ln(1 + f) / \ln(2)$)
- **Cool Roof (High Albedo):** Maximum **2.50°C** (Santamouris et al. albedo shift model)
- **Green Roof (Extensive):** Maximum **2.00°C** (Akbari et al. latent heat flux model)
- **Cool Pavement:** Maximum **1.80°C** (Reflective permeable model)
- **Combined Multi-Intervention Cell Saturation:** Maximum **4.50°C** per 100m cell.
- **Sub-Additive Attenuation:** When multiple interventions occur in one cell:
  $$f_{\text{attenuation}} = 1.0 - 0.25 \times \frac{\min(\Delta T_1, \Delta T_2)}{\max(\Delta T_1, \Delta T_2)}$$

### 4. Extensive vs. Intensive Metric Separation
- **Intensive temperature reductions (°C) are NEVER summed across disconnected cells.** (e.g., cooling Cell A by 2°C and Cell B by 2°C does NOT equal "4°C of cooling").
- **Portfolio Thermal Benefit (Extensive):** $B_{\text{portfolio}} = \sum A_i \times \Delta T_i$ reported in **°C·m²**.
- **Treated Footprint Mean Cooling:** $\overline{\Delta T}_{\text{treated}} = B_{\text{portfolio}} / \sum A_i$ (°C).
- **Citywide Area-Average Cooling:** $\Delta T_{\text{citywide}} = B_{\text{portfolio}} / A_{\text{domain}}$ where $A_{\text{domain}} = 461{,}630{,}791\text{ m}^2$ (authoritative SMC domain).
- **Population Exposure:** Set to `POPULATION_DATA_UNAVAILABLE` unless an authoritative ward-level census layer is explicitly loaded. Do not fabricate synthetic demographics.

### 5. Remote Sensing Provenance (Strict Truth)
- Thermal Data: **USGS Landsat 8/9 Collection 2 Level-2 TIRS-2 (Band 10)**.
- Optical Multispectral: **Landsat 8/9 OLI-2 (Bands 2–7)** at 30m native resolution, resampled to the 100m canonical grid.
- **PROHIBITED CLAIMS:** There is **NO Sentinel-2 MSI** (10m) and **NO ERA5 atmospheric reanalysis** in the active pipeline. If you see old documentation or comments mentioning Sentinel-2 or ERA5, correct them to Landsat 8/9 Level-2.
- Overpass solar time: **~10:30 local solar time (about 11:00 IST / ~05:33 UTC)**.
- Single NRT scenes (e.g. October 14, 2026) are for situational awareness only and are **strictly excluded from multi-year HPI computation**.

### 6. Skin Temperature ($T_{\text{skin}}$) vs. Ambient Air Temperature ($T_{\text{air}}$)
- Satellite Land Surface Temperature ($T_{\text{skin}}$) represents the thermodynamic radiometric surface skin.
- In Surat summer, asphalt roads, concrete roofs, and industrial sheds reach **8°C to 16°C hotter** than the standard 2m ambient air temperature ($T_{\text{air}}$).
- Never report $T_{\text{skin}}$ as air temperature. Always label metrics as Land Surface Temperature (LST / $T_{\text{skin}}$).

### 7. Cryptographic Freeze Invariants (41 SHA-256 Hashes)
- The files in `artifacts/ml_freeze/` are cryptographically locked and verified by `verify_checksums.py`.
- **Never modify, retrain over, or overwrite files in `artifacts/ml_freeze/` without explicit user permission and a new manifest generation.**
- `evaluation_count: 1` in metadata is a provenance constant written by `scripts/final_holdout_evaluation.py`, not a runtime counter.

### 8. Cadastral & Structural Realism
- High vegetation deficit and low NDBI identify unbuilt, permeable ground; they **do not establish legal municipal ownership or legal vacancy**. On-site cadastral Town Planning Scheme (TPS) surveys are required.
- Existing lightweight roofs (corrugated metal, asbestos cement) in informal settlements or industrial estates cannot structurally bear green roofs. Always include the explicit warning: *"roof structure unverified — field survey required for structural feasibility."*

---

## 5. Machine Learning & Heat Priority Index (HPI) Specifications

### ML Model Baseline & Dual $R^2$ Reporting
- **Algorithm:** Gradient Boosted Decision Trees (`xgb_tuned_policy_d.json`) trained on physical surface indices (NDVI, NDBI, NDWI, observation count, QA score). Coordinates (`lat`, `lon`, `row`, `col`, `block_id`) are **100% excluded** to ensure generalization.
- **Pooled Random-Split Accuracy:** $R^2 = 0.9006$, $\text{MAE} = 1.2726^\circ\text{C}$, $\text{RMSE} = 1.7524^\circ\text{C}$ on 203,758 holdout rows.
- **Spatially Blocked Holdout:** $R^2 = 0.6919$ across 33 isolated $2\text{km} \times 2\text{km}$ spatial holdout blocks ($\text{Dev} \cap \text{Test} = \emptyset$). Both metrics must be disclosed side-by-side.
- **Conformal Prediction:** Non-parametric split conformal calibration provides $\pm 2.98^\circ\text{C}$ uncertainty intervals (90.15% overall coverage). Note: Monsoon coverage is 79.19% and Decile 10 (hottest cells) is 83.43% due to localized industrial thermal variance.
- **Confidence Disclaimer:** "Confidence index is a heuristic, not a calibrated probability."

### Heat Priority Index (HPI) Formulation
Multi-criteria spatial vulnerability normalized to $[0, 100]$:
$$\text{HPI} = 100 \times (0.40 T_{\text{norm}} + 0.30 P_{\text{persist}} + 0.15 V_{\text{deficit}} + 0.15 B_{\text{density}})$$

- $T_{\text{norm}}$: Normalized Summer 2026 LST ($[30^\circ\text{C}, 50^\circ\text{C}] \rightarrow [0, 1]$).
- $P_{\text{persist}}$: Multi-year summer thermal persistence across 19 seasonal composites. **223 chronic hotspots** identified ($\ge 90$th percentile across summer overpasses under fixed 19-season denominator).
- $V_{\text{deficit}}$: Vegetation deficit ($1 - \text{norm}(\text{NDVI})$ clamped to $[0.05, 0.45]$).
- $B_{\text{density}}$: Built-up density index ($\text{norm}(\text{NDBI})$ clamped to $[-0.25, 0.15]$).

---

## 6. Complete REST API Route Inventory (24 Endpoints)

All endpoints live under `/api/v1/`:

| Method | Path | Access Role | Description & Caching |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Service, database, and raster health check |
| `POST` | `/auth/login` | Public (5 req/min) | JWT token issuance (returns access_token, 60-min life) |
| `GET` | `/auth/me` | Authenticated | Current user profile, role, and department |
| `POST` | `/auth/refresh` | Authenticated | Extends active JWT token |
| `GET` | `/heat-priority/summary` | Public | Citywide HPI metrics, chronic hotspot count (ETag cached) |
| `GET` | `/heat-priority/cells` | Public | Viewport bounding box grid query (max 350 cells, cached 5m) |
| `GET` | `/heat-priority/cell/{pixel_id}` | Public | Detailed multi-criteria breakdown for a single 100m cell |
| `GET` | `/heat-priority/lst-stats` | Public | Seasonal LST distributions & scene provenance (ETag cached) |
| `GET` | `/heat-priority/model-validation` | Public | ML holdout metrics, RF vs XGB comparison, sensor metadata |
| `GET` | `/interventions/candidates` | Public | Filterable cooling intervention candidate catalog |
| `GET` | `/interventions/candidates/{id}` | Public | Detailed candidate specs, unit costs, and cooling caps |
| `GET` | `/interventions/scenarios` | Public | Precomputed reference packages (₹50L, ₹2.5Cr, ₹10Cr) |
| `POST` | `/interventions/optimize` | Planner, Admin | NSGA-II Pareto optimization or Greedy budget allocation |
| `POST` | `/interventions/diminishing-returns` | Planner, Admin (30/m)| Computes real physical diminishing returns across budgets |
| `POST` | `/analysis/zonal-stats` | Public | Multi-season zonal stats for arbitrary drawn GeoJSON polygon |
| `POST` | `/analysis/resolve-area-name` | Public | Fast reverse geocoding for drawn polygon |
| `POST` | `/analysis/resolve-area-name-postgis` | Public | PostGIS spatial reverse geocoding against SMC grid/localities |
| `POST` | `/analysis/recommendations` | Public (30 req/min) | Rule-based cooling recommendations for drawn polygon |
| `GET` | `/rasters/lst/tiles/{z}/{x}/{y}.png` | Public | XYZ PNG tile streamer from Cloud-Optimized GeoTIFF (COG) |
| `GET` | `/scenes` | Public | Authentic Landsat Level-2 scenes listing (excludes mocks) |
| `GET` | `/admin/audit-logs` | Admin | Security audit trail logs with filtering |
| `PUT` | `/admin/cost-parameters` | Admin | Updates configurable intervention unit costs & markups |
| `POST` | `/admin/ingest` | Admin | Triggers satellite scene or tabular ingestion pipeline |
| `GET` | `/admin/model-metadata` | Researcher, Admin | Hyperparameters, Optuna study logs, and feature schemas |

---

## 7. Frontend Views & Navigation

The WebGIS UI consists of 7 lazy-loaded, route-split views in `frontend/src/`:

1. **Dashboard (`/` — `HPIDashboardView.tsx`):** Executive overview of Surat heat vulnerability, 49,747 analytical cells, 223 chronic hotspots, and quick links.
2. **Heat Map (`Heat Map` — `MapShell.tsx`):** Interactive Leaflet canvas, 20°C–60°C thermal ramp, 100m grid cell inspection (`CellInspector.tsx`), seasonal raster switching, collapsible legend (`HPILegend.tsx`), and NRT scene view.
3. **Area Analysis (`Area Analysis` — `MapShell.tsx` + `AreaDrawing.tsx`):** Interactive polygon drawing tool. Clips polygons to official 461.63 km² SMC boundary, calculates multi-season zonal stats (`POST /analysis/zonal-stats`), and displays automated cooling recommendations (`AreaRecommendationsPanel.tsx`) with CSV/JSON export.
4. **Intervention Explorer (`Intervention Explorer` — `InterventionExplorer.tsx`):** Filter 11 cooling candidates by urban typology (Dense Informal, Industrial, Commercial RCC, Roads, Parks). Shows itemized costs, structural feasibility warnings, and 3-way candidate comparison modal.
5. **Scenario Lab (`Scenario Lab` — `ScenarioLab.tsx`):** Precomputed reference tiers (₹50L, ₹2.5Cr, ₹10Cr) + custom budget slider (₹10L to ₹20Cr). Driven by real backend diminishing-returns solver (`POST /interventions/diminishing-returns`). Requires `planner` or `admin` role for custom simulations.
6. **Optimization (`Optimization` — `Optimization.tsx`):** Dual optimization solvers: NSGA-II Genetic Pareto Front and Greedy Knapsack. Interactive Pareto scatter plot, candidate map, and CSV export for municipal engineers.
7. **Validation / Trust (`Validation / Trust` — `ValidationTrust.tsx`):** Scientific transparency center displaying spatial holdout validation ($R^2 = 0.9006$ pooled, $R^2 = 0.6919$ spatial), Random Forest vs. XGBoost comparisons, conformal coverage table, sensor provenance, and evidence classifications.

---

## 8. Authentication & RBAC

- **Role Levels:** `public` < `planner` < `researcher` < `admin`.
- **Seeded Dev Accounts (Development Environment):**
  - `public_user` (`public`) — Citizen / Public viewer
  - `planner_officer` (`planner`) — SMC Town Planning Department (can run optimizations)
  - `climate_researcher` (`researcher`) — SVNIT Microclimate Lab (can view ML metadata)
  - `smc_admin` (`admin`) — Smart City Center Admin (full privileges)
- **Password Sourcing:** Passwords are **never hardcoded**. In development, the password for all seeded accounts is dynamically read from the `DEV_USER_PASSWORD` environment variable at boot time.
- **Production Guard (`APP_ENV=production`):** All seeded accounts are unconditionally refused (`authenticate_user()` returns `None`), and Pydantic halts boot if default JWT keys or insecure passwords are used.
- **Client Token Invariant:** JWT tokens are held **strictly in-memory** in React context state (`AuthContext.tsx`). Tokens are NEVER written to `localStorage`, `sessionStorage`, or cookies.

---

## 9. Operations, Verification & Testing Commands

### Prerequisites
- Python 3.12+ (in `.venv`)
- Node.js v20+ / npm 10+
- Docker Engine & Docker Compose (for PostGIS on port 5433)

### 1. Verification (MANDATORY BEFORE ANY COMMIT)
```powershell
# 1. Cryptographic Checksum Verifier (Must show 41/41 PASS)
.\.venv\Scripts\python.exe verify_checksums.py

# 2. Automated Validation Harness (14 checks)
.\.venv\Scripts\python.exe scripts/validation_harness.py --strict --markdown reports/validation_harness_report.md
```

### 2. Starting Services
```powershell
# Start PostGIS Database Container (Port 5433)
docker compose up -d

# Start FastAPI Backend API (Port 8000)
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Start Vite Frontend (Port 5173)
cd frontend
npm run dev
```

### 3. Running Backend Tests
```powershell
# Run all 343 backend tests
.\.venv\Scripts\python.exe -m pytest backend/tests/ -v

# Run fast unit/API tests (skipping slow integration tests)
.\.venv\Scripts\python.exe -m pytest backend/tests/ -v -m "not integration"
```

### 4. Running Frontend Tests & Production Build
```powershell
cd frontend

# Run all 58 Vitest tests
npm test -- --run

# Validate TypeScript & build production bundle
npm run build
```

### 5. Database Migrations
```powershell
# Run pending migrations
alembic upgrade head

# Test offline SQL downgrade generation (zero-connection dry-run)
alembic downgrade b2c3d4e5f6a7:a1b2c3d4e5f6 --sql
```

---

## 10. Strict Operating Rules for Claude AI Agent

When editing code, proposing improvements, or answering questions in this repository, Claude **MUST ALWAYS** obey the following directives:

1. **NEVER modify files in `artifacts/ml_freeze/`:** This directory is frozen under SHA-256 digests. Any edit will cause `verify_checksums.py` to fail.
2. **NEVER hallucinate Sentinel-2 or ERA5:** The remote sensing chain of custody is exclusively Landsat 8/9 Level-2 (OLI-2/TIRS-2).
3. **NEVER sum intensive temperature reductions across cells:** Always compute extensive thermal benefit ($B = \sum A_i \Delta T_i$) in °C·m².
4. **NEVER apply unverified parked patches:** `reports/runtime_verification_2026-10-21/parked/stage_d_science_wip.patch` contains exploratory research code that alters function signatures. It must remain UNAPPLIED.
5. **NEVER hardcode secrets or passwords:** Sourced exclusively from `.env` via `DEV_USER_PASSWORD` and `JWT_SECRET_KEY`.
6. **NEVER remove structural/cadastral disclaimers:** Interventions on roofs must carry the unverified structural feasibility warning, and greening must note that spectral vacancy does not confirm cadastral ownership.
7. **MAINTAIN clean test suites:** After making changes, run `verify_checksums.py`, `pytest backend/tests/`, `npm test -- --run`, and `npm run build`. Ensure zero regressions.

---

## 11. Claude AI Operating Protocol: Continuing Work & Asking for Prompts

When starting a new session or receiving a prompt from the user, Claude AI should follow this standardized communication and execution workflow:

### Step 1: Initial Handshake & Status Check
When the user asks you to start or resume working, respond with a concise status confirmation:
- Confirm that you have reviewed `CLAUDE.md`.
- Report current repository health (run `verify_checksums.py`).
- State the active branch (`fix/runtime-working`).
- Present the menu of available workstreams and ask the user which prompt/feature they want to pursue.

### Step 2: Available Backlog Workstreams & Roadmap
Offer the user the following active expansion options:

* **Workstream A: In-Situ IoT Weather Sensor Telemetry Integration**
  - *Goal:* Connect real-time weather stations across Surat (e.g., SVNIT, Adajan, Katargam) to validate and compare $T_{\text{air}}$ against satellite $T_{\text{skin}}$.
  - *Tech:* New table `stage_c_weather_sensors`, REST endpoint `GET /api/v1/sensors/realtime`, and Map overlay layer.

* **Workstream B: Authoritative SMC Town Planning Scheme (TPS) Cadastral Boundary Ingestion**
  - *Goal:* Replace OpenStreetMap locality approximations with authentic municipal ward and TPS reservation polygons.
  - *Tech:* PostGIS ingestion script for SMC vector GeoJSON/Shapefiles, updated reverse-geocoding, and cadastral ownership status flagging.

* **Workstream C: Automated Executive PDF Report Generation for SMC UHAP Committee**
  - *Goal:* One-click PDF generation summarizing area analysis, chronic hotspot mitigations, budget allocation, and engineering bill of quantities (BOQ).
  - *Tech:* ReportLab / WeasyPrint backend endpoint `POST /api/v1/analysis/export-pdf` and frontend export button.

* **Workstream D: Ward-Level Vulnerability & Socio-Economic Demographic Overlay**
  - *Goal:* Integrate census-based vulnerability indices (slum populations, elderly demographics, outdoor worker density) with physical HPI.
  - *Tech:* Multi-criteria weight adjustment in `scoring.py`, demographic schema in `backend/app/db/schemas.py`, and dashboard toggle.

* **Workstream E: Progressive Web App (PWA) Offline Caching for Municipal Field Surveyors**
  - *Goal:* Enable SMC field engineers to inspect candidate sites on mobile tablets without active cellular connection.
  - *Tech:* Service worker raster tile caching, offline IndexedDB candidate storage, and survey checklist forms.

### Step 3: Prompting Template for the User
When asking the user for their prompt or next command, use this standardized structure:

```markdown
### 🤖 Ready to Proceed with HEATSENSE AI
I have ingested `CLAUDE.md`, verified the 41/41 cryptographic freeze integrity (`[PASS]`), and checked system services.

**Which area would you like to work on next?**
1. **[Feature Implementation]** Select a workstream from the roadmap (e.g. In-Situ Sensors, TPS Cadastral Ingestion, PDF Reporting, Ward Demographics, or Offline PWA).
2. **[Backend / API]** Extend an existing endpoint, add a new optimization objective, or enhance database queries.
3. **[Frontend / WebGIS]** Enhance map layers, add new interactive charts, or refine mobile responsiveness.
4. **[Testing & Validation]** Add new stress tests, benchmark simulations, or CI/CD automation.
5. **[Custom Prompt]** Provide your specific requirement or bug fix instructions.

*Please reply with your choice or prompt to begin!*
```
