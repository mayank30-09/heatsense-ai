# HEATSENSE AI: Assumptions & Data Register
**Document Version:** 1.0.0  
**Date:** October 30, 2026  
**Standard:** Every numerical threshold, rate, formula parameter, and spatial dataset must be classified as **MEASURED/INGESTED**, **SOURCED**, **MODEL-DERIVED**, or **ASSUMPTION**. Parameters without authoritative sources are designated as **HUMAN DECISION REQUIRED**.

---

## 1. Physical & Spatial Datasets Register

| Dataset Name | Ingestion Status | Spatial Extent & Resolution | CRS | Authority & License | Provenance / File Path | Data Quality & Known Gaps |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SMC Municipal Study Boundary** | **INGESTED** | $461.63\text{ km}^2$, single vector polygon | EPSG:4326 / EPSG:32643 | Surat Municipal Corporation (SMC) | `data/raw/boundaries/surat_smc_boundary.geojson` | Polygon verified; 49,747 regular grid cells cover 99.55% centroid-inside. |
| **Stage C Analytical Grid Cells** | **INGESTED** | 49,747 regular polygon cells ($93.2\text{ m} \times 99.5\text{ m}$) | EPSG:32643 | Derived from Landsat regular bounding grid | Table: `stage_c_grid_cells` (PostGIS) | Projected planar area is $9,273\text{ m}^2$ (0.927 ha). Total area $461.77\text{ km}^2$ (+0.03% vs boundary). |
| **Landsat 8/9 Level-2 Surface Temperature (LST)** | **INGESTED** | 30m thermal resampled from 100m native TIRS | EPSG:32643 | USGS / NASA Landsat Science Team (Public Domain) | `data/processed/analytical/` | Multi-temporal observations (2022–2026). Clear-sky overpass ~10:30 solar time (~11:00 IST). |
| **Dynamic World 10m Land Cover** | **INGESTED** | 10m Sentinel-2 multi-spectral composite | EPSG:32643 | Google / World Resources Institute (CC BY 4.0) | Brown et al. (2022); table: `stage_d_dynamic_world_landcover` | Used strictly as secondary screening evidence. Does NOT establish property ownership or roof structural loads. |
| **OpenStreetMap Place Names** | **INGESTED** | 44 point landmarks across Surat | EPSG:4326 | OpenStreetMap Contributors (ODbL) | `data/raw/place_names/surat_osm_place_points.geojson` | Used for reverse-proximity spatial indexing; 23 distinct places mapped to SMC grid. |
| **Cadastral Building Footprints & Structural Loads** | **UNAVAILABLE** | None | N/A | Municipal Cadastre (Not in repo/DB) | Missing | Structural slab load capacity must be established via certified engineering survey prior to cool/green roof tender. |
| **Municipal Road Network & ROW Widths** | **UNAVAILABLE** | None | N/A | SMC Engineering Dept (Not in repo/DB) | Missing | Right-of-Way (ROW) setbacks and underground utility clearance require physical site survey. |
| **Revenue Parcel Ownership & Tenure** | **UNAVAILABLE** | None | N/A | Gujarat Revenue Dept (Not in repo/DB) | Missing | Private vs. public municipal tenure is unverified from satellite rasters. |
| **High-Resolution LiDAR DEM & Stormwater Inverts** | **UNAVAILABLE** | None | N/A | SMC Stormwater Drainage (Not in repo/DB) | Missing | Bioswales and retention ponds require total-station topographic survey. |

---

## 2. Scientific & Engineering Parameters Register

| Parameter | Value & Unit | Classification | Source / Justification | Human Decision / Municipal Policy Required? |
| :--- | :--- | :--- | :--- | :--- |
| **Peak May Solar Irradiance ($I_{\text{solar}}$)** | $870.0\text{ W/m}^2$ | **SOURCED** | Astronomical clear-sky irradiance for Surat latitude ($21.17^\circ\text{ N}$) at 10:30 IST Landsat overpass. | No (Physical invariant). |
| **Effective Thermal Conductance ($h_{\text{eff}}$)** | $45.6\text{ W/(m}^2\text{K)}$ | **SOURCED** | Sum of aerodynamic convection $h_c = 38.9\text{ W/m}^2\text{K}$ ($r_a = 30\text{ s/m}$) and linearized radiation $h_r = 6.5\text{ W/m}^2\text{K}$ at $T_{\text{air}}=38^\circ\text{C}$. | No (Climatological standard). |
| **Cool Roof Albedo Shift ($\Delta\alpha$)** | $+0.45$ ($\alpha: 0.20 \to 0.65$) | **SOURCED** | Aged high-SRI acrylic coating after 3-year weathering (ASTM D7897 / Santamouris 2014). | No. |
| **Cool Roof Direct Surface Skin Cooling ($\Delta T_{\text{skin}}$)** | $-8.59^\circ\text{C}$ | **MODEL-DERIVED** | Derived from energy balance: $(870 \times 0.45) / 45.6 = -8.59^\circ\text{C}$. | No (Model outcome). |
| **Tree Canopy Direct Skin Cooling ($\Delta T_{\text{skin}}$)** | $-7.50^\circ\text{C}$ | **SOURCED** | Solar attenuation (Beer-Lambert $\text{LAI}=3.2, k=0.6$) + stomatal latent flux $LE=70\text{ W/m}^2$ (Bowler 2010). | No. |
| **Ambient 2-Meter Air Cooling ($\Delta T_{\text{air}}$)** | Explicitly **UNMODELED** | **SCIENTIFIC CONSTRAINT** | True 2m air cooling requires 3D CFD boundary layer simulation with advection. | Mandatory notice in all reports: ambient air is unmodeled. |
| **Usable Rooftop Fraction ($f_{\text{usable}}$)** | $0.70$ (70%) | **ASSUMPTION** | Empirical deduction for parapets, staircases, water tanks, and HVAC equipment. | **YES**: SMC Town Planning must adjust for high-density informal settlements. |
| **Usable Pavement Parking Fraction** | $0.20$ (20%) | **ASSUMPTION** | Ground parking and walkway fraction within built cluster pixels. | **YES**: Field survey required to measure curb and parking footprints. |
| **Cool Roof Base Unit Rate** | ₹300 / $\text{m}^2$ | **ASSUMPTION** | Indicative benchmark based on prevailing civil waterproofing rates in Gujarat (₹220 mat + ₹80 lab). | **YES**: SMC Standing Committee must certify rate against Gujarat PWD SoR 2026. |
| **Cool Pavement Base Unit Rate** | ₹400 / $\text{m}^2$ | **ASSUMPTION** | Indicative benchmark for high-reflectance interlocking pavers (₹280 mat + ₹120 lab). | **YES**: Gujarat PWD Roads Schedule of Rates alignment required. |
| **Native Tree Base Unit Rate** | ₹2,000 / tree | **ASSUMPTION** | Indicative benchmark for 6–8 ft containerized sapling, tree guard, excavation, and planting. | **YES**: SMC Parks & Gardens annual rate contract verification required. |
| **Public-Works Markup: Design & Supervision** | $6.0\%$ | **SOURCED** | CPWD Manual Section 5 norm for architectural and engineering consultancy. | No. |
| **Public-Works Markup: GST** | $18.0\%$ | **SOURCED** | Statutory Goods and Services Tax (GST) rate on works contracts in India. | No. |
| **Public-Works Markup: Physical Contingency** | $12.0\%$ | **SOURCED** | CPWD / Gujarat PWD contingency norm for civil urban retrofit contracts. | No. |
| **Water Conflict Hard Rejection Threshold** | $\ge 0.35$ (35% water) | **ASSUMPTION** | Polygons dominated by wetlands or open water reject terrestrial interventions. | No (Environmental safety invariant). |
| **Critical HPI Threshold** | $\ge 60.0$ | **ASSUMPTION** | Priority cutoff for urgent municipal intervention eligibility. | **YES**: SMC Heat Action Plan taskforce decision. |
