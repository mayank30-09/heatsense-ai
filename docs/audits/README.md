# HeatSense AI — Stage A/B Audit Archive

**Archive Date:** 2026-10-04 (Local Time: 01:50 IST)  
**Branch:** `feature/scientific-freeze-correction`  
**Current HEAD Commit:** `5dc4d74b7a53522c8bbcab04f46ff518c41691de`  
**Historical Scientific Freeze Tag / Commit:** `ml-qc-freeze-before-final-corrections` (`c91bc69038d1796c568772a5bce9fba900be7e96`)  
**Audit Status:** Stage A/B Formally Verified & Closed (Release Gate Cleared)

---

## 1. Archived Documents in this Directory

| Archived File | Canonical Source | SHA-256 Checksum | Description |
|---|---|---|---|
| `stage-a-b-release-audit.md` | `E:\FINAL YEAR PROJECT\heatsense-ai\PRE_HEAT_PRIORITY_GATE_REPORT.md` | `8555001F9C4CCF36FECFA9FBF041DCE0B5E8F176030D682472613F9751959D57` | Comprehensive pre-heat-priority gate report, GIS integrity, Policy D evaluation, ML holdout reproduction, optical sentinel sensitivity audit, and Stage A/B release decision. |
| `master-audit-ledger-gates-1-4.md` | `C:\Users\admin\.gemini\antigravity-ide\brain\bb9a7ac8-27d9-49d0-98c7-c062c16abcac\audit_ledger.md` | `C2B097BDD55AEC77116ED4A9DBC61440AA6027DD91F3082115D37471ECAE4065` | Master audit ledger tracking Gates 1–4, historical claims vs. reproduced evidence, and post-freeze modifications. |

---

## 2. Note on Historical Raw Paste Files

During repository inspection and filesystem traversal across `E:\FINAL YEAR PROJECT`:
- The raw temporary files named `Pasted text(4).txt` and `Pasted text (2)(1).txt` referenced in historical audit instructions could **not** be located on the local disk.
- Per strict non-negotiable safety rules, these missing raw paste files were **not** fabricated or synthetic substitutes.
- Instead, the authoritative, fully realized markdown audit records (`audit_ledger.md` and `PRE_HEAT_PRIORITY_GATE_REPORT.md`), which contain the complete, verbatim findings, tables, and gate decisions, have been preserved and archived here byte-for-byte with exact SHA-256 verification.

---

## 3. Verified Cryptographic & Test Evidence

### Protected Artifact Checksums
- `artifacts/ml_freeze/xgb_tuned_policy_d.joblib`:
  - `e1aedd4946b1b29823bdea66ea3ec7b9ba5f20c4ddbfdf6920c2e62e6b30b7c9` (PASS)
- `data/processed/sensitivity/policy_d/analysis.parquet`:
  - `e824794e5ba2e26937ac40f55f5fd788adad70b1a6b23c6ab435b08223dd9997` (PASS)
- `artifacts/ml_freeze/holdout_split.json`:
  - `8a04b20c97b088ffc7d3f513ecd3e41007adea51ad16401f104529f40d8c1a2d` (PASS)

### Checksum Manifest
- `artifacts/ml_freeze/checksums.sha256`:
  - 41 of 41 registered entries verified against disk. 0 failures, 0 missing files.

### Test & Build Verification (Rerun on 2026-10-04)
1. **Git Whitespace:** `git diff --check` -> Clean (exit code 0).
2. **PostGIS Locality Resolution:** `test_resolve_area_name_postgis_contains` -> PASSED (1.67s).
3. **Integration Suite:** `pytest backend/tests -m "integration"` -> 2 passed (4.47s).
4. **Optical Sentinel Regression Suite:** `pytest backend/tests/test_optical_sentinel_audit.py` -> 14 passed (3.71s).
5. **Full Backend Test Suite:** `python -m pytest backend/tests -q` -> 114 passed, 24 warnings (14.27s).
6. **Frontend Production Build:** `npm run build` -> Clean (exit code 0, 3.52s, built dist bundle).
7. **Pre-Heat-Priority Machine Validation:** 20/20 JSON artifacts in `artifacts/pre_heat_priority_validation/` verified valid with `status: PASS`.

---

## 4. Known Scientific Limitations & Operating Boundaries

1. **Nominal Resolution:** 100 m grid cells derived from Landsat products must never be represented as independent 30 m thermal truth.
2. **Seasonal Disparity:** Monsoon holdout RMSE is 2.4353 °C due to severe cloud cover and atmospheric water vapor, compared to Winter (RMSE 1.1852 °C) and Summer (RMSE 1.3411 °C).
3. **Chronic Hotspot Performance:** The frozen ML model has weak explanatory power on extreme chronic hotspots (RMSE 4.8413 °C, R² 0.2118). Modeled LST must NOT be used alone to establish chronic heat priority.
4. **Post-Monsoon 2026:** Post-monsoon 2026 data were absent from the frozen dataset. Full seasonal coverage for that year must not be claimed.
5. **Non-Causal ML Attribution:** SHAP TreeExplainer values represent predictive feature attribution within the frozen tree structure, not physical causality.
6. **Optical Sentinel Policy:** 8 development observations with optical index `-9999` exhibit non-causal tree partitioning behavior (Outcome B). They must never be treated as physical surface reflectance.
