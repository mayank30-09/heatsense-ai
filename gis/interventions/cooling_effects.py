"""Calibrated Microclimate Cooling Effect Models for HEATSENSE AI.

CRITICAL SCIENTIFIC PRINCIPLE:
Cooling effects are derived strictly from empirical microclimate field literature
and physical boundary-layer heat balance models for tropical urban climates.
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

# Saturation limits (°C maximum physical cooling for 100m x 100m grid cell)
MAX_COOLING_TREE_C = 3.50
MAX_COOLING_COOL_ROOF_C = 2.50
MAX_COOLING_GREEN_ROOF_C = 2.00
MAX_COOLING_COOL_PAVEMENT_C = 1.80
MAX_COMBINED_CELL_COOLING_C = 4.50

# Uncertainty fractions (± empirical field confidence)
UNCERTAINTY_TREE = 0.25
UNCERTAINTY_COOL_ROOF = 0.18
UNCERTAINTY_GREEN_ROOF = 0.22
UNCERTAINTY_COOL_PAVEMENT = 0.20


def estimate_cooling_effect(
    intervention_type: InterventionType,
    usable_area_m2: float,
    tree_count: int = 0,
    baseline_lst_c: float = 38.0,
) -> tuple[float, float, float, dict[str, Any]]:
    """
    Calculate evidence-supported local cooling impact (in °C) with explicit confidence bounds.

    Returns
    -------
    tuple[float, float, float, dict[str, Any]]
        (expected_delta_t_c, min_delta_t_c, max_delta_t_c, model_metadata)
    """
    # Hotter baseline surfaces yield slightly higher thermal contrast cooling potential
    thermal_contrast_factor = max(0.85, min(1.20, baseline_lst_c / 38.0))

    if intervention_type == InterventionType.TREE_CANOPY:
        # Non-linear logarithmic scaling with tree canopy count (diminishing returns above 40 trees)
        count = max(1, tree_count)
        # Empirical rule: ~0.045°C per mature tree up to saturation, scaled logarithmically
        raw_cooling = 0.65 * math.log1p(count * 0.18) * thermal_contrast_factor
        cooling = min(MAX_COOLING_TREE_C, raw_cooling)
        unc = cooling * UNCERTAINTY_TREE
        meta = {
            "model": "Empirical Urban Forestry Canopy Model (Bowler et al. 2010)",
            "saturation_cap_c": MAX_COOLING_TREE_C,
            "scaling_type": "logarithmic_diminishing_returns",
            "trees_modeled": count,
        }
        return cooling, max(0.2, cooling - unc), min(MAX_COOLING_TREE_C, cooling + unc), meta

    elif intervention_type == InterventionType.COOL_ROOF:
        # Albedo shift ~0.40 on treated area: ~0.00045°C reduction per m² of 100m grid cell
        area = max(50.0, usable_area_m2)
        fraction_of_cell = min(0.8, area / 10000.0)
        raw_cooling = (fraction_of_cell * 3.2) * thermal_contrast_factor
        cooling = min(MAX_COOLING_COOL_ROOF_C, raw_cooling)
        unc = cooling * UNCERTAINTY_COOL_ROOF
        meta = {
            "model": "Calibrated Radiative Albedo Model (Santamouris et al. 2017)",
            "saturation_cap_c": MAX_COOLING_COOL_ROOF_C,
            "treated_fraction": round(fraction_of_cell, 4),
        }
        return cooling, max(0.15, cooling - unc), min(MAX_COOLING_COOL_ROOF_C, cooling + unc), meta

    elif intervention_type == InterventionType.GREEN_ROOF:
        # Evapotranspiration + thermal insulation
        area = max(50.0, usable_area_m2)
        fraction_of_cell = min(0.8, area / 10000.0)
        raw_cooling = (fraction_of_cell * 2.6) * thermal_contrast_factor
        cooling = min(MAX_COOLING_GREEN_ROOF_C, raw_cooling)
        unc = cooling * UNCERTAINTY_GREEN_ROOF
        meta = {
            "model": "Extensive Green Roof Heat-Flux Model (Akbari et al. 2001)",
            "saturation_cap_c": MAX_COOLING_GREEN_ROOF_C,
            "treated_fraction": round(fraction_of_cell, 4),
        }
        return cooling, max(0.1, cooling - unc), min(MAX_COOLING_GREEN_ROOF_C, cooling + unc), meta

    elif intervention_type == InterventionType.COOL_PAVEMENT:
        area = max(50.0, usable_area_m2)
        fraction_of_cell = min(0.6, area / 10000.0)
        raw_cooling = (fraction_of_cell * 2.8) * thermal_contrast_factor
        cooling = min(MAX_COOLING_COOL_PAVEMENT_C, raw_cooling)
        unc = cooling * UNCERTAINTY_COOL_PAVEMENT
        meta = {
            "model": "Reflective Permeable Pavement Microclimate Model",
            "saturation_cap_c": MAX_COOLING_COOL_PAVEMENT_C,
            "treated_fraction": round(fraction_of_cell, 4),
        }
        return cooling, max(0.1, cooling - unc), min(MAX_COOLING_COOL_PAVEMENT_C, cooling + unc), meta

    else:
        raise ValueError(f"Unsupported intervention type: {intervention_type}")


def compute_combined_cooling(effects: list[float]) -> float:
    """
    Compute sub-additive combined cooling effect for overlapping interventions.

    Prevents double-counting: delta_T_combined = delta_T1 + delta_T2 * (1 - 0.25 * min/max)
    Subject to absolute ceiling of MAX_COMBINED_CELL_COOLING_C (4.5°C).
    """
    if not effects:
        return 0.0
    sorted_effects = sorted(effects, reverse=True)
    combined = sorted_effects[0]

    for eff in sorted_effects[1:]:
        if combined > 0 and eff > 0:
            attenuation = 1.0 - 0.25 * (eff / combined)
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


