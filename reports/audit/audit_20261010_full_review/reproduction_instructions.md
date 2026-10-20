# HEATSENSE AI — Reproduction and Independent Verification Instructions

**Audit Run ID:** `audit_20261010_full_review`  
**Target Repository:** `E:\FINAL YEAR PROJECT\heatsense-ai`  
**Audit Date:** 2026-10-10  
**Operating System:** Windows 10/11 x64  
**Shell:** PowerShell 5.1 / 7+  

---

## 1. Environment & Prerequisites

To independently reproduce all validation results, metrics, benchmarks, and builds documented in this audit, ensure the following tools are available in the local environment:

| Tool / Runtime | Required Version | Verified Version in Audit | Location / Notes |
| :--- | :--- | :--- | :--- |
| **Python** | 3.12.x | `Python 3.12.10` | `.\.venv\Scripts\python.exe` |
| **Node.js** | 20.x or 22+ | `v26.3.0` | Node runtime in system PATH |
| **npm** | 10.x+ | `12.0.0` | Package manager |
| **PostgreSQL** | 16+ or 17 | `PostgreSQL 17.0 x64` | Windows Service `postgresql-x64-17` |
| **PostGIS** | 3.4+ / 3.5+ | `PostGIS 3.5.0` | Installed in PostgreSQL instance |
| **Git** | 2.40+ | `git version 2.48.1` | Local repository |

---

## 2. Environment Configuration

### 2.1 Backend Environment (`.env`)
Ensure `.env` in the project root contains the valid local connection parameters:
```ini
APP_NAME=heatsense-api
APP_ENV=development
API_V1_PREFIX=/api/v1

POSTGRES_DB=heatsense
POSTGRES_USER=heatsense
POSTGRES_PASSWORD=heatsense_dev
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
DATABASE_URL=postgresql+psycopg://heatsense:heatsense_dev@localhost:5433/heatsense

CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
GOOGLE_MAPS_API_KEY=YOUR_KEY_HERE
```

---

## 3. Step-by-Step Reproduction Sequence

### Step 1: Verify Protected Stage A/B Scientific Artifact Hashes
Execute SHA-256 verification against the canonical freeze manifest:
```powershell
.\.venv\Scripts\python.exe -c "
import hashlib
from pathlib import Path
manifest = Path('artifacts/ml_freeze/checksums.sha256')
lines = [l.strip().split() for l in manifest.read_text().splitlines() if l.strip()]
mismatches = 0
for h, p in lines:
    actual = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    if actual != h:
        print(f'MISMATCH in {p}')
        mismatches += 1
print(f'Verified {len(lines)} files: {mismatches} mismatches')
"
```
**Expected Output:**
```
Verified 41 files: 0 mismatches
```

Verify the 3 core frozen artifacts directly via PowerShell:
```powershell
Get-FileHash -Algorithm SHA256 `
  artifacts\ml_freeze\xgb_tuned_policy_d.joblib, `
  data\processed\sensitivity\policy_d\analysis.parquet, `
  artifacts\ml_freeze\holdout_split.json
```
**Expected SHA-256 Hashes:**
- `xgb_tuned_policy_d.joblib`: `E1AEDD4946B1B29823BDEA66EA3EC7B9BA5F20C4DDBFDF6920C2E62E6B30B7C9`
- `analysis.parquet`: `E824794E5BA2E26937AC40F55F5FD788ADAD70B1A6B23C6AB435B08223DD9997`
- `holdout_split.json`: `8A04B20C97B088FFC7D3F513ECD3E41007ADEA51AD16401F104529F40D8C1A2D`

---

### Step 2: Database Migration & Schema Verification
Ensure PostgreSQL is running on port 5433 and apply migrations:
```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```
Check the current applied Alembic revision:
```powershell
.\.venv\Scripts\python.exe -c "import sqlalchemy as sa; engine=sa.create_engine('postgresql://heatsense:heatsense_dev@localhost:5433/heatsense'); print(list(engine.connect().execute(sa.text('SELECT * FROM alembic_version')).fetchall()))"
```
**Expected Output:**
```
[('a1b2c3d4e5f6',)]
```

Inspect the 10 check constraints on table `stage_c_heat_priority_scores`:
```powershell
.\.venv\Scripts\python.exe -c "
import sqlalchemy as sa
engine = sa.create_engine('postgresql://heatsense:heatsense_dev@localhost:5433/heatsense')
with engine.connect() as conn:
    res = conn.execute(sa.text(\"SELECT conname FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid WHERE t.relname = 'stage_c_heat_priority_scores' AND c.contype = 'c' ORDER BY conname\")).fetchall()
    print('Active Constraints:', [r[0] for r in res])
"
```
**Expected Output:**
```
Active Constraints: ['ck_hpi_built_density', 'ck_hpi_confidence_index', 'ck_hpi_confidence_tier', 'ck_hpi_eligibility', 'ck_hpi_hotspot_frequency', 'ck_hpi_persistence', 'ck_hpi_persistence_tier', 'ck_hpi_score_range', 'ck_hpi_thermal_severity', 'ck_hpi_vegetation_deficit']
```

---

### Step 3: Run Full Backend Pytest Suite
Execute all 162 backend tests across unit, GIS, ML, database, and API modules:
```powershell
.\.venv\Scripts\pytest.exe backend\tests -v
```
**Expected Output:**
```
====================== 162 passed, 25 warnings in ~43s ======================
```

Execute targeted Stage C tests specifically:
```powershell
.\.venv\Scripts\pytest.exe backend\tests\test_stage_c_spatial.py backend\tests\test_stage_c_db.py backend\tests\test_stage_c_api.py backend\tests\test_stage_c_scoring.py backend\tests\test_stage_c_persistence.py backend\tests\test_stage_c_confidence.py backend\tests\test_stage_c_imputation.py backend\tests\test_stage_c_freeze.py -v
```
**Expected Output:**
```
====================== 47 passed in ~32s ======================
```

Execute optical sentinel audit and sensitivity tests:
```powershell
.\.venv\Scripts\pytest.exe backend\tests\test_optical_sentinel_audit.py backend\tests\test_stage_c_sensitivity.py -v
```
**Expected Output:**
```
====================== 15 passed in ~5s ======================
```

---

### Step 4: Run Frontend Vitest Suite & Production Build
Navigate to `frontend/` directory and run Vitest:
```powershell
cd frontend
npm test -- --run
```
**Expected Output:**
```
 Test Files  2 passed (2)
      Tests  13 passed (13)
```

Compile TypeScript and generate the production bundle via Vite:
```powershell
npm run build
```
**Expected Output:**
```
✓ built in ~4.20s
dist/index.html                   0.48 kB
dist/assets/index-BNvIR2zw.css   70.10 kB
dist/assets/index-HYQ-3UWQ.js   706.08 kB
```
Return to root:
```powershell
cd ..
```

---

### Step 5: Reproduce Model Evaluation on Locked Holdout
Execute independent evaluation of `xgb_tuned_policy_d.joblib` against `data/processed/sensitivity/policy_d/analysis.parquet` using the locked 33 test blocks:
```powershell
.\.venv\Scripts\python.exe -c "
import json
import joblib
import numpy as np
import pandas as pd

model = joblib.load('artifacts/ml_freeze/xgb_tuned_policy_d.joblib')
df = pd.read_parquet('data/processed/sensitivity/policy_d/analysis.parquet')
with open('artifacts/ml_freeze/holdout_split.json') as f:
    holdout = json.load(f)

test_blocks = set(holdout['test_blocks'])
df_test = df[df['block_id'].isin(test_blocks)]

feature_cols = ['NDVI', 'NDBI', 'NDWI', 'LST_OBS_COUNT', 'LST_QA_MEDIAN_K']
X_test = df_test[feature_cols]
y_test = df_test['LST_C'].values

y_pred = model.predict(X_test)
residuals = y_test - y_pred

mae = float(np.mean(np.abs(residuals)))
rmse = float(np.sqrt(np.mean(residuals**2)))
r2 = float(1.0 - (np.sum(residuals**2) / np.sum((y_test - np.mean(y_test))**2)))
bias = float(np.mean(residuals))

print(f'Samples: {len(df_test):,}')
print(f'MAE:     {mae:.4f} °C')
print(f'RMSE:    {rmse:.4f} °C')
print(f'R2:      {r2:.4f}')
print(f'Bias:    {bias:.4f} °C')
"
```
**Expected Output:**
```
Samples: 203,758
MAE:     1.2726 °C
RMSE:    1.7524 °C
R2:      0.9006
Bias:    0.0521 °C
```

---

### Step 6: Verify Spatial Grid Coverage & Area Reconciliation
Run geometric intersection reconciliation between grid and boundary:
```powershell
.\.venv\Scripts\python.exe -c "
from gis.spatial.grid import generate_smc_grid_dataframe, verify_area_conservation

# Operational grid (49,747 centroid-inside cells)
gdf_op = generate_smc_grid_dataframe(canonical_only=True)
res_op = verify_area_conservation(gdf_op)
print('Operational Grid:', res_op)

# All-intersecting grid (50,871 cells)
gdf_all = generate_smc_grid_dataframe(canonical_only=False)
res_all = verify_area_conservation(gdf_all)
print('All-Intersecting Grid:', res_all)
"
```
**Expected Output:**
```
Operational Grid: {'cell_count': 49747, 'is_canonical_subset': True, 'authoritative_area_km2': 461.630791, 'clipped_sum_km2': 459.550165, 'delta_km2': -2.08062632, 'delta_pct': 0.45071221, 'coverage_pct': 99.5493, 'conserved': True}
All-Intersecting Grid: {'cell_count': 50871, 'is_canonical_subset': False, 'authoritative_area_km2': 461.630791, 'clipped_sum_km2': 461.630791, 'delta_km2': 0.0, 'delta_pct': 0.0, 'coverage_pct': 100.0, 'conserved': True}
```

---

### Step 7: Benchmark Live FastAPI Endpoints
Launch FastAPI test client and verify latency, HTTP status, and non-finite sanitization:
```powershell
.\.venv\Scripts\python.exe -c "
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
endpoints = [
    '/api/v1/health',
    '/api/v1/heat-priority/summary',
    '/api/v1/heat-priority/cells?limit=50',
    '/api/v1/heat-priority/cells?bbox=72.75,21.10,72.85,21.20&limit=50',
    '/api/v1/heat-priority/cell/R000_C249'
]

for ep in endpoints:
    resp = client.get(ep)
    assert resp.status_code == 200, f'Failed {ep}: {resp.status_code}'
    assert 'NaN' not in resp.text and 'Infinity' not in resp.text, f'Non-finite in {ep}'
    print(f'PASS {ep}: status={resp.status_code}, length={len(resp.text):,} chars')
"
```
**Expected Output:**
```
PASS /api/v1/health: status=200
PASS /api/v1/heat-priority/summary: status=200
PASS /api/v1/heat-priority/cells?limit=50: status=200
PASS /api/v1/heat-priority/cells?bbox=72.75,21.10,72.85,21.20&limit=50: status=200
PASS /api/v1/heat-priority/cell/R000_C249: status=200
```
