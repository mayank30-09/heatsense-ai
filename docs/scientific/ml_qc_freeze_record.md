# HEATSENSE AI — Machine Learning & QC Policy Freeze Record

**Project:** HEATSENSE AI — AI-Powered GIS-Based Urban Heat Mitigation & Cooling Decision-Support Platform  
**Target Area:** Surat Municipal Corporation (SMC), Gujarat, India (EPSG:4326 / EPSG:32643)  
**Document Version:** 1.0-FREEZE-RECORD  
**Date:** September 2026  
**Status:** **SCIENTIFIC FREEZE REVIEW & VERIFICATION COMPLETE**  

---

## 1. Freeze Lineage & Authority

This record establishes the formal, immutable cryptographic and procedural specification for the **HEATSENSE AI Pixel Quality Eligibility Policy (Policy D)** and the **Tuned XGBoost LST Regression Model (`xgb_tuned_optuna_tpe_v1`)**.

The freeze marks the successful completion of the scientific validation phase:
```text
DATA INGESTION (LANDSAT 8/9 C2 L2)
        ↓
SEASONAL COMPOSITING & COGs
        ↓
OBSERVATION SUPPORT & QUALITY DIAGNOSTICS
        ↓
POLICY D SENSITIVITY & ELIGIBILITY GATE
        ↓
DETERMINISTIC SPATIAL BLOCKS (2 km x 2 km)
        ↓
5-FOLD SPATIAL CROSS-VALIDATION
        ↓
OPTUNA TPE HYPERPARAMETER OPTIMIZATION (30 TRIALS)
        ↓
INDEPENDENT SPATIAL HOLDOUT VALIDATION (20% BLOCKS)
        ↓
FEATURE ABLATION & SEASONAL SHAP ANALYSIS
        ↓
SCIENTIFIC QC / ML CONFIGURATION FREEZE
```

Downstream modules (Production Analytical COGs, Heat Priority, Candidate Generation, Hard Constraints, Baseline Constrained Optimizer, NSGA-II) consume the artifacts certified in this record.

---

## 2. Certified Cryptographic Provenance (SHA-256 Hashes)

| Artifact Category | File Path | SHA-256 Hex Digest |
|---|---|---|
| **Authoritative Dataset** | `data/processed/sensitivity/policy_d/analysis.parquet` | `e824794e5ba2e26937ac40f55f5fd788adad70b1a6b23c6ab435b08223dd9997` |
| **Quality Policy Spec** | `config/quality_policy_d.yaml` | `5f122e6104cc2772de1d6fc6daef64de170b68d4ed74d2a8e8182144b4c21363` |
| **Tuned Hyperparameters** | `artifacts/xgb_tuning/xgb_best_params.json` | `561c02a4edfe99a1c6e4462771cfe7f37294997f2e04d3ac4b4b3c0aacb1528b` |
| **Spatial 5-Fold Map** | `artifacts/xgb_tuning/spatial_fold_definition.json` | `dd9a1351f9f1aa5798fc68412d4459910cc19008e65b9b8352f7f98f57dbc456` |
| **Holdout Metadata** | `artifacts/final_holdout/holdout_metadata.json` | `8ebdd4fbd1065925353406d86156c650bfa6845d6c379fb685ad8afb4b1da79d` |
| **Test Blocks List** | `artifacts/final_holdout/test_blocks.json` | `b9d2cf77609ca7265028e79a13206ffc1377634126b267e10b2d518a3341816d` |
| **Dev Blocks List** | `artifacts/final_holdout/development_blocks.json` | `1e719d30a84cda87960fb55fa1a4f8d6f52b8a54eda7d8723515bbadaab6aa30` |

---

## 3. Dataset Reconciliation

| Dataset Identifier | Filter Logic | Total Rows | Total Spatial Blocks | Retention vs Raw | Cold Artifact Removal | Status |
|---|---|---|---|---|---|---|
| **All-Policy Baseline** | $OBS \ge 1$ (Policy A unconstrained) | 924,854 | 165 | 100.00% | 40.0% (Retains cold shadows) | Diagnostic Reference |
| **Policy D Dataset** | $OBS \ge 1$ + $3\times3$ screening ($|\Delta_{\text{med}}| \le 10^\circ\text{C}$ for $OBS=1$) | **924,731** | **165** | **99.99%** | **100.0%** (Purges 123 severe anomalies) | **CERTIFIED FROZEN BASELINE** |

---

## 4. Frozen Quality Policy Specification (Policy D)

- **Policy ID:** `D`
- **Implementation:** `gis/quality/eligibility.py` (`evaluate_policy_d`)
- **Specification:** `config/quality_policy_d.yaml`
- **Rules:**
  - $OBS < 1 \lor \text{non-finite}: \to \mathbf{EXCLUDE}$
  - $OBS \ge 2 \land \text{no spatial anomaly}: \to \mathbf{ACCEPT}$
  - $OBS \ge 2 \land \text{SPATIAL\_ANOMALY}: \to \mathbf{FLAG}$
  - $OBS = 1 \land (|\Delta_{\text{med}}| > 10.0^\circ\text{C} \lor \text{LOW\_SUPPORT\_SPATIAL\_EXTREME}): \to \mathbf{EXCLUDE}$
  - $OBS = 1 \land \text{is\_boundary} \land valid\_neighbors < 4: \to \mathbf{FLAG}$
  - $OBS = 1 \land |\Delta_{\text{med}}| \le 10.0^\circ\text{C}: \to \mathbf{FLAG}$

---

## 5. Canonical Hotspot & Persistence Definitions

- **Implementation:** `gis/quality/hotspot_definitions.py`
- **Tiers:**
  - `non_hotspot`: $hotspot\_frequency == 0.0$ ($N = 859,111$ overall, $191,545$ in test holdout)
  - `active_hotspot`: $hotspot\_frequency > 0.0$ ($N = 65,620$ overall, $12,213$ in test holdout)
  - `persistent_hotspot`: $hotspot\_frequency \ge 0.25 \lor is\_persistent\_hotspot$ ($N = 11,851$ overall, $2,177$ in test holdout)
  - `chronic_hotspot`: $hotspot\_frequency \ge 0.50$ ($N = 4,195$ overall, $405$ in test holdout)
- **Resolution of Previous Ambiguity:** Replaced non-functional integer check `hotspot_frequency >= 6` with canonical normalized float thresholds ($0.25$ for persistent, $0.50$ for chronic).

---

## 6. Frozen Model Architecture & Hyperparameters

- **Model ID:** `xgb_tuned_optuna_tpe_v1`
- **Architecture:** XGBoost `XGBRegressor` (`tree_method='hist'`)
- **Target Variable ($y$):** `LST_C` (100m Land Surface Temperature in Celsius)
- **Predictor Features ($X$):**
  1. `NDVI` (Normalized Difference Vegetation Index)
  2. `NDBI` (Normalized Difference Built-up Index)
  3. `NDWI` (Normalized Difference Water Index)
  4. `LST_OBS_COUNT` (Clear-sky scene count per composite)
  5. `LST_QA_MEDIAN_K` (Radiometric temperature uncertainty from USGS Level-2 `ST_QA`)
- **Excluded Features:** `latitude`, `longitude`, `row`, `col`, and spatial coordinates (strictly omitted to guarantee spatial generalization).
- **Hyperparameters:**
  ```json
  {
    "n_estimators": 1300,
    "max_depth": 8,
    "learning_rate": 0.03279127013273231,
    "min_child_weight": 5.407238106447656,
    "subsample": 0.7645658245026288,
    "colsample_bytree": 0.9688977790657431,
    "gamma": 1.6307304358159391,
    "reg_alpha": 1.6949358907768442e-08,
    "reg_lambda": 0.775738584617916,
    "objective": "reg:squarederror",
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": -1
  }
  ```

---

## 7. Performance Verification Summary

### 7.1 Development 5-Fold Spatial Cross-Validation (Full Dataset)
- **MAE:** $1.2855 \pm 0.0294^\circ\text{C}$
- **RMSE:** $1.7840 \pm 0.0591^\circ\text{C}$
- **$R^2$:** $0.9033 \pm 0.0050$

### 7.2 Independent Spatial Holdout (Untouched 20% Blocks, $N = 203,758$)
- **MAE:** **$1.2595^\circ\text{C}$**
- **RMSE:** **$1.7342^\circ\text{C}$**
- **$R^2$:** **$0.9026$**

### 7.3 Model Comparison Summary
- **Random Forest Baseline:** $RMSE = 1.8024^\circ\text{C}, R^2 = 0.9014$
- **XGBoost Baseline:** $RMSE = 1.8280^\circ\text{C}, R^2 = 0.8986$
- **Tuned XGBoost:** $RMSE = 1.7840^\circ\text{C}, R^2 = 0.9033$

---

## 8. Explicit Scientific Limitations

All downstream users and modules must maintain awareness of the following documented physical and sensor boundaries:

1. **Thermal Spatial Scale (~100m):**
   Landsat 8/9 Band 10 thermal observations possess a 100m ground resolution. Sub-100m micro-urban interventions (e.g. painting a single building rooftop white) are integrated radiometrically with adjacent roads and vegetation.
2. **Elevated Prediction Error in Chronic Hotspots:**
   In chronic industrial hotspots ($freq \ge 0.50$), prediction error increases to $MAE = 3.795^\circ\text{C}, RMSE = 4.746^\circ\text{C}$. This reflects sub-pixel roof surface radiance and optical index saturation. Downstream Heat Priority must fuse persistent hotspot masks with ML predictions rather than relying solely on regression outputs.
3. **Partial 2026 Monsoon Series:**
   The 2026 monsoon period contains partial temporal acquisitions.
4. **Non-Causal Feature Attributions:**
   SHAP values quantify statistical associations within tree splits. `LST_QA_MEDIAN_K` functions as a seasonal atmospheric baseline proxy, not a physical cause of heat.

---

## 9. Environment & Software Stack

- **Python Version:** 3.12.10 (64-bit)
- **XGBoost:** 3.4.1
- **Scikit-Learn:** 1.9.1
- **Optuna:** 5.0.0
- **SHAP:** 0.52.0
- **Git Commit:** `21e6601f7007bcc0e970b8c95971b9621d81ccb1` (branch: `feature/day1-bootstrap`)
