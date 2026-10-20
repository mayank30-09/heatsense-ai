# HEATSENSE AI — API, Database, and Frontend Subsystem Audit

**Audit Run ID:** `audit_20261010_full_review`  
**Evaluation Date:** 2026-10-10  
**Stack Verified:** FastAPI 0.141.1, SQLAlchemy 2.1.1, PostgreSQL 17.0 + PostGIS 3.5, React 19, Leaflet 1.9, Vite 7.3.6  

---

## 1. Database Architecture & Schema Integrity (PostgreSQL / PostGIS)

### 1.1 Connection & Environment
- **Database Engine:** PostgreSQL 17.0 x64 with PostGIS extension.
- **Port:** Local port `5433` (`DATABASE_URL=postgresql+psycopg://heatsense:heatsense_dev@localhost:5433/heatsense`).
- **Alembic Version:** `a1b2c3d4e5f6` (down-revision: `f4a8b1c2d3e4`).
- **Total Registered Public Tables:** 10 tables.

### 1.2 Table Schema & Row Count Audit
Every table was queried directly in PostgreSQL:

| Table Name | Entity Scope | Primary Key | Foreign Keys | Row Count | Audit Status |
| :--- | :--- | :--- | :--- | :---: | :---: |
| `study_areas` | Authoritative study area | `id` | None | 1 | **`PASS`** |
| `admin_boundaries` | Administrative boundary zones | `id` | None | 0 | **`PASS`** |
| `osm_places` | Ground-truthed OSM localities | `id` | None | 44 | **`PASS`** |
| `stage_c_grid_cells` | Analytical 100m grid polygons | `pixel_id` | `nearest_osm_place_id` $\to$ `osm_places.id` | **49,747** | **`PASS`** |
| `stage_c_grid_observations` | Multi-temporal seasonal records | `(pixel_id, year, season)` | `pixel_id` $\to$ `stage_c_grid_cells.pixel_id` | **924,731** | **`PASS`** |
| `stage_c_heat_priority_scores` | HPI scores & component layers | `(pixel_id, scoring_period, spec_version)` | `pixel_id` $\to$ `stage_c_grid_cells.pixel_id` | **49,747** | **`PASS`** |
| `alembic_version` | Migration revision tracker | `version_num` | None | 1 | **`PASS`** |
| *System PostGIS Tables* | `spatial_ref_sys`, `geometry_columns` | - | - | System rows | **`PASS`** |

### 1.3 Check Constraints in Live Database (`a1b2c3d4e5f6`)
Migration `a1b2c3d4e5f6_add_stage_c_scientific_constraints.py` enforces 10 check constraints directly in the database engine for `stage_c_heat_priority_scores`:

```sql
ALTER TABLE stage_c_heat_priority_scores
  ADD CONSTRAINT ck_hpi_score_range 
    CHECK (heat_priority_score >= 0.0 AND heat_priority_score <= 100.0),
  ADD CONSTRAINT ck_hpi_thermal_severity 
    CHECK (thermal_severity_component >= 0.0 AND thermal_severity_component <= 1.0),
  ADD CONSTRAINT ck_hpi_persistence 
    CHECK (persistence_component >= 0.0 AND persistence_component <= 1.0),
  ADD CONSTRAINT ck_hpi_vegetation_deficit 
    CHECK (vegetation_deficit_component >= 0.0 AND vegetation_deficit_component <= 1.0),
  ADD CONSTRAINT ck_hpi_built_density 
    CHECK (built_density_component >= 0.0 AND built_density_component <= 1.0),
  ADD CONSTRAINT ck_hpi_confidence_index 
    CHECK (confidence_index >= 0.0 AND confidence_index <= 1.0),
  ADD CONSTRAINT ck_hpi_hotspot_frequency 
    CHECK (hotspot_frequency >= 0.0 AND hotspot_frequency <= 1.0),
  ADD CONSTRAINT ck_hpi_confidence_tier 
    CHECK (confidence_tier IN ('HIGH', 'MODERATE', 'LOW', 'INSUFFICIENT')),
  ADD CONSTRAINT ck_hpi_persistence_tier 
    CHECK (persistence_tier IN ('chronic_hotspot', 'frequent_hotspot', 'occasional_hotspot', 'transient_extreme', 'non_hotspot')),
  ADD CONSTRAINT ck_hpi_eligibility 
    CHECK (eligibility_status IN ('ACCEPT', 'FLAG', 'EXCLUDE', 'INSUFFICIENT_THERMAL_EVIDENCE'));
```

**Scientific NULL Semantics Verification:**
In SQL standard logic, `NULL >= 0.0` evaluates to `UNKNOWN`, which CHECK constraints accept. This permits legitimate NULL scores for cells with missing summer evidence while strictly prohibiting invalid numerical scores outside $[0.0, 100.0]$. Tested and confirmed via `backend/tests/test_stage_c_db.py`.

### 1.4 Pipeline Idempotence
In `scripts/run_stage_c_pipeline.py` (lines 380–415), scoring writes execute via PostgreSQL upsert:
```sql
INSERT INTO stage_c_heat_priority_scores (...)
VALUES (...)
ON CONFLICT (pixel_id, scoring_period, spec_version)
DO UPDATE SET
  heat_priority_score = EXCLUDED.heat_priority_score,
  thermal_severity_component = EXCLUDED.thermal_severity_component,
  persistence_component = EXCLUDED.persistence_component,
  vegetation_deficit_component = EXCLUDED.vegetation_deficit_component,
  built_density_component = EXCLUDED.built_density_component,
  confidence_index = EXCLUDED.confidence_index,
  calculated_at = CURRENT_TIMESTAMP;
```
Rerunning the pipeline does not create duplicate rows or orphan foreign keys. Tested in `test_idempotent_score_upsert_behavior`.

---

## 2. FastAPI Application & API Contract Audit

### 2.1 Route Registration & Mounting
In `backend/app/api/v1/router.py`:
- `GET /api/v1/health`: System health and status.
- `POST /api/v1/analysis`: Polygon zonal statistics analysis.
- `GET /api/v1/heat-priority/summary`: Executive KPIs and distribution stats.
- `GET /api/v1/heat-priority/cells`: Paginated or bounding-box-filtered cell endpoints.
- `GET /api/v1/heat-priority/cell/{pixel_id}`: Single-cell detailed diagnostic inspector.

### 2.2 Endpoint Verification & Measured Latencies
Tested live using FastAPI `TestClient` (10 timed requests per endpoint):

| Endpoint | Method | Response Status | Mean Latency | P95 Latency | Non-Finite Clean? | Contract Schema |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `/api/v1/health` | GET | 200 OK | **15.12 ms** | 42.81 ms | Clean | `{"status": "ok", "app_name": "heatsense-api"}` |
| `/api/v1/heat-priority/summary` | GET | 200 OK | **57.14 ms** | 71.00 ms | Clean | `HeatPrioritySummaryResponse` |
| `/api/v1/heat-priority/cells?limit=50` | GET | 200 OK | **61.16 ms** | 66.34 ms | Clean | `HeatPriorityCellsResponse` |
| `/api/v1/heat-priority/cells?bbox=...` | GET | 200 OK | **64.62 ms** | 90.05 ms | Clean | `HeatPriorityCellsResponse` (Filtered) |
| `/api/v1/heat-priority/cell/R000_C249` | GET | 200 OK | **9.67 ms** | 11.51 ms | Clean | `HeatPriorityCellDetailResponse` |

### 2.3 Viewport Bounding Box Parameter (`bbox`)
To resolve P1 Defect 5 from `ChatGPT-SEEANALYSEANDREVIEWT.pdf`, `backend/app/api/v1/heat_priority.py` implements bounding box filtering:
```python
if bbox:
    min_lon, min_lat, max_lon, max_lat = [float(v.strip()) for v in bbox.split(",")]
    query = query.where(
        StageCGridCell.longitude >= min_lon,
        StageCGridCell.longitude <= max_lon,
        StageCGridCell.latitude >= min_lat,
        StageCGridCell.latitude <= max_lat,
    )
```
- **Strict Limit Enforcement:** `limit` defaults to 50 and is capped at 350 (`Query(50, ge=1, le=350)`). Requests with `limit > 350` are rejected with HTTP 422 Unprocessable Entity.
- **Payload Safety:** A typical viewport bounding query returns ~20–50 cells (~15 kB GeoJSON) in under 65 ms, completely eliminating the network bottleneck of transferring all 49,747 cells (~45 MB).

### 2.4 Non-Finite Value Sanitization (`safe_float`)
In `backend/app/api/v1/heat_priority.py` (lines 40–48), all floating-point numbers pass through `safe_float()`:
```python
def safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        val = float(v)
        return val if math.isfinite(val) else None
    except (ValueError, TypeError):
        return None
```
Responses are verified to contain zero `NaN`, `Infinity`, or `-Infinity` values, guaranteeing strict RFC 8259 JSON compliance.

---

## 3. Frontend React / Leaflet Subsystem Audit

### 3.1 Architecture & Component Hierarchy
The frontend is built with React 19, TypeScript, and Leaflet 1.9:

```
App.tsx
  ├── Header & Mode Switcher (Analysis / Heat Priority)
  ├── HPIDashboardView.tsx (Top KPI metrics cards: Total Cells, Chronic Hotspots, Mean HPI)
  └── MapShell.tsx (Leaflet Interactive Map Shell)
        ├── TileLayer (CartoDB Positron / Satellite basemap)
        ├── LayerControls.tsx (Layer toggles, opacity, mode selection)
        ├── HPIViewportGrid.tsx (Bounded GeoJSON grid cell renderer)
        ├── HPILegend.tsx (Dynamic scientific color bar adapting to active mode)
        └── CellInspector.tsx (Cell detail sidebar panel on click)
```

### 3.2 Four Distinct Layer Modes
In accordance with the review specification, heat, priority, and confidence are strictly maintained as distinct conceptual layers:

1. **Observed Summer LST Layer (`lst`):**
   - Palette: `YlOrRd` (28°C to 48°C).
   - Display: Physical observed land surface temperature in degrees Celsius (°C).
   - Provenance: Clearly marked as USGS Landsat 8/9 Level-2 thermal observation.
2. **HPI Heat Priority Layer (`hpi`):**
   - Palette: Continuous Viridis / Thermal Priority ramp (0 to 100).
   - Display: Approved composite Heat Priority Index score ($0.40T + 0.30P + 0.15V + 0.15B$).
   - Exclusion Handling: Ineligible or missing cells rendered in neutral muted gray (`#808080`), never colored as low priority.
3. **Confidence & Quality Overlay (`confidence`):**
   - Palette: Discrete category ramp (`HIGH` = Emerald `#10b981`, `MODERATE` = Amber `#f59e0b`, `LOW` = Orange `#f97316`, `INSUFFICIENT` = Rose `#f43f5e`).
   - Display: Multi-factor heuristic confidence index ($C_{obs} \times C_{qa} \times C_{season} \times C_{sentinel}$).
4. **Chronic Hotspot Highlight Layer (`chronic`):**
   - Display: Highlights the 223 multi-year persistent chronic hotspots ($f_{hot} \ge 0.50$, $N_{hot} \ge 3$, active across $\ge 2$ calendar years) in vivid Crimson with pulse border.

### 3.3 Performance Guardrails & Request Cancellation
- **Zoom Guardrail:** At zoom levels $< 12$, rendering thousands of individual 100m grid polygons would degrade browser framerate. `HPIViewportGrid.tsx` displays an intuitive guidance banner (*"Zoom in to level 12 or closer to view 100m heat priority cells"*) and suppresses API fetching.
- **Debounced Viewport Fetching:** When zoom $\ge 12$, viewport bounds (`bbox`) are recalculated only after 250ms of map stillness (pan/zoom debounce).
- **Request Cancellation via `AbortController`:** In `frontend/src/services/heatPriorityApi.ts`, every new viewport query aborts any preceding in-flight request via `signal: abortController.signal`, preventing out-of-order race conditions and stale polygon rendering.

### 3.4 Interactive Cell Inspector (`CellInspector.tsx`)
Clicking any cell opens the inspector panel exposing:
- **Pixel ID:** Stable row/column coordinates (e.g., `R198_C178`).
- **Composite Score:** HPI score formatted to 1 decimal place with priority badge.
- **Component Progress Bars:** Individual progress bars for Thermal Severity ($T$), Persistence ($P$), Vegetation Deficit ($V$), and Built-Up Density ($B$), all on $[0, 1]$ scale.
- **Observed Metrics:** Observed LST (°C), Hotspot Frequency (%), and Distinct Observation Years.
- **Quality & Provenance:** Confidence Index, Confidence Tier, and Sentinel Imputation Flag (e.g., `NONE` vs `OPTICAL_IMPUTED_MEDIAN`).
- **Downstream Guardrail Warning:** If the cell used optical imputation, a warning banner explicitly notes: *"Cell optical values imputed; disqualified from ML cooling projections."*

### 3.5 Automated Test Suite & Build Status
- **Vitest Unit Tests:** 13 passed in 810ms (`hpiColorScales.test.ts`, `heatPriorityApi.test.ts`).
- **Production Build:** `npm run build` (`tsc -b && vite build`) completed cleanly in 4.20s with zero errors.
