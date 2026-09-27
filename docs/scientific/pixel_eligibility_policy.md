# HEATSENSE AI — Pixel Quality and Eligibility Policy Specification (DRAFT)

**Project:** HEATSENSE AI — AI-Powered GIS-Based Urban Heat Mitigation & Cooling Decision-Support Platform  
**Target Area:** Surat Municipal Corporation (SMC), Gujarat, India (EPSG:4326 / EPSG:32643)  
**Document Version:** 1.0-DRAFT  
**Status:** **DRAFT / UNDER SCIENTIFIC REVIEW — NOT YET FROZEN**  
**Date:** September 2026  

---

## 1. Purpose

The objective of the HEATSENSE AI Pixel Eligibility Policy is to establish a rigorous quality-control gate between raw satellite observations and downstream machine learning and spatial optimization pipelines. 

In urban heat island (UHI) analytics, satellite thermal observations frequently suffer from localized radiative transfer distortions, unflagged cloud-edge artifacts, and retrieval uncertainties under high atmospheric moisture conditions. A naive filter that simply deletes all extreme values (e.g. clipping $LST > 50^\circ\text{C}$ or enforcing universal $OBS \ge 2$) purges critical real-world industrial heat generators and starves the model of 40% of Surat's landmass during monsoon seasons. Conversely, an unfiltered dataset permits erroneous cold-edge anomalies (such as single-observation $6.47^\circ\text{C}$ minimums) to enter baseline training data.

This policy establishes an evidence-based, tripartite classification:
- **ACCEPT:** Uncompromised pixel with sufficient multi-temporal support and spatial consistency.
- **FLAG:** Retained for modeling but annotated with quality warnings (e.g. single-observation coverage or elevated radiometric uncertainty) to guide uncertainty-aware loss functions.
- **EXCLUDE:** Discarded due to strong evidence of being a non-physical artifact (e.g. single-pass severe spatial outliers on raster boundaries).

---

## 2. Input Data & Lineage

The policy evaluates a multivariate attribute tuple derived from USGS Landsat 8/9 Collection 2 Level-2 Surface Temperature and Surface Reflectance products:

1. **`LST_C`:** Land Surface Temperature in Celsius derived from Band 10 thermal infrared radiance using single-channel atmospheric compensation.
2. **`LST_OBS_COUNT`:** Number of clear-sky observations contributing to the seasonal composite.
3. **`ST_QA_K`:** Pixel-level radiometric surface temperature uncertainty in Kelvin from the USGS Level-2 `ST_QA` band.
4. **`NDVI` / `NDBI` / `NDWI`:** Seasonal median optical indices representing vegetation abundance, built-up density, and surface water moisture.
5. **Optical Observation Counts:** `ndvi_obs_count`, `ndbi_obs_count`, `ndwi_obs_count`.
6. **3×3 Neighborhood Metrics:** Non-circular statistics calculated over the 8 surrounding cells (excluding center pixel): `neighborhood_median`, `neighborhood_mean`, `neighborhood_std`, and `valid_neighbor_count`.
7. **Spatial Deviation:** Absolute and signed differences between center pixel LST and neighborhood median ($\Delta_{\text{med}}$).
8. **Boundary Context:** Indicator for raster edge pixels ($row \in \{0, H-1\}$ or $col \in \{0, W-1\}$) and cells with insufficient neighbors ($< 4$ valid adjacent cells).
9. **Hotspot Persistence:** Historical recurrence frequency of the pixel in upper percentiles ($P_{99}$ or Top 20) across all observed multi-year seasons (`hotspot_frequency` and `is_persistent_hotspot`).

---

## 3. Quality Indicators

| Indicator | Definition | Normal Range | Anomaly / Warning Threshold |
|---|---|---|---|
| **Temporal Support** | Clear-sky scene count ($OBS$) | $\ge 4$ (Winter/Summer: 10–20) | $OBS < 2$ (Low), $2 \le OBS < 4$ (Moderate) |
| **Spatial Consistency** | Absolute deviation from 3×3 median ($|\Delta_{\text{med}}|$) | $\le 5.0^\circ\text{C}$ | $> 10.0^\circ\text{C}$ (Spatial Anomaly) |
| **Neighborhood Density** | Count of valid adjacent 100m cells | 8 cells | $< 4$ cells (Insufficient Support) |
| **Radiometric QA** | Median USGS ST_QA uncertainty | $2.0 - 5.0\text{ K}$ | $> 15.0\text{ K}$ (Elevated uncertainty) |
| **Hotspot Persistence** | Fraction of seasons active in Top 1% LST | $< 0.10$ (Transient) | $\ge 0.25$ (Frequent), $\ge 0.50$ (Chronic) |

---

## 4. Tripartite Eligibility Classification Framework

### 4.1 ACCEPT Conditions
A pixel is assigned **ACCEPT** when:
1. Clear-sky observation count is robust ($OBS \ge 2$).
2. Spatial deviation from 3×3 neighborhood median is within plausible urban thermal bounds ($|\Delta_{\text{med}}| \le 10.0^\circ\text{C}$).
3. Minimum neighborhood density is satisfied ($\ge 4$ valid neighbors).

### 4.2 FLAG Conditions
A pixel is assigned **FLAG** when it represents valid physical data but carries elevated uncertainty:
1. **Low Temporal Support Hotspot:** $OBS = 1$, but the pixel is spatially coherent ($|\Delta_{\text{med}}| \le 10.0^\circ\text{C}$) or verified as a chronic persistent hotspot (`is_persistent_hotspot == True`, e.g. Pandesara GIDC metal roofing).
2. **Elevated Radiometric Uncertainty:** $ST\_QA > 15.0\text{ K}$, typical of low-emissivity industrial surfaces across all seasons.
3. **Boundary Edge with Plausible LST:** Border pixels with $< 4$ neighbors but lacking extreme spatial spikes.

### 4.3 EXCLUDE Conditions
A pixel is assigned **EXCLUDE** only when multiple compounding lines of evidence prove it to be an unobservable or corrupted cell:
1. $OBS = 0$ (unobserved NoData).
2. Non-finite or missing LST value.
3. **Severe Single-Observation Spatial Anomaly:** $OBS = 1$ AND $|\Delta_{\text{med}}| > 10.0^\circ\text{C}$ (e.g. unflagged cloud-shadow fringes like the 6.47°C anomaly in 2023 monsoon).

---

## 5. Seasonal & Monsoon Handling

### 5.1 Dry Seasons (Winter, Summer, Post-Monsoon)
- Observation support is uniformly abundant across Surat ($mean = 7.0 - 13.3$ clear scenes).
- 100% of the municipal area achieves $OBS \ge 4$.
- Discrepancies between candidate eligibility policies during dry seasons are essentially zero (100% retention under all policies).

### 5.2 Monsoon Season (June – September)
- Severe persistent cloud cover restricts clear views, reducing mean seasonal observation counts to $1.77 - 3.96$.
- In peak monsoon, **over 70% of upper-tier industrial hotspots are observed only once ($OBS = 1$)**.
- Enforcing a naive $OBS \ge 2$ rule deletes **62.27% of monsoon hotspots** and collapses spatial coverage across Surat to **59.40%**.
- Therefore, **Monsoon pixels with $OBS = 1$ MUST NOT be automatically discarded**. They must be evaluated against 3×3 spatial coherence and historical persistence:
  - Spatially coherent hotspots are retained as **FLAG**.
  - Isolated spikes with large negative deviations ($\Delta < -10^\circ\text{C}$) are purged as **EXCLUDE**.

---

## 6. Candidate Eligibility Policies Evaluated

Four candidate policies were systematically tested across all 19 seasons (2022–2026):

| Policy ID | Policy Formulation | Monsoon Retention (%) | Monsoon Coverage (%) | Monsoon Hotspot Retention (%) | Monsoon Cold Anomaly Removal (%) |
|---|---|---|---|---|---|
| **Policy A** | $OBS \ge 1$ (Unconstrained baseline) | 100.00% | 90.01% | 100.00% | 40.00% (Retains severe cloud artifacts) |
| **Policy B** | $OBS \ge 2$ (Strict multi-observation cutoff) | 64.68% | 59.40% | 37.73% (Loses 62.3% of hotspots) | 100.00% |
| **Policy C** | $OBS \ge 2$ OR Chronic Persistent Hotspot | 65.16% | 59.82% | 61.39% (Rescues chronic hotspots) | 100.00% |
| **Policy D** | $OBS \ge 1$ with Selective Anomaly Exclusion | **99.95%** | **89.96%** | **99.18%** (Preserves urban heat islands) | **100.00%** (Purges extreme spatial anomalies) |

### 6.1 Policy Tradeoff Evaluation
- **Policy A** fails because it permits unflagged severe cold outliers (e.g. 6.47°C) into the downstream dataset.
- **Policy B** creates severe spatial and thematic starvation, discarding 40.6% of Surat's land area and 62.3% of its monsoon urban heat islands.
- **Policy C** successfully protects verified multi-season hotspots (e.g. Pandesara 70.23°C hotspot), but still suffers from 40% spatial data loss across non-hotspot residential/commercial wards.
- **Policy D** represents the most balanced **EVIDENCE-SUPPORTED CANDIDATE**: it satisfies the single-observation spatial-anomaly exclusion rule, purging 123 severe single-observation anomalies (including cloud-edge/cloud-shadow-like depressions) while preserving 99.18% of urban heat islands and 89.96% of city-wide spatial coverage.

---

## 7. Known Limitations & Scientific Uncertainties

1. **Monsoon Extreme Magnitude Uncertainty:** While Policy D correctly retains verified industrial hotspots with $OBS = 1$, the unusually high monsoon temperature magnitude (e.g. observed peaks exceeding 70°C) may reflect a combination of limited temporal support, atmospheric/retrieval conditions, and genuine thermal characteristics of the industrial surface. The present analysis does not isolate the causal contribution of these mechanisms. Downstream models must treat absolute monsoon values with appropriate caution.
2. **ST_QA Thresholding Failure:** Radiometric uncertainty cannot be used as an exclusion criterion because low-emissivity industrial surfaces systematically trigger high uncertainty ($ST\_QA > 65\text{ K}$) during winter, summer, and monsoon alike.
3. **Formal Policy Status:** This policy specification is formally documented in `config/quality_policy_d.yaml` and verified against independent spatial holdout and feature ablation benchmarks.

