"""Patch gis/interventions/clustering.py to integrate Dynamic World Land Cover."""

from pathlib import Path

path = Path("gis/interventions/clustering.py")
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add model and evaluator imports
import_target = "from backend.app.db.models.stage_c import ("
import_replacement = """from backend.app.db.models.stage_d import StageDDynamicWorldLandCover
from gis.interventions.landcover_suitability import (
    evaluate_landcover_suitability,
    HEURISTIC_DISCLOSURE_LABEL,
    PHYSICAL_SURVEY_PREREQUISITE_LABEL,
)
from backend.app.db.models.stage_c import ("""

if import_target in code and "StageDDynamicWorldLandCover" not in code:
    code = code.replace(import_target, import_replacement, 1)

# 2. Update derive_cell_surface_areas to accept dw_record
sig_target = """def derive_cell_surface_areas(
    pixel_id: str,
    cell_area_m2: float = 10000.0,
    ndbi: float | None = None,
    ndvi: float | None = None,
    ndwi: float | None = None,
    built_density: float | None = None,
    veg_deficit: float | None = None,
) -> dict[str, Any]:"""

sig_replacement = """def derive_cell_surface_areas(
    pixel_id: str,
    cell_area_m2: float = 10000.0,
    ndbi: float | None = None,
    ndvi: float | None = None,
    ndwi: float | None = None,
    built_density: float | None = None,
    veg_deficit: float | None = None,
    dw_record: dict[str, Any] | None = None,
) -> dict[str, Any]:"""

if sig_target in code:
    code = code.replace(sig_target, sig_replacement, 1)

# In derive_cell_surface_areas, handle dw_record
area_body_target = """    if pixel_id in _OPEN_BUILDINGS_INDEX:
        ob = _OPEN_BUILDINGS_INDEX[pixel_id]
        b_cnt = int(ob.get("building_count", 0))
        tot_roof = float(ob.get("total_roof_area_m2", 0.0))
        if b_cnt > 0 and tot_roof > 0:
            a_roof = round(min(nom_area * 0.85, tot_roof), 1)
            a_canopy = round(nom_area * max(0.01, min(0.35, obs_ndvi * 0.50)))
            a_ground = max(0.0, nom_area - a_roof - a_canopy)
            a_pave = round(a_ground * max(0.10, min(0.60, obs_ndbi + 0.30)))
            a_green = max(0.0, a_ground - a_pave)
            source_str = "Google Open Buildings V3 measured footprint"
            is_proxy = False
        else:
            a_roof = 0.0
            a_canopy = round(nom_area * max(0.02, min(0.60, obs_ndvi * 0.70)))
            a_ground = max(0.0, nom_area - a_canopy)
            a_pave = round(a_ground * max(0.05, min(0.40, obs_ndbi + 0.15)))
            a_green = max(0.0, a_ground - a_pave)
            source_str = "Google Open Buildings V3 (verified zero buildings)"
            is_proxy = False
    else:
        norm_b = max(0.0, min(1.0, built_factor))
        # Proxy estimate: rounded to nearest 100 m² as required by audit
        raw_roof = nom_area * min(0.70, norm_b * 0.65)
        a_roof = round(raw_roof / 100.0) * 100.0
        a_canopy = round(nom_area * max(0.02, min(0.50, obs_ndvi * 0.65)))
        a_ground = max(0.0, nom_area - a_roof - a_canopy)
        a_pave = round((a_ground * max(0.10, min(0.50, obs_ndbi + 0.25))) / 100.0) * 100.0
        a_green = max(0.0, a_ground - a_pave)
        source_str = "Landsat NDBI/NDVI proxy (unverified structure)"
        is_proxy = True"""

area_body_replacement = """    dw_obs = int(dw_record.get("valid_observation_count") or 0) if dw_record else 0
    dw_p_built = float(dw_record.get("mean_built") or 0.0) if dw_record else None
    dw_p_bare = float(dw_record.get("mean_bare") or 0.0) if dw_record else None
    dw_p_grass = float(dw_record.get("mean_grass") or 0.0) if dw_record else None
    dw_p_trees = float(dw_record.get("mean_trees") or 0.0) if dw_record else None

    if pixel_id in _OPEN_BUILDINGS_INDEX:
        ob = _OPEN_BUILDINGS_INDEX[pixel_id]
        b_cnt = int(ob.get("building_count", 0))
        tot_roof = float(ob.get("total_roof_area_m2", 0.0))
        if b_cnt > 0 and tot_roof > 0:
            a_roof = round(min(nom_area * 0.85, tot_roof), 1)
            if dw_p_trees is not None and dw_obs >= 3:
                a_canopy = round(nom_area * max(0.01, min(0.40, dw_p_trees)))
            else:
                a_canopy = round(nom_area * max(0.01, min(0.35, obs_ndvi * 0.50)))
            a_ground = max(0.0, nom_area - a_roof - a_canopy)
            a_pave = round(a_ground * max(0.10, min(0.60, obs_ndbi + 0.30)))
            a_green = max(0.0, a_ground - a_pave)
            source_str = "Google Open Buildings V3 measured footprint"
            is_proxy = False
        else:
            a_roof = 0.0
            if dw_p_trees is not None and dw_obs >= 3:
                a_canopy = round(nom_area * max(0.02, min(0.60, dw_p_trees)))
            else:
                a_canopy = round(nom_area * max(0.02, min(0.60, obs_ndvi * 0.70)))
            a_ground = max(0.0, nom_area - a_canopy)
            a_pave = round(a_ground * max(0.05, min(0.40, obs_ndbi + 0.15)))
            a_green = max(0.0, a_ground - a_pave)
            source_str = "Google Open Buildings V3 (verified zero buildings)"
            is_proxy = False
    elif dw_record is not None and dw_obs >= 3 and dw_p_built is not None:
        # Dynamic World Sentinel-2 10m deep-learning land cover model
        raw_roof = nom_area * min(0.75, dw_p_built * 0.70)
        a_roof = round(raw_roof / 50.0) * 50.0
        a_canopy = round((nom_area * max(0.01, min(0.50, dw_p_trees or 0.0))) / 50.0) * 50.0
        a_ground = max(0.0, nom_area - a_roof - a_canopy)
        p_veg = (dw_p_grass or 0.0) + (dw_p_bare or 0.0)
        p_ratio = (dw_p_built / max(0.1, dw_p_built + p_veg))
        a_pave = round((a_ground * max(0.10, min(0.60, p_ratio))) / 50.0) * 50.0
        a_green = max(0.0, a_ground - a_pave)
        source_str = "Google Dynamic World V1 (10m LULC Sentinel-2 model)"
        is_proxy = False
    else:
        norm_b = max(0.0, min(1.0, built_factor))
        # Proxy estimate: rounded to nearest 100 m² as required by audit
        raw_roof = nom_area * min(0.70, norm_b * 0.65)
        a_roof = round(raw_roof / 100.0) * 100.0
        a_canopy = round(nom_area * max(0.02, min(0.50, obs_ndvi * 0.65)))
        a_ground = max(0.0, nom_area - a_roof - a_canopy)
        a_pave = round((a_ground * max(0.10, min(0.50, obs_ndbi + 0.25))) / 100.0) * 100.0
        a_green = max(0.0, a_ground - a_pave)
        source_str = "Landsat NDBI/NDVI proxy (unverified structure)"
        is_proxy = True"""

if area_body_target in code:
    code = code.replace(area_body_target, area_body_replacement, 1)

# 3. Update assign_cell_intervention signature to accept dw_record
assign_sig_target = """def assign_cell_intervention(
    pixel_id: str,
    surfaces: dict[str, Any],
    hpi: float,
    lst_c: float,
    is_chronic: bool,
    target_type: InterventionType | None = None,
) -> dict[str, Any] | None:"""

assign_sig_replacement = """def assign_cell_intervention(
    pixel_id: str,
    surfaces: dict[str, Any],
    hpi: float,
    lst_c: float,
    is_chronic: bool,
    target_type: InterventionType | None = None,
    dw_record: dict[str, Any] | None = None,
) -> dict[str, Any] | None:"""

if assign_sig_target in code:
    code = code.replace(assign_sig_target, assign_sig_replacement, 1)

with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(code)

print("Patched gis/interventions/clustering.py successfully.")

