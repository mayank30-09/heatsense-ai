# HEATSENSE AI — Known Limitations & Operational Disclosures

**Project:** HEATSENSE AI — AI-Powered GIS-Based Urban Heat Mitigation & Cooling Decision-Support Platform  
**Target Municipality:** Surat Municipal Corporation (SMC), Gujarat, India  
**Date:** October 2026  
**Document Status:** OFFICIAL REFERENCE  

---

This document consolidates known scientific, operational, computational, and institutional limitations of the HEATSENSE AI platform. Users, municipal planners, and researchers should review these disclosures when interpreting model outputs, spatial priority scores, and scenario simulations.

---

## 1. Spatial Resolution & Screening-Level Interventions (100m Grid)
- **Screening-Level Analytical Cells:** All thermal composites, machine learning predictions, and Stage D intervention candidates are aggregated and analyzed on a canonical **100m analytical grid** (derived from Landsat 30m optical and ~100m native thermal data resampled to the grid).
- **Not Cadastral or Parcel-Level:** The 100m cells represent macroscopic neighborhood zones, not parcel-level property boundaries, cadastral plots, or architectural blueprints.
- **Municipal Requirement:** Proposed interventions (e.g. tree planting corridors, cool roofs) require ground-truth site surveys, structural load assessments (especially for existing roofs), land tenure verification, and municipal engineering feasibility studies prior to procurement or installation.

---

## 2. Intervention Cooling Physics, Cost Parameters & Land Tenure Guardrails
- **Linearized Heat Dissipation Model vs. Numerical PDE/CFD Solvers:** The active Stage D engine implements an empirical first-order linearized heat dissipation model ($\Delta T_s = f_{\text{treated}} \times |\Delta T_{s,\text{skin}}| \times \eta_{\text{cell}}$) with effective surface thermal conductance $h_{\text{eff}} = 45.6\text{ W/(m}^2\cdot\text{K)}$ under Surat summer solar irradiance ($870\text{ W/m}^2$). The system **does not solve** full continuum partial differential equations (PDEs) or 3D computational fluid dynamics (CFD) boundary layers.
- **Physical Saturation Caps & Empirical Bounds:** Parametric caps govern cell-scale maximum cooling:
  - Tree canopy cooling cap: **3.50°C**
  - Cool roof cooling cap: **2.50°C**
  - Green roof cooling cap: **2.00°C**
  - Cool pavement cooling cap: **1.80°C**
  - Combined multi-intervention cell ceiling: **4.50°C**
- **Unverified In-Situ Microclimate Cooling:** These cooling effects are derived from peer-reviewed literature (Akbari 2001, Santamouris 2017, Bowler 2010). Their exact microclimatic realized cooling in Surat's coastal semi-arid / humid tropical setting is **unverified by local in-situ sensor networks**.
- **Indicative Cost Engineering & Schedule Alignment:** Costs incorporate transparent civil engineering markups (18% GST, 12% contingency, 6% design/supervision, non-linear setup scaling $\text{Base} \times \sqrt{A/500}$, water tanker ₹120/kL, and 3-year/10-year whole-life maintenance). However, raw CPWD DSR and SMC annual rate contract schedules are not committed in the repository. All base unit rates are labeled `INDICATIVE_ASSUMPTION` with schedule alignment marked `UNVERIFIED_IN_REPO`.
- **Land Tenure & Vacancy Heuristics:** High vegetation deficit ($V_{\text{def}} \ge 0.50$) and low NDBI identify unbuilt, permeable ground. Satellite spectral features **do not establish legal municipal ownership, reservation status, or confirmed legal vacancy**. Municipal cadastral records and Town Planning Scheme (TPS) maps must be surveyed prior to project sanction.
- **Newer Interventions & Miyawaki Planting Guardrails:** The 7 newer intervention types (public parks, Miyawaki forests, bioswales, retention ponds, shaded parking, green walls, permeable cover) have `local_field_validated: False`. In particular, Miyawaki high-density planting cooling ($9.0^\circ\text{C}$ skin, $1.4^\circ\text{C}$ air) and 3-year establishment assumptions are unverified by municipal longitudinal field trials in Surat.

---

## 3. Monsoon 2026 Partial Coverage & Cloud Contamination
- **Cloud-Restricted Observation Count:** Monsoon seasons in coastal Gujarat experience persistent overcast cloud cover during the Southwest Monsoon (June–September).
- **Reduced Clear-Sky Support:** The Monsoon 2026 seasonal composite is based on partial acquisitions where clear-sky sample support is low and radiometric uncertainty indicators are elevated.
- **Conformal Undercoverage:** As documented in validation benchmarks, the monsoon stratum exhibits conformal undercoverage (79.19% vs nominal 90.0%), possibly related to cloud-mask boundary effects and low clear-sky sample support (not tested).

---

## 4. Heat Priority Index ($HPI$) Summer-2026 Baseline
- **Peak Summer Focus:** The current operational Heat Priority Index ($HPI$) is evaluated with the **Summer 2026** seasonal composite serving as the primary current thermal exposure anchor ($T_{norm}$).
- **Seasonal Scope:** $HPI$ measures biophysical urgency during peak summer heat exposure. It is not an annual average thermal metric, nor does it quantify winter night-time thermal comfort or cold-season conditions.

---

## 5. Administrative Ward Mapping (OSM Locality Approximations)
- **Locality Proximity:** In development and staging environments, administrative ward names and zone assignments are linked to cells using nearest OpenStreetMap (OSM) locality names and centroid spatial joins.
- **Cadastral Boundary Reconciliation:** They do not represent authoritative SMC cadastral ward survey polygons. Formal municipal ward boundary shapes must be integrated prior to binding administrative budgeting.

---

## 6. Near-Real-Time (NRT) Single Scenes vs. Seasonal Composites
- **Instantaneous Skin Temperature:** The Near-Real-Time (NRT) view displays raw single-pass Landsat 8/9 Level-2 overpass acquisitions (Landsat overpass ~10:24 local solar time (scene centre ~05:33 UTC = ~11:03 IST)).
- **Atmospheric Fluctuations:** An individual scene reflects instantaneous weather conditions (surface moisture, wind speed, transient clouds) and cannot be directly compared to 19-season multi-temporal median composites.
- **Exclusion from HPI:** NRT scenes are purely observational diagnostic feeds; they are strictly excluded from the multi-year Heat Priority Index ($HPI$) computation.

---

## 7. Multi-Year Persistence Denominator Discrepancy
- **Specification vs. Reference Script:** As detailed in [stage_c_heat_priority_specification.md](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/docs/specifications/stage_c_heat_priority_specification.md#L173), Section 3.3.2 and Section 4.1 define chronic hotspot recurrence frequency over locally valid observed seasons ($f_{hot} = N_{hot\_seasons} / N_{valid\_seasons}$).
- **Fixed Denominator in Code:** The operational analysis script `scripts/analyze_hotspot_persistence.py:104-105` evaluates recurrence over a fixed 19-season archive denominator (`valid_seasons_count = total_seasons_count = 19`).
- **Differing Cell Count:** This results in **223 chronic hotspots** under the fixed 19-season denominator versus **233 chronic hotspots** if evaluated strictly across locally valid seasons. The 10 differing cells are: `R029_C299`, `R078_C239`, `R104_C174`, `R105_C213`, `R146_C182`, `R146_C185`, `R161_C162`, `R215_C174`, `R242_C188`, `R245_C190`.
- **Operational Freeze:** The 223 chronic hotspots remain the authoritative frozen set used in database tables, validation holdout reports, and downstream models.

---

## 8. Authentication & Demonstration Accounts
- **Development Seed Accounts:** Seeded accounts (`public_user`, `planner_officer`, `climate_researcher`, `smc_admin`) in `DEV_USERS_DB` are demonstration profiles designed for local testing and stakeholder review.
- **Production Gating:** Development accounts are automatically refused when running under `APP_ENV=production`.
- **Enterprise Integration:** No municipal Single Sign-On (SSO), LDAP, or external identity provider is currently integrated. Production deployment requires connecting SMC's authoritative IAM infrastructure.
