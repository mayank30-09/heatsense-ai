# HEATSENSE AI — Execution and Run Guide

This guide provides step-by-step instructions for launching, developing, and verifying the HEATSENSE AI Surat Urban Heat WebGIS platform.

---

## 1. Prerequisites

- **Python:** 3.12+ (tested with Python 3.12.10)
- **Node.js:** v20+ (tested with Node.js v26.3.0 and npm 12.0.0)
- **Docker & Docker Compose:** For running the PostgreSQL 16 + PostGIS spatial database container
- **Git:** With LF line-ending preservation configured

---

## 2. Environment Configuration

Copy the example environment configuration if you are setting up a fresh environment:

```bash
# In the repository root
cp .env.example .env
```

Ensure `.env` contains the following keys configured for local execution:
- `POSTGRES_USER`: Database username (default: `heatsense`)
- `POSTGRES_PASSWORD`: Database password
- `POSTGRES_PORT`: Port exposed on host (default: `5433`)
- `POSTGRES_DB`: Database name (default: `heatsense`)
- `DATABASE_URL`: `postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5433/heatsense`
- `JWT_SECRET_KEY`: Random 32+ character secret
- `DEV_USER_PASSWORD`: Password for development seed accounts

> [!WARNING]
> Never commit `.env` or plain-text credentials to version control. The `.env` file is excluded in `.gitignore`.

---

## 3. Starting the PostGIS Database

The application requires PostgreSQL 16 with the PostGIS extension enabled. Start the preconfigured Docker Compose service:

```powershell
docker compose up -d
```

Verify that the database is healthy and listening on port 5433:

```powershell
docker compose ps
```

---

## 4. Starting the Backend API

1. **Activate the Python virtual environment:**

   ```powershell
   # Windows PowerShell
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   source .venv/bin/activate
   ```

2. **Verify freeze artifact checksums:**

   Always verify scientific freeze digests before running the server:

   ```powershell
   python verify_checksums.py
   ```
   *(Expected output: `Verified Matches: 41 (100% MATCH)`)*

3. **Start the FastAPI backend server:**

   ```powershell
   python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

   - API Base URL: `http://127.0.0.1:8000/api/v1`
   - Interactive OpenAPI Docs (Swagger UI): `http://127.0.0.1:8000/docs`
   - Health Check Endpoint: `http://127.0.0.1:8000/api/v1/health`

---

## 5. Starting the Frontend Application

1. **Navigate to the frontend directory:**

   ```powershell
   cd frontend
   ```

2. **Install dependencies (if not already installed):**

   ```powershell
   npm install
   ```

3. **Start the Vite development server:**

   ```powershell
   npm run dev
   ```

   The application will be accessible at `http://localhost:5173`.
   By default, the frontend connects to `http://127.0.0.1:8000/api/v1`. To override this, set `VITE_API_BASE_URL` in `frontend/.env.local`:

   ```env
   VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
   ```

4. **Build for production:**

   ```powershell
   npm run build
   ```

---

## 6. Running Test Suites

### Backend Unit & Integration Tests (pytest)

Run all backend tests:

```powershell
python -m pytest backend/tests/ -v
```

Run targeted tests for specific modules:

```powershell
# Analysis and Zonal Statistics
python -m pytest backend/tests/test_analysis.py -v

# Stage C Heat Priority Scoring
python -m pytest backend/tests/test_stage_c_api.py backend/tests/test_stage_c_scoring.py -v

# Stage D Interventions & Optimization
python -m pytest backend/tests/test_stage_d_api.py backend/tests/test_stage_d_optimizer.py -v

# Security and RBAC audit
python -m pytest backend/tests/test_security_audit.py -v
```

### Frontend Tests (Vitest)

```powershell
cd frontend
npm test -- --run
```

---

## 7. Protected Freeze Artifacts Policy

The repository enforces a cryptographic freeze manifest (`artifacts/ml_freeze/checksums.sha256`) covering 41 mission-critical scientific artifacts (ML models, calibration tables, sensitivity results, and test data).

- **Rule:** Never modify, move, or re-generate files under `artifacts/ml_freeze/`.
- **Verification Command:**
  ```powershell
  python verify_checksums.py
  ```
  Any change to a frozen artifact will fail manifest validation and break CI/CD pipelines.
