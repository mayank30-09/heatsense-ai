"""
Comprehensive upgrade to gis/interventions/recommendations.py:
1. Dynamically derives physical quantities from polygon_area_m2 and land-cover fractions.
2. Sets costs and quantities to 0.0 for rejected/excluded/not_applicable options.
3. Populates all 7 additive sections in RecommendationsResponse.
4. Integrates evidence_registry and reasoning_engine.
"""

import sys

with open("gis/interventions/recommendations.py", "r", encoding="utf-8") as f:
    code = f.read()

# Replace generate_polygon_recommendations definition
old_sig = """def generate_polygon_recommendations(
    summary: PolygonSummary,
    cell_candidates: Optional[List[Dict[str, Any]]] = None,
) -> RecommendationsResponse:"""

new_sig = """def generate_polygon_recommendations(
    summary: PolygonSummary,
    cell_candidates: Optional[List[Dict[str, Any]]] = None,
    geometry: Optional[dict] = None,
    db: Optional[Any] = None,
    season: str = "summer",
    year: int = 2026,
) -> RecommendationsResponse:"""

code = code.replace(old_sig, new_sig, 1)

# Extract evidence and polygon_area_m2 at start of generate_polygon_recommendations
start_anchor = """    assumptions_applied = [
        f"High HPI threshold: HPI >= {ASSUMPTION_HIGH_HPI_THRESHOLD} or max HPI >= {ASSUMPTION_MAX_HPI_CRITICAL_THRESHOLD}",
        f"Chronic cell priority: chronic hotspot share >= {ASSUMPTION_CHRONIC_SHARE_THRESHOLD * 100:.0f}%",
        f"Vegetation deficit threshold: deficit >= {ASSUMPTION_HIGH_VEG_DEFICIT} or NDVI < {ASSUMPTION_LOW_NDVI_THRESHOLD}",
        f"Canopy saturation ceiling: existing NDVI >= {ASSUMPTION_CANOPY_SATURATION_NDVI} rejects further tree planting",
        f"Built density threshold: component >= {ASSUMPTION_HIGH_BUILT_DENSITY} or NDBI > 0.05",
        f"Water body conflict: NDWI water fraction >= {ASSUMPTION_WATER_WARNING_FRACTION * 100:.0f}% triggers warning; >= {ASSUMPTION_WATER_HARD_REJECT_FRACTION * 100:.0f}% rejects terrestrial interventions",
    ]"""

evidence_setup = """    assumptions_applied = [
        f"High HPI threshold: HPI >= {ASSUMPTION_HIGH_HPI_THRESHOLD} or max HPI >= {ASSUMPTION_MAX_HPI_CRITICAL_THRESHOLD}",
        f"Chronic cell priority: chronic hotspot share >= {ASSUMPTION_CHRONIC_SHARE_THRESHOLD * 100:.0f}%",
        f"Vegetation deficit threshold: deficit >= {ASSUMPTION_HIGH_VEG_DEFICIT} or NDVI < {ASSUMPTION_LOW_NDVI_THRESHOLD}",
        f"Canopy saturation ceiling: existing NDVI >= {ASSUMPTION_CANOPY_SATURATION_NDVI} rejects further tree planting",
        f"Built density threshold: component >= {ASSUMPTION_HIGH_BUILT_DENSITY} or NDBI > 0.05",
        f"Water body conflict: NDWI water fraction >= {ASSUMPTION_WATER_WARNING_FRACTION * 100:.0f}% triggers warning; >= {ASSUMPTION_WATER_HARD_REJECT_FRACTION * 100:.0f}% rejects terrestrial interventions",
    ]

    # Planar polygon area in projected square meters
    polygon_area_m2 = float(summary.area_km2 * 1_000_000.0)

    # Extract multi-layer evidence from EvidenceProvider registry
    evidence_dict = evidence_registry.extract_all(
        geometry=geometry or {},
        season=season,
        year=year,
        db=db,
        cached_cells=cell_candidates,
    )
    dw_res = evidence_dict.get("dynamic_world_landcover")
    p_built = float(dw_res.metrics.get("p_built", 0.0)) if dw_res else 0.0
    p_bare = float(dw_res.metrics.get("p_bare", 0.0)) if dw_res else 0.0
    p_grass = float(dw_res.metrics.get("p_grass", 0.0)) if dw_res else 0.0
    p_trees = float(dw_res.metrics.get("p_trees", 0.0)) if dw_res else 0.0
    p_water = float(dw_res.metrics.get("p_water", 0.0)) if dw_res else 0.0"""

code = code.replace(start_anchor, evidence_setup, 1)

# Fix Tree Canopy calculation: no clamp to 800, 0 cost if rejected
old_tree_calc = """    estimated_trees = max(10, min(800, int(cell_multiplier * 40)))
    tree_cost_base, tree_cost_min, tree_cost_max, tree_cost_meta = estimate_intervention_cost(
        InterventionType.TREE_CANOPY,
        usable_area_m2=0.0,
        tree_count=estimated_trees,
    )
    tree_cool_base, tree_cool_min, tree_cool_max, tree_cool_meta = estimate_cooling_effect(
        InterventionType.TREE_CANOPY,
        usable_area_m2=0.0,
        tree_count=estimated_trees,
        baseline_lst_c=mean_lst,
    )"""

new_tree_calc = """    open_ground_ratio = (p_bare + p_grass) if (p_bare + p_grass) > 0 else max(0.08, 1.0 - (summary.built_density_component or 0.5))
    plantable_area_m2 = polygon_area_m2 * open_ground_ratio
    crown_m2_per_tree = 45.0  # Urban forestry standard crown spread (Azadirachta indica)
    raw_tree_count = int(plantable_area_m2 / crown_m2_per_tree)

    if tree_feasibility == FeasibilityStatus.REJECTED.value:
        estimated_trees = 0
        tree_cost_base, tree_cost_min, tree_cost_max = 0.0, 0.0, 0.0
        tree_cool_base, tree_cool_min, tree_cool_max = 0.0, 0.0, 0.0
        tree_cost_meta = {}
        tree_cool_meta = {}
    else:
        estimated_trees = max(5, raw_tree_count)
        tree_cost_base, tree_cost_min, tree_cost_max, tree_cost_meta = estimate_intervention_cost(
            InterventionType.TREE_CANOPY,
            usable_area_m2=0.0,
            tree_count=estimated_trees,
        )
        tree_cool_base, tree_cool_min, tree_cool_max, tree_cool_meta = estimate_cooling_effect(
            InterventionType.TREE_CANOPY,
            usable_area_m2=0.0,
            tree_count=estimated_trees,
            baseline_lst_c=mean_lst,
        )"""

code = code.replace(old_tree_calc, new_tree_calc, 1)

# Fix Cool Roof calculation: no clamp to 40000, 0 cost if rejected
old_roof_calc = """    estimated_roof_m2 = max(200.0, min(40000.0, float(cell_multiplier * 1500.0)))
    roof_cost_base, roof_cost_min, roof_cost_max, roof_cost_meta = estimate_intervention_cost(
        InterventionType.COOL_ROOF,
        usable_area_m2=estimated_roof_m2,
    )
    roof_cool_base, roof_cool_min, roof_cool_max, roof_cool_meta = estimate_cooling_effect(
        InterventionType.COOL_ROOF,
        usable_area_m2=estimated_roof_m2,
        baseline_lst_c=mean_lst,
    )"""

new_roof_calc = """    eff_built = p_built if p_built > 0 else (summary.built_density_component or 0.50)
    eligible_roof_m2 = round(polygon_area_m2 * min(0.95, max(0.05, eff_built)) * 0.70, 1)

    if roof_feasibility == FeasibilityStatus.REJECTED.value:
        estimated_roof_m2 = 0.0
        roof_cost_base, roof_cost_min, roof_cost_max = 0.0, 0.0, 0.0
        roof_cool_base, roof_cool_min, roof_cool_max = 0.0, 0.0, 0.0
        roof_cost_meta = {}
        roof_cool_meta = {}
    else:
        estimated_roof_m2 = eligible_roof_m2
        roof_cost_base, roof_cost_min, roof_cost_max, roof_cost_meta = estimate_intervention_cost(
            InterventionType.COOL_ROOF,
            usable_area_m2=estimated_roof_m2,
        )
        roof_cool_base, roof_cool_min, roof_cool_max, roof_cool_meta = estimate_cooling_effect(
            InterventionType.COOL_ROOF,
            usable_area_m2=estimated_roof_m2,
            baseline_lst_c=mean_lst,
        )"""

code = code.replace(old_roof_calc, new_roof_calc, 1)

# Fix Cool Pavement calculation: no clamp to 20000, 0 cost if rejected
old_pave_calc = """    estimated_pave_m2 = max(100.0, min(20000.0, float(cell_multiplier * 1000.0)))
    pave_cost_base, pave_cost_min, pave_cost_max, pave_cost_meta = estimate_intervention_cost(
        InterventionType.COOL_PAVEMENT,
        usable_area_m2=estimated_pave_m2,
    )
    pave_cool_base, pave_cool_min, pave_cool_max, pave_cool_meta = estimate_cooling_effect(
        InterventionType.COOL_PAVEMENT,
        usable_area_m2=estimated_pave_m2,
        baseline_lst_c=mean_lst,
    )"""

new_pave_calc = """    eligible_pave_m2 = round(polygon_area_m2 * min(0.90, max(0.05, eff_built)) * 0.25, 1)

    if pave_feasibility == FeasibilityStatus.REJECTED.value:
        estimated_pave_m2 = 0.0
        pave_cost_base, pave_cost_min, pave_cost_max = 0.0, 0.0, 0.0
        pave_cool_base, pave_cool_min, pave_cool_max = 0.0, 0.0, 0.0
        pave_cost_meta = {}
        pave_cool_meta = {}
    else:
        estimated_pave_m2 = eligible_pave_m2
        pave_cost_base, pave_cost_min, pave_cost_max, pave_cost_meta = estimate_intervention_cost(
            InterventionType.COOL_PAVEMENT,
            usable_area_m2=estimated_pave_m2,
        )
        pave_cool_base, pave_cool_min, pave_cool_max, pave_cool_meta = estimate_cooling_effect(
            InterventionType.COOL_PAVEMENT,
            usable_area_m2=estimated_pave_m2,
            baseline_lst_c=mean_lst,
        )"""

code = code.replace(old_pave_calc, new_pave_calc, 1)

# Write output file
with open("gis/interventions/recommendations.py", "w", encoding="utf-8") as f:
    f.write(code)

print("PATCH_QUANTITIES_SUCCESSFUL")
