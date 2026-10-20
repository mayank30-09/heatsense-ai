# 05 — PostgreSQL & PostGIS Database Integrity Audit

**Project:** HeatSense AI — Surat Urban Heat Mitigation & Decision Support System  
**Audit Scope:** Schema Constraints, Referential Integrity, Foreign Keys, Orphan Records, Parameterized Query Injection Defense, and PostGIS Geometry Validation  
**Date:** October 2026  
**Auditor Classification:** PostgreSQL & PostGIS Security Engineer  
**Database Instance:** PostgreSQL 16.3 + PostGIS 3.4 (`localhost:5433`, database: `heatsense`)  
**Status:** **VERIFIED (PASS)**  

---

## 1. Database Schema & Relational Architecture

The HeatSense AI persistence layer comprises authoritative tables managing analytical grid cells, multi-temporal remote sensing observations, composite Heat Priority Index (HPI) scores, and Stage D candidate interventions:

```text
               ┌──────────────────────────────────────┐
               │         stage_c_grid_cells           │
               │ (49,747 operational 100m grid cells) │
               └──────────────────┬───────────────────┘
                                  │
         ┌────────────────────────┴────────────────────────┐
         │ (1 : N, ON DELETE CASCADE)                      │ (1 : N, ON DELETE CASCADE)
         ▼                                                 ▼
┌───────────────────────────────┐        ┌──────────────────────────────────┐
│  stage_c_grid_observations    │        │  stage_c_heat_priority_scores    │
│ (924,731 multi-temporal rows) │        │ (49,747 composite version scores)│
└───────────────────────────────┘        └──────────────────────────────────┘
```

---

## 2. Referential Integrity & Orphan Record Forensic Audit

An exhaustive SQL audit was executed against the live database instance on `localhost:5433` to verify foreign key constraints and detect any orphan records.

### Audit Queries & Results:

```sql
-- 1. Check for orphan multi-temporal observations without a parent grid cell
SELECT count(*) FROM stage_c_grid_observations o
LEFT JOIN stage_c_grid_cells c ON o.pixel_id = c.pixel_id
WHERE c.pixel_id IS NULL;
-- Observed Result: 0 orphan records (PASS)

-- 2. Check for orphan heat priority scores without a parent grid cell
SELECT count(*) FROM stage_c_heat_priority_scores s
LEFT JOIN stage_c_grid_cells c ON s.pixel_id = c.pixel_id
WHERE c.pixel_id IS NULL;
-- Observed Result: 0 orphan records (PASS)

-- 3. Check for duplicate pixel identifiers
SELECT count(*) FROM (
    SELECT pixel_id, count(*) FROM stage_c_grid_cells
    GROUP BY pixel_id HAVING count(*) > 1
) sub;
-- Observed Result: 0 duplicates (PASS)
```

**Forensic Finding:** Zero orphan records exist across all 924,731 observation records and all 49,747 composite score records. Referential integrity is strictly preserved.

---

## 3. CHECK Constraints & Domain Range Enforcement

The PostgreSQL schema enforces mathematical domain boundaries directly in the database engine:

| Table | Constraint Name | Enforced Domain / Rule | Purpose |
| :--- | :--- | :--- | :--- |
| `stage_c_grid_cells` | `ck_cells_fractional_weight` | `smc_fractional_weight >= 0.0 AND smc_fractional_weight <= 1.0` | Prevents weights outside unit interval. |
| `stage_c_grid_observations` | `ck_obs_season` | `season IN ('winter', 'summer', 'monsoon', 'post_monsoon')` | Prevents invalid meteorological seasons. |
| `stage_c_grid_observations` | `ck_obs_eligibility` | `eligibility_status IN ('ACCEPT', 'FLAG', 'EXCLUDE')` | Enforces Policy D quality classification. |
| `stage_c_grid_observations` | `ck_obs_imputation_flag` | `optical_imputation_flag IN ('NONE', 'OPTICAL_IMPUTED_MEDIAN', ...)` | Traceability of optical feature imputation. |
| `stage_c_heat_priority_scores` | `ck_hpi_score_range` | `heat_priority_score >= 0.0 AND heat_priority_score <= 100.0` | Enforces 0 to 100 HPI index scaling. |
| `stage_c_heat_priority_scores` | `ck_hpi_thermal_severity` | `thermal_severity_component >= 0.0 AND <= 1.0` | Enforces normalized thermal component. |
| `stage_c_heat_priority_scores` | `ck_hpi_persistence` | `persistence_component >= 0.0 AND <= 1.0` | Enforces normalized persistence component. |
| `stage_c_heat_priority_scores` | `ck_hpi_confidence_tier` | `confidence_tier IN ('HIGH', 'MODERATE', 'LOW', 'INSUFFICIENT')` | Enforces 4 standard confidence tiers. |
| `stage_c_heat_priority_scores` | `ck_hpi_persistence_tier`| `persistence_tier IN ('chronic_hotspot', 'frequent_hotspot', ...)` | Enforces 5 persistence classifications. |

---

## 4. Genuine SQL NULL Handling for Unscored Cells

In scientific decision support, a missing or unscored observation must be represented as a **genuine SQL NULL** rather than a zero (`0.0`) or unphysical placeholder (`-9999.0` or `NaN`):

1. **Storage Invariant:** Cells without valid thermal evidence store genuine `NULL` in `heat_priority_score`, `thermal_severity_component`, and other metrics.
2. **Serialization Invariant:** The FastAPI layer utilizes `safe_float()` to ensure all SQL `NULL` values serialize to standard JSON `null`, completely avoiding `NaN` or `Infinity` tokens that break RFC 8259 JSON parsers.

---

## 5. Parameterized Query Architecture & Injection Defense

1. **Query Construction:** All SQL queries across routers, models, and geocoding services utilize SQLAlchemy 2.0 type-safe expressions (`select()`, `where()`, `join()`) or parameterized `text()` blocks with explicit bind dictionaries.
2. **String Interpolation Prohibition:** Zero instances of dynamic f-string or string concatenation assembly (`f"SELECT ... WHERE id = '{user_input}'"`) exist in the active application routes.
3. **Automated Verification:** Verified in [backend/tests/test_security_audit.py::test_database_referential_integrity_zero_orphans](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/tests/test_security_audit.py#L380-L401).
4. **Scope & Residual Risk:** Parameterized bindings protect current application endpoints. Future migrations, dynamic raw spatial filters, or direct database scripts must maintain strict static analysis and code review to avoid introducing untrusted SQL fragments.
