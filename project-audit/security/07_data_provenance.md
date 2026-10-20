# 07 — Scientific Data Provenance & Ingestion Integrity Audit

**Project:** HeatSense AI — Surat Urban Heat Mitigation & Decision Support System  
**Audit Scope:** Satellite Data Provenance, Remote Sensing Bands, Optical Sentinel Audits, Radiometric Uncertainty, and Checksum Traceability  
**Date:** October 2026  
**Auditor Classification:** Remote Sensing & Scientific Data Provenance Engineer  
**Dataset Reference:** `data/processed/sensitivity/policy_d/analysis.parquet` (924,731 rows)  
*(Note: Reconciled from previous document typographical reference `data/processed/analysis/policy_d/analysis.parquet` to the authoritative filesystem path recorded in `artifacts/ml_freeze/checksums.sha256`)*  
**Status:** **VERIFIED (PASS)**  

---

## 1. Remote Sensing Data Sources & Sensor Traceability

The analytical dataset combines multi-mission satellite imagery covering Surat City across multiple years (2015–2026) and four meteorological seasons (Winter, Summer, Monsoon, Post-Monsoon):

| Observable Variable | Primary Instrument / Satellite | Processing Level | Spatial Resolution | Units | Scientific Provenance |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Land Surface Temperature (`LST_C`)** | USGS Landsat-8/9 TIRS (Band 10) | Level-2 Science Product | 30m resampled to 100m | Degrees Celsius (°C) | Derived via USGS radiative transfer model; converted from Kelvin via $T_{\text{C}} = T_{\text{K}} - 273.15$. |
| **Surface Temperature QA (`LST_QA_MEDIAN_K`)** | USGS Landsat-8/9 `ST_QA` Band | Level-2 Science Product | 100m composite | Kelvin (K) | Radiometric retrieval uncertainty estimate (scale factor 0.01). Contextual QA, not causal driver. |
| **Normalized Difference Veg. Index (`NDVI`)** | Copernicus Sentinel-2 MSI (B8, B4) | Level-2A BOA Surface Reflectance | 10m aggregated to 100m | Unitless `[-1.0, 1.0]` | $\text{NDVI} = \frac{\text{NIR} - \text{Red}}{\text{NIR} + \text{Red}}$. Cloud-screened composite. |
| **Normalized Difference Built Index (`NDBI`)** | Copernicus Sentinel-2 MSI (B11, B8) | Level-2A BOA Surface Reflectance | 20m aggregated to 100m | Unitless `[-1.0, 1.0]` | $\text{NDBI} = \frac{\text{SWIR1} - \text{NIR}}{\text{SWIR1} + \text{NIR}}$. Physical impervious built-up proxy. |
| **Normalized Difference Water Index (`NDWI`)** | Copernicus Sentinel-2 MSI (B3, B8) | Level-2A BOA Surface Reflectance | 10m aggregated to 100m | Unitless `[-1.0, 1.0]` | $\text{NDWI} = \frac{\text{Green} - \text{NIR}}{\text{Green} + \text{NIR}}$. Surface water / moisture proxy. |

---

## 2. Dataset Key Uniqueness & Integrity Audit

A comprehensive integrity scan was executed on `policy_d/analysis.parquet`:
- **Total Records:** 924,731 rows.
- **Composite Primary Key:** `['year', 'season', 'row', 'col']`.
- **Key Duplicate Count:** **Exactly 0 duplicates** across all 924,731 observations.
- **Core Feature Completeness:** Coordinates, target `LST_C`, and spatial block IDs are 100% non-null and finite.

Verified via automated test: [backend/tests/test_analysis_dataset_quality.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/tests/test_analysis_dataset_quality.py).

---

## 3. Optical Sentinel (-9999) Forensic Audit

In raw satellite raster composites, no-data pixels are frequently encoded as `-9999`.

### Forensic Audit Findings:
1. **Detection:** Exactly **8 rows** out of 924,731 contain optical sentinel values (`<= -9000`).
2. **Spatial Localization:** All 8 sentinel rows reside strictly within development block `B_05_11`.
3. **Partition Isolation:** **Zero sentinel rows exist in the locked test holdout partition**.
4. **Treatment in ML Pipelines:** Sentinels are converted to `np.nan` and imputed strictly within training folds using median replacement, preventing `-9999` from contaminating gradient tree splits.

Verified via automated test: [backend/tests/test_optical_sentinel_audit.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/tests/test_optical_sentinel_audit.py).

---

## 4. Radiometric Uncertainty QA (`LST_QA_MEDIAN_K`) Forensic

- **Origin:** Traced to USGS Landsat Level-2 `ST_QA` band with scale factor 0.01 (units: Kelvin).
- **Findings:** Exactly 1,005 observations exhibit uncertainty $> 10.0\text{ K}$ (reaching ~87.52 K) during cloud-restricted monsoon composites.
- **Architectural Policy:** In accordance with the scientific freeze, `LST_QA_MEDIAN_K` is preserved as an observation quality feature and uncertainty context, NOT as a physical causal driver of urban heat.

---

## 5. Temperature Extremes & Policy D Quality Classification

- **Extreme Thermal Observation (70.2328°C):** Located at `row=201, col=199` in 2023 monsoon within development block `B_10_09`. Verified as single observation (`LST_OBS_COUNT = 1`) with high retrieval uncertainty (`LST_QA_MEDIAN_K = 84.99 K`). Classified under Policy D as `FLAGGED` for sensitivity analysis.
- **Unphysical Cold Artifacts (< 10°C):** Cold cloud shadow artifacts (such as a 6.47°C anomaly with neighbor discrepancy $< -10^\circ\text{C}$) are classified as `INVALID` and excluded under Policy D.

---

## 6. Cryptographic Provenance Manifest

All frozen scientific artifacts are sealed via SHA-256 checksums in `artifacts/ml_freeze/checksums.sha256`:

```text
e824794e5ba2e26937ac40f55f5fd788adad70b1a6b23c6ab435b08223dd9997  data/processed/sensitivity/policy_d/analysis.parquet
8a04b20c97b088ffc7d3f513ecd3e41007adea51ad16401f104529f40d8c1a2d  artifacts/ml_freeze/holdout_split.json
e7c94e8c4a527a13d7b9538d491c8e27125fb5a1c245b565df2d390113c2c7e5  artifacts/ml_freeze/feature_schema.json
e1aedd4946b1b29823bdea66ea3ec7b9ba5f20c4ddbfdf6920c2e62e6b30b7c9  artifacts/ml_freeze/xgb_tuned_policy_d.joblib
ee51f60ab3b956b1a4294d9cebb495069c8ba5fd5e7ed1a937bafc13778a2b15  artifacts/ml_freeze/model_metadata.json
5f122e6104cc2772de1d6fc6daef64de170b68d4ed74d2a8e8182144b4c21363  config/quality_policy_d.yaml
```

Verified via automated test: [backend/tests/test_scientific_freeze_audit.py::test_authoritative_manifest_and_checksum_integrity](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/tests/test_scientific_freeze_audit.py#L32-L50).
