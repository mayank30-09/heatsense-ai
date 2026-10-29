"""Patch frontend types and API service with Dynamic World Land Cover."""

from pathlib import Path

# 1. Update frontend/src/types/interventions.ts
types_path = Path("frontend/src/types/interventions.ts")
types_content = types_path.read_text(encoding="utf-8")

extra_types = """

export interface DynamicWorldProbabilities {
  water: number | null;
  trees: number | null;
  grass: number | null;
  flooded_vegetation: number | null;
  crops: number | null;
  shrub_and_scrub: number | null;
  built: number | null;
  bare: number | null;
  snow_and_ice: number | null;
}

export interface LandCoverSuitability {
  rule_fired: string;
  suitable_interventions: string[];
  screened_out_interventions: string[];
  screening_status: string;
  screening_reason: string;
  feasibility_prerequisite: string;
  scientific_notice: string;
  data_confidence: string;
  thresholds_applied: Record<string, number>;
}

export interface CellLandCoverData {
  cell_id: string;
  season: string;
  year: number;
  start_date: string;
  end_date: string;
  probabilities: DynamicWorldProbabilities;
  proportions: DynamicWorldProbabilities;
  valid_observation_count: number;
  top_class: string | null;
  confidence: number | null;
  margin: number | null;
  entropy: number | null;
  status: string;
  suitability: LandCoverSuitability | null;
  attribution: string;
  citation: string;
  license: string;
  source_dataset: string;
  pipeline_version: string;
}

export interface LandCoverSummaryData {
  season: string;
  year: number;
  total_cells_recorded: number;
  cells_sufficient: number;
  cells_insufficient: number;
  cells_no_observations: number;
  class_distribution: Record<string, number>;
  mean_probabilities: Record<string, number>;
  mean_confidence: number | null;
  mean_entropy: number | null;
  attribution: string;
  citation: string;
  license: string;
  pipeline_version: string;
}
"""

if "CellLandCoverData" not in types_content:
    types_content += extra_types
    types_path.write_text(types_content, encoding="utf-8", newline="\n")
    print("Updated frontend/src/types/interventions.ts")

# 2. Update frontend/src/services/interventionsApi.ts
api_path = Path("frontend/src/services/interventionsApi.ts")
api_content = api_path.read_text(encoding="utf-8")

extra_funcs = """
export async function fetchCellLandCover(
  cellId: string,
  season: string = "summer",
  year: number = 2024,
  signal?: AbortSignal
): Promise<CellLandCoverData> {
  const url = `${INTERVENTIONS_BASE_URL}/landcover/${encodeURIComponent(cellId)}?season=${season}&year=${year}`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch cell land cover: HTTP ${response.status}`);
  }
  return response.json() as Promise<CellLandCoverData>;
}

export async function fetchLandCoverSummary(
  season: string = "summer",
  year: number = 2024,
  signal?: AbortSignal
): Promise<LandCoverSummaryData> {
  const url = `${INTERVENTIONS_BASE_URL}/landcover/summary?season=${season}&year=${year}`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch land cover summary: HTTP ${response.status}`);
  }
  return response.json() as Promise<LandCoverSummaryData>;
}
"""

if "fetchCellLandCover" not in api_content:
    # also add imports to top
    if "CellLandCoverData" not in api_content:
        api_content = api_content.replace(
            "  PlanningScenario,\n} from \"../types/interventions\";",
            "  PlanningScenario,\n  CellLandCoverData,\n  LandCoverSummaryData,\n} from \"../types/interventions\";",
        )
    api_content += extra_funcs
    api_path.write_text(api_content, encoding="utf-8", newline="\n")
    print("Updated frontend/src/services/interventionsApi.ts")

