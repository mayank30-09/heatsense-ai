"""Patch backend/app/api/v1/interventions.py to expose land-cover endpoints."""

from pathlib import Path

path = Path("backend/app/api/v1/interventions.py")
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

# Add imports if missing
add_imports = """from backend.app.db.models.stage_d import StageDDynamicWorldLandCover, StageDLandCoverPipelineRun
from gis.interventions.landcover_suitability import (
    fetch_cell_landcover,
    evaluate_landcover_suitability,
    HEURISTIC_DISCLOSURE_LABEL,
    PHYSICAL_SURVEY_PREREQUISITE_LABEL,
)
from gis.gee.dynamic_world_pipeline import (
    DW_CLASSES,
    ATTRIBUTION_TEXT,
    CITATION_TEXT,
    LICENSE_TEXT,
    PIPELINE_VERSION,
)
"""

if "StageDDynamicWorldLandCover" not in code:
    code = add_imports + "\n" + code

endpoints_code = """

# ---------------------------------------------------------------------------
# Phase 6 Dynamic World Land Cover Endpoints
# ---------------------------------------------------------------------------

class DynamicWorldProbabilities(BaseModel):
    water: float | None = None
    trees: float | None = None
    grass: float | None = None
    flooded_vegetation: float | None = None
    crops: float | None = None
    shrub_and_scrub: float | None = None
    built: float | None = None
    bare: float | None = None
    snow_and_ice: float | None = None


class LandCoverSuitabilityResponse(BaseModel):
    rule_fired: str
    suitable_interventions: list[str]
    screened_out_interventions: list[str]
    screening_status: str
    screening_reason: str
    feasibility_prerequisite: str
    scientific_notice: str
    data_confidence: str
    thresholds_applied: dict[str, float]


class CellLandCoverResponse(BaseModel):
    cell_id: str
    season: str
    year: int
    start_date: str
    end_date: str
    probabilities: DynamicWorldProbabilities
    proportions: DynamicWorldProbabilities
    valid_observation_count: int
    top_class: str | None
    confidence: float | None
    margin: float | None
    entropy: float | None
    status: str
    suitability: LandCoverSuitabilityResponse | None = None
    attribution: str
    citation: str
    license: str
    source_dataset: str
    pipeline_version: str


class LandCoverSummaryResponse(BaseModel):
    season: str
    year: int
    total_cells_recorded: int
    cells_sufficient: int
    cells_insufficient: int
    cells_no_observations: int
    class_distribution: dict[str, int]
    mean_probabilities: dict[str, float]
    mean_confidence: float | None
    mean_entropy: float | None
    attribution: str
    citation: str
    license: str
    pipeline_version: str


class LandCoverGridItem(BaseModel):
    cell_id: str
    top_class: str | None
    confidence: float | None
    entropy: float | None
    mean_built: float | None
    mean_trees: float | None
    mean_bare: float | None
    mean_grass: float | None
    mean_crops: float | None
    mean_water: float | None


@router.get("/landcover/summary", response_model=LandCoverSummaryResponse)
def get_landcover_summary(
    season: str = "summer",
    year: int = 2024,
    db: Session = Depends(get_db),
):
    \"\"\"
    Retrieve citywide seasonal Dynamic World land-cover summary diagnostics and class distribution.
    \"\"\"
    rows = (
        db.query(StageDDynamicWorldLandCover)
        .filter(
            StageDDynamicWorldLandCover.season == season,
            StageDDynamicWorldLandCover.year == year,
        )
        .all()
    )

    total = len(rows)
    cnt_suff = sum(1 for r in rows if r.status == "SUFFICIENT")
    cnt_insuff = sum(1 for r in rows if r.status == "INSUFFICIENT_OBSERVATIONS")
    cnt_no_obs = sum(1 for r in rows if r.status == "NO_OBSERVATIONS")

    dist: dict[str, int] = {}
    prob_sums: dict[str, float] = {c: 0.0 for c in DW_CLASSES}
    valid_probs_cnt: dict[str, int] = {c: 0 for c in DW_CLASSES}
    conf_sum = 0.0
    conf_cnt = 0
    entropy_sum = 0.0
    entropy_cnt = 0

    for r in rows:
        if r.top_class:
            dist[r.top_class] = dist.get(r.top_class, 0) + 1
        if r.confidence is not None:
            conf_sum += r.confidence
            conf_cnt += 1
        if r.entropy is not None:
            entropy_sum += r.entropy
            entropy_cnt += 1

        for c in DW_CLASSES:
            val = getattr(r, f"mean_{c}", None)
            if val is not None:
                prob_sums[c] += val
                valid_probs_cnt[c] += 1

    mean_probs = {
        c: round(prob_sums[c] / valid_probs_cnt[c], 4) if valid_probs_cnt[c] > 0 else 0.0
        for c in DW_CLASSES
    }

    return LandCoverSummaryResponse(
        season=season,
        year=year,
        total_cells_recorded=total,
        cells_sufficient=cnt_suff,
        cells_insufficient=cnt_insuff,
        cells_no_observations=cnt_no_obs,
        class_distribution=dist,
        mean_probabilities=mean_probs,
        mean_confidence=round(conf_sum / conf_cnt, 4) if conf_cnt > 0 else None,
        mean_entropy=round(entropy_sum / entropy_cnt, 4) if entropy_cnt > 0 else None,
        attribution=ATTRIBUTION_TEXT,
        citation=CITATION_TEXT,
        license=LICENSE_TEXT,
        pipeline_version=PIPELINE_VERSION,
    )


@router.get("/landcover/grid", response_model=list[LandCoverGridItem])
def get_landcover_grid(
    season: str = "summer",
    year: int = 2024,
    limit: int = 2000,
    db: Session = Depends(get_db),
):
    \"\"\"
    Retrieve lightweight grid land-cover predictions for map visualization.
    \"\"\"
    rows = (
        db.query(StageDDynamicWorldLandCover)
        .filter(
            StageDDynamicWorldLandCover.season == season,
            StageDDynamicWorldLandCover.year == year,
        )
        .limit(limit)
        .all()
    )

    return [
        LandCoverGridItem(
            cell_id=r.cell_id,
            top_class=r.top_class,
            confidence=r.confidence,
            entropy=r.entropy,
            mean_built=r.mean_built,
            mean_trees=r.mean_trees,
            mean_bare=r.mean_bare,
            mean_grass=r.mean_grass,
            mean_crops=r.mean_crops,
            mean_water=r.mean_water,
        )
        for r in rows
    ]


@router.get("/landcover/{cell_id}", response_model=CellLandCoverResponse)
def get_cell_landcover(
    cell_id: str,
    season: str = "summer",
    year: int = 2024,
    db: Session = Depends(get_db),
):
    \"\"\"
    Retrieve detailed seasonal Dynamic World probabilities, hard proportions, and suitability assessment for a cell.
    \"\"\"
    rec = fetch_cell_landcover(cell_id=cell_id, season=season, year=year, db=db)
    if not rec:
        raise HTTPException(
            status_code=404,
            detail=f"No Dynamic World land cover record found for cell '{cell_id}' in season '{season}' {year}.",
        )

    probs = DynamicWorldProbabilities(
        water=rec["mean_water"],
        trees=rec["mean_trees"],
        grass=rec["mean_grass"],
        flooded_vegetation=rec["mean_flooded_vegetation"],
        crops=rec["mean_crops"],
        shrub_and_scrub=rec["mean_shrub_and_scrub"],
        built=rec["mean_built"],
        bare=rec["mean_bare"],
        snow_and_ice=rec["mean_snow_and_ice"],
    )

    props = DynamicWorldProbabilities(
        water=rec["prop_water"],
        trees=rec["prop_trees"],
        grass=rec["prop_grass"],
        flooded_vegetation=rec["prop_flooded_vegetation"],
        crops=rec["prop_crops"],
        shrub_and_scrub=rec["prop_shrub_and_scrub"],
        built=rec["prop_built"],
        bare=rec["prop_bare"],
        snow_and_ice=rec["prop_snow_and_ice"],
    )

    suit_eval = evaluate_landcover_suitability(dw_record=rec, cell_id=cell_id)
    suit_resp = LandCoverSuitabilityResponse(
        rule_fired=suit_eval.rule_fired,
        suitable_interventions=[i.value for i in suit_eval.suitable_interventions],
        screened_out_interventions=[i.value for i in suit_eval.screened_out_interventions],
        screening_status=suit_eval.screening_status,
        screening_reason=suit_eval.screening_reason,
        feasibility_prerequisite=suit_eval.feasibility_prerequisite,
        scientific_notice=suit_eval.scientific_notice,
        data_confidence=suit_eval.data_confidence,
        thresholds_applied=suit_eval.thresholds_applied,
    )

    return CellLandCoverResponse(
        cell_id=cell_id,
        season=season,
        year=year,
        start_date=rec["start_date"],
        end_date=rec["end_date"],
        probabilities=probs,
        proportions=props,
        valid_observation_count=rec["valid_observation_count"],
        top_class=rec["top_class"],
        confidence=rec["confidence"],
        margin=rec["margin"],
        entropy=rec["entropy"],
        status=rec["status"],
        suitability=suit_resp,
        attribution=ATTRIBUTION_TEXT,
        citation=CITATION_TEXT,
        license=LICENSE_TEXT,
        source_dataset=rec["source_dataset"],
        pipeline_version=rec["pipeline_version"],
    )
"""

code += endpoints_code

with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(code)

print("Appended landcover endpoints to backend/app/api/v1/interventions.py successfully")

