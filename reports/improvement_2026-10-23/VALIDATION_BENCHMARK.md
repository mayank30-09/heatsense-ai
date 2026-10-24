# HEATSENSE AI — Phase 2: Validation, Baseline Comparison & Holdout Safety Report

**Date:** 2026-10-23  
**Active Branch:** `fix/runtime-working`  
**Evaluation Scope:** Development Set Validation & Spatial Holdout Evaluation  
**Study Domain:** Surat Municipal Corporation (SMC), Gujarat, India  

---

## 1. Executive Summary

Phase 2 establishes the empirical scientific validation of HEATSENSE AI's thermal models. Candidate models and baselines are benchmarked within the **132 development spatial blocks**. In accordance with machine learning protocols:
1. **Spatial Holdout Split:** The 33 test blocks ($20.0\%$ of the domain, 203,758 observations) were reserved for final evaluation and excluded from hyperparameter tuning and model selection.
2. **Zero Spatial Overlap:** The spatial intersection between development blocks and test blocks is **strictly empty** ($\text{dev\_blocks} \cap \text{test\_blocks} = \emptyset$).
3. **Controlled Architecture Comparison:** Under identical 5-fold spatial cross-validation (`model_comparison_rf_xgb.csv`), Random Forest achieves an RMSE of $1.8024 \pm 0.0545^\circ\text{C}$ ($R^2 = 0.9014$) and XGBoost achieves $1.8280 \pm 0.0607^\circ\text{C}$ ($R^2 = 0.8986$). Earlier comparisons that reported RF RMSE as $2.0931^\circ\text{C}$ used a different fold definition and are superseded. While Random Forest achieves a marginally lower CV RMSE, XGBoost is selected for production because of inference throughput ($186,000$ cells/sec CPU batch latency) and compact artifact size ($17\text{MB}$ vs $>120\text{MB}$ for Random Forest).

---

## 2. Spatial Holdout Disjointness & Partition Integrity

The Surat SMC domain is partitioned into $165$ discrete $2\text{km} \times 2\text{km}$ spatial blocks. Under seed 42 with an $80/20$ split ratio:

| Metric | Development Split | Test Holdout Split | Total / Domain |
| :--- | :---: | :---: | :---: |
| **Spatial Blocks** | 132 blocks ($80.0\%$) | 33 blocks ($20.0\%$) | 165 blocks ($100.0\%$) |
| **Dataset Rows** | 720,973 ($77.97\%$) | 203,758 ($22.03\%$) | 924,731 ($100.0\%$) |
| **Block Disjointness** | **Strictly Disjoint** | **Strictly Disjoint** | $\text{Dev} \cap \text{Test} = \emptyset$ |
| **Row Leakage** | 0 overlapping rows | 0 overlapping rows | 0 leakage |
| **Coordinate Exclusion** | `lat`, `lon`, `row`, `col`, `block_id` excluded from ML features | Same | Coordinates 100% excluded |

### Spatial Holdout Protocol
- `test_accessed_during_tuning`: `False` (documented in `artifacts/ml_freeze/evaluation_manifest.json`).
- `test_blocks_excluded_from_optuna`: `True` (documented in `artifacts/ml_freeze/qc_summary.json`).
- `test_blocks_excluded_from_feature_selection`: `True`.
- `test_blocks_excluded_from_model_selection`: `True`.
- `test_blocks_excluded_from_final_training`: `True`.
- Final evaluation on the 33 locked test blocks: $\text{MAE} = 1.2726^\circ\text{C}$, $\text{RMSE} = 1.7524^\circ\text{C}$, $R^2 = 0.9006$.

### Holdout Usage Disclosure
> "The final model (xgb_tuned_policy_d, SHA-256 e1aedd49...) was evaluated once on the 33 locked test blocks: MAE 1.2726 C, RMSE 1.7524 C, R2 0.9006. Earlier, a preliminary tuning study (artifacts/xgb_tuning/) was run before the holdout split existed; its CV used all 165 blocks (unique_blocks_count 165), so the blocks later locked as the test set were part of that study, and a configuration from it was evaluated on them (RMSE 1.7342 C in the file committed in 32197ef, which does not match the frozen model). That result is superseded. The frozen study searched the 132 development blocks only (unique_blocks_in_search 132). evaluation_count: 1 is a constant written by scripts/final_holdout_evaluation.py, not a runtime counter."

---

## 3. Comprehensive Model & Baseline Benchmark (Development Set)

### Controlled RF vs XGBoost Spatial Cross-Validation
Source: `data/diagnostics/ml/model_comparison_rf_xgb.csv` [MEASURED]

The raw CSV artifact content:
```csv
model,mean_MAE,std_MAE,mean_RMSE,std_RMSE,mean_R2,std_R2
RandomForest,1.29272,0.028016370214572785,1.8023599999999997,0.05452405890980607,0.90138,0.00426110314355333
XGBoost,1.31902,0.02736598253306467,1.82802,0.060655230607096045,0.89856,0.0044858666944080795
```

Summary Table (Identical 5-Fold Spatially Grouped CV):
| Model | CV MAE (°C) | CV RMSE (°C) | CV $R^2$ | Notes |
| :--- | :---: | :---: | :---: | :--- |
| **RandomForest** | $1.2927 \pm 0.0280$ | $1.8024 \pm 0.0545$ | $0.9014 \pm 0.0043$ | Multi-tree ensemble (>120 MB artifact, higher latency) |
| **XGBoost** | $1.3190 \pm 0.0274$ | $1.8280 \pm 0.0607$ | $0.8986 \pm 0.0045$ | Production model (17 MB artifact, 186k cells/s inference) |

> **Methodological Note on Cross-Fold Comparison:** Numbers from different cross-validation fold definitions must never be directly compared. In the controlled 5-fold split above, RF slightly outperforms XGBoost in RMSE by 0.0256°C. XGBoost is chosen because of production serving constraints (low inference latency and disk footprint), not superior RMSE.

### Development Baselines & Ablation Studies (132 Development Blocks)

| Model / Baseline | Features | CV MAE (°C) | CV RMSE (°C) | CV $R^2$ | Upper Decile RMSE (°C) | Upper Decile Bias (°C) | Status / Role |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Global Mean Baseline** | None (constant mean) | 4.8812 | 5.8107 | 0.0000 | 8.9412 | +7.8920 | Naive lower bound |
| **Seasonal Mean Baseline** | `season` | 3.1245 | 3.7963 | 0.5732 | 5.6210 | +4.1023 | Temporal naive baseline |
| **Cell Mean Baseline [in-sample (not cross-validated)]** | `(row, col)` | 1.6143 | 2.4170 | 0.8268 | 4.1025 | +2.9150 | Spatial persistence memorization (in-sample) |
| **XGBoost (Optical Only)** | NDVI, NDBI, NDWI | 4.0525 | 4.9580 | 0.2668 | 7.8211 | +6.8941 | Ablation A (Ablated) |
| **XGBoost (Optical + Temp)**| Optical + `OBS_COUNT` | 3.2862 | 4.1541 | 0.4854 | 6.0384 | +4.8842 | Ablation B (Ablated) |
| **XGBoost (Optical + QA)** | Optical + `QA_MEDIAN` | 1.5675 | 2.2482 | 0.8489 | 3.6796 | +2.4294 | Ablation C (Ablated) |
| **XGBoost Baseline (Frozen)**| Full 5 features | **1.4319** | **1.8478** | **0.8815** | 3.0422 | +1.8421 | **Authoritative Frozen Model (CV)** |
| **XGBoost (TailWeight Mild)**| Full 5 features (2x Top) | 1.4411 | 2.0090 | 0.8795 | **2.8611** | **+1.5450** | Experimental Candidate 1 |
| **XGBoost (TailWeight Strong)**| Full 5 features (3.5x Top)| 1.4578 | 2.0331 | 0.8766 | **2.7140** | **+1.3320** | Experimental Candidate 2 |

### Key Benchmark Findings:
1. **Model Value Add:** The frozen XGBoost model improves RMSE by **$3.96^\circ\text{C}$** over the global mean baseline and **$0.57^\circ\text{C}$** over the in-sample cell-mean baseline.
2. **Feature Importance:** Optical features alone only explain $26.7\%$ of variance. Adding `LST_QA_MEDIAN_K` provides critical atmospheric brightness temperature grounding, jumping $R^2$ to $84.9\%$.
3. **Candidate Assessment:** The tail-weighted candidates compress upper-decile extreme heat error (reducing top-decile RMSE from $3.0422^\circ\text{C}$ down to $2.8611^\circ\text{C}$ / $2.7140^\circ\text{C}$). However, pursuant to the repository scientific freeze protocol, the frozen model `xgb_tuned_policy_d.joblib` (SHA-256 `e1aedd49...`) is **RETAINED** as production standard, with candidates cataloged as experimental alternatives.

---

## 4. Conformal Calibration & Subgroup Coverage Analysis

Spatial conformal prediction was evaluated at nominal coverage $1 - \alpha = 0.90$ across holdout blocks:

- **Overall Empirical Coverage:** $90.15\%$ (Nominal: $90.00\%$, Calibrated).
- **Average Prediction Interval Width:** $\pm 2.98^\circ\text{C}$ (Full width: $5.97^\circ\text{C}$).
- **Seasonal Subgroup Coverage:**
  - Summer: $90.53\%$ (Nominal met)
  - Winter: $95.68\%$ (Conservative)
  - Post-Monsoon: $95.80\%$ (Conservative)
  - Monsoon: $79.19\%$ (Undershoot: -10.81% gap caused by cloud masking variance and dry-spell extreme breaks).
- **Decile Subgroup Coverage:**
  - Deciles 1–9: $87.93\% - 94.86\%$ coverage across bins.
  - Decile 10 (Extreme Tail): $83.43\%$ (Undershoot: -6.57% gap due to sharp industrial localized hotspots).

> **Calibrated Probability Disclosure:** "Confidence index is a heuristic, not a calibrated probability." The spatial confidence score $C_i$ synthesizes observation frequency, thermal radiometer saturation, and atmospheric QA bitmasks into an operational prioritization ranking; it must not be interpreted as an empirical probability.

### Policy D Quality Screening Counts & Data Freshness
- **Total Valid Observations:** 924,731 rows
- **Development Split:** 720,973 rows (77.97%) across 132 blocks
- **Test Holdout Split:** 203,758 rows (22.03%) across 33 blocks
- **Spatial Grid:** 49,747 regular analytical cells per composite (100m resolution, EPSG:4326)
- **Temporal Freshness & Scope:** 19 seasonal composites across 2022–2026 (Landsat 8/9 TIRS & OLI-2, USGS Collection 2 Level 2, ~10:30 local solar / 11:00 IST overpass)

---

## 5. Artifact Verification & Compliance Checklist

- [x] `artifacts/ml_freeze/holdout_split.json` verified matching 41-file manifest.
- [x] `artifacts/ml_freeze/qc_summary.json` verified matching 41-file manifest.
- [x] `artifacts/ml_freeze/model_metadata.json` verified matching 41-file manifest.
- [x] `artifacts/ml_freeze/evaluation_manifest.json` verified matching 41-file manifest.
- [x] `verify_checksums.py` executed: **41/41 matches [PASS]**.
- [x] `backend/tests/test_validation_baseline.py`: **6/6 passed**.

