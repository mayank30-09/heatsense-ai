# HEATSENSE AI

**AI-Powered GIS-Based Urban Heat Mitigation & Cooling Decision-Support Platform**  
*Target Municipality:* Surat Municipal Corporation (SMC), Gujarat, India  
*Spatial Domain:* 461.63 km² administrative territory · 49,747 canonical 100m analytical grid cells  
*Current Operational Baseline:* Summer 2026 Baseline (19 multi-temporal Landsat seasons, 2022–2026)  
*Cryptographic Freeze Integrity:* 41/41 Verified SHA-256 Digests (`[PASS]`)  

---

## 1. Executive Overview

**HEATSENSE AI** is an enterprise-grade geospatial artificial intelligence (GeoAI) decision-support platform engineered specifically for the Surat Municipal Corporation (SMC). The platform combines multi-temporal satellite thermal observations, biophysical remote sensing, spatially blocked machine learning models, and physical urban cooling calculations to support municipal heat resilience planning under the Surat Urban Heat Action Plan (UHAP 2026).

Crucially, HEATSENSE AI enforces rigorous scientific and municipal engineering guardrails:
- **Non-Inversion Principle:** Machine learning feature attributions (SHAP values) represent diagnostic correlations and are strictly quarantined from direct causal cooling extrapolations.
- **Linearized Heat Dissipation:** Active cooling projections are derived from a first-order linearized microclimate heat dissipation equation ($h_{\text{eff}} = 45.6\text{ W/(m}^2\cdot\text{K)}$) and empirical literature caps, **not** numerical continuum partial differential equations (PDE) or computational fluid dynamics (CFD) simulation.
- **Itemized Engineering Costing:** All capital and maintenance budgets incorporate statutory taxes (18% GST), physical contingencies (12%), design/supervision fees (6%), non-linear setup scaling ($\text{Base} \times \sqrt{A/500}$), and water tanker provisions. Base rates are explicitly marked as indicative modeling assumptions.
- **Cadastral Ownership Limitations:** Satellite spectral indicators identify unbuilt open ground as candidates for municipal greening, but **do not confirm legal municipal ownership or legal vacancy**. On-site cadastral title verification is mandatory before municipal procurement.

---

## 2. System Architecture & Services

HEATSENSE AI operates as a synchronized microservices architecture:

| Service | Technology Stack | Host Binding | Container / Internal Port | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Spatial Database** | PostgreSQL 16 + PostGIS 3.4 | `127.0.0.1:5433` | `5432` | PostGIS spatial database storing 49,747 100m grid cells, multi-season LST observations, and SMC boundary polygons |
| **Backend REST API** | FastAPI, SQLAlchemy 2.0, Rasterio, XGBoost | `127.0.0.1:8000` | N/A | High-performance geospatial API (36 documented endpoints across 8 modular routers), raster tile streamer, zonal stats calculator, and optimization engines |
| **Frontend WebGIS** | React 18, TypeScript, Vite, Tailwind CSS, Leaflet | `http://localhost:5173` | N/A | Interactive 7-tab WebGIS dashboard for municipal climate planners, researchers, and public stakeholders |

---

## 3. Prerequisites & Environment Setup

### System Prerequisites
- **Python:** 3.12+ (tested on Python 3.12.10)
- **Node.js:** v20+ (tested on Node.js v26.3.0 and npm 12.0.0)
- **Docker Engine & Docker Compose:** Required for running the PostGIS database container
- **Git:** Configured with LF line-ending preservation

### Initial Setup Steps

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd heatsense-ai
   ```

2. **Configure Environment Variables:**
   Create a `.env` file in the repository root with secure local credentials:
   ```env
   POSTGRES_USER=heatsense
   POSTGRES_PASSWORD=<CHOOSE_YOUR_POSTGRES_PASSWORD>
   POSTGRES_PORT=5433
   POSTGRES_DB=heatsense
   DATABASE_URL=postgresql+psycopg://heatsense:<CHOOSE_YOUR_POSTGRES_PASSWORD>@127.0.0.1:5433/heatsense
   JWT_SECRET_KEY=<GENERATE_MIN_32_CHAR_SECRET_KEY>
   DEV_USER_PASSWORD=<CHOOSE_YOUR_DEV_USER_PASSWORD>
   ```

3. **Start the PostGIS Database:**
   ```powershell
   docker compose up -d db
   ```
   Verify database health:
   ```powershell
   docker compose ps
   ```

4. **Initialize Python Virtual Environment:**
   ```powershell
   python -m venv .venv
   # Windows PowerShell:
   .\.venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate

   # Install dependencies
   pip install -e .
   ```

5. **Run Database Migrations:**
   ```powershell
   alembic upgrade head
   ```

6. **Install Frontend Dependencies:**
   ```powershell
   cd frontend
   npm install
   cd ..
   ```

---

## 4. Execution & Development Guide

### Starting the Backend Server
```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.app.main:app --reload --port 8000
```
- API Health Endpoint: `http://localhost:8000/api/v1/health`
- Interactive OpenAPI Swagger UI: `http://localhost:8000/docs`

### Starting the Frontend WebGIS
```powershell
cd frontend
npm run dev
```
- Interactive WebGIS: `http://localhost:5173`

---

## 5. Testing, Verification & Cryptographic Invariants

HEATSENSE AI enforces four tiers of automated testing and verification:

### 1. Cryptographic Checksum Verifier (MANDATORY)
Verifies that none of the 41 frozen machine learning models, spatial holdout partitions, feature matrices, or training baselines have drifted or suffered unauthorized modification:
```powershell
.\.venv\Scripts\python.exe verify_checksums.py
```
*Expected Output:* `Verified Matches: 41`, `[PASS] ALL CHECKSUMS VERIFIED OK (100% MATCH)!`

### 2. Automated Validation Harness
Executes 17 automated statistical, geospatial, documentation, and governance checks:
```powershell
.\.venv\Scripts\python.exe scripts/validation_harness.py --strict --output reports/validation_harness_report.json --markdown reports/validation_harness_report.md
```
*Expected Output:* `17 verified checks, 0 failed, 8 documented field limitations cataloged (17/25 Passed, 8 Unverified, 0 Failed - PASS)`.

### 3. Backend Test Suite
```powershell
# Run all 460 backend and GIS optimization tests
pytest backend/tests/ -v

# Run final QA invariants and Stage D acceptance tests
pytest backend/tests/test_final_qa_invariants.py backend/tests/test_stage_d_cooling_metrics.py -v
```
*Expected Output:* `460 passed, 0 failed, 0 skipped`.

### 4. Frontend Vitest Suite & Production Build
```powershell
cd frontend
npm test -- --run
npm run build
cd ..
```
*Expected Output:* 15 test files passed (91 tests passed), clean TypeScript/Vite bundle in `frontend/dist/`.

---

## 6. Scientific Framework & Methodology Summary

### 1. Multi-Temporal Landsat Thermal Observations
- Seasonal composites integrate **62 scenes in the four current seasonal composites (Summer 2026: 22, Winter 2026: 20, Monsoon 2026: 6, Post-Monsoon 2025: 14); the archive has 19 seasonal composites** (WRS-2 Path 148, Row 045).
- Pixel-wise median aggregation filters transient clouds, smoke, and atmospheric artifacts.
- Near-Real-Time (NRT) overpass feed (e.g. October 14, 2026) displays single-pass observations for situational awareness, strictly excluded from multi-year baseline indices.

### 2. Machine Learning Baseline & Dual $R^2$ Reporting
- **Model:** Gradient Boosted Decision Trees (`artifacts/ml_freeze/xgb_tuned_policy_d.json`) trained on physical indices (`NDVI`, `NDBI`, `NDWI`, observation count, QA score). Coordinates are 100% excluded.
- **Pooled Random-Split Accuracy:** $R^2 = 0.9006$, $\text{MAE} = 1.2726^\circ\text{C}$, $\text{RMSE} = 1.7524^\circ\text{C}$ on 203,758 holdout rows.
- **Geographically Blocked Spatial Holdout:** Evaluated across 33 isolated $2\text{km} \times 2\text{km}$ spatial blocks ($\text{Dev} \cap \text{Test} = \emptyset$): pooled holdout $R^2 = 0.9006$, with seasonal holdout partitions documented in `artifacts/ml_freeze/qc_summary.json` (Summer $R^2 = 0.7119$, Winter $R^2 = 0.6512$).
- **Conformal Prediction:** Non-parametric split conformal calibration provides $\pm 2.98^\circ\text{C}$ uncertainty bounds (90.15% empirical coverage at nominal 90.0%).

### 3. Heat Priority Index (HPI) & Sensitivity Analysis
- Multi-criteria spatial vulnerability index normalized to $[0, 100]$:
  $$HPI = 100 \times (0.40 T_{\text{norm}} + 0.30 P_{\text{persist}} + 0.15 V_{\text{deficit}} + 0.15 B_{\text{density}})$$
- **Hotspot Persistence:** Evaluated across the multi-year archive, identifying **223 chronic heat hotspots** ($\ge 90$th percentile across summer overpasses under the fixed 19-season denominator).
- **Sensitivity Scenarios:** Tested across 4 policy-justified scenarios (Baseline, Extreme Thermal, Nature-First, Built-Density). Spearman rank correlations ($\rho \in [0.966, 0.992]$) demonstrate ranking robustness across policy weights while recognizing that stability reflects component correlation rather than causal truth.

### 4. Prescriptive Interventions & Linearized Heat Dissipation
- Models 11 field-grade urban cooling strategies across 11 land-use typologies.
- Active cooling calculates skin temperature reduction:
  $$\Delta T_s = f_{\text{treated}} \times |\Delta T_{s,\text{skin}}| \times \eta_{\text{cell}}$$
  with effective dissipation conductance $h_{\text{eff}} = 45.6\text{ W/(m}^2\cdot\text{K)}$ under solar irradiance $870\text{ W/m}^2$.
- Physical saturation ceilings prevent unphysical runaway extrapolations (Tree canopy: $3.50^\circ\text{C}$, Cool roof: $2.50^\circ\text{C}$, Green roof: $2.00^\circ\text{C}$, Combined cell: $4.50^\circ\text{C}$).
- Seven newer interventions (public parks, Miyawaki forests, bioswales, retention ponds, shaded parking, green walls, permeable cover) are tagged `local_field_validated: False`. Miyawaki ultra-dense planting assumptions are documented as `UNVERIFIED IN SURAT`.

### 5. Multi-Objective Portfolio Optimization
- **Greedy Knapsack:** Efficient marginal benefit-to-cost ranking allocating municipal budgets under a strict 1-intervention-per-cell exclusivity constraint.
- **NSGA-II Genetic Algorithm:** Multi-objective evolutionary search producing non-dominated Pareto fronts trading off capital cost, extensive thermal benefit ($^\circ\text{C}\cdot\text{m}^2$), and chronic hotspot coverage.
- **Budget Integrity:** Both algorithms enforce strict budget ceilings; total expenditure **never exceeds the municipal budget allocation under any circumstance**.

---

## 7. Key Documentation & Evidence Links

- [`docs/qa/final_submission_qa_report.md`](docs/qa/final_submission_qa_report.md): Authoritative final release audit and verification report.
- [`docs/qa/assumptions_and_data_register.md`](docs/qa/assumptions_and_data_register.md): Master assumptions and 4-tier provenance register with verified DOIs.
- [`docs/qa/defect_log.md`](docs/qa/defect_log.md): Master defect log and verification history (DEF-001 through DEF-015).
- [`RUN_GUIDE.md`](RUN_GUIDE.md): End-to-end operational execution, database restoration, and walkthrough guide.
- [`docs/EVIDENCE_REGISTER.md`](docs/EVIDENCE_REGISTER.md): Consolidated platform evidence register distinguishing verified, supported, assumption, and unverified claims.
- [`docs/VALIDATION_STATUS.md`](docs/VALIDATION_STATUS.md): Master validation matrix, verified invariants, and documented field limitations.
- [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md): Operational, statistical, physical, and institutional limitations register.
- [`reports/INTERVENTION_REALISM_REPORT.md`](reports/INTERVENTION_REALISM_REPORT.md): Audit report on cooling physics, cost schedules, and land tenure boundaries.
- [`reports/hpi_sensitivity_analysis.md`](reports/hpi_sensitivity_analysis.md): Four-scenario HPI sensitivity evaluation and rank stability analysis.
- [`reports/validation_harness_report.md`](reports/validation_harness_report.md): Output report generated by the automated validation harness.

---

## 8. Operational Governance & Scientific Disclaimers

1. **Screening-Level Decision Support:** All outputs represent 100m grid cell aggregations designed for municipal planning prioritization. They do not constitute property-level architectural blueprints.
2. **Skin vs. Air Temperature:** Satellite Land Surface Temperature ($T_{\text{skin}}$) reflects thermodynamic skin surface radiometry. During clear summer days in Surat, skin temperatures are **8°C to 16°C hotter than 2m ambient air temperature**.
3. **Mandatory Cadastral & Structural Field Surveys:** Proposed civil interventions (e.g., green roofs, cool roofs, tree corridors) require certified on-site structural engineering assessments (to prevent collapse hazards on lightweight roofs) and official SMC cadastral Town Planning Scheme (TPS) title verification before municipal funds are committed.
4. **Local Microclimate Field Validation:** Simulated microclimatic cooling effects from proposed interventions represent empirical engineering projections grounded in literature; they are not yet calibrated to localized in-situ weather station sensor networks in Surat.
