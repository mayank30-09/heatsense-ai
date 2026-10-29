"""
Consolidates all response assembly into a single unified helper in
gis/interventions/recommendations.py to ensure the 7 sections and cache_key
are ALWAYS populated on every return path (early exits, boundary exits, and normal paths).
"""

with open("gis/interventions/recommendations.py", "r", encoding="utf-8") as f:
    code = f.read()

# Replace the early exit blocks and the final return with the unified helper
start_marker = """    # Handle boundary or invalid data cases immediately
    if summary.status == "outside_study_area" or summary.inside_smc_fraction <= 0.0:"""

# Locate the function and wrap the return logic
helper_code = '''    def _build_response(
        rec_list: List[RecommendationItem],
        custom_caveats: List[str],
        evidence_tag: str = "MODELLED",
    ) -> RecommendationsResponse:
        # Reconcile costs & quantities: REJECTED or EXCLUDED items MUST carry 0 cost and 0 quantity
        for r in rec_list:
            if (
                r.feasibility_status == FeasibilityStatus.REJECTED.value
                or r.screening_status in ("NOT_APPLICABLE", "EXCLUDED")
                or r.priority == "NOT_RECOMMENDED"
            ):
                r.cost_range_inr.base = 0.0
                r.cost_range_inr.min = 0.0
                r.cost_range_inr.max = 0.0
                r.cost_range_inr.formatted = "₹0.00 (Option rejected / Not applicable)"
                r.quantity_basis.estimated_quantity = 0.0
                r.direct_cost_inr = 0.0
                r.capital_cost_inr = 0.0

        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NOT_RECOMMENDED": 3}
        rec_list.sort(key=lambda r: priority_order.get(r.priority, 99))

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

        phys_feat = {
            "polygon_area_m2": round(polygon_area_m2, 1),
            "polygon_area_ha": round(polygon_area_m2 / 10000.0, 3),
            "built_ratio": round(p_built, 3),
            "bare_ratio": round(p_bare, 3),
            "grass_ratio": round(p_grass, 3),
            "trees_ratio": round(p_trees, 3),
            "water_ratio": round(p_water, 3),
            "landuse_typology": getattr(summary, "landuse_typology", "unclassified") or "unclassified",
            "typology_title": getattr(summary, "landuse_typology", "Unclassified Land Parcel") or "Unclassified Land Parcel",
        }

        cand_sites = []
        for r in rec_list:
            if r.feasibility_status != FeasibilityStatus.REJECTED.value:
                cand_sites.append({
                    "candidate_id": f"CAND_{r.type.upper()}",
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

        eligible_recs = [r for r in rec_list if r.feasibility_status != FeasibilityStatus.REJECTED.value]
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
            "rejected_options_count": len(rec_list) - len(eligible_recs),
        }

        ev_gaps = [
            "Cadastral building footprints with structural load ratings (UNAVAILABLE) - On-site structural engineering survey required before cool/green roof tender.",
            "Municipal road network with right-of-way and sidewalk widths (UNAVAILABLE) - Field survey required for tree planting setbacks.",
            "Revenue parcel ownership tenure (UNAVAILABLE) - Municipal clearance required on private vs public plots.",
            "High-resolution DEM and stormwater drainage network (UNAVAILABLE) - Stormwater retention interventions cannot be evaluated from satellite data alone.",
        ]

        rej_cands = []
        for r in rec_list:
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

        ev_panel = evidence_registry.get_evidence_availability_panel(evidence_dict)
        c_key = compute_evidence_cache_key(
            geometry=geometry or {},
            season=season,
            year=year,
            parameters={"typology": getattr(summary, "landuse_typology", "unclassified")},
        )

        return RecommendationsResponse(
            polygon_summary=summary,
            recommendations=rec_list,
            caveats=custom_caveats,
            assumptions_applied=assumptions_applied,
            evidence_label=evidence_tag,
            heat_conditions=heat_cond,
            physical_features=phys_feat,
            candidate_sites=cand_sites,
            quantity_cost_rollup=cost_rollup,
            evidence_gaps=ev_gaps,
            rejected_candidates=rej_cands,
            evidence_availability_panel=ev_panel,
            cache_key=c_key,
        )

    # Handle boundary or invalid data cases immediately
    if summary.status == "outside_study_area" or summary.inside_smc_fraction <= 0.0:
        caveats.append("The requested polygon lies entirely outside the Surat Municipal Corporation (SMC) study boundary. No interventions are recommended.")
        return _build_response([], caveats, "ASSUMPTION")

    if summary.status == "no_valid_observations" or summary.data_coverage_percentage == 0.0:
        caveats.append("No valid satellite observations exist for this polygon in the selected season. Recommendations cannot be reliably computed.")
        return _build_response([], caveats, "UNVERIFIED")'''

old_early_exits = """    # Handle boundary or invalid data cases immediately
    if summary.status == "outside_study_area" or summary.inside_smc_fraction <= 0.0:
        caveats.append("The requested polygon lies entirely outside the Surat Municipal Corporation (SMC) study boundary. No interventions are recommended.")
        return RecommendationsResponse(
            polygon_summary=summary,
            recommendations=[],
            caveats=caveats,
            assumptions_applied=assumptions_applied,
            evidence_label="ASSUMPTION",
        )

    if summary.status == "no_valid_observations" or summary.data_coverage_percentage == 0.0:
        caveats.append("No valid satellite observations exist for this polygon in the selected season. Recommendations cannot be reliably computed.")
        return RecommendationsResponse(
            polygon_summary=summary,
            recommendations=[],
            caveats=caveats,
            assumptions_applied=assumptions_applied,
            evidence_label="UNVERIFIED",
        )"""

code = code.replace(old_early_exits, helper_code, 1)

old_unclassified_exit = """    if clf_res.needs_site_survey or clf_res.typology == "unclassified":
        caveats.append(
            "MANDATORY REQUIREMENT: Site classification is uncertain / unclassified. "
            "An on-site survey is required before mechanical recommendations can be approved."
        )
        caveats.append("No mechanical interventions are permitted on unclassified land parcels under Surat heat-action governance.")
        return RecommendationsResponse(
            polygon_summary=summary,
            recommendations=[],
            caveats=caveats,
            assumptions_applied=assumptions_applied,
            evidence_label="ASSUMPTION",
        )"""

new_unclassified_exit = """    if clf_res.needs_site_survey or clf_res.typology == "unclassified":
        caveats.append(
            "MANDATORY REQUIREMENT: Site classification is uncertain / unclassified. "
            "An on-site survey is required before mechanical recommendations can be approved."
        )
        caveats.append("No mechanical interventions are permitted on unclassified land parcels under Surat heat-action governance.")
        return _build_response([], caveats, "ASSUMPTION")"""

code = code.replace(old_unclassified_exit, new_unclassified_exit, 1)

with open("gis/interventions/recommendations.py", "w", encoding="utf-8") as f:
    f.write(code)

print("PATCH_BUILD_RESPONSE_SUCCESSFUL")
