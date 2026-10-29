"""
Patch script for gis/interventions/recommendations.py to populate the 7 sections
and set costs/quantities to 0 for any rejected item before returning.
"""

file_path = "gis/interventions/recommendations.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

target = """    # Sort recommendations by priority: HIGH -> MEDIUM -> LOW -> NOT_RECOMMENDED
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NOT_RECOMMENDED": 3}
    recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))

    return RecommendationsResponse(
        polygon_summary=summary,
        recommendations=recommendations,
        caveats=caveats,
        assumptions_applied=assumptions_applied,
        evidence_label="MODELLED",
    )"""

replacement = """    # Reconcile costs & quantities: REJECTED or EXCLUDED items MUST carry 0 cost and 0 quantity
    for r in recommendations:
        if r.feasibility_status == FeasibilityStatus.REJECTED.value or r.screening_status in ("NOT_APPLICABLE", "EXCLUDED") or r.priority == "NOT_RECOMMENDED":
            r.cost_range_inr.base = 0.0
            r.cost_range_inr.min = 0.0
            r.cost_range_inr.max = 0.0
            r.cost_range_inr.formatted = "₹0.00 (Option rejected / Not applicable)"
            r.quantity_basis.estimated_quantity = 0.0
            r.direct_cost_inr = 0.0
            r.capital_cost_inr = 0.0

    # Sort recommendations by priority: HIGH -> MEDIUM -> LOW -> NOT_RECOMMENDED
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NOT_RECOMMENDED": 3}
    recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))

    # Assemble 7 Core Sections for Spatial Intervention Reasoning
    # Section 1: Heat Conditions
    heat_cond = {
        "mean_lst_c": summary.mean_lst_c,
        "max_lst_c": summary.max_lst_c,
        "min_lst_c": summary.min_lst_c,
        "p90_lst_c": summary.p90_lst_c,
        "mean_hpi": summary.mean_hpi,
        "max_hpi": summary.max_hpi,
        "chronic_hotspot_cells": summary.chronic_cell_count,
        "chronic_hotspot_share": summary.chronic_cell_share,
        "confidence_score": summary.confidence_score,
        "confidence_tier": summary.confidence_tier,
        "mean_ndvi": summary.mean_ndvi,
        "mean_ndbi": summary.mean_ndbi,
        "mean_ndwi": summary.mean_ndwi,
    }

    # Section 2: Physical Features & Opportunities
    phys_feat = {
        "polygon_area_m2": round(polygon_area_m2, 1),
        "polygon_area_ha": round(polygon_area_m2 / 10000.0, 3),
        "built_ratio": round(p_built, 3),
        "bare_ratio": round(p_bare, 3),
        "grass_ratio": round(p_grass, 3),
        "trees_ratio": round(p_trees, 3),
        "water_ratio": round(p_water, 3),
        "landuse_typology": clf_res.typology,
        "typology_title": clf_res.title,
    }

    # Section 3: Candidate Sites with Geometry
    cand_sites = []
    for r in recommendations:
        if r.feasibility_status != FeasibilityStatus.REJECTED.value:
            cand_sites.append({
                "candidate_id": f"CAND_{r.type.upper()}_{clf_res.typology.upper()}",
                "type": r.type,
                "title": r.title,
                "spatial_unit": r.spatial_unit,
                "reasoning_state": r.reasoning_state,
                "quantity": r.quantity_basis.estimated_quantity,
                "unit": r.quantity_basis.unit,
                "cost_base_inr": r.cost_range_inr.base,
                "cooling_skin_expected_c": r.cooling_range_c.expected,
                "bounding_geometry": geometry if geometry else None,
            })

    # Section 4: Quantity and Cost Roll-up
    eligible_recs = [r for r in recommendations if r.feasibility_status != FeasibilityStatus.REJECTED.value]
    tot_capital = sum(r.cost_range_inr.base for r in eligible_recs)
    tot_direct = sum(r.direct_cost_inr for r in eligible_recs)
    tot_maint = sum(r.cost_range_inr.base * 0.02 for r in eligible_recs)
    tot_area_m2 = sum(r.quantity_basis.estimated_quantity for r in eligible_recs if "m²" in r.quantity_basis.unit)

    cost_rollup = {
        "total_capital_spend_inr": round(tot_capital, 2),
        "total_capital_spend_formatted": format_inr(tot_capital),
        "total_direct_cost_inr": round(tot_direct, 2),
        "total_annual_maintenance_inr": round(tot_maint, 2),
        "total_treated_area_m2": round(tot_area_m2, 1),
        "total_treated_area_ha": round(tot_area_m2 / 10000.0, 3),
        "eligible_options_count": len(eligible_recs),
        "rejected_options_count": len(recommendations) - len(eligible_recs),
    }

    # Section 5: Evidence Gaps & Required Field Checks
    ev_gaps = [
        "Cadastral building footprints with structural load ratings (UNAVAILABLE) - On-site structural engineering survey required before cool/green roof tender.",
        "Municipal road network with right-of-way and sidewalk widths (UNAVAILABLE) - Field survey required for tree planting setbacks.",
        "Revenue parcel ownership tenure (UNAVAILABLE) - Municipal clearance required on private vs public plots.",
        "High-resolution DEM and stormwater drainage network (UNAVAILABLE) - Stormwater retention interventions cannot be evaluated from satellite data alone.",
    ]

    # Section 6: Rejected Candidates with Rule IDs
    rej_cands = []
    for r in recommendations:
        if r.feasibility_status == FeasibilityStatus.REJECTED.value or r.priority == "NOT_RECOMMENDED":
            rej_cands.append({
                "type": r.type,
                "title": r.title,
                "rule_id": r.rule_id,
                "spatial_unit": r.spatial_unit,
                "reasoning_state": r.reasoning_state,
                "screening_status": r.screening_status,
                "reasons": r.rejection_reasons or [r.screening_reason_code],
            })

    # Section 7: Evidence Availability Panel
    ev_panel = evidence_registry.get_evidence_availability_panel(evidence_dict)

    # Compute deterministic cache key
    c_key = compute_evidence_cache_key(
        geometry=geometry or {},
        season=season,
        year=year,
        parameters={"typology": clf_res.typology},
    )

    return RecommendationsResponse(
        polygon_summary=summary,
        recommendations=recommendations,
        caveats=caveats,
        assumptions_applied=assumptions_applied,
        evidence_label="MODELLED",
        heat_conditions=heat_cond,
        physical_features=phys_feat,
        candidate_sites=cand_sites,
        quantity_cost_rollup=cost_rollup,
        evidence_gaps=ev_gaps,
        rejected_candidates=rej_cands,
        evidence_availability_panel=ev_panel,
        cache_key=c_key,
    )"""

assert target in code, "Target return block not found!"
code = code.replace(target, replacement, 1)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("PATCH_RETURN_SECTIONS_SUCCESSFUL")
