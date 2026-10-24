# HEATSENSE AI — Data Availability Statement

**Project:** Geospatial AI/ML WebGIS for Urban Heat Island Mitigation & Physics-Informed Interventions  
**Target Domain:** Surat Municipal Corporation (SMC), Gujarat, India (461.63 km²)  
**Document Purpose:** Clear inventory of primary datasets, access protocols, licensing, frozen artifact checksums, and reproducibility instructions.

---

## 1. Authoritative Frozen Scientific Artifacts (Tier 1 — In-Repo)

All core models, evaluation partitions, baseline metrics, and calibration tables required to reproduce the validation benchmark are preserved directly in this repository under `artifacts/ml_freeze/`.

Every file is cryptographically locked and tracked in `artifacts/ml_freeze/checksums.sha256`:

| Artifact Category | File Path | Description / Role |
| :--- | :--- | :--- |
| **Trained ML Model** | `artifacts/ml_freeze/xgb_tuned_policy_d.json` | Authoritative frozen XGBoost model trained on 132 development blocks (720,973 rows) |
| **Model Metadata** | `artifacts/ml_freeze/model_metadata.json` | Model hyperparameters, training timestamp, and feature schema definitions |
| **Spatial Holdout Split** | `artifacts/ml_freeze/holdout_split.json` | Block-disjoint partition (132 dev blocks / 33 test blocks; 0 overlap) |
| **Evaluation Performance** | `artifacts/ml_freeze/holdout_performance.json` | Final independent holdout test evaluation (MAE: 1.2726°C, RMSE: 1.7524°C, R²: 0.9006) |
| **Conformal Calibration** | `artifacts/ml_freeze/conformal_calibration.json` | Non-parametric split conformal calibration intervals and non-conformity quantiles |
| **Quality Control Log** | `artifacts/ml_freeze/qc_summary.json` | Policy D data quality screening summary (924,731 valid rows across 19 seasonal composites) |
| **Model Comparison** | `data/diagnostics/ml/model_comparison_rf_xgb.csv` | 5-fold spatial cross-validation comparison on development blocks (RF RMSE 1.8024°C vs XGB 1.8280°C) |
| **Experimental Metrics** | `artifacts/ml_experiments/ml_experimental_evaluation.json` | Stratified error distributions across seasons and deciles |

### Verification Protocol
To verify that these artifacts have not suffered bit rot or tampering:
```powershell
.\.venv\Scripts\python.exe verify_checksums.py
```
*Expected result:* 41 of 41 files verified matching SHA-256 digests (`[PASS]`).

---

## 2. Satellite Remote Sensing Observations (Tier 2 — Publicly Available)

All primary satellite observations derive from the **USGS Landsat 8 and Landsat 9** satellite missions operated by NASA and the U.S. Geological Survey (USGS).

| Product | Instrument | Resolution | Processing Level | Source & Access Protocol |
| :--- | :--- | :--- | :--- | :--- |
| **Surface Temperature (ST)** | TIRS-2 Band 10 | 100m thermal resampled to 30m by USGS | Collection 2 Level-2 (L2SP) | USGS EarthExplorer / Google Earth Engine (`LANDSAT/LC09/C02/T1_L2`, `LANDSAT/LC08/C02/T1_L2`) |
| **Surface Reflectance (SR)** | OLI / OLI-2 Bands 1–7 | 30m native | Collection 2 Level-2 (L2SP) | USGS EarthExplorer / Google Earth Engine (Used for NDVI, NDBI, NDWI) |
| **Pixel Quality (QA)** | QA_PIXEL, QA_RADSAT | 30m native | Collection 2 Level-2 | Surface temperature quality assessment and cloud/cloud-shadow dilations |

### Radiometric Calibration Formula
Landsat Collection 2 Level-2 thermal digital numbers are converted to Land Surface Temperature ($T_{\text{skin}}$ in °C) using USGS standard scale factors:
$$T_{\text{skin}} = (\text{ST\_B10} \times 0.00341802 + 149.0) - 273.15 \quad [^\circ\text{C}]$$

*Note: Sentinel-2 MSI is not used in the canonical machine learning feature extraction or prediction pipeline.*

---

## 3. Administrative Boundaries and Municipal Baselines (Tier 3)

| Dataset | Location in Repository | Description / Origin |
| :--- | :--- | :--- |
| **SMC Municipal Boundary** | `data/boundaries/smc_boundary.geojson` | Official administrative boundary of the Surat Municipal Corporation (461.63 km²). Used for polygon clipping and citywide area-weighted cooling normalizations. |
| **Analytical Grid Cells** | PostGIS database `stage_c_grid_cells` | 49,747 regular Cartesian 100m × 100m grid cells spanning the SMC bounding box [72.60, 20.95, 73.08, 21.40]. |
| **Seasonal COG Rasters** | `data/cogs/` | Multi-season Cloud-Optimized GeoTIFF composites (Summer 2026, Winter 2026, Post-Monsoon 2025). |

---

## 4. Large Experimental Datasets & Regeneration (Tier 4 — On-Demand)

Large diagnostic sensitivity tables exceeding Git repository conventions are ignored from version control to prevent repository bloat:

- `artifacts/ml_freeze/sentinel_sensitivity/sentinel_local_effect.csv` (76.8 MB)
- `artifacts/ml_freeze/sentinel_sensitivity/sentinel_spatial_proximity.csv` (95.6 MB)

These sensitivity datasets evaluate the spatial influence of 8 development-set sentinel rows. Their summary JSON metrics (`sentinel_local_effect_summary.json` and `sentinel_spatial_proximity_summary.json`) are tracked in source control.

To regenerate these two CSV files locally from the frozen training matrix:
```powershell
.\.venv\Scripts\python.exe scripts/analyze_optical_sentinel_local_effect.py
.\.venv\Scripts\python.exe scripts/analyze_optical_sentinel_spatial_proximity.py
```

---

## 5. Automated Reproduction Scripts

To inspect and reproduce the validation report from stored artifacts without requiring live model training:
```powershell
.\.venv\Scripts\python.exe scripts/reproduce_validation_report.py
```
This script computes all 10 displayed metrics directly from stored artifacts, verifies 41/41 checksums, and emits a structured validation audit report.
