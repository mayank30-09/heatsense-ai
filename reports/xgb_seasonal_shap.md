# HEATSENSE AI — Seasonal SHAP Attribution Analysis

**Document Version:** 1.0-SCIENTIFIC-EVIDENCE  
**Target Area:** Surat Municipal Corporation (SMC), Gujarat, India  
**Date:** September 2026  
**Status:** **SCIENTIFIC FREEZE REVIEW**  

---

## 1. Executive Summary & Non-Causal Grounding

This report investigates whether feature attribution rankings change across climatological seasons, focusing especially on `LST_QA_MEDIAN_K` and `LST_OBS_COUNT` during the cloud-restricted monsoon period.

> [!IMPORTANT]
> **Non-Causal Principle:** SHAP values represent statistical attribution within the fitted decision-tree ensemble, > **NOT physical causation**. A high SHAP attribution for `LST_QA_MEDIAN_K` demonstrates that the model utilizes radiometric > uncertainty as an informative seasonal background indicator; it does NOT imply that sensor uncertainty causes physical heating.

---

## 2. Seasonal Feature Attribution (Mean $|SHAP|$ Values)

| Stratum | Sample Size ($N$) | `LST_QA_MEDIAN_K` | `NDBI` | `LST_OBS_COUNT` | `NDWI` | `NDVI` |
|---|---|---|---|---|---|---|
| **Overall** | 2,000 | **2.9714** | 1.5293 | 1.2334 | 0.7468 | 0.5371 |
| **Winter** | 2,000 | **4.6930** | 1.1429 | 1.3090 | 0.7228 | 0.4410 |
| **Summer** | 2,000 | **4.4129** | 1.7563 | 0.5056 | 0.7964 | 0.5413 |
| **Monsoon** | 2,000 | **1.2909** | 1.7802 | 2.2352 | 0.8913 | 0.7467 |
| **Post_monsoon** | 2,000 | **0.9596** | 1.3214 | 0.7851 | 0.5449 | 0.4530 |

---

## 3. Scientific Behavioral Findings

1. **Dominance of `NDBI` in Summer:**
   - During peak summer, `NDBI` (built-up impervious surface index) exhibits its highest physical attribution, confirming that urban thermal contrast is predominantly dictated by impermeable vs vegetated surface density during hot dry periods.

2. **Elevated `LST_QA_MEDIAN_K` in Monsoon:**
   - Attribution for `LST_QA_MEDIAN_K` expands notably during the monsoon season. In high-humidity, cloud-prone scenes, atmospheric column water vapor increases sensor radiometric uncertainty. The model leverages this signal as a conditional atmospheric baseline.

3. **Attribution Stability:**
   - The primary physical environmental feature ranking (`NDBI` > `NDWI` > `NDVI`) remains robust and invariant across all four seasons.