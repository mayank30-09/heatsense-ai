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
}

export interface RecommendationsResponse {
  polygon_summary: PolygonSummary;
  recommendations: RecommendationItem[];
  caveats: string[];
  assumptions_applied: string[];
  evidence_label: string;
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
    "Feasibility Status",
    "Quantity Basis",
    "Unit",
    "Cost Base (INR)",
    "Cost Min (INR)",
    "Cost Max (INR)",
    "Expected Cooling (°C)",
    "Cooling Min (°C)",
    "Cooling Max (°C)",
    "Rationale",
    "Maintenance Note",
    "Evidence Label",
    "Rejection Reasons",
    "Missing Data Survey Requirements",
  ];

  const rows = data.recommendations.map((r) => [
    `"${r.type}"`,
    `"${r.title.replace(/"/g, '""')}"`,
    `"${r.priority}"`,
    `"${r.feasibility_status}"`,
    r.quantity_basis.estimated_quantity,
    `"${r.quantity_basis.unit}"`,
    r.cost_range_inr.base,
    r.cost_range_inr.min,
    r.cost_range_inr.max,
    r.cooling_range_c.expected,
    r.cooling_range_c.min,
    r.cooling_range_c.max,
    `"${r.rationale.replace(/"/g, '""')}"`,
    `"${r.maintenance_note.replace(/"/g, '""')}"`,
    `"${r.evidence_label}"`,
    `"${r.rejection_reasons.join("; ").replace(/"/g, '""')}"`,
    `"${r.missing_data_survey_requirements.join("; ").replace(/"/g, '""')}"`,
  ]);

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
