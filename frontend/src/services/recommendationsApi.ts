import { API_BASE_URL } from "./api";

export interface QuantityBasis {
  estimated_quantity: number;
  unit: string;
  basis_description: string;
  missing_data_survey_note: string;
}

export interface CostRangeINR {
  base: number;
  min: number;
  max: number;
  formatted: string;
  maintenance_horizon: string;
}

export interface CoolingRangeC {
  expected: number;
  min: number;
  max: number;
  formatted: string;
  model_source: string;
}

export interface RejectedAlternative {
  intervention_type: string;
  title: string;
  rejection_reason: string;
}

export interface RecommendationItem {
  type: string;
  title: string;
  priority: "HIGH" | "MEDIUM" | "LOW" | "NOT_RECOMMENDED";
  rationale: string;
  quantity_basis: QuantityBasis;
  cost_range_inr: CostRangeINR;
  cooling_range_c: CoolingRangeC;
  feasibility_status: "FEASIBLE" | "CONDITIONALLY_FEASIBLE" | "REJECTED";
  rejection_reasons: string[];
  feasibility_notes: string[];
  maintenance_note: string;
  evidence_label: "MEASURED" | "MODELLED" | "ASSUMPTION" | "UNVERIFIED";
  missing_data_survey_requirements: string[];
  landuse_typology?: string;
  allowed_interventions?: string[];
  selection_rationale?: string;
  rejected_alternatives?: RejectedAlternative[];
  water_need_description?: string;
  maintenance_burden?: string;
  construction_time?: string;
  whole_life_cost_3yr_inr?: number;
  whole_life_cost_per_c_m2?: number;
  air_cooling_c?: number;
  needs_site_survey?: boolean;
  screening_status?: "MODEL_ELIGIBLE" | "NOT_APPLICABLE" | "EXCLUDED" | string;
  screening_reason_code?: string;
  site_suitability?: string;
  ownership_legal?: string;
  engineering_clearance?: string;
  procurement_status?: string;
  benefit_evidence?: string;
  data_confidence?: string;
  cooling_metric?: string;
  cell_scope_note?: string;
  price_date_note?: string;
  schedule_alignment_note?: string;
  unit_rate?: number;
  unit_rate_unit?: string;
  markups_description?: string;
}

export interface PolygonSummary {
  status: "ok" | "outside_study_area" | "partially_outside" | "no_valid_observations";
  area_km2: number;
  inside_smc_fraction: number;
  season: string;
  effective_year: number;
  mean_lst_c?: number | null;
  max_lst_c?: number | null;
  min_lst_c?: number | null;
  p90_lst_c?: number | null;
  mean_hpi?: number | null;
  max_hpi?: number | null;
  vegetation_deficit_component?: number | null;
  built_density_component?: number | null;
  mean_ndvi?: number | null;
  mean_ndbi?: number | null;
  mean_ndwi?: number | null;
  water_fraction: number;
  water_warning: boolean;
  cell_count: number;
  chronic_cell_count: number;
  chronic_cell_share: number;
  frequent_cell_share: number;
  data_coverage_percentage: number;
  confidence_score: number;
  confidence_tier: string;
  landuse_typology?: string | null;
  needs_site_survey?: boolean;
  crs?: string;
  area_method?: string;
  pixel_size?: string;
  total_intersecting_pixels?: number;
  valid_pixels?: number;
  nodata_count?: number;
  coverage_definition?: string;
  boundary_source?: string;
  geometry_warning?: string | null;
}

export interface CandidateSite {
  candidate_id: string;
  type: string;
  title: string;
  spatial_unit: string;
  reasoning_state: string;
  quantity: number;
  unit: string;
  cost_base_inr: number;
  cooling_skin_expected_c: number;
  bounding_geometry?: any;
}

export interface QuantityCostRollup {
  total_capital_spend_inr: number;
  total_capital_spend_formatted: string;
  total_direct_cost_inr: number;
  total_annual_maintenance_inr: number;
  total_treated_area_m2: number;
  total_treated_area_ha: number;
  eligible_options_count: number;
  rejected_options_count: number;
}

export interface RejectedCandidate {
  type: string;
  title: string;
  rule_id: string;
  spatial_unit: string;
  reasoning_state: string;
  screening_status: string;
  reasons: string[];
}

export interface EvidenceAvailabilityItem {
  provider_id: string;
  layer_title: string;
  availability: "AVAILABLE" | "PARTIAL" | "UNAVAILABLE";
  dataset_name: string;
  version: string;
  effective_date: string;
  spatial_resolution: string;
  authority: string;
  coverage_fraction: number;
  quality_flag: string;
  missing_reason?: string | null;
}

export interface RecommendationsResponse {
  polygon_summary: PolygonSummary;
  recommendations: RecommendationItem[];
  caveats: string[];
  assumptions_applied: string[];
  evidence_label: string;
  heat_conditions?: Record<string, any>;
  physical_features?: Record<string, any>;
  candidate_sites?: CandidateSite[];
  quantity_cost_rollup?: QuantityCostRollup;
  evidence_gaps?: string[];
  rejected_candidates?: RejectedCandidate[];
  evidence_availability_panel?: EvidenceAvailabilityItem[];
  cache_key?: string | null;
}

export async function fetchPolygonRecommendations(
  geometry: any,
  season: string = "summer",
  year?: number,
  signal?: AbortSignal
): Promise<RecommendationsResponse> {
  const response = await fetch(`${API_BASE_URL}/analysis/recommendations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      geometry,
      season,
      year: year ?? null,
    }),
    signal,
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}`;
    try {
      const err = await response.json();
      if (err?.detail) {
        errorDetail = err.detail;
      }
    } catch {
      // ignore json error
    }
    throw new Error(errorDetail);
  }

  return response.json() as Promise<RecommendationsResponse>;
}

export function exportRecommendationsToJson(data: RecommendationsResponse, filename: string): void {
  const jsonStr = JSON.stringify(data, null, 2);
  const blob = new Blob([jsonStr], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.endsWith(".json") ? filename : `${filename}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function exportRecommendationsToCsv(data: RecommendationsResponse, filename: string): void {
  const headers = [
    "Type",
    "Title",
    "Priority",
    "Screening Status",
    "Screening Reason Code",
    "Site Suitability",
    "Ownership Legal",
    "Engineering Clearance",
    "Procurement Status",
    "Feasibility Status",
    "Quantity Basis",
    "Unit",
    "Unit Rate (INR)",
    "Unit Rate Basis",
    "Markups Description",
    "Price Date Note",
    "Schedule Alignment Note",
    "Cost Base (INR)",
    "Cost Min (INR)",
    "Cost Max (INR)",
    "Cooling Metric",
    "Modelled surface temperature reduction (skin), not air temperature - Expected (°C)",
    "Modelled surface temperature reduction (skin), not air temperature - Min (°C)",
    "Modelled surface temperature reduction (skin), not air temperature - Max (°C)",
    "Scope Note",
    "Rationale",
    "Maintenance Note",
    "Evidence Label",
    "Rejection Reasons",
    "Missing Data Survey Requirements",
  ];

  const rows = data.recommendations.map((r) => {
    const isRejected =
      r.feasibility_status === "REJECTED" ||
      r.screening_status === "NOT_APPLICABLE" ||
      r.screening_status === "EXCLUDED" ||
      r.priority === "NOT_RECOMMENDED";
    const exportQuantity = isRejected ? 0 : r.quantity_basis.estimated_quantity;
    const exportCostBase = isRejected ? 0.0 : r.cost_range_inr.base;
    const exportCostMin = isRejected ? 0.0 : r.cost_range_inr.min;
    const exportCostMax = isRejected ? 0.0 : r.cost_range_inr.max;

    return [
      `"${r.type}"`,
      `"${r.title.replace(/"/g, '""')}"`,
      `"${r.priority}"`,
      `"${r.screening_status || (isRejected ? 'NOT_APPLICABLE' : 'MODEL_ELIGIBLE')}"`,
      `"${r.screening_reason_code || (isRejected ? 'INCOMPATIBLE_LANDUSE_TYPOLOGY' : 'ELIGIBLE')}"`,
      `"${r.site_suitability || 'UNKNOWN - survey required'}"`,
      `"${r.ownership_legal || 'UNVERIFIED'}"`,
      `"${r.engineering_clearance || 'NOT ASSESSED'}"`,
      `"${r.procurement_status || 'NOT STARTED'}"`,
      `"${r.feasibility_status}"`,
      exportQuantity,
      `"${r.quantity_basis.unit}"`,
      isRejected ? 0 : (r.unit_rate ?? ""),
      `"${(r.unit_rate_unit || r.quantity_basis.unit).replace(/"/g, '""')}"`,
      `"${(r.markups_description || '').replace(/"/g, '""')}"`,
      `"${(r.price_date_note || 'indicative, not a tender price').replace(/"/g, '""')}"`,
      `"${(r.schedule_alignment_note || 'rates not verified against CPWD/SMC schedule').replace(/"/g, '""')}"`,
      exportCostBase,
      exportCostMin,
      exportCostMax,
      `"${(r.cooling_metric || 'modelled surface (skin) temperature reduction on treated area').replace(/"/g, '""')}"`,
      isRejected ? 0.0 : r.cooling_range_c.expected,
      isRejected ? 0.0 : r.cooling_range_c.min,
      isRejected ? 0.0 : r.cooling_range_c.max,
      `"${(r.cell_scope_note || 'Modelled surface skin temperature reduction on treated area, not ambient air temperature.').replace(/"/g, '""')}"`,
      `"${r.rationale.replace(/"/g, '""')}"`,
      `"${r.maintenance_note.replace(/"/g, '""')}"`,
      `"${r.evidence_label}"`,
      `"${r.rejection_reasons.join("; ").replace(/"/g, '""')}"`,
      `"${r.missing_data_survey_requirements.join("; ").replace(/"/g, '""')}"`,
    ];
  });

  const csvContent = [headers.join(","), ...rows.map((row) => row.join(","))].join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
