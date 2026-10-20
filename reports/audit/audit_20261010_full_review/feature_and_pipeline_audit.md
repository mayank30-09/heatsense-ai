# HEATSENSE AI — Feature Engineering and Scientific Pipeline Audit

**Audit Run ID:** `audit_20261010_full_review`  
**Evaluation Date:** 2026-10-10  
**Authoritative Review Specification:** `ChatGPT-SEEANALYSEANDREVIEWT.pdf`  
**Primary Standards:** Real Code, Physical Landsat Calibration, USGS Level-2 Specifications, PostGIS Live Database  

---

## 1. End-to-End Scientific Transformation Trace

The complete data pipeline transforms raw spaceborne observations into operational decision-support priority scores through seven auditable stages:

```
[USGS Landsat 8/9 Level-2 Collection 2 (GEE)]
                    ↓
[Thermal & Optical Radiometric Calibration (ST_B10, QA_PIXEL, Surface Reflectance)]
                    ↓
[Seasonal Compositing & QA Filtering (Winter, Summer, Monsoon, Post-Monsoon: 2022–2026)]
                    ↓
[Cloud-Optimized GeoTIFF Generation (19 COGs, 10 Bands, 318x324 @ ~100m in EPSG:4326)]
                    ↓
[Pixel Eligibility Policy D Filtering (Purge OBS=1 Spatial Anomalies → 924,731 Rows)]
                    ↓
[Stage C Analytical Grid Construction (49,747 Operational Centroid-Inside Cells)]
                    ↓
[Multi-Temporal Persistence & Moore Neighborhood Optical Imputation]
                    ↓
[HPI Composite Scoring (v2.0: 0.40T + 0.30P + 0.15V + 0.15B) & PostGIS Persistence]
```

---

## 2. Satellite Source Ingestion & Physical Radiometric Calibration

### 2.1 Sensor & Collection Verification
- **Source Provider:** USGS Earth Resources Observation and Science (EROS) via Google Earth Engine (`ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")` and `ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")`).
- **Scene Ingestion Period:** 2022-01-01 to 2026-06-01.
- **Scenes Verified:** Exactly **329 retained scenes** (162 Landsat 8, 167 Landsat 9) intersecting the Surat Municipal Corporation boundary box (`[72.6836, 21.0345, 72.9679, 21.3242]`).
- **Temporal Integrity:** Verified in Gate 01 (`artifacts/pre_heat_priority_validation/01_source_validation.json`).

### 2.2 Land Surface Temperature (LST) Calibration Formula
In `gis/gee/seasonal_features.py` (lines 84–97), the USGS Collection 2 Level-2 thermal band `ST_B10` is converted to physical Celsius temperature using the official USGS multiplicative scale factor and additive offset:

$$LST_{\text{Kelvin}} = ST\_B10 \times 0.00341802 + 149.0$$

$$LST_{{}^\circ\text{C}} = LST_{\text{Kelvin}} - 273.15 = ST\_B10 \times 0.00341802 - 124.15$$

**Audit Verification:**
- Tested across 50 diverse Surat sample pixels.
- Maximum deviation between production COG values and independent Python USGS conversion was $< 1 \times 10^{-5}\ ^\circ\text{C}$ (`02_lst_conversion_validation.json`).

### 2.3 Cloud and Radiometric Saturation Masking
In `gis/gee/seasonal_features.py` (lines 102–126), pixels are masked using bitwise operators on `QA_PIXEL` and `QA_RADSAT`:
- `QA_PIXEL` Bit 0: Fill (`1 << 0`)
- `QA_PIXEL` Bit 1: Dilated Cloud (`1 << 1`)
- `QA_PIXEL` Bit 2: Cirrus (`1 << 2`)
- `QA_PIXEL` Bit 3: Cloud (`1 << 3`)
- `QA_PIXEL` Bit 4: Cloud Shadow (`1 << 4`)
- `QA_PIXEL` Bit 5: Snow (`1 << 5`)
- `QA_RADSAT`: Bitwise test for thermal detector saturation (`QA_RADSAT == 0`).

**Audit Verification:** 100% of bitwise test patterns pass in `backend/tests/test_scientific_freeze_audit.py` (`03_qa_mask_validation.json`).

---

## 3. Seasonal Compositing & Production COG Rasters

### 3.1 Seasonal Window Definitions
Seasonal compositing strictly enforces meteorological windows aligned with western India climate patterns:

| Season Name | Exact Calendar Span | Rationale & Solar/Monsoon Context | COGs Available |
| :--- | :--- | :--- | :---: |
| **Winter** | Dec 1 (prior year) to Feb 28/29 | Minimum solar elevation, cool dry conditions | 2022, 2023, 2024, 2025, 2026 (5) |
| **Summer** | Mar 1 to May 31 | Pre-monsoon peak thermal extremity, clear sky | 2022, 2023, 2024, 2025, 2026 (5) |
| **Monsoon** | Jun 1 to Sep 30 | Southwest monsoon, heavy cloud cover, rain | 2022, 2023, 2024, 2025, 2026 (5) |
| **Post-Monsoon** | Oct 1 to Nov 30 | Retreating monsoon, transitional humidity | 2022, 2023, 2024, 2025 (4) |
| **Total** | 2022 through Summer 2026 | Comprehensive multi-year climate record | **19 COGs** |

### 3.2 Production Cloud-Optimized GeoTIFF (COG) Specifications
All 19 seasonal raster files in `data/processed/seasonal/<year>/<season>/surat_<year>_<season>_features_cog.tif` conform to the Cloud-Optimized GeoTIFF standard:
- **Spatial Dimensions:** 318 columns $\times$ 324 rows = 103,032 pixels.
- **Pixel Ground Resolution:** $0.000898315284^\circ$ ($\approx 100\text{ m}$ latitude, $\approx 93\text{ m}$ longitude).
- **Coordinate Reference System:** `EPSG:4326` (WGS 84).
- **Data Type:** `Float32` across all bands.
- **Tiling & Overviews:** Internal tile dimension $256 \times 256$; 4 internal pyramid overviews (2x, 4x, 8x, 16x).
- **NoData Value:** `-9999.0`.
- **Band Schema (10 Bands):**
  1. `LST_C`: Multi-temporal seasonal median Land Surface Temperature (°C).
  2. `LST_OBS_COUNT`: Number of valid clear-sky thermal observations per pixel.
  3. `LST_QA_MEDIAN_K`: Median radiometric uncertainty from `ST_QA` (Kelvin).
  4. `NDVI`: Normalized Difference Vegetation Index.
  5. `NDBI`: Normalized Difference Built-Up Index.
  6. `NDWI`: Normalized Difference Water Index.
  7. `QUALITY_FLAG`: Encoded pixel eligibility bitmask.
  8. `IS_HOT`: Boolean indicator for thermal extremity in the season.
  9. `HOTSPOT_FREQUENCY`: Multi-temporal hot frequency across prior seasons.
  10. `RESERVED`: Spatial context and auxiliary mask.

---

## 4. Pixel Eligibility Policies & Policy D Formulation

To determine how low-observation and cloudy pixels are handled, four candidate policies were tested across 924,000+ observations:

| Policy | Description | Filtering Rule | Resulting Dataset Rows | Key Scientific Behavior |
| :--- | :--- | :--- | :---: | :--- |
| **Policy A** | Unconstrained Baseline | Retain all $OBS \ge 1$ | 924,854 | Retains 123 unvalidated cloud-shadow artifacts on boundary edges. |
| **Policy B** | Strict Cutoff | Exclude all $OBS < 2$ | 847,179 | Discards 77,552 valid low-observation pixels during cloud-restricted monsoon seasons. |
| **Policy C** | Hotspot-Rescued | Require $OBS \ge 2$, rescue chronic hotspots with $OBS = 1$ | 848,252 | Rescues 1,073 chronic hotspot pixels, but discards non-hotspot rural/coastal pixels with $OBS = 1$. |
| **Policy D** | **Authoritative Standard** | **Accept $OBS \ge 1$, selectively purge OBS = 1 spatial anomalies** | **924,731** | **Purges the 6.47°C cold cloud artifact while retaining the spatially coherent 70.23°C extreme.** |

### 4.1 Policy D Decision Logic (`gis/quality/eligibility.py`)
Lines 128–173 implement the approved Policy D filtering logic:
```python
def evaluate_policy_d(
    obs_count: float | int | None,
    quality_flags: list[str] | None = None,
    abs_diff_med: float | None = None,
    valid_neighbor_count: int = 8,
    is_boundary_context: bool = False,
    anomaly_diff_thresh: float = 10.0,
    **kwargs: Any,
) -> tuple[EligibilityStatus, str]:
    if _is_invalid_or_zero_obs(obs_count):
        return EligibilityStatus.EXCLUDE, "Excluded (OBS < 1)"
    flags = quality_flags or []
    if obs_count >= 2:
        if "SPATIAL_ANOMALY" in flags:
            return EligibilityStatus.FLAG, "Retained under Policy D (OBS >= 2) with spatial anomaly warning"
        return EligibilityStatus.ACCEPT, "Eligible under Policy D (OBS >= 2)"
    
    # OBS == 1 handling
    has_large_dev = (abs_diff_med is not None and abs_diff_med > anomaly_diff_thresh)
    is_severe_anomaly = ("LOW_SUPPORT_SPATIAL_EXTREME" in flags) or has_large_dev
    if is_severe_anomaly:
        return EligibilityStatus.EXCLUDE, "Excluded under Policy D (OBS=1 with severe spatial neighborhood anomaly)"
    if is_boundary_context and valid_neighbor_count < 4:
        return EligibilityStatus.FLAG, "Retained under Policy D (OBS=1 on boundary edge, review recommended)"
    return EligibilityStatus.FLAG, "Retained under Policy D (OBS=1, spatially coherent, flagged for temporal support)"
```

---

## 5. Optical Sentinel Investigation & Moore Neighborhood Imputation

### 5.1 Sentinel Presence Deep-Dive
During Gate 06 dataset profiling, numerical nodata sentinel values (`-9999.0`) were detected in optical columns:
- `NDVI == -9999.0`: Exactly 7 rows (0.000757%).
- `NDBI == -9999.0`: Exactly 2 rows (0.000216%).
- `NDWI == -9999.0`: Exactly 3 rows (0.000324%).
- **Unique Sentinel Observations:** Exactly **8 rows** out of 924,731 (**0.000865%** of the dataset).

### 5.2 Isolation to Development Partition
- **Development Partition (132 blocks):** 8 rows (all in blocks `B_05_11` [7 rows] and `B_10_04` [1 row]).
- **Locked Test Partition (33 blocks):** Exactly **0 rows** (0.0000%). The held-out evaluation population contains zero sentinel values.
- **Season:** 100% (8 / 8) occurred in Monsoon season composites where severe cloud cover prevented cloud-free optical acquisition, but a valid thermal retrieval existed.

### 5.3 Deterministic Moore Neighborhood Imputation (`gis/quality/imputation.py`)
To prevent passing raw `-9999.0` into clipping formulas (where `-9999` would artificially saturate vegetation deficit to 1.0), the 8-connected Moore neighborhood imputation engine was implemented:

1. **Neighborhood Median ($\ge 4$ valid 8-connected neighbors):**
   - Imputed value = Median of valid spatial neighbors.
   - Flag: `OPTICAL_IMPUTED_MEDIAN`.
   - Quality factor: $C_{sentinel} = 0.70$.
2. **Boundary Mean (1–3 valid 8-connected neighbors):**
   - Imputed value = Mean of available neighbors.
   - Flag: `OPTICAL_IMPUTED_BOUNDARY`.
   - Quality factor: $C_{sentinel} = 0.50$.
3. **Isolated Neutral Fallback (0 valid neighbors):**
   - Imputed constants: $\text{NDVI} = 0.20$, $\text{NDBI} = 0.00$, $\text{NDWI} = -0.30$.
   - Flag: `OPTICAL_FALLBACK_NEUTRAL`.
   - Quality factor: $C_{sentinel} = 0.30$.

### 5.4 Machine-Learning Cooling Disqualification Guardrail
In `gis/quality/imputation.py` (line 145), an explicit guardrail is enforced:
```python
ml_cooling_eligible = (optical_imputation_flag == "NONE")
```
Cells relying on imputed optical values are explicitly marked ineligible for downstream micro-climate cooling projection scenarios in Stage D.

---

## 6. Stage C Heat Priority Index (HPI) Formulation

### 6.1 Mathematical Formula
In accordance with `ChatGPT-SEEANALYSEANDREVIEWT.pdf` (Section 3, Pages 4–8) and `gis/heat_priority/scoring.py`, the Heat Priority Index is calculated as:

$$HPI = 100 \times \left(0.40 \cdot T + 0.30 \cdot P + 0.15 \cdot V + 0.15 \cdot B\right)$$

where:
1. **$T$ (Thermal Severity Component):** Normalized observed summer Land Surface Temperature:
   $$T = \text{clamp}\left(\frac{LST_{\text{observed}} - 30.0}{50.0 - 30.0},\ 0.0,\ 1.0\right)$$
   Reference bounds: $30.0^\circ\text{C}$ (baseline comfortable summer threshold in Surat) to $50.0^\circ\text{C}$ (severe extreme heat threshold).
2. **$P$ (Persistence Component):** Valid multi-year hot-observation frequency:
   $$P = \text{clamp}\left(\frac{N_{\text{hot}}}{N_{\text{valid}}},\ 0.0,\ 1.0\right)$$
   where $N_{\text{valid}} \ge 4$. If $N_{\text{valid}} < 4$, $P = 0.0$.
3. **$V$ (Vegetation Deficit Component):** Normalized vegetation deficit derived from valid/cleaned NDVI:
   $$V = \text{clamp}\left(\frac{0.45 - \text{NDVI}}{0.45 - 0.05},\ 0.0,\ 1.0\right)$$
   Reference bounds: $\text{NDVI} \ge 0.45$ represents healthy cooling canopy ($V = 0.0$); $\text{NDVI} \le 0.05$ represents barren ground/pavement ($V = 1.0$).
4. **$B$ (Built-Up Density Component):** Normalized built-up index derived from valid/cleaned NDBI:
   $$B = \text{clamp}\left(\frac{\text{NDBI} - (-0.25)}{0.15 - (-0.25)},\ 0.0,\ 1.0\right)$$
   Reference bounds: $\text{NDBI} \le -0.25$ represents water/dense green space ($B = 0.0$); $\text{NDBI} \ge 0.15$ represents high-density impervious built environment ($B = 1.0$).

### 6.2 Component Weight Conservation
The weights are strictly validated in `gis/heat_priority/scoring.py` (lines 142–148):
```python
weights = (cfg.w_thermal, cfg.w_persistence, cfg.w_vegetation, cfg.w_built)
assert all(w >= 0.0 for w in weights), "Weights must be non-negative"
assert math.isclose(sum(weights), 1.0, abs_tol=1e-12), "Weights must sum to 1.0"
```

### 6.3 Missing Summer Policy & Genuine SQL NULL Semantics
If observed summer LST is missing, non-finite, or invalid, the scoring function returns an insufficient-data result:
```python
if not summer_observation_valid or lst is None:
    return HPIResult(
        score=None,
        thermal=None,
        persistence=None,
        vegetation_deficit=None,
        built_density=None,
        eligibility="INSUFFICIENT_DATA",
        reason="MISSING_OR_INVALID_OBSERVED_SUMMER_LST",
    )
```
The score is stored as genuine SQL `NULL` in PostgreSQL and serialized as JSON `null` in the API. Modeled or neighboring LST is **never** silently substituted for observed summer LST.

---

## 7. Persistence Rules & Chronic Hotspot Identification

### 7.1 Temporal Denominator Rule
In `gis/heat_priority/persistence.py`, persistence frequency is calculated strictly against valid seasonal observations:
- Hot threshold: $LST \ge P90$ calculated per year-season across valid SMC pixels.
- Denominator ($N_{\text{valid}}$): Count of clear-sky passes with $OBS \ge 2$.
- Cloudy unobserved seasons are **never** counted as cool passes.

### 7.2 Chronic Hotspot Classification Criteria
A grid cell is classified as a **Chronic Hotspot** (`is_chronic_hotspot = True`, `persistence_tier = 'chronic_hotspot'`) if and only if:
1. $N_{\text{valid}} \ge 4$ (sufficient multi-temporal observation support).
2. $N_{\text{hot}} \ge 3$ (at least 3 qualifying extreme hot passes).
3. Hot passes span $\ge 2$ distinct calendar years (rejection of single-year anomalies/heatwaves).
4. $f_{\text{hot}} = N_{\text{hot}} / N_{\text{valid}} \ge 0.50$ (hot during at least 50% of observable opportunities).

**Audit Result:**
- Exactly **223 chronic hotspots** identified dynamically across Surat.
- All 223 cells satisfy the multi-year and observation support criteria.
- No count was hard-coded; classification is evaluated strictly via boolean array masking.

---

## 8. Multi-Factor Heuristic Confidence Index

In `gis/heat_priority/quality.py`, data quality is evaluated via a multiplicative confidence index:

$$CI = C_{\text{obs}} \times C_{\text{qa}} \times C_{\text{season}} \times C_{\text{sentinel}} \in [0.0,\ 1.0]$$

where:
1. $C_{\text{obs}} \in [0.5, 1.0]$: Penalty for low seasonal observation counts ($OBS < 2$).
2. $C_{\text{qa}} \in [0.4, 1.0]$: Radiometric calibration quality based on Landsat `ST_QA` uncertainty (Kelvin):
   - $ST\_QA \le 2.50\text{ K} \implies 1.00$
   - $2.50\text{ K} < ST\_QA \le 3.50\text{ K} \implies 0.85$
   - $3.50\text{ K} < ST\_QA \le 4.50\text{ K} \implies 0.65$
   - $ST\_QA > 4.50\text{ K} \implies 0.40$
3. $C_{\text{season}} \in [0.4, 1.0]$: Seasonal observation completeness:
   - Complete multi-season record (summer, winter, post-monsoon) $\implies 1.00$
   - Dry seasons complete (summer + winter) $\implies 0.90$
   - Summer only $\implies 0.70$
   - Missing summer $\implies 0.40$
4. $C_{\text{sentinel}} \in [0.3, 1.0]$: Optical quality factor (1.00 for clean optical data; 0.70 for median imputation; 0.50 for boundary mean; 0.30 for neutral fallback).

### 8.1 Confidence Tiers in the 2026 Operational Run
- `HIGH` ($CI \ge 0.75$): **49,674 cells** (99.85%)
- `MODERATE` ($0.50 \le CI < 0.75$): **73 cells** (0.15%)
- `LOW` ($0.30 \le CI < 0.50$): **0 cells** (0.00%)
- `INSUFFICIENT` ($CI < 0.30$): **0 cells** (0.00%)
- **Total Operational Cells:** **49,747 cells**.
