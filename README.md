# HEATSENSE AI

AI-powered GIS-based urban heat analysis and mitigation decision-support platform.

## Day 1 scope

Day 1 establishes the local development foundation only:

- Dockerized PostgreSQL + PostGIS
- Alembic migration with PostGIS extension
- FastAPI backend
- `GET /api/v1/health` database/PostGIS health check
- React + Vite + TypeScript frontend
- Leaflet map shell centered on Surat

Real Google Earth Engine, Landsat, Sentinel-2, raster, ML, intervention, scenario, and optimization pipelines are intentionally deferred to later implementation gates.

## Prerequisites

- Python 3.12
- Node.js 20+
- Docker Desktop
- Git

## 1. Environment

Copy `.env.example` to `.env` and change the development password if desired.

## 2. Start PostGIS

```bash
docker compose up -d db
```

Verify:

```bash
docker compose ps
```

## 3. Python environment

```bash
python -m venv .venv
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
# macOS/Linux
source .venv/bin/activate
pip install -e .
```

## 4. Run migration

```bash
alembic upgrade head
```

## 5. Start API

```bash
uvicorn backend.app.main:app --reload
```

Health endpoint:

```text
http://localhost:8000/api/v1/health
```

Swagger UI:

```text
http://localhost:8000/docs
```

## 6. Start frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## 7. Tests

```bash
pytest
```
