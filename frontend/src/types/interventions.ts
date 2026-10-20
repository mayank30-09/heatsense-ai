export type InterventionType =
  | "tree_canopy"
  | "cool_roof"
  | "green_roof"
  | "cool_pavement";

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
  evidence_status: string;
  geometry: {
    type: string;
    coordinates: number[][][];
  };
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
