"""Patch gis/interventions/clustering.py to integrate dw_dict lookups into get_area_summary and generate_clusters_for_area."""

from pathlib import Path

path = Path("gis/interventions/clustering.py")
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update assign_cell_intervention returned dict to include landcover fields
old_ret = """    return {
        "pixel_id": pixel_id,
        "assigned_type": assigned_type,
        "treatable_area_m2": round(treatable_area, 1),
        "tree_count": tree_cnt,
        "targeted_surface": surface_desc,
        "surface_source": surfaces["surface_source"],
        "is_proxy": surfaces.get("is_proxy", False),
        "baseline_hpi": hpi,
        "baseline_lst_c": lst_c,
        "is_chronic": is_chronic,
        "cost_base": cost,
        "cost_min": cost_min,
        "cost_max": cost_max,
        "cooling_base": c_exp,
        "cooling_min": c_min,
        "cooling_max": c_max,
        "cost_meta": cost_meta,
    }"""

new_ret = """    dw_eval = None
    if dw_record is not None:
        dw_eval = evaluate_landcover_suitability(dw_record, pixel_id, hpi)

    return {
        "pixel_id": pixel_id,
        "assigned_type": assigned_type,
        "treatable_area_m2": round(treatable_area, 1),
        "tree_count": tree_cnt,
        "targeted_surface": surface_desc,
        "surface_source": surfaces["surface_source"],
        "is_proxy": surfaces.get("is_proxy", False),
        "baseline_hpi": hpi,
        "baseline_lst_c": lst_c,
        "is_chronic": is_chronic,
        "cost_base": cost,
        "cost_min": cost_min,
        "cost_max": cost_max,
        "cooling_base": c_exp,
        "cooling_min": c_min,
        "cooling_max": c_max,
        "cost_meta": cost_meta,
        "landcover_assessment": dw_eval.to_dict() if dw_eval else None,
        "landcover_rule_fired": dw_eval.rule_fired if dw_eval else "NONE",
        "landcover_disclosure": dw_eval.scientific_notice if dw_eval else HEURISTIC_DISCLOSURE_LABEL,
        "landcover_top_class": dw_eval.dw_top_class if dw_eval else None,
        "landcover_confidence": dw_eval.dw_confidence if dw_eval else None,
        "landcover_entropy": dw_eval.dw_entropy if dw_eval else None,
    }"""

if old_ret in code:
    code = code.replace(old_ret, new_ret, 1)

# 2. In get_area_summary, fetch dw_dict
area_summary_loop_old = """    # Derive surfaces and assign each cell
    assigned_cells: list[dict[str, Any]] = []
    unassigned_count = 0
    chronic_count = 0
    hpi_sum = 0.0
    lst_sum = 0.0
    valid_lst_count = 0
    survey_needed_count = 0

    for r in rows:"""

area_summary_loop_new = """    # Fetch Dynamic World land cover records for these cells
    pids = [str(r.pixel_id) for r in rows]
    dw_dict = {}
    if pids:
        dw_rows = db.query(StageDDynamicWorldLandCover).filter(
            StageDDynamicWorldLandCover.cell_id.in_(pids),
            StageDDynamicWorldLandCover.season == "summer",
            StageDDynamicWorldLandCover.year == 2024,
        ).all()
        for dwr in dw_rows:
            dw_dict[dwr.cell_id] = {
                "cell_id": dwr.cell_id,
                "mean_built": dwr.mean_built,
                "mean_bare": dwr.mean_bare,
                "mean_trees": dwr.mean_trees,
                "mean_grass": dwr.mean_grass,
                "mean_crops": dwr.mean_crops,
                "mean_water": dwr.mean_water,
                "mean_flooded_vegetation": dwr.mean_flooded_vegetation,
                "mean_shrub_and_scrub": dwr.mean_shrub_and_scrub,
                "valid_observation_count": dwr.valid_observation_count,
                "top_class": dwr.top_class,
                "confidence": dwr.confidence,
                "margin": dwr.margin,
                "entropy": dwr.entropy,
                "status": dwr.status,
                "source_dataset": dwr.source_dataset,
                "pipeline_version": dwr.pipeline_version,
            }

    # Derive surfaces and assign each cell
    assigned_cells: list[dict[str, Any]] = []
    unassigned_count = 0
    chronic_count = 0
    hpi_sum = 0.0
    lst_sum = 0.0
    valid_lst_count = 0
    survey_needed_count = 0

    for r in rows:"""

if area_summary_loop_old in code:
    code = code.replace(area_summary_loop_old, area_summary_loop_new, 1)

# Pass dw_record into derive_cell_surface_areas and assign_cell_intervention in get_area_summary
area_calls_old = """        surfaces = derive_cell_surface_areas(
            pixel_id=str(r.pixel_id),
            cell_area_m2=float(r.smc_clipped_area_m2 or 10000.0),
            ndbi=r.ndbi,
            ndvi=r.ndvi,
            ndwi=r.ndwi,
            built_density=r.built_density_component,
            veg_deficit=r.vegetation_deficit_component,
        )

        assigned = assign_cell_intervention(
            pixel_id=str(r.pixel_id),
            surfaces=surfaces,
            hpi=raw_hpi,
            lst_c=lst_val,
            is_chronic=is_chr,
            target_type=target_itype,
        )"""

area_calls_new = """        dw_rec = dw_dict.get(str(r.pixel_id))
        surfaces = derive_cell_surface_areas(
            pixel_id=str(r.pixel_id),
            cell_area_m2=float(r.smc_clipped_area_m2 or 10000.0),
            ndbi=r.ndbi,
            ndvi=r.ndvi,
            ndwi=r.ndwi,
            built_density=r.built_density_component,
            veg_deficit=r.vegetation_deficit_component,
            dw_record=dw_rec,
        )

        assigned = assign_cell_intervention(
            pixel_id=str(r.pixel_id),
            surfaces=surfaces,
            hpi=raw_hpi,
            lst_c=lst_val,
            is_chronic=is_chr,
            target_type=target_itype,
            dw_record=dw_rec,
        )"""

if area_calls_old in code:
    code = code.replace(area_calls_old, area_calls_new, 1)

# 3. Same in generate_clusters_for_area
cluster_loop_old = """    # 2. Derive surfaces and assign each cell to its mutually exclusive best-fit intervention
    assigned_by_id: dict[str, dict[str, Any]] = {}
    eligible_count = 0

    for r in rows:"""

cluster_loop_new = """    # Fetch Dynamic World land cover records for these cells
    pids = [str(r.pixel_id) for r in rows]
    dw_dict = {}
    if pids:
        dw_rows = db.query(StageDDynamicWorldLandCover).filter(
            StageDDynamicWorldLandCover.cell_id.in_(pids),
            StageDDynamicWorldLandCover.season == "summer",
            StageDDynamicWorldLandCover.year == 2024,
        ).all()
        for dwr in dw_rows:
            dw_dict[dwr.cell_id] = {
                "cell_id": dwr.cell_id,
                "mean_built": dwr.mean_built,
                "mean_bare": dwr.mean_bare,
                "mean_trees": dwr.mean_trees,
                "mean_grass": dwr.mean_grass,
                "mean_crops": dwr.mean_crops,
                "mean_water": dwr.mean_water,
                "mean_flooded_vegetation": dwr.mean_flooded_vegetation,
                "mean_shrub_and_scrub": dwr.mean_shrub_and_scrub,
                "valid_observation_count": dwr.valid_observation_count,
                "top_class": dwr.top_class,
                "confidence": dwr.confidence,
                "margin": dwr.margin,
                "entropy": dwr.entropy,
                "status": dwr.status,
                "source_dataset": dwr.source_dataset,
                "pipeline_version": dwr.pipeline_version,
            }

    # 2. Derive surfaces and assign each cell to its mutually exclusive best-fit intervention
    assigned_by_id: dict[str, dict[str, Any]] = {}
    eligible_count = 0

    for r in rows:"""

if cluster_loop_old in code:
    code = code.replace(cluster_loop_old, cluster_loop_new, 1)

cluster_calls_old = """        surfaces = derive_cell_surface_areas(
            pixel_id=str(r.pixel_id),
            cell_area_m2=float(r.smc_clipped_area_m2 or 10000.0),
            ndbi=r.ndbi,
            ndvi=r.ndvi,
            ndwi=r.ndwi,
            built_density=r.built_density_component,
            veg_deficit=r.vegetation_deficit_component,
        )

        assigned = assign_cell_intervention(
            pixel_id=str(r.pixel_id),
            surfaces=surfaces,
            hpi=raw_hpi,
            lst_c=lst_val,
            is_chronic=is_chr,
            target_type=target_itype,
        )"""

cluster_calls_new = """        dw_rec = dw_dict.get(str(r.pixel_id))
        surfaces = derive_cell_surface_areas(
            pixel_id=str(r.pixel_id),
            cell_area_m2=float(r.smc_clipped_area_m2 or 10000.0),
            ndbi=r.ndbi,
            ndvi=r.ndvi,
            ndwi=r.ndwi,
            built_density=r.built_density_component,
            veg_deficit=r.vegetation_deficit_component,
            dw_record=dw_rec,
        )

        assigned = assign_cell_intervention(
            pixel_id=str(r.pixel_id),
            surfaces=surfaces,
            hpi=raw_hpi,
            lst_c=lst_val,
            is_chronic=is_chr,
            target_type=target_itype,
            dw_record=dw_rec,
        )"""

if cluster_calls_old in code:
    code = code.replace(cluster_calls_old, cluster_calls_new, 1)

with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(code)

print("Updated clustering loops with dw_dict lookups successfully.")

