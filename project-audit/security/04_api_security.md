# 04 — API Input Validation & Malformed Request Handling Audit

**Project:** HeatSense AI — Surat Urban Heat Mitigation & Decision Support System  
**Audit Scope:** Pydantic v2 Schema Validation, Spatial Boundary Checking, Non-Negative Numbers, Zoom Bounds, and Pagination Defense  
**Date:** October 2026  
**Auditor Classification:** Senior Application Security Engineer  
**Component:** `backend/app/api/v1/interventions.py`, `backend/app/api/v1/heat_priority.py`, `backend/app/api/v1/rasters.py`, `backend/app/api/v1/analysis.py`  
**Status:** **VERIFIED & HARDENED**  

---

## 1. Input Validation Architecture

FastAPI and Pydantic v2 provide automated request validation. However, geospatial and analytical engines require additional domain-specific boundary checks to prevent unhandled exceptions, database query degradation, and denial-of-service loops.

The HeatSense AI API enforces strict defensive controls on all input vectors:

```text
Incoming Request
      │
      ├─► [Pydantic Type & Range Checks] ── Fail ──► 422 Unprocessable Entity
      │
      ├─► [Spatial Bounding Box Checks] ── Fail ──► 400 Bad Request
      │     - Range: [-180, 180] lon, [-90, 90] lat
      │     - Extent: min_lon <= max_lon, min_lat <= max_lat
      │
      ├─► [Tile Pyramid Bounds] ────────── Fail ──► 422 Unprocessable Entity
      │     - Zoom: 0 <= z <= 24
      │     - Coords: x >= 0, y >= 0
      │
      └─► Validated Request Passed to Service Layer
```

---

## 2. Detailed Parameter Validation Matrix

| Parameter | Location / Route | Validation Rules | Error Code on Violation |
| :--- | :--- | :--- | :---: |
| `budget_inr` | Body (`POST /interventions/optimize`) | `float`, strictly positive (`gt=0.0`), ceiling `le=10_000_000_000.0` (₹1,000 Cr). | `422 Unprocessable Entity` |
| `algorithm` | Body (`POST /interventions/optimize`) | Must match case-insensitively `greedy`, `nsga2`, `nsga-ii`, or `pareto`. | `400 Bad Request` |
| `max_candidates`| Body (`POST /interventions/optimize`) | Integer `ge=10, le=500`. | `422 Unprocessable Entity` |
| `generations` | Body (`POST /interventions/optimize`) | Integer `ge=5, le=100`. | `422 Unprocessable Entity` |
| `bbox` | Query (`/interventions/candidates`, `/heat-priority/cells`) | Exact 4 float coordinates: `min_lon,min_lat,max_lon,max_lat`. Latitude in `[-90, 90]`, Longitude in `[-180, 180]`. Extent must not be reversed (`min <= max`). | `400 Bad Request` |
| `z` (zoom) | Path (`GET /rasters/lst/tiles/{z}/{x}/{y}.png`) | Integer `ge=0, le=24`. | `422 Unprocessable Entity` |
| `x`, `y` | Path (`GET /rasters/lst/tiles/{z}/{x}/{y}.png`) | Integer `ge=0`. | `422 Unprocessable Entity` |
| `limit` | Query (`/heat-priority/cells`) | Integer `ge=1, le=500`. | `422 Unprocessable Entity` |
| `offset` | Query (`/heat-priority/cells`) | Integer `ge=0`. | `422 Unprocessable Entity` |
| `min_hpi` | Query (`/heat-priority/cells`) | Float `ge=0.0, le=100.0`. | `422 Unprocessable Entity` |
| `confidence_tier` | Query (`/heat-priority/cells`) | Regex pattern: `^(HIGH\|MODERATE\|LOW\|INSUFFICIENT)$`. | `422 Unprocessable Entity` |
| `persistence_tier`| Query (`/heat-priority/cells`) | Regex pattern: `^(chronic_hotspot\|frequent_hotspot\|occasional_hotspot\|transient_extreme\|non_hotspot)$`. | `422 Unprocessable Entity` |
| `pixel_id` | Path (`/heat-priority/cell/{pixel_id}`) | String length 1 to 16 (e.g. `R045_C067`). | `422 Unprocessable Entity` |

---

## 3. Empirical Test Scenarios & Observed Results

Automated validation tests in [backend/tests/test_security_audit.py](file:///e:/FINAL%20YEAR%20PROJECT/heatsense-ai/backend/tests/test_security_audit.py#L272-L340) demonstrate robust error handling:

| Test Case | Injected Malicious / Malformed Input | Target Endpoint | Expected Status | Observed Result | Evidence |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **VAL-01** | Negative budget: `budget_inr = -5000000.0` | `POST /interventions/optimize` | `422 Unprocessable` | `422`, detail: `"greater than 0"`. | `test_optimization_negative_and_zero_budget_rejected` |
| **VAL-02** | Zero budget: `budget_inr = 0.0` | `POST /interventions/optimize` | `422 Unprocessable` | `422`, detail: `"greater than 0"`. | `test_optimization_negative_and_zero_budget_rejected` |
| **VAL-03** | Reversed bbox: `bbox = "72.75,21.30,72.90,21.10"` | `GET /interventions/candidates` | `400 Bad Request` | `400`, detail: `"Reversed bounding box extent"`. | `test_candidates_bbox_validation` |
| **VAL-04** | Out-of-bounds latitude: `lat = 121.25` | `GET /interventions/candidates` | `400 Bad Request` | `400`, detail: `"coordinates out of range"`. | `test_candidates_bbox_validation` |
| **VAL-05** | Reversed longitude: `bbox = "73.0,21.10,72.50,21.25"` | `GET /heat-priority/cells` | `400 Bad Request` | `400`, detail: `"Reversed bounding box"`. | `test_heat_priority_cells_bbox_validation` |
| **VAL-06** | Out-of-bounds longitude: `lon = -200.0` | `GET /heat-priority/cells` | `400 Bad Request` | `400`, detail: `"coordinates out of range"`. | `test_heat_priority_cells_bbox_validation` |
| **VAL-07** | Negative tile zoom: `z = -1` | `GET /rasters/lst/tiles/{z}/{x}/{y}.png` | `422 Unprocessable` | `422`, detail: `"greater than or equal to 0"`. | `test_raster_tile_zoom_and_coordinate_bounds` |
| **VAL-08** | Excessive tile zoom: `z = 25` | `GET /rasters/lst/tiles/{z}/{x}/{y}.png` | `422 Unprocessable` | `422`, detail: `"less than or equal to 24"`. | `test_raster_tile_zoom_and_coordinate_bounds` |
| **VAL-09** | Unsupported algorithm: `"unsupported_algo"` | `POST /interventions/optimize` | `400 Bad Request` | `400`, detail: `"Unsupported algorithm"`. | `test_optimize_endpoint_unsupported_algorithm` |
| **VAL-10** | Limit exceeding 500: `limit = 501` | `GET /heat-priority/cells` | `422 Unprocessable` | `422`, detail: `"less than or equal to 500"`. | `test_heat_priority_cells_pagination_validation` |
| **VAL-11** | Excessive polygon complexity: `> 2500` vertices | `POST /analysis/zonal-stats` | `400 Bad Request` | `400`, detail: `"exceeds maximum allowed complexity"`. | `test_analysis_geometry_complexity_limit_rejected` |
| **VAL-12** | Geometry coordinates out of bounds: `lat = 195.0` | `POST /analysis/zonal-stats` | `400 Bad Request` | `400`, detail: `"out of valid range [-180, 180] lon, [-90, 90] lat"`. | `test_analysis_geometry_coordinates_out_of_bounds` |
| **VAL-13** | Non-finite coordinates (`NaN`, `Infinity`) | `POST /analysis/zonal-stats` | `400 Bad Request` | `400`, detail: `"must be finite numbers"`. | `test_analysis_geometry_nan_and_inf_rejected` |
| **VAL-14** | Unclosed linear ring (`first != last`) | `POST /analysis/zonal-stats` | `400 Bad Request` | `400`, detail: `"first and last coordinates must match"`. | `test_analysis_geometry_unclosed_ring_rejected` |
| **VAL-15** | Degenerate linear ring (`< 3 distinct vertices`) | `POST /analysis/zonal-stats` | `400 Bad Request` | `400`, detail: `"must contain at least 3 distinct coordinate positions"`. | `test_analysis_geometry_degenerate_ring_rejected` |
| **VAL-16** | Boolean coordinate values (`True`, `False`) | `POST /analysis/zonal-stats` | `400 Bad Request` | `400`, detail: `"must be numeric, not boolean"`. | `test_analysis_geometry_boolean_coordinate_rejected` |

---

## 4. Conclusion & Status

- **Status:** **VERIFIED (PASS FOR EVALUATED BOUNDARIES)**.
- **Verified Boundary Defenses:** Validated endpoints enforce strict numeric ranges, type safety, vertex complexity caps ($\le 2500$ vertices), geographic bounds ($[-180, 180]$ lon, $[-90, 90]$ lat), non-finite rejection (`NaN`/`Inf`), linear ring closure, degenerate polygon rejection, and boolean type exclusion. Tested malformed inputs fail safely with standard 400 Bad Request or 422 Unprocessable Entity responses.
- **Topological Boundary Scope:** The validator guards structure, finiteness, and complexity. Complex topological validity (e.g. self-intersecting rings, valid interior/exterior orientations) relies on downstream GEOS/Shapely and PostGIS engines (`ST_IsValid`). The application does not claim to eliminate all theoretical spatial library vulnerabilities.

