# HEATSENSE AI — Tuned XGBoost Seasonal SHAP Attribution Analysis

**Status:** EXPERIMENTAL DIAGNOSTIC  
**Model:** `xgb_tuned_policy_d` (Tuned on 132 Development Blocks)  
**Evaluation Data:** Independent Spatial Test Holdout (33 Blocks)  
**Sample Size:** Up to 2,000 samples per seasonal stratum  

---

## 1. Seasonal Mean Absolute SHAP Attribution Table (|SHAP| degC)

| Season | `LST_QA_MEDIAN_K` | `LST_OBS_COUNT` | `NDBI` | `NDWI` | `NDVI` |
|:---|:---:|:---:|:---:|:---:|:---:|
| **OVERALL** | 2.9800 | 1.2879 | 1.3867 | 0.6981 | 0.5347 |
| **WINTER** | 4.7802 | 1.2379 | 1.1056 | 0.7026 | 0.4461 |
| **SUMMER** | 4.4230 | 0.5449 | 1.5739 | 0.7442 | 0.5028 |
| **MONSOON** | 1.1709 | 2.5202 | 1.5900 | 0.7828 | 0.7365 |
| **POST_MONSOON** | 1.0171 | 0.7262 | 1.1810 | 0.5139 | 0.5030 |

---

## 2. Scientific Behavioral Findings & Attribution Non-Causality

1. **Dominance of `NDBI` Among Physical Predictors in Summer:**
   - During peak summer, `NDBI` (built-up impervious surface index) exhibits high predictive attribution (mean |SHAP| ≈ 1.5739°C), confirming that urban thermal contrast is predominantly predicted by impermeable vs vegetated surface density during hot dry periods.

2. **Monsoon Observation Support Surges While QA Attribution Drops:**
   - During monsoon, `LST_OBS_COUNT` becomes the most influential predictor among the evaluated features (mean |SHAP| = 2.5202°C), while `LST_QA_MEDIAN_K` attribution decreases to 1.1709°C. This indicates that temporal observation support becomes particularly informative under cloud-restricted conditions.

3. **Non-Causal Interpretation of `LST_QA_MEDIAN_K`:**
   - `LST_QA_MEDIAN_K` provides a strong retrieval-quality and observation-context signal associated with seasonal atmospheric conditions. Its high predictive contribution must NOT be interpreted as evidence that radiometric uncertainty itself physically causes surface heating. SHAP values represent decision tree feature attribution, not physical causal mechanisms.

4. **Attribution Stability:**
   - Across all seasons, `NDBI` consistently leads the physical surface predictors (`NDBI` > `NDWI` > `NDVI`).