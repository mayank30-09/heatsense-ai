# Stage C Heat Priority Index (HPI) Sensitivity Analysis Report

**Generated (UTC):** `2026-10-26T07:04:36.328919+00:00`  
**Target Grid Cells:** `49,747` (Surat Municipal Corporation 100m grid)  
**Baseline Period:** `2026_summer_operational (v2.0)`  
**Integrity Status:** `READ-ONLY / INVARIANTS PRESERVED`  

---

## 1. Executive Summary & Scientific Distinction

> [!IMPORTANT]
> **SENSITIVITY ANALYSIS IS NOT MODEL VALIDATION:**
> This sensitivity analysis evaluates how spatial priority rankings respond to variations in weighting assumptions 
> ($w_T, w_P, w_V, w_B$) under strictly fixed observations. While high rank correlation ($\rho \ge 0.96$ in 3 of 4 scenarios) 
> confirms that the spatial prioritization is mathematically robust and not an artifact of delicate parameter tuning, 
> **stability does not prove empirical validity, ground truth accuracy, or causal cooling efficacy**.

- **Baseline Preservation:** The production database table `stage_c_heat_priority_scores` was verified without mutation.
- **Recomputation Invariant:** Maximum difference between database score and formula recomputation across all 49,747 cells is **0.00000800** (floating point precision).
- **Consensus High-Priority Core:** Across all 4 policy scenarios, top priority cells exhibit strong mutual overlap (Top-500 Jaccard similarity: 83.8% to 94.2%).

---

## 2. Canonical Baseline Definition

The production HPI formula synthesizes four normalized components into a composite priority index ($[0, 100]$):

$$\text{HPI} = 100 \times (0.40 \cdot T_{\text{norm}} + 0.30 \cdot P_{\text{persist}} + 0.15 \cdot V_{\text{deficit}} + 0.15 \cdot B_{\text{density}})$$

| Parameter | Component Description | Baseline Weight | Normalization / Range |
| :--- | :--- | :---: | :--- |
| $w_T$ | Summer 2026 Thermal Severity ($T_{\text{norm}}$) | **0.40** | Linear clip $[30.0^\circ\text{C}, 50.0^\circ\text{C}] \to [0, 1]$ |
| $w_P$ | Multi-Year Hotspot Persistence ($P_{\text{persist}}$) | **0.30** | Historical frequency $[0, 1]$ across 2021-2026 |
| $w_V$ | Vegetation Canopy Deficit ($V_{\text{deficit}}$) | **0.15** | Deficit $(0.45 - \text{NDVI})/0.40 \to [0, 1]$ |
| $w_B$ | Built-Up Impervious Density ($B_{\text{density}}$) | **0.15** | Normalized NDBI $[0, 1]$ |

- **Baseline Mean HPI:** `42.14` (Std: `12.58`, Range: `[4.83, 96.39]`)
- **Chronic Hotspots Identified:** `223` cells (frequency $\ge 0.60$, distinct years $\ge 3$, valid seasons $\ge 4$)

---

## 3. Controlled Sensitivity Scenarios

Four policy-justified sensitivity scenarios were evaluated, holding all raw grid observations constant:

### Scenario: Thermal-Dominant (Heatwave Emergency)
- **Weights:** $w_T = 0.60, w_P = 0.20, w_V = 0.10, w_B = 0.10$
- **Formula:** `HPI = 100 * (0.60 * T_norm + 0.20 * P_persist + 0.10 * V_deficit + 0.10 * B_density)`
- **Policy Rationale:** Simulates acute emergency response mobilization during extreme heatwave alerts. Municipal disaster management prioritizes immediate, severe thermal exposure (60% weight) over chronic multi-year history or static neighborhood surface density.

### Scenario: Persistence-Dominant (Infrastructure)
- **Weights:** $w_T = 0.25, w_P = 0.50, w_V = 0.15, w_B = 0.10$
- **Formula:** `HPI = 100 * (0.25 * T_norm + 0.50 * P_persist + 0.15 * V_deficit + 0.10 * B_density)`
- **Policy Rationale:** Simulates long-term municipal capital investment planning (e.g. permanent shade corridors, cool roofing subsidies). Prioritizes locations with chronic, repeated multi-year heat trapping (50% weight) over single-year temperature spikes or transient meteorological fluctuations.

### Scenario: Nature-Deficit (Urban Greening)
- **Weights:** $w_T = 0.30, w_P = 0.20, w_V = 0.30, w_B = 0.20$
- **Formula:** `HPI = 100 * (0.30 * T_norm + 0.20 * P_persist + 0.30 * V_deficit + 0.20 * B_density)`
- **Policy Rationale:** Simulates urban forestry and ecological restoration planning. Focuses municipal resources on areas exhibiting severe canopy deficits (30% weight) and high impervious built surface density (20% weight) where nature-based interventions have the greatest biophysical cooling potential.

### Scenario: Equal Component Weighting
- **Weights:** $w_T = 0.25, w_P = 0.25, w_V = 0.25, w_B = 0.25$
- **Formula:** `HPI = 100 * (0.25 * T_norm + 0.25 * P_persist + 0.25 * V_deficit + 0.25 * B_density)`
- **Policy Rationale:** Serves as an unweighted neutral baseline to evaluate whether the subjective 40/30/15/15 weighting scheme introduces disproportionate spatial distortion compared to an agnostic multi-criteria composite index.

---

## 4. Quantitative Sensitivity Comparison

| Scenario | Mean Score (Diff) | Pearson $r$ | Spearman $\rho$ | Top 10% Jaccard | Top 500 Jaccard | Mean Rank Shift | Max Shift | Cells Shifted > 1k |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Thermal-Dominant (Heatwave Emergency)** | 51.06 (+8.92) | 0.9741 | 0.9802 | 73.6% | 86.6% | 2195.5 | 15,758 | 34,860 |
| **Persistence-Dominant (Infrastructure)** | 29.48 (-12.65) | 0.9787 | 0.9917 | 84.4% | 89.0% | 1341.0 | 25,552 | 26,356 |
| **Nature-Deficit (Urban Greening)** | 44.41 (+2.27) | 0.9559 | 0.9660 | 64.3% | 72.1% | 2740.1 | 16,744 | 36,008 |
| **Equal Component Weighting** | 41.28 (-0.86) | 0.9640 | 0.9701 | 66.0% | 80.5% | 2628.6 | 15,094 | 35,451 |

### Key Findings:
1. **Persistence-Dominant Scenario:** Exhibits the strongest rank correlation relative to baseline (Spearman $\rho = 0.9917$, Top-500 Jaccard 89.0%, 445/500 shared). Downward mean score shift of $-12.65$ points occurs because multi-year persistence averages lower across the broader grid than single-season daytime thermal severity.
2. **Thermal-Dominant Scenario:** Elevates mean scores (+8.92 points, mean 51.06) while maintaining high ranking fidelity (Spearman $\rho = 0.9802$, Top-500 Jaccard 86.6%, 464/500 shared).
3. **Nature-Deficit Scenario:** Shows the largest mean rank shift (2,740.1 positions) and lowest Top-10% Jaccard overlap (64.3%, 3,893/4,975 shared), reflecting spatial discordance between vegetated riverine outskirts and densely paved inner wards.
4. **Equal Weighting Reference:** Closely tracks baseline prioritization (mean score 41.28 vs baseline 42.14, diff $-0.86$, Spearman $\rho = 0.9701$, Top-500 Jaccard 80.5%), confirming that the baseline weights do not introduce disproportionate rank distortions compared to an unweighted composite.

---

## 5. Methodological & Policy Limitations

> [!WARNING]
> **LIMITATIONS OF MULTI-CRITERIA SCORING:**
> - **No Ground Truth for Priority:** Priority is a normative planning construct rather than a physical observable. No sensor measures 'priority'.
> - **Non-Linear Threshold Effects:** Simple linear combination assumes substitutability between components (e.g. extreme heat can compensate for high vegetation).
> - **Resolution Granularity:** 100m grid cells may aggregate heterogeneous microclimatic environments (e.g. narrow alleyways adjacent to parks).

---

## 6. Reproducibility & Evidence Paths

All calculations were executed directly on the locked 49,747 SMC grid cells in PostgreSQL without modifying stored state.
- **Command:** `python scripts/analyze_hpi_sensitivity.py --json-out reports/hpi_sensitivity_analysis.json --md-out reports/hpi_sensitivity_analysis.md`
- **Source Code:** [`gis/heat_priority/scoring.py`](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/gis/heat_priority/scoring.py)
- **Analysis Engine:** [`scripts/analyze_hpi_sensitivity.py`](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/scripts/analyze_hpi_sensitivity.py)
- **API Endpoint:** `GET /api/v1/heat-priority/sensitivity-analysis`
- **Automated Test Suite:** [`backend/tests/test_hpi_sensitivity.py`](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/tests/test_hpi_sensitivity.py)
