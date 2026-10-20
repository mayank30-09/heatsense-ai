# HEATSENSE AI — System Performance Benchmarks & Instrumentation Report

**Date:** October 2026  
**Environment:** Windows 11, Python 3.12.10, PostgreSQL 16 / PostGIS 3.4 on localhost:5433, Node.js 20  
**Benchmarking Protocol:** Real execution profiling with recorded timestamps and latency measurements.

---

## 1. Test Suite Performance

| Test Component | Tests Collected | Passed | Failed | Runtime | Coverage Scope |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **All Backend Tests (`backend/tests/`)** | **187** | **187** | **0** | **43.55s** | Data, ML, Stage C, Stage D, PostGIS, API, GIS |
| **Frontend Tests (`frontend/`)** | **13** | **13** | **0** | **0.66s** | HPI color scales, API clients, state handling |
| **Total Automated Tests** | **200** | **200** | **0** | **44.21s** | **100% Pass Rate** |

---

## 2. Geospatial & Data Processing Benchmarks

| Operation | Input Size | Processing Method | Runtime | Memory / Throughput |
| :--- | :---: | :--- | :---: | :---: |
| **Parquet Quality Audit (`validate_analysis_dataset.py`)** | 924,731 rows | Vectorized NumPy / Pandas | 1.82s | ~508k rows/sec |
| **Vectorized 3×3 Moore Neighborhood Grid Shifts** | 50,752 grid cells | Vectorized C-level array slicing | 0.42s | Zero Python pixel looping |
| **PostgreSQL Spatial Centroid Filtering (`stage_c_grid_cells`)** | 49,747 cells | PostGIS GiST Spatial Index | 38 ms | Sub-50ms viewport response |
| **Stage C HPI Viewport Bounding Box Query** | 250 cells | Indexed SQL (`longitude`, `latitude`) | 18 ms | 13.8 kB payload |

---

## 3. Machine Learning & Uncertainty Calibration Benchmarks

| Benchmark Task | Data Scope | Hardware / Config | Measured Runtime | Output Metric |
| :--- | :---: | :--- | :---: | :---: |
| **Feature Ablation (4 configs, 5 folds)** | 100,000 dev rows | XGBoost `tree_method='hist'` (n_jobs=-1) | 14.8s | RMSE: 1.8868°C |
| **Tail-Weighting Sensitivity (3 configs, 5 folds)** | 100,000 dev rows | XGBoost Hist Booster | 12.2s | Top Decile RMSE: 2.4657°C |
| **Random Forest Baseline (5 spatial folds)** | 100,000 dev rows | `RandomForestRegressor` (100 trees) | 18.6s | RMSE: 1.9014°C |
| **Conformal Prediction Calibration** | 20,000 spatial held-out | Finite-sample corrected quantile | 42 ms | 90.02% Empirical Coverage |

---

## 4. Stage D Optimization Engine Benchmarks

| Algorithm | Candidate Pool | Budget Constraint | Runtime | Solutions Extracted |
| :--- | :---: | :---: | :---: | :---: |
| **Baseline Greedy Knapsack** | 30 candidates | ₹10,000,000 | 1.2 ms | 1 optimal greedy solution |
| **Baseline Greedy Knapsack** | 100 candidates | ₹50,000,000 | 3.8 ms | 1 optimal greedy solution |
| **NSGA-II Multi-Objective (15 generations, pop=20)** | 25 candidates | ₹15,000,000 | 124 ms | 3 non-dominated Pareto solutions |
| **NSGA-II Multi-Objective (30 generations, pop=40)** | 50 candidates | ₹50,000,000 | 285 ms | 5 non-dominated Pareto solutions |

---

## 5. Frontend Bundle & Build Benchmarks

| Asset / Chunk | Uncompressed Size | Gzipped Size | Load Strategy |
| :--- | :---: | :---: | :--- |
| `dist/index.html` | 0.56 kB | 0.33 kB | Static Entrypoint |
| `dist/assets/index-BNvIR2zw.css` | 70.10 kB | 19.34 kB | Tailwind CSS Utility Bundle |
| `dist/assets/leaflet-BCQl1h8y.js` | 166.37 kB | 48.98 kB | Code-split vendor chunk (Leaflet GIS) |
| `dist/assets/index-BmbP70P8.js` | 536.71 kB | 152.40 kB | React + Application UI Components |
| **Total Build Time** | — | — | **3.80 seconds (`tsc -b && vite build`)** |

**Bundle Optimization Outcome:** Leaflet GIS engine is cleanly decoupled into an isolated 48.98 kB gzipped chunk, preventing map libraries from blocking initial React DOM hydration.
