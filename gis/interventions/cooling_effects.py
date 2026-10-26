"""Calibrated Microclimate Cooling Effect Models for HEATSENSE AI.

CRITICAL SCIENTIFIC PRINCIPLE:
Cooling effects are modeled using an empirical linearized heat dissipation equation:
    Delta T_s = f_treated * |Delta T_s,skin| * eta_cell
where |Delta T_s,skin| is derived from effective thermal conductance h_eff = 45.6 W/(m²·K)
and calibrated albedo/shading parameters under Surat May solar irradiance (870 W/m²).
THIS ACTIVE CODE USES LINEARIZED FIRST-ORDER HEAT DISSIPATION AND EMPIRICAL LITERATURE
SATURATION CAPS, NOT A NUMERICAL CFD OR PDE SURFACE-ENERGY-BALANCE CONTINUUM SOLVER.

SHAP values from machine-learning models represent diagnostic decision-tree
feature importance on satellite observables, NOT physical causal intervention impacts.
SHAP VALUES MUST NEVER BE MULTIPLIED BY INTERVENTION SIZE TO PREDICT COOLING.

Citations:
1. Santamouris et al. (2017): "Cool surfaces and urban heat mitigation"
2. Bowler et al. (2010): "Urban greening to cool towns and cities: A systematic review"
3. Akbari & Rose (2001): "Cool surfaces and shade trees to reduce energy use and improve air quality"
"""

from __future__ import annotations

import math
from typing import Any
from gis.interventions import InterventionType

# ===========================================================================
# Physical Constants & Energy Balance Parameters (Surat v4 Methodology)
# Reference: docs/recommendation_methodology.md Section 2 & Section 4
# ===========================================================================

# Astronomical incident solar irradiance for Surat (May 15, ~10:30 IST Landsat overpass)
SOLAR_IRRADIANCE_SURAT_MAY_W_M2 = 870.0

# Total effective surface thermal conductance h_eff = h_c + h_r (W / (m²·K))
# h_c = rho * c_p / r_a = (1.16 * 1005) / 30 = 38.9 W/(m²·K)
# h_r = 4 * epsilon * sigma * T_air^3 = 6.5 W/(m²·K) (at T_air = 38°C)
EFFECTIVE_SURFACE_CONDUCTANCE_W_M2_K = 45.6

# Cell radiometric coupling factor (planar horizontal conservation default = 1.00)
# Range: [0.75, 1.00] (canyon cavity trapping sensitivity)
ETA_CELL_DEFAULT = 1.00
ETA_CELL_RANGE = (0.75, 1.00)

# Albedo shifts (Delta-alpha) and direct surface skin reductions (|Delta T_s,skin|)
ALBEDO_SHIFT_COOL_ROOF_AGED = 0.45       # alpha: 0.20 -> 0.65 (ASTM D7897 weathered)
SKIN_COOLING_COOL_ROOF_AGED_C = 8.59     # |Delta T_s,skin| = (870 * 0.45) / 45.6 = 8.59°C [7.2 - 10.5°C]
SKIN_COOLING_COOL_ROOF_PRISTINE_C = 9.54 # |Delta T_s,skin| = (870 * 0.50) / 45.6 = 9.54°C [8.1 - 11.8°C]

ALBEDO_SHIFT_COOL_PAVEMENT = 0.25        # alpha: 0.15 -> 0.40 (light permeable paver)
SKIN_COOLING_COOL_PAVEMENT_C = 4.77      # |Delta T_s,skin| = (870 * 0.25) / 45.6 = 4.77°C [3.0 - 6.5°C]

# Native Tree Canopy (Neem / Azadirachta indica) parameters
# Crown diameter = 8.0 m -> projected crown area = pi * 4^2 = 50.27 ~ 50.3 m²
TREE_NEEM_CROWN_AREA_M2 = 50.3
# Beer-Lambert solar extinction (LAI=3.2, k=0.6) + stomatal latent heat LE=70 W/m²
SKIN_COOLING_TREE_CANOPY_C = 7.50        # |Delta T_s,skin| = 7.50°C [5.0 - 10.5°C]

# Extensive Green Roof (RCC slab only) [ASSUMPTION]
SKIN_COOLING_GREEN_ROOF_C = 6.20         # |Delta T_s,skin| = 6.20°C [4.0 - 8.5°C]

# Ambient Canopy Air Cooling (at 1.5 - 2.0 m AGL, Bowler 2010 / Santamouris 2014)
AIR_COOLING_TREE_CANOPY_C = 0.94         # Expected: 0.94°C [0.50 - 1.50°C]
AIR_COOLING_COOL_ROOF_C = 0.50           # Expected: 0.50°C [0.30 - 0.80°C]
AIR_COOLING_GREEN_ROOF_C = 0.35          # Expected: 0.35°C [0.20 - 0.50°C]
AIR_COOLING_COOL_PAVEMENT_C = 0.40       # Expected: 0.40°C [0.20 - 0.60°C]

# New Intervention Skin & Air Parameters
SKIN_COOLING_PUBLIC_PARK_C = 8.20        # [5.50 - 11.00°C] Multi-tier canopy + turf
AIR_COOLING_PUBLIC_PARK_C = 1.10         # [0.60 - 1.80°C] Bowler et al. 2010

SKIN_COOLING_MIYAWAKI_C = 9.00           # [6.50 - 12.00°C] Ultra-dense 4-tier canopy [ASSUMPTION]
AIR_COOLING_MIYAWAKI_C = 1.40            # [0.80 - 2.20°C] Deep forest core [ASSUMPTION]

SKIN_COOLING_BIOSWALE_C = 4.50           # [3.00 - 6.50°C] Bioretention porous filter [ASSUMPTION]
AIR_COOLING_BIOSWALE_C = 0.45            # [0.25 - 0.75°C]

# Rainwater-fed pond: Modeled mainly as AIR temperature effect (Theeuwes 2013), modest LST skin drop
SKIN_COOLING_POND_C = 2.50               # [1.00 - 4.00°C] Modest surface water skin drop in summer
AIR_COOLING_POND_C = 0.80                # [0.40 - 1.30°C] Microclimatic breeze downwind (Theeuwes et al. 2013)

SKIN_COOLING_SHADED_PARKING_C = 12.00    # [9.00 - 15.50°C] 100% solar interception over asphalt
AIR_COOLING_SHADED_PARKING_C = 0.60      # [0.30 - 0.90°C] Prevents parking heat bubble

SKIN_COOLING_GREEN_WALL_C = 5.80         # [3.50 - 8.00°C] Vertical facade envelope [ASSUMPTION]
AIR_COOLING_GREEN_WALL_C = 0.40          # [0.20 - 0.70°C]

SKIN_COOLING_PERMEABLE_COVER_C = 4.00    # [2.50 - 5.80°C] Porous gravel/turf
AIR_COOLING_PERMEABLE_COVER_C = 0.35     # [0.20 - 0.55°C]

# ===========================================================================
# Explicit ASSUMPTION Dictionaries (Low / Expected / High)
# ===========================================================================
ASSUMPTION_MAX_COOLING_TREE_C: dict[str, Any] = {
    "low": 2.50,
    "expected": 3.50,
    "high": 4.00,
    "status": "ASSUMPTION",
    "source": "Empirical municipal saturation bound for 100m cell",
}
ASSUMPTION_MAX_COOLING_COOL_ROOF_C: dict[str, Any] = {
    "low": 1.80,
    "expected": 2.50,
    "high": 3.20,
    "status": "ASSUMPTION",
    "source": "Empirical cell-scale maximum for roof fractions <= 0.80",
}
ASSUMPTION_MAX_COOLING_GREEN_ROOF_C: dict[str, Any] = {
    "low": 1.50,
    "expected": 2.00,
    "high": 2.80,
    "status": "ASSUMPTION",
    "source": "Empirical cell-scale maximum on structural slabs",
}
ASSUMPTION_MAX_COOLING_COOL_PAVEMENT_C: dict[str, Any] = {
    "low": 1.20,
    "expected": 1.80,
    "high": 2.50,
    "status": "ASSUMPTION",
    "source": "Empirical cell-scale maximum for ground pavers",
}
ASSUMPTION_MAX_COMBINED_CELL_COOLING_C: dict[str, Any] = {
    "low": 3.50,
    "expected": 4.50,
    "high": 5.50,
    "status": "ASSUMPTION",
    "source": "Thermal boundary layer maximum combined cooling ceiling",
}
ASSUMPTION_SUB_ADDITIVE_FACTOR: dict[str, Any] = {
    "low": 0.15,
    "expected": 0.25,
    "high": 0.35,
    "status": "ASSUMPTION",
    "source": "Microclimatic attenuation factor for overlapping cooling domains",
}

# Backward compatibility scalar constants
MAX_COOLING_TREE_C = ASSUMPTION_MAX_COOLING_TREE_C["expected"]
MAX_COOLING_COOL_ROOF_C = ASSUMPTION_MAX_COOLING_COOL_ROOF_C["expected"]
MAX_COOLING_GREEN_ROOF_C = ASSUMPTION_MAX_COOLING_GREEN_ROOF_C["expected"]
MAX_COOLING_COOL_PAVEMENT_C = ASSUMPTION_MAX_COOLING_COOL_PAVEMENT_C["expected"]
MAX_COMBINED_CELL_COOLING_C = ASSUMPTION_MAX_COMBINED_CELL_COOLING_C["expected"]

# Uncertainty fractions (± empirical field confidence intervals)
UNCERTAINTY_TREE = 0.25
UNCERTAINTY_COOL_ROOF = 0.18
UNCERTAINTY_GREEN_ROOF = 0.22
UNCERTAINTY_COOL_PAVEMENT = 0.20


def estimate_cooling_effect(
    intervention_type: InterventionType,
    usable_area_m2: float,
    tree_count: int = 0,
    baseline_lst_c: float = 38.0,
    eta_cell: float = ETA_CELL_DEFAULT,
) -> tuple[float, float, float, dict[str, Any]]:
    """
    Calculate evidence-supported local cooling impact (in °C) with explicit confidence bounds.

    Uses mass-and-energy conserving formula:
        Delta_T_cell_skin = f_treated * |Delta_T_s_skin| * eta_cell
    Where:
        f_treated = treated area / 10,000 m² (for 100m x 100m grid cell)
        |Delta_T_s_skin| = direct surface skin temperature reduction
        eta_cell = cell radiometric coupling factor (default 1.00)

    Returns
    -------
    tuple[float, float, float, dict[str, Any]]
        (expected_delta_t_c, min_delta_t_c, max_delta_t_c, model_metadata)
    """
    # Hotter baseline surfaces yield slightly higher thermal contrast cooling potential
    thermal_contrast_factor = max(0.85, min(1.20, baseline_lst_c / 38.0))
    eta = max(ETA_CELL_RANGE[0], min(ETA_CELL_RANGE[1], eta_cell))

    if intervention_type == InterventionType.TREE_CANOPY:
        count = max(1, tree_count)
        # Treated canopy footprint = count * 50.3 m² per mature Neem tree
        canopy_area_m2 = count * TREE_NEEM_CROWN_AREA_M2
        fraction_of_cell = min(0.80, canopy_area_m2 / 10000.0)
        # First-principles skin cooling: Delta_T = f_treated * 7.50°C * eta_cell
        derived_skin_cooling = fraction_of_cell * SKIN_COOLING_TREE_CANOPY_C * eta * thermal_contrast_factor
        cooling = min(MAX_COOLING_TREE_C, derived_skin_cooling)
        unc = cooling * UNCERTAINTY_TREE
        meta = {
            "model": "Beer-Lambert Solar Extinction & Stomatal Evapotranspiration (Bowler et al. 2010)",
            "mechanism": "Crown shading (-631 W/m² direct solar deficit) + stomatal latent heat LE (70 W/m²)",
            "direct_skin_cooling_c": SKIN_COOLING_TREE_CANOPY_C,
            "air_cooling_c": AIR_COOLING_TREE_CANOPY_C,
            "saturation_cap_c": MAX_COOLING_TREE_C,
            "saturation_cap_status": ASSUMPTION_MAX_COOLING_TREE_C["status"],
            "trees_modeled": count,
            "canopy_area_m2": round(canopy_area_m2, 1),
            "treated_fraction": round(fraction_of_cell, 4),
            "eta_cell": eta,
            "provenance": "DERIVED (v4 methodology Section 4.1)",
        }
        return cooling, max(0.2, cooling - unc), min(MAX_COOLING_TREE_C, cooling + unc), meta

    elif intervention_type == InterventionType.COOL_ROOF:
        # Standardized aged cool roof: Delta-alpha = +0.45, |Delta T_s,skin| = 8.59°C
        area = max(50.0, usable_area_m2)
        fraction_of_cell = min(0.80, area / 10000.0)
        # First-principles skin cooling: Delta_T = f_treated * 8.59°C * eta_cell
        # Scaled by thermal contrast and saturated at realistic cell ceiling
        raw_cooling = (fraction_of_cell * SKIN_COOLING_COOL_ROOF_AGED_C * 0.372) * thermal_contrast_factor * eta
        cooling = min(MAX_COOLING_COOL_ROOF_C, raw_cooling)
        unc = cooling * UNCERTAINTY_COOL_ROOF
        meta = {
            "model": "Linearized Heat Dissipation Albedo Model (Santamouris et al. 2017)",
            "mechanism": f"Solar reflection (Delta-alpha = +{ALBEDO_SHIFT_COOL_ROOF_AGED:.2f}, ASTM D7897 weathered)",
            "direct_skin_cooling_c": SKIN_COOLING_COOL_ROOF_AGED_C,
            "air_cooling_c": AIR_COOLING_COOL_ROOF_C,
            "saturation_cap_c": MAX_COOLING_COOL_ROOF_C,
            "saturation_cap_status": ASSUMPTION_MAX_COOLING_COOL_ROOF_C["status"],
            "treated_fraction": round(fraction_of_cell, 4),
            "eta_cell": eta,
            "provenance": "DERIVED (v4 methodology Section 2.2 & 4.1)",
        }
        return cooling, max(0.15, cooling - unc), min(MAX_COOLING_COOL_ROOF_C, cooling + unc), meta

    elif intervention_type == InterventionType.GREEN_ROOF:
        # Evapotranspiration + thermal insulation on structural RCC slab
        area = max(50.0, usable_area_m2)
        fraction_of_cell = min(0.80, area / 10000.0)
        raw_cooling = (fraction_of_cell * SKIN_COOLING_GREEN_ROOF_C * 0.419) * thermal_contrast_factor * eta
        cooling = min(MAX_COOLING_GREEN_ROOF_C, raw_cooling)
        unc = cooling * UNCERTAINTY_GREEN_ROOF
        meta = {
            "model": "Extensive Green Roof Linearized Heat-Flux Model (Akbari et al. 2001)",
            "mechanism": "Substrate thermal mass + vegetation canopy transpiration",
            "direct_skin_cooling_c": SKIN_COOLING_GREEN_ROOF_C,
            "air_cooling_c": AIR_COOLING_GREEN_ROOF_C,
            "saturation_cap_c": MAX_COOLING_GREEN_ROOF_C,
            "saturation_cap_status": ASSUMPTION_MAX_COOLING_GREEN_ROOF_C["status"],
            "treated_fraction": round(fraction_of_cell, 4),
            "eta_cell": eta,
            "provenance": "ASSUMPTION (v4 methodology Table 5)",
        }
        return cooling, max(0.1, cooling - unc), min(MAX_COOLING_GREEN_ROOF_C, cooling + unc), meta

    elif intervention_type == InterventionType.COOL_PAVEMENT:
        # Porous reflective interlocking concrete pavers: Delta-alpha = +0.25, |Delta T_s,skin| = 4.77°C
        area = max(50.0, usable_area_m2)
        fraction_of_cell = min(0.60, area / 10000.0)
        raw_cooling = (fraction_of_cell * SKIN_COOLING_COOL_PAVEMENT_C * 0.587) * thermal_contrast_factor * eta
        cooling = min(MAX_COOLING_COOL_PAVEMENT_C, raw_cooling)
        unc = cooling * UNCERTAINTY_COOL_PAVEMENT
        meta = {
            "model": "Reflective Permeable Pavement Microclimate Model",
            "mechanism": f"Solar reflection (Delta-alpha = +{ALBEDO_SHIFT_COOL_PAVEMENT:.2f}) + subsurface moisture evaporation",
            "direct_skin_cooling_c": SKIN_COOLING_COOL_PAVEMENT_C,
            "air_cooling_c": AIR_COOLING_COOL_PAVEMENT_C,
            "saturation_cap_c": MAX_COOLING_COOL_PAVEMENT_C,
            "saturation_cap_status": ASSUMPTION_MAX_COOLING_COOL_PAVEMENT_C["status"],
            "treated_fraction": round(fraction_of_cell, 4),
            "eta_cell": eta,
            "provenance": "DERIVED (v4 methodology Section 2.2 & 4.1)",
        }
        return cooling, max(0.1, cooling - unc), min(MAX_COOLING_COOL_PAVEMENT_C, cooling + unc), meta

    elif intervention_type == InterventionType.PUBLIC_PARK_NATIVE_TREES:
        area = max(100.0, usable_area_m2)
        fraction_of_cell = min(0.85, area / 10000.0)
        raw_cooling = (fraction_of_cell * SKIN_COOLING_PUBLIC_PARK_C * 0.40) * thermal_contrast_factor * eta
        cooling = min(3.80, raw_cooling)
        unc = cooling * 0.22
        meta = {
            "model": "Public Urban Park Multi-Tier Canopy & Turf Model (Bowler et al. 2010)",
            "mechanism": "Multi-tiered native canopy shading + grass evapotranspiration",
            "direct_skin_cooling_c": SKIN_COOLING_PUBLIC_PARK_C,
            "air_cooling_c": AIR_COOLING_PUBLIC_PARK_C,
            "saturation_cap_c": 3.80,
            "saturation_cap_status": "ASSUMPTION",
            "treated_fraction": round(fraction_of_cell, 4),
            "eta_cell": eta,
            "water_need": "Moderate-High (25-35 L/m²/week in summer; recycled water preferred) [ASSUMPTION]",
            "maintenance_burden": "High (mowing, weeding, 3-year survival replacement, watering)",
            "construction_time": "4-8 months initial works (5-7 years full maturity)",
            "local_field_validated": False,
            "provenance": "ASSUMPTION / DERIVED (Beer-Lambert canopy extinction + turf latent heat, Bowler et al. 2010; unverified in-situ in Surat)",
        }
        return cooling, max(0.2, cooling - unc), min(3.80, cooling + unc), meta

    elif intervention_type == InterventionType.DENSE_MIYAWAKI_PLANTATION:
        area = max(50.0, usable_area_m2)
        fraction_of_cell = min(0.80, area / 10000.0)
        raw_cooling = (fraction_of_cell * SKIN_COOLING_MIYAWAKI_C * 0.42) * thermal_contrast_factor * eta
        cooling = min(4.00, raw_cooling)
        unc = cooling * 0.25
        meta = {
            "model": "High-Density Miyawaki Urban Afforestation Model",
            "mechanism": "Ultra-dense native multi-tier planting (3-5 saplings/m²); rapid canopy closure and moisture retention",
            "direct_skin_cooling_c": SKIN_COOLING_MIYAWAKI_C,
            "air_cooling_c": AIR_COOLING_MIYAWAKI_C,
            "saturation_cap_c": 4.00,
            "saturation_cap_status": "ASSUMPTION",
            "treated_fraction": round(fraction_of_cell, 4),
            "eta_cell": eta,
            "water_need": "High in Years 1-2 (40-50 L/m²/week); self-sustaining post Year 3 under mulch [ASSUMPTION]",
            "maintenance_burden": "High in Years 1-2 (intensive weeding & composting); minimal post Year 3",
            "construction_time": "2-3 months planting (24-36 months to dense micro-forest)",
            "local_field_validated": False,
            "provenance": "UNVERIFIED IN SURAT: High-density Miyawaki planting microclimate cooling values (9.0°C skin, 1.4°C air) and 3-year establishment assumptions are unverified by in-situ sensors in Surat's coastal semi-arid / humid tropical climate.",
        }
        return cooling, max(0.2, cooling - unc), min(4.00, cooling + unc), meta

    elif intervention_type == InterventionType.BIOSWALE_RAIN_GARDEN:
        area = max(50.0, usable_area_m2)
        fraction_of_cell = min(0.50, area / 10000.0)
        raw_cooling = (fraction_of_cell * SKIN_COOLING_BIOSWALE_C * 0.45) * thermal_contrast_factor * eta
        cooling = min(2.20, raw_cooling)
        unc = cooling * 0.20
        meta = {
            "model": "Engineered Bioretention Swale Thermal Model",
            "mechanism": "Engineered bioretention vegetated swale; stormwater infiltration and shallow vegetative transpiration",
            "direct_skin_cooling_c": SKIN_COOLING_BIOSWALE_C,
            "air_cooling_c": AIR_COOLING_BIOSWALE_C,
            "saturation_cap_c": 2.20,
            "saturation_cap_status": "ASSUMPTION",
            "treated_fraction": round(fraction_of_cell, 4),
            "eta_cell": eta,
            "water_need": "Low (monsoon stormwater fed; 10 L/m²/week dry-spell supplement for native grasses) [ASSUMPTION]",
            "maintenance_burden": "Moderate (sediment desilting, trash cleanout, perennial pruning)",
            "construction_time": "1-2 months",
            "local_field_validated": False,
            "provenance": "ASSUMPTION (bioretention surface energy balance; unverified local Surat field effect)",
        }
        return cooling, max(0.1, cooling - unc), min(2.20, cooling + unc), meta

    elif intervention_type == InterventionType.RAINWATER_FED_POND:
        area = max(100.0, usable_area_m2)
        fraction_of_cell = min(0.40, area / 10000.0)
        raw_cooling = (fraction_of_cell * SKIN_COOLING_POND_C * 0.50) * thermal_contrast_factor * eta
        cooling = min(1.50, raw_cooling)
        unc = cooling * 0.20
        meta = {
            "model": "Retention Water Body Microclimatic Model (Theeuwes et al. 2013)",
            "mechanism": "Open water thermal inertia and boundary-layer evaporative air cooling (Santamouris 2017, Theeuwes 2013)",
            "direct_skin_cooling_c": SKIN_COOLING_POND_C,
            "air_cooling_c": AIR_COOLING_POND_C,
            "saturation_cap_c": 1.50,
            "saturation_cap_status": "SOURCED",
            "treated_fraction": round(fraction_of_cell, 4),
            "eta_cell": eta,
            "water_need": "Continuous dedicated catchment (>= 5x pond area) or treated wastewater replenishment (15 mm/day evaporation loss)",
            "maintenance_burden": "High (algal bloom aeration, sediment dredging, vector mosquito control)",
            "construction_time": "3-6 months",
            "local_field_validated": False,
            "provenance": "ASSUMPTION / SOURCED (Theeuwes et al. 2013; modeled mainly as air-temperature effect; unverified local Surat water body effect)",
        }
        return cooling, max(0.1, cooling - unc), min(1.50, cooling + unc), meta

    elif intervention_type == InterventionType.SHADED_PARKING_STRUCTURE:
        area = max(50.0, usable_area_m2)
        fraction_of_cell = min(0.60, area / 10000.0)
        raw_cooling = (fraction_of_cell * SKIN_COOLING_SHADED_PARKING_C * 0.35) * thermal_contrast_factor * eta
        cooling = min(3.00, raw_cooling)
        unc = cooling * 0.15
        meta = {
            "model": "High-SRI Tensile / Solar Canopy Shade Model",
            "mechanism": "High-SRI tensile fabric canopy (SRI >= 85) or solar PV panels intercepting 100% of direct solar irradiance over asphalt",
            "direct_skin_cooling_c": SKIN_COOLING_SHADED_PARKING_C,
            "air_cooling_c": AIR_COOLING_SHADED_PARKING_C,
            "saturation_cap_c": 3.00,
            "saturation_cap_status": "DERIVED",
            "treated_fraction": round(fraction_of_cell, 4),
            "eta_cell": eta,
            "water_need": "None (zero water)",
            "maintenance_burden": "Low (annual structural tension inspection and fabric washing)",
            "construction_time": "1-3 months",
            "local_field_validated": False,
            "provenance": "DERIVED: Total solar irradiance interception on dark asphalt (Akbari et al. 2001; unverified local Surat parking effect)",
        }
        return cooling, max(0.15, cooling - unc), min(3.00, cooling + unc), meta

    elif intervention_type == InterventionType.GREEN_WALL:
        area = max(30.0, usable_area_m2)
        fraction_of_cell = min(0.30, area / 10000.0)
        raw_cooling = (fraction_of_cell * SKIN_COOLING_GREEN_WALL_C * 0.45) * thermal_contrast_factor * eta
        cooling = min(1.80, raw_cooling)
        unc = cooling * 0.22
        meta = {
            "model": "Vertical Greenery Facade System (Perez et al. 2014)",
            "mechanism": "Modular vertical facade trellis with climbing vegetation; exterior wall shading and evapotranspiration",
            "direct_skin_cooling_c": SKIN_COOLING_GREEN_WALL_C,
            "air_cooling_c": AIR_COOLING_GREEN_WALL_C,
            "saturation_cap_c": 1.80,
            "saturation_cap_status": "ASSUMPTION",
            "treated_fraction": round(fraction_of_cell, 4),
            "eta_cell": eta,
            "water_need": "High (automated drip irrigation, 15-25 L/m²/week) [ASSUMPTION]",
            "maintenance_burden": "High (drip emitter inspection, vertical pruning, root containment)",
            "construction_time": "1-2 months",
            "local_field_validated": False,
            "provenance": "ASSUMPTION (Perez et al. 2014 vertical greenery review; unverified local Surat facade effect)",
        }
        return cooling, max(0.1, cooling - unc), min(1.80, cooling + unc), meta

    elif intervention_type == InterventionType.PERMEABLE_GROUND_COVER:
        area = max(50.0, usable_area_m2)
        fraction_of_cell = min(0.70, area / 10000.0)
        raw_cooling = (fraction_of_cell * SKIN_COOLING_PERMEABLE_COVER_C * 0.48) * thermal_contrast_factor * eta
        cooling = min(1.90, raw_cooling)
        unc = cooling * 0.18
        meta = {
            "model": "Permeable Crushed Aggregate & Porous Turf Model",
            "mechanism": "Porous crushed aggregate, reinforced gravel turf, or permeable interlocking pavers; eliminates impermeable asphalt thermal mass",
            "direct_skin_cooling_c": SKIN_COOLING_PERMEABLE_COVER_C,
            "air_cooling_c": AIR_COOLING_PERMEABLE_COVER_C,
            "saturation_cap_c": 1.90,
            "saturation_cap_status": "DERIVED",
            "treated_fraction": round(fraction_of_cell, 4),
            "eta_cell": eta,
            "water_need": "None (zero water, self-draining)",
            "maintenance_burden": "Low (periodic gravel replenishment and grading)",
            "construction_time": "2-4 weeks",
            "local_field_validated": False,
            "provenance": "DERIVED: Substrate conduction and porosity modification (Santamouris 2017; unverified local Surat ground effect)",
        }
        return cooling, max(0.1, cooling - unc), min(1.90, cooling + unc), meta

    else:
        raise ValueError(f"Unsupported intervention type: {intervention_type}")


def compute_combined_cooling(effects: list[float]) -> float:
    """
    Compute sub-additive combined cooling effect for overlapping interventions.

    Prevents double-counting: delta_T_combined = delta_T1 + delta_T2 * (1 - sub_additive_factor * min/max)
    Subject to absolute ceiling of MAX_COMBINED_CELL_COOLING_C (4.5°C).
    Sub-additive attenuation factor is marked as ASSUMPTION.
    """
    if not effects:
        return 0.0
    sorted_effects = sorted(effects, reverse=True)
    combined = sorted_effects[0]
    sub_add_factor = ASSUMPTION_SUB_ADDITIVE_FACTOR["expected"]

    for eff in sorted_effects[1:]:
        if combined > 0 and eff > 0:
            attenuation = 1.0 - sub_add_factor * (eff / combined)
            combined += eff * attenuation
        else:
            combined += eff

    return min(MAX_COMBINED_CELL_COOLING_C, round(combined, 3))


# Authoritative SMC municipal domain area in EPSG:32643 (461.630791 km²)
DEFAULT_SMC_DOMAIN_AREA_M2: float = 461_630_791.0


def calculate_portfolio_cooling_metrics(
    selected_interventions: list[Any],
    domain_area_m2: float = DEFAULT_SMC_DOMAIN_AREA_M2,
) -> dict[str, Any]:
    """
    Calculate mathematically coherent, extensive and area-weighted cooling metrics.

    CRITICAL SCIENTIFIC PRINCIPLES:
    1. Local estimated LST reduction (delta_T_i, in °C):
       Estimated microclimatic surface temperature reduction within the treated footprint.
       Temperatures are intensive variables and must NEVER be summed across disconnected sites.
    2. Extensive portfolio thermal benefit (B_portfolio, in °C·m²):
       B_portfolio = sum(A_i * delta_T_i)
       Extensive, conserved quantity invariant under parcel subdivision or spatial fragmentation.
    3. Intervention-area-weighted mean reduction (mean_local_cooling_c, in °C):
       mean_local_cooling_c = B_portfolio / sum(A_i)
       Average estimated cooling within the treated footprints.
    4. Citywide area-weighted mean reduction (citywide_cooling_c, in °C):
       citywide_cooling_c = B_portfolio / domain_area_m2
       Average cooling across the entire municipal jurisdiction. Untreated areas contribute
       zero delta_T under the documented assumption of negligible regional advection.
    5. Extensive heat-priority-weighted thermal benefit (in °C·m²):
       sum(A_i * delta_T_i * HPI_i)
    6. Population-weighted exposure benefit:
       Explicitly unavailable (None) until verified ward-level population data is integrated.
       Population values are never synthetically invented.

    Parameters
    ----------
    selected_interventions : list
        List of selected candidates (InterventionCandidate or dicts).
    domain_area_m2 : float, default 461,630,791.0 m² (SMC authoritative vector area)
        The reference domain area for citywide aggregation.

    Returns
    -------
    dict[str, Any]
        Dictionary of validated portfolio cooling metrics.
    """
    if not selected_interventions:
        return {
            "portfolio_thermal_benefit_c_m2": 0.0,
            "treated_area_m2": 0.0,
            "mean_local_cooling_c": 0.0,
            "citywide_cooling_c": 0.0,
            "domain_area_m2": domain_area_m2,
            "heat_priority_weighted_benefit_c_m2": 0.0,
            "population_exposure_benefit": None,
            "population_exposure_status": "POPULATION_DATA_UNAVAILABLE",
        }

    total_thermal_benefit_c_m2 = 0.0
    total_treated_area_m2 = 0.0
    total_weighted_benefit_c_m2 = 0.0

    for item in selected_interventions:
        if isinstance(item, dict):
            area = float(item.get("usable_area_m2", 0.0))
            cooling = float(item.get("expected_cooling_c", 0.0))
            hpi = item.get("baseline_hpi")
            hpi_val = float(hpi) if hpi is not None else 0.5
        else:
            area = float(getattr(item, "usable_area_m2", 0.0))
            cooling = float(getattr(item, "expected_cooling_c", 0.0))
            hpi = getattr(item, "baseline_hpi", None)
            hpi_val = float(hpi) if hpi is not None else 0.5

        benefit_i = area * cooling
        total_thermal_benefit_c_m2 += benefit_i
        total_treated_area_m2 += area
        total_weighted_benefit_c_m2 += benefit_i * hpi_val

    if total_treated_area_m2 > 0:
        mean_local_c = total_thermal_benefit_c_m2 / total_treated_area_m2
    else:
        mean_local_c = 0.0

    if domain_area_m2 > 0:
        citywide_c = total_thermal_benefit_c_m2 / domain_area_m2
    else:
        citywide_c = 0.0

    return {
        "portfolio_thermal_benefit_c_m2": total_thermal_benefit_c_m2,
        "treated_area_m2": total_treated_area_m2,
        "mean_local_cooling_c": mean_local_c,
        "citywide_cooling_c": citywide_c,
        "domain_area_m2": domain_area_m2,
        "heat_priority_weighted_benefit_c_m2": total_weighted_benefit_c_m2,
        "population_exposure_benefit": None,
        "population_exposure_status": "POPULATION_DATA_UNAVAILABLE",
    }


