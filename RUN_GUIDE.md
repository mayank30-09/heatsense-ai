# HEATSENSE AI — Complete Direct Startup & Execution Guide

This document contains **all direct codes and instructions** to start, verify, and run the complete **HEATSENSE AI** system (FastAPI backend, React + Vite frontend, PostgreSQL / PostGIS database, and ML / optimization services).

---

## ⚡ Option 1: One-Click Startup (Recommended)

### On Windows Command Prompt / File Explorer:
Double-click `START_PROJECT.bat` or run:
```cmd
START_PROJECT.bat
```

### On Windows PowerShell:
```powershell
.\start_project.ps1
```

*This automatically checks the database on port 5433, launches the backend and frontend in separate dedicated windows, and opens `http://127.0.0.1:5173` in your default browser.*

---

## 💻 Option 2: Manual Two-Terminal Startup (Direct Codes)

If you prefer to start each service manually in your own terminal windows, use the exact commands below:

### Terminal 1: FastAPI Backend (Port 8000)

```powershell
# 1. Navigate to the project root directory
cd "E:\FINAL YEAR PROJECT\heatsense-ai"

# 2. Set PYTHONPATH to include the project root and the backend directory
$env:PYTHONPATH=".;backend"

# 3. Start the FastAPI backend with uvicorn (auto-reload enabled)
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```

*If using Windows Command Prompt (cmd.exe):*
```cmd
cd /d "E:\FINAL YEAR PROJECT\heatsense-ai"
set PYTHONPATH=.;backend
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

### Terminal 2: React + Vite Frontend (Port 5173)

```powershell
# 1. Navigate to the frontend directory
cd "E:\FINAL YEAR PROJECT\heatsense-ai\frontend"

# 2. Start the Vite development server on port 5173
npm run dev -- --host 127.0.0.1 --port 5173
```

---

## 🔍 Verification & Health Checks

Once both terminals are running, open a third terminal or your browser to verify that all systems are healthy:

### 1. Verify Backend Health (Port 8000)
```powershell
curl http://127.0.0.1:8000/api/v1/health
```
**Expected Response:**
```json
{"status":"ok","service":"heatsense-api","database":"connected"}
```

### 2. Verify Frontend Dev Server (Port 5173)
Open your browser and navigate to:
```
http://127.0.0.1:5173
```

### 3. Interactive API Documentation (Swagger UI)
```
http://127.0.0.1:8000/docs
```

---

## 👥 Pre-Configured Test Accounts (RBAC)

The application includes pre-configured role-based user accounts for testing:

| Role | Username | Department | Access Scope |
| :--- | :--- | :--- | :--- |
| **Municipal Planner** | `planner_officer` | Town Planning Dept, SMC | Full optimization, budget allocations, spatial exports |
| **Microclimate Researcher** | `climate_researcher` | Urban Microclimate Lab, SVNIT | Validation & Trust Center, SHAP diagnostics, sensor feeds |
| **SMC System Administrator** | `smc_admin` | IT & Smart City Mission | User management, pipeline configuration, system telemetry |
| **Public Citizen** | `public_user` | Surat Citizen | Heat Map, public HPI dashboard, read-only awareness |

> [!NOTE]
> All default accounts authenticate using the password set in your `.env` under `DEV_USER_PASSWORD`.

---

## 🛠️ Testing & Verification Commands

### Run Frontend Vitest Unit Tests (91 Tests)
```powershell
npm --prefix frontend test -- --run
```

### Run Python Backend Invariants & GIS Optimization Tests (460 Tests)
```powershell
$env:PYTHONPATH=".;backend"
.venv\Scripts\pytest.exe backend/tests/test_final_qa_invariants.py -v
.venv\Scripts\pytest.exe backend/tests/test_stage_d_area_optimization_canonical.py -v
```

---

## 💾 Authoritative Database Backup & Clean Package Verification

### 1. Verified Backup Artifacts
The repository includes clean, standalone backup archives in the `backups/` directory:
- **PostgreSQL Custom Dump:** `backups/heatsense_backup_final_20261030.dump` (19.52 MB, 139 TOC entries verified via `pg_restore --list`)
  - **SHA-256:** `017841538252c97ec8c37a1d614e7984183846ebd29344e648be6224df831566`
- **Clean Project Zip:** `backups/heatsense_project_final_20261030.zip` (252.33 MB, 1,519 files; excludes `.git`, `node_modules`, `.venv`, caches, and build artifacts)
  - **SHA-256:** `c8854284287f0bd5fa8b9f5895d5f39ad88ffe1d005b9dc49b1bbb2fb9a1a84e`

### 2. Database Restoration Command
To restore the database from scratch onto an existing or clean PostgreSQL 16+ instance with PostGIS:
```powershell
# 1. Create clean target database
createdb -h 127.0.0.1 -p 5433 -U heatsense heatsense

# 2. Restore all 18 tables, spatial indexes, and schema definitions
pg_restore -h 127.0.0.1 -p 5433 -U heatsense -d heatsense --no-owner --clean --if-exists backups/heatsense_backup_final_20261030.dump

# 3. Verify restore table counts
psql -h 127.0.0.1 -p 5433 -U heatsense -d heatsense -c "SELECT count(*) FROM stage_c_grid_cells;"
# Expected output: 49747
```

---

## ❓ Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Database connection error** | PostgreSQL is not running on port 5433 | Ensure the PostGIS database container or service is started on port 5433: `pg_isready -h 127.0.0.1 -p 5433` |
| **`No module named 'app'`** | Missing `PYTHONPATH` | Always run with `$env:PYTHONPATH=".;backend"` before invoking python or uvicorn |
| **Port 8000 already in use** | An old uvicorn process is still running | Kill the lingering process: `Get-Process python* \| Stop-Process` or find PID with `Get-NetTCPConnection -LocalPort 8000` |
| **Port 5173 already in use** | Lingering node process | Run: `Get-Process node* \| Stop-Process` |

