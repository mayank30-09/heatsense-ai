export type InterventionType =
  | "tree_canopy"
  | "cool_roof"
  | "green_roof"
  | "cool_pavement"
  | "public_park_native_trees"
  | "dense_miyawaki_plantation"
  | "bioswale_rain_garden"
  | "rainwater_fed_pond"
  | "shaded_parking_structure"
  | "green_wall"
  | "permeable_ground_cover";

export type FeasibilityStatus = "FEASIBLE" | "REJECTED";

export interface InterventionCandidateItem {
  candidate_id: string;
  cell_id: string;
  row: number;
  col: number;
  longitude: number;
  latitude: number;
  intervention_type: InterventionType;
  usable_area_m2: number;
  tree_count: number;
  baseline_hpi: number | null;
  baseline_lst_c: number | null;
  is_chronic_hotspot: boolean;
  administrative_zone: string;
  feasibility_status: FeasibilityStatus;
  rejection_reason: string;
  cost_inr: number;
  cost_inr_range: [number, number];
  expected_cooling_c: number;
  expected_cooling_c_range: [number, number];
  air_cooling_c?: number;
  evidence_status: string;
  geometry: {
    type: string;
    coordinates: number[][][];
  };
  landuse_typology?: string;
  needs_site_survey?: boolean;
  selection_rationale?: string;
  rejected_alternatives?: Array<{
    intervention_type: string;
    title: string;
    rejection_reason: string;
  }>;
  water_need_description?: string;
  maintenance_burden?: string;
  construction_time?: string;
  whole_life_cost_per_c_m2?: number;
}

export interface CandidateListResponse {
  total_count: number;
  limit: number;
  offset: number;
  items: InterventionCandidateItem[];
}

export interface OptimizeRequestPayload {
  budget_inr: number;
  algorithm: "nsga2" | "greedy";
  target_types?: InterventionType[];
  max_candidates?: number;
  generations?: number;
}

export interface ScenarioSolutionItem {
  solution_id: string;
  algorithm: string;
  total_cost_inr: number;
  portfolio_thermal_benefit_c_m2: number;
  treated_area_m2: number;
  mean_local_cooling_c: number;
  citywide_cooling_c: number;
  domain_area_m2: number;
  heat_priority_weighted_benefit_c_m2: number;
  population_exposure_benefit: number | null;
  population_exposure_status: string;
  chronic_hotspots_count: number;
  interventions_count: number;
  budget_limit_inr: number;
  budget_utilized_percent: number;
  is_feasible: boolean;
  pareto_rank: number;
  crowding_distance: number;
  selected_candidate_ids: string[];
  total_expected_cooling_c?: number;
  heat_priority_weighted_cooling?: number;
}

export interface OptimizationResultResponse {
  algorithm: string;
  budget_inr: number;
  solutions_count: number;
  solutions: ScenarioSolutionItem[];
}

export interface PlanningScenario {
  scenario_name: string;
  tier?: "low" | "medium" | "high";
  budget_inr: number;
  target_focus: string;
  recommended_types: InterventionType[];
  treated_cells?: number;
  total_treated_m2?: number;
  mean_dlst_treated?: [number, number, number];
  peak_hotspot_dlst?: [number, number, number];
  breakdown?: {
    cool_roof_m2: number;
    cool_paver_m2: number;
    green_roof_m2: number;
    trees_count: number;
  };
}

export interface DiminishingReturnsPoint {
  budget_inr: number;
  total_cost_inr: number;
  treated_cells_count: number;
  treated_area_m2: number;
  mean_local_cooling_c: number;
  citywide_cooling_c: number;
  heat_priority_weighted_benefit_c_m2: number;
  chronic_hotspots_count: number;
  trees_count: number;
  cool_roof_m2: number;
  cool_paver_m2: number;
  green_roof_m2: number;
}

export interface DiminishingReturnsResponse {
  algorithm: string;
  curve_points: DiminishingReturnsPoint[];
  parameters: Record<string, unknown>;
}

export interface DiminishingReturnsRequestPayload {
  budgets_inr?: number[];
  max_candidates?: number;
  target_types?: InterventionType[];
}
