# 01 — Security Baseline & Threat Model

**Project:** HeatSense AI — Surat Urban Heat Mitigation & Decision Support System  
**Audit Scope:** Application Security, API Security, PostgreSQL/PostGIS Integrity, ML/Data Provenance, and Production Reliability  
**Date:** October 2026  
**Auditor Classification:** Senior Application Security & Database Integrity Engineering Workstream  
**Repository:** `E:\FINAL YEAR PROJECT\heatsense-ai`  
**Target Municipality:** Surat Municipal Corporation (SMC), Gujarat, India  
**Status:** **VERIFIED BASELINE & HARDENED**  

---

## 1. Executive Summary

HeatSense AI is an artificial intelligence-driven, WebGIS-integrated decision-support platform designed for the Surat Municipal Corporation (SMC), Gujarat, India. The platform integrates high-resolution satellite remote sensing (Landsat-9 thermal infrared and Sentinel-2 optical bands), multi-temporal Land Surface Temperature (LST) reconstruction, machine learning inference (XGBoost regression with spatial holdout validation), composite Heat Priority Index (HPI) scoring across 49,747 analytical grid cells, and multi-objective Pareto optimization (NSGA-II and greedy knapsack algorithms) for municipal heat mitigation interventions.

This workstream establishes the architectural security baseline, defines component trust boundaries, performs STRIDE threat modeling, and documents the defensive controls implemented to ensure reliable, multi-role municipal operations without disrupting ongoing parallel functional and performance workstreams.

---

## 2. System Architecture & Component Trust Boundaries

```text
[ Public Web Clients / Municipal Planners / Researchers / Admins ]
                               │
                       (HTTP / HTTPS)
                               ▼
        ┌────────────────────────────────────────┐
        │ Vite Frontend / Reverse Proxy Ingress  │
        └────────────────────────────────────────┘
                               │
        ┌────────────────────────────────────────────────────────┐
        │ FastAPI Asynchronous Backend (Port 8000)               │
        │  ├─ SecurityHeadersMiddleware (OWASP Defensive Headers)│
        │  ├─ AuditLogMiddleware (Telemetry & X-Request-ID)      │
        │  ├─ CORS Policy (Allow origins & credentials control)  │
        │  ├─ Authentication Engine (PyJWT HS256, bcrypt)        │
        │  ├─ Role-Based Access Control (RBAC RoleChecker)       │
        │  ├─ Input Validation (Pydantic v2 & Geo Bounds)        │
        │  ├─ Global Error Shielding (500 sanitizer)             │
        │  ├─ Parameterized SQL Services (SQLAlchemy 2.0 Core)   │
        │  └─ File Ingestion Validation Engine (Defensive Guard) │
        └────────────────────────────────────────────────────────┘
                               │
                     (Localhost TCP: 5433)
                               ▼
        ┌────────────────────────────────────────────────────────┐
        │ PostgreSQL 16 + PostGIS 3.4 (heatsense-postgis)        │
        │  ├─ Database: heatsense                                │
        │  ├─ Relational Constraints (Foreign Keys, NOT NULL)    │
        │  ├─ Spatial Fishnet Grid (49,747 Centroid-Inside Cells)│
        │  ├─ Multi-Temporal Observations (924,731 records)      │
        │  ├─ Heat Priority Composite Scores (49,747 records)    │
        │  ├─ Intervention Candidates & Optimization Scenarios   │
        │  └─ PostGIS Geometries (SRID 4326, 100% Valid)         │
        └────────────────────────────────────────────────────────┘
```

### Component Trust Boundaries:
1. **Trust Boundary A (External Client ↔ FastAPI Application):** Untrusted boundary. All HTTP requests, query parameters (`bbox`, `limit`, `offset`, `min_hpi`), path parameters (`pixel_id`, `candidate_id`), and body payloads are treated as untrusted and subjected to strict Pydantic v2 schema validation, geographic coordinate boundary checks, and JWT authentication.
2. **Trust Boundary B (FastAPI Service Layer ↔ PostgreSQL/PostGIS Engine):** Internal system boundary. All interactions execute via SQLAlchemy 2.0 parameterized queries with bind variables. Dynamic SQL string interpolation (`f"SELECT..."`) is strictly prohibited.
3. **Trust Boundary C (Application Layer ↔ Local Filesystem & Model Artifacts):** Ingestion and artifact boundary. Model artifacts (`xgb_tuned_policy_d.joblib`) are cryptographically sealed with SHA-256 checksums. File ingestion pipelines are guarded by magic byte inspection, path traversal sanitization, and executable extension blocking.

---

## 3. STRIDE Threat Modeling Analysis

| STRIDE Threat Category | Potential Risk in HeatSense AI | Defensive Control Implemented | Verification Status |
| :--- | :--- | :--- | :---: |
| **Spoofing Identity** | Unauthorized callers accessing administrative endpoints or impersonating municipal planners to alter budgets. | Cryptographically signed JWT tokens with HMAC-SHA256, expiration (`exp`), issuer (`iss`), subject (`sub`), and bcrypt salted password hashing. | **VERIFIED** |
| **Tampering with Data** | Attackers modifying cost parameters, altering intervention cooling coefficients, or injecting arbitrary SQL into grid queries. | Server-side RBAC (`RoleChecker`), Pydantic schema constraints, and strictly parameterized SQL queries. | **VERIFIED** |
| **Repudiation** | Planners or administrators running computationally heavy optimization or updating configurations without audit records. | `AuditLogMiddleware` capturing client IP, route, method, response status, duration, and `X-Request-ID` telemetry. | **VERIFIED** |
| **Information Disclosure** | Server 500 errors leaking Python tracebacks, database credentials, or server directory structures (`E:\...`). | Global exception shielding middleware intercepting unhandled exceptions, sanitizing client responses, and logging tracebacks securely. | **VERIFIED** |
| **Denial of Service (DoS)** | Callers submitting negative or extreme budgets, reversed bounding boxes, or massive loop requests to crash optimization engines. | Strict Pydantic input limits (`gt=0.0`, `le=10_000_000_000.0`), geographic range checks (`[-180, 180]`, `[-90, 90]`), and zoom level constraints (`[0, 24]`). | **VERIFIED** |
| **Elevation of Privilege** | Authenticated public citizens attempting to execute NSGA-II genetic optimization or administrative dataset ingestion. | Server-side role enforcement blocking `public` users from `/interventions/optimize` and restricting `/admin/*` routes to `admin`. | **VERIFIED** |

---

## 4. Parallel Workstream Safety Protocol

To guarantee that this security and data integrity workstream does not disrupt ongoing parallel functional and WebGIS performance workstreams, the following operational rules are strictly enforced:

1. **Additive Security Modifications:** Security headers, audit telemetry, authentication routes, and input boundary validations are added as non-breaking middleware and helper modules.
2. **Backward Compatibility:** Public read-only routes (`/health`, `/rasters/lst/tiles/{z}/{x}/{y}.png`, `/heat-priority/summary`, `/interventions/scenarios`) remain unblocked to prevent frontend map or Leaflet rendering breakage.
3. **Scientific Logic Preservation:** Machine learning model weights, spatial block partitions, empirical cooling formulas (Bowler 2010, Santamouris 2017), and municipal cost models are strictly unmodified.
4. **Zero Test Regression:** Every change is regression tested against the authoritative test suite (221 backend tests + 13 frontend tests = 234 total tests passing).
