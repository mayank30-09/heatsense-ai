"""Fix dw_dict in generate_clusters_for_area."""

from pathlib import Path

path = Path("gis/interventions/clustering.py")
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

target = """    target_itype = InterventionType(intervention_type) if intervention_type else None

    # Step 1: Assign each cell uniquely based on physical land cover"""

replacement = """    target_itype = InterventionType(intervention_type) if intervention_type else None

    # Fetch Dynamic World land cover records for these cells
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

    # Step 1: Assign each cell uniquely based on physical land cover"""

if target in code:
    code = code.replace(target, replacement, 1)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    print("Fixed dw_dict successfully")
else:
    print("Target not found in clustering.py")

