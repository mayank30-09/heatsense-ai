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
  targeted_surface?: string;
  surface_source?: string;
  is_proxy?: boolean;
  cost_breakdown?: Partial<CostBreakdown>;
}

export interface CandidateListResponse {
  total_count: number;
  limit: number;
  offset: number;
  items: InterventionCandidateItem[];
}

export interface OptimizeRequestPayload {
  budget_inr: number;
  algorithm?: "exact" | "nsga2" | "greedy";
  strategy?: "hotspot_first" | "max_benefit" | "cost_effective";
  scope?: string;
  target_types?: InterventionType[];
  max_candidates?: number;
  generations?: number;
}

export interface DeploymentDetail {
  candidate_id: string;
  cell_id: string;
  intervention_type: InterventionType;
  cost_inr: number;
  usable_area_m2: number;
  expected_cooling_c: number;
  baseline_hpi: number | null;
  baseline_lst_c: number | null;
  is_chronic_hotspot: boolean;
  administrative_zone: string;
  latitude: number;
  longitude: number;
  landuse_typology: string;
  feasibility_status: FeasibilityStatus;
  prerequisites_status: string;
  survey_prerequisites: string[];
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
  run_id?: string;
  deployments?: DeploymentDetail[];
  unresolved_prerequisites_count?: number;
  total_expected_cooling_c?: number;
  heat_priority_weighted_cooling?: number;
  selected_packages?: PackageItem[];
  packages_count?: number;
  cells_count?: number;
  optimality_gap_percent?: number;
  budget_curve?: BudgetCurvePoint[];
  locality_rollup?: LocalityRollupItem[];
  strategy_comparison?: StrategyComparison;
}

export interface OptimizationConfig {
  run_id?: string;
  budget_inr: number;
  algorithm: string;
  max_candidates: number;
  generations?: number;
  target_types?: string[];
  random_seed?: number;
}

export interface OptimizationResultResponse {
  run_id?: string;
  algorithm: string;
  budget_inr: number;
  solutions_count: number;
  solutions: ScenarioSolutionItem[];
  recommended_solution?: ScenarioSolutionItem;
  budget_curve?: BudgetCurvePoint[];
  locality_rollup?: LocalityRollupItem[];
  strategy_comparison?: StrategyComparison;
  candidate_count?: number;
  eligible_count?: number;
  selected_packages?: PackageItem[];
  spend_inr?: number;
  utilization_pct?: number;
  hotspot_cells_covered?: number;
  benefit_k_m2?: number;
  runtime_ms?: number;
  status?: string;
  reason?: string;
  config?: OptimizationConfig;
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
  budget_utilization_percent?: number;
  treated_cells_count: number;
  treated_area_m2: number;
  mean_local_cooling_c: number;
  citywide_cooling_c: number;
  heat_priority_weighted_benefit_c_m2: number;
  marginal_benefit_per_inr?: number;
  marginal_cooling_per_cr_inr?: number;
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

export interface AreaItem {
  area_name: string;
  total_cells: number;
  eligible_cell_count: number;
  chronic_hotspot_count: number;
  mean_hpi: number;
  max_hpi: number;
  is_sufficient: boolean;
  data_status: string;
  insufficient_reason?: string | null;
  top_recommended_type: string;
  estimated_portfolio_cost_inr: number;
  expected_portfolio_cooling_c: number;
}

export interface CostBreakdown {
  materials_cost_inr: number;
  labour_cost_inr: number;
  direct_cost_inr: number;
  design_supervision_inr: number;
  gst_18_pct_inr: number;
  contingency_inr: number;
  scaled_site_setup_inr: number;
  water_tanker_inr: number;
  plant_replacement_inr: number;
  capital_cost_inr: number;
  maintenance_3yr_inr: number;
  maintenance_10yr_inr: number;
  whole_life_cost_3yr_inr: number;
  whole_life_cost_10yr_inr: number;
}

export interface RateProvenance {
  source_name: string;
  schedule_type: string;
  item_reference: string;
  rate_basis?: string | null;
  statutory_tax_note: string;
  contingency_note: string;
  design_supervision_note: string;
  verified?: boolean;
}

export interface EvidenceRationale {
  rule_fired: string;
  governing_principle?: string | null;
  thermodynamics_formula?: string | null;
  empirical_cooling_range?: string | null;
  maturity_notice?: string | null;
  verified_literature_citations: string[];
  uncertainties: string[];
  survey_requirements: string[];
}

export interface Phase1Portfolio {
  budget_cap_inr: number;
  budget_utilized_inr: number;
  budget_utilization_pct: number;
  clusters_count: number;
  cells_count: number;
  chronic_hotspots_covered: number;
  mean_cooling_c: number;
  treated_footprint_m2: number;
}

export interface DataConfidenceSummary {
  survey_required_percentage: number;
  unverified_roof_percentage: number;
  valid_observations_percentage: number;
  measured_buildings_cells_count?: number;
  proxy_cells_count?: number;
  measured_percentage?: number;
  proxy_percentage?: number;
}

export interface AreaSummary {
  area_name: string;
  is_all_areas: boolean;
  total_cells: number;
  eligible_cells: number;
  chronic_cells: number;
  assigned_cells_count: number;
  unassigned_insufficient_surface_count: number;
  mean_hpi: number;
  mean_baseline_lst_c: number;
  best_option_mean_cooling_c: number;
  best_option_portfolio_cost_inr: number;
  full_coverage_bound_inr: number;
  total_treated_area_m2: number;
  total_geographic_area_ha: number;
  qualifying_candidates_count: number;
  clusters_count: number;
  is_sufficient: boolean;
  insufficient_reason?: string | null;
  phase1_portfolio?: Phase1Portfolio;
  data_confidence_summary: DataConfidenceSummary;
}

export interface ClusterCentroid {
  latitude: number;
  longitude: number;
}

export interface ClusterBoundingBox {
  min_lon: number;
  min_lat: number;
  max_lon: number;
  max_lat: number;
}

export interface ClusterRankingFactors {
  hpi_factor: number;
  chronic_factor: number;
  cooling_factor: number;
  cost_effectiveness_factor: number;
}

export interface ClusterRecommendation {
  cluster_id: string;
  area_name: string;
  intervention_type: InterventionType;
  title: string;
  priority_rank: number;
  priority_score: number;
  priority_tier: "CRITICAL" | "HIGH" | "MEDIUM" | "MODERATE";
  cell_count: number;
  treated_footprint_m2: number;
  geographic_coverage_ha: number;
  expected_cooling_c: number;
  expected_cooling_c_range: [number, number];
  indicative_diluted_cooling_c: number;
  estimated_cost_inr: number;
  estimated_cost_inr_range: [number, number];
  unit_cost_inr_per_m2: number;
  mean_hpi: number;
  max_hpi: number;
  chronic_hotspot_cells_count: number;
  mean_baseline_lst_c: number;
  centroid: ClusterCentroid;
  bounding_box: ClusterBoundingBox;
  confidence_rating: "HIGH" | "MEDIUM" | "LOW";
  survey_required_cells_count: number;
  unverified_roof_cells_count: number;
  targeted_surface?: string;
  land_cover_source?: string;
  cost_breakdown?: CostBreakdown;
  rate_provenance?: RateProvenance;
  evidence_rationale?: EvidenceRationale;
  in_phase1_plan?: boolean;
  caveats_and_warnings: string[];
  co_benefits_summary: string;
  ranking_factors: ClusterRankingFactors;
}

export interface ClustersListResponse {
  total_clusters: number;
  limit: number;
  offset: number;
  area_name: string;
  is_sufficient: boolean;
  insufficient_reason?: string | null;
  clusters: ClusterRecommendation[];
}

export interface ClusterCellsResponse {
  cluster_id: string;
  area_name: string;
  intervention_type: string;
  cell_count: number;
  cells: InterventionCandidateItem[];
}


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

// ============================================================================
// Stage D Area-Based Optimization & Packaging Types
// ============================================================================

export interface PackageItem {
  package_id: string;
  cluster_id: string;
  locality: string;
  intervention_type: InterventionType;
  cell_ids: string[];
  cell_count: number;
  cells: InterventionCandidateItem[];
  geographic_coverage_ha?: number;
  treated_footprint_m2: number;
  estimated_cost_inr: number;
  capex_breakdown: Record<string, number>;
  opex_3yr_inr: number;
  expected_cooling_c: number;
  delta_t_skin_c: number;
  delta_t_cell_c: number;
  thermal_benefit_k_m2: number;
  indicative_diluted_cooling_c?: number;
  chronic_hotspot_cells_count: number;
  mean_hpi?: number;
  max_hpi?: number;
  landcover_summary?: Record<string, unknown>;
  confidence_rating?: string;
  unresolved_prerequisites?: string[];
  feasibility_status?: string;
}

export interface LocalityRollupItem {
  locality: string;
  packages_count: number;
  cells_count: number;
  spend_inr: number;
  treated_area_m2: number;
  thermal_benefit_k_m2: number;
  chronic_hotspot_cells_count: number;
  intervention_types: string[];
}

export interface StrategyMetrics {
  title: string;
  description: string;
  packages_count: number;
  cells_count: number;
  spend_inr: number;
  budget_utilized_percent: number;
  thermal_benefit_k_m2: number;
  chronic_hotspots_count: number;
  treated_area_m2: number;
  mean_local_cooling_c: number;
  is_exact_optimal: boolean;
  optimality_gap_percent?: number;
}

export interface StrategyComparison {
  strategy_a_hotspot_first: StrategyMetrics;
  strategy_b_max_benefit: StrategyMetrics;
  strategy_c_greedy_baseline: StrategyMetrics;
  recommended_strategy: string;
  optimality_gap_percent: number;
}

export interface BudgetCurvePoint {
  step: number;
  budget_fraction: number;
  budget_cap_inr: number;
  actual_spend_inr: number;
  spend_utilized_percent: number;
  packages_count: number;
  cells_count: number;
  chronic_hotspots_count: number;
  thermal_benefit_k_m2: number;
}

export interface TypeAvailabilityItem {
  title: string;
  is_assessable: boolean;
  candidate_packages_count: number;
  reason: string | null;
  data_available: string | null;
  data_needed: string | null;
  prerequisites: string | null;
}

export type TypeAvailabilityMap = Record<string, TypeAvailabilityItem>;
