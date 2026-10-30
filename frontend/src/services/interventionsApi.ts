import type {
  AreaItem,
  AreaSummary,
  CandidateListResponse,
  ClusterCellsResponse,
  ClustersListResponse,
  DiminishingReturnsRequestPayload,
  DiminishingReturnsResponse,
  InterventionCandidateItem,
  InterventionType,
  OptimizationResultResponse,
  OptimizeRequestPayload,
  PlanningScenario,
  CellLandCoverData,
  LandCoverSummaryData,
  TypeAvailabilityMap,
} from "../types/interventions";

import { API_BASE_URL } from "./api";

const INTERVENTIONS_BASE_URL = `${API_BASE_URL}/interventions`;

export async function fetchInterventionCandidates(
  filters: {
    bbox?: { min_lon: number; min_lat: number; max_lon: number; max_lat: number };
    intervention_type?: InterventionType;
    feasibility_status?: string;
    min_hpi?: number;
    locality?: string;
    max_budget?: number;
    sort_by?: "hpi_desc" | "cost_asc" | "cost_desc" | "cooling_desc";
    cell_id?: string;
    limit?: number;
    offset?: number;
  } = {},
  signal?: AbortSignal
): Promise<CandidateListResponse> {
  const params = new URLSearchParams();
  if (filters.bbox) {
    const { min_lon, min_lat, max_lon, max_lat } = filters.bbox;
    params.set("bbox", `${min_lon},${min_lat},${max_lon},${max_lat}`);
  }
  if (filters.intervention_type) {
    params.set("intervention_type", filters.intervention_type);
  }
  if (filters.feasibility_status) {
    params.set("feasibility_status", filters.feasibility_status);
  }
  if (filters.min_hpi !== undefined) {
    params.set("min_hpi", filters.min_hpi.toString());
  }
  if (filters.locality) {
    params.set("locality", filters.locality);
  }
  if (filters.max_budget !== undefined) {
    params.set("max_budget", filters.max_budget.toString());
  }
  if (filters.sort_by) {
    params.set("sort_by", filters.sort_by);
  }
  if (filters.cell_id) {
    params.set("cell_id", filters.cell_id);
  }
  params.set("limit", (filters.limit ?? 50).toString());
  params.set("offset", (filters.offset ?? 0).toString());

  const url = `${INTERVENTIONS_BASE_URL}/candidates?${params.toString()}`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Failed to load intervention candidates: HTTP ${response.status}`);
  }
  return response.json() as Promise<CandidateListResponse>;
}

export async function fetchCandidateDetail(
  candidateId: string,
  signal?: AbortSignal
): Promise<InterventionCandidateItem> {
  const url = `${INTERVENTIONS_BASE_URL}/candidates/${encodeURIComponent(candidateId)}`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Failed to load candidate detail: HTTP ${response.status}`);
  }
  return response.json() as Promise<InterventionCandidateItem>;
}

export async function runInterventionOptimization(
  payload: OptimizeRequestPayload,
  token?: string,
  signal?: AbortSignal
): Promise<OptimizationResultResponse> {
  const url = `${INTERVENTIONS_BASE_URL}/optimize`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson && errJson.detail) {
        detail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore
    }
    throw new Error(`Optimization failed: ${detail}`);
  }
  return response.json() as Promise<OptimizationResultResponse>;
}

export const optimizeInterventions = runInterventionOptimization;

export async function fetchScenarios(signal?: AbortSignal): Promise<PlanningScenario[]> {
  const url = `${INTERVENTIONS_BASE_URL}/scenarios`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Failed to load planning scenarios: HTTP ${response.status}`);
  }
  return response.json() as Promise<PlanningScenario[]>;
}

export async function fetchDiminishingReturns(
  payload: DiminishingReturnsRequestPayload = {},
  token?: string,
  signal?: AbortSignal
): Promise<DiminishingReturnsResponse> {
  const url = `${INTERVENTIONS_BASE_URL}/diminishing-returns`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    throw new Error(`Failed to load diminishing returns curve: HTTP ${response.status}`);
  }
  return response.json() as Promise<DiminishingReturnsResponse>;
}

export async function fetchInterventionAreas(
  minHpi = 35.0,
  signal?: AbortSignal
): Promise<AreaItem[]> {
  const url = `${INTERVENTIONS_BASE_URL}/areas?min_hpi=${minHpi}`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch intervention areas: HTTP ${response.status}`);
  }
  return response.json() as Promise<AreaItem[]>;
}

export async function fetchAreaSummary(
  area: string,
  params: {
    min_hpi?: number;
    intervention_type?: string;
    feasibility_status?: string;
    budget_cap_inr?: number;
  } = {},
  signal?: AbortSignal
): Promise<AreaSummary> {
  const query = new URLSearchParams();
  if (params.min_hpi !== undefined) query.set("min_hpi", params.min_hpi.toString());
  if (params.intervention_type) query.set("intervention_type", params.intervention_type);
  if (params.feasibility_status) query.set("feasibility_status", params.feasibility_status);
  if (params.budget_cap_inr !== undefined) query.set("budget_cap_inr", params.budget_cap_inr.toString());

  const url = `${INTERVENTIONS_BASE_URL}/areas/${encodeURIComponent(area)}/summary?${query.toString()}`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch area summary: HTTP ${response.status}`);
  }
  return response.json() as Promise<AreaSummary>;
}

export async function fetchAreaClusters(
  area: string,
  params: {
    intervention_type?: string;
    feasibility_status?: string;
    min_hpi?: number;
    min_priority?: number;
    sort_by?: string;
    budget_cap_inr?: number;
    limit?: number;
    offset?: number;
    max_cluster_size?: number;
  } = {},
  signal?: AbortSignal
): Promise<ClustersListResponse> {
  const query = new URLSearchParams();
  if (params.intervention_type) query.set("intervention_type", params.intervention_type);
  if (params.feasibility_status) query.set("feasibility_status", params.feasibility_status);
  if (params.min_hpi !== undefined) query.set("min_hpi", params.min_hpi.toString());
  if (params.min_priority !== undefined) query.set("min_priority", params.min_priority.toString());
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.budget_cap_inr !== undefined) query.set("budget_cap_inr", params.budget_cap_inr.toString());
  query.set("limit", (params.limit ?? 10).toString());
  query.set("offset", (params.offset ?? 0).toString());
  if (params.max_cluster_size) query.set("max_cluster_size", params.max_cluster_size.toString());

  const url = `${INTERVENTIONS_BASE_URL}/areas/${encodeURIComponent(area)}/clusters?${query.toString()}`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch area clusters: HTTP ${response.status}`);
  }
  return response.json() as Promise<ClustersListResponse>;
}

export async function fetchClusterCells(
  clusterId: string,
  signal?: AbortSignal
): Promise<ClusterCellsResponse> {
  const url = `${INTERVENTIONS_BASE_URL}/clusters/${encodeURIComponent(clusterId)}/cells`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch cluster cells: HTTP ${response.status}`);
  }
  return response.json() as Promise<ClusterCellsResponse>;
}



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

export async function fetchTypeAvailability(
  areaName: string = "all",
  minHpi = 35.0,
  signal?: AbortSignal
): Promise<TypeAvailabilityMap> {
  const url = `${INTERVENTIONS_BASE_URL}/types/availability?area_name=${encodeURIComponent(areaName)}&min_hpi=${minHpi}`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch type availability: HTTP ${response.status}`);
  }
  return response.json() as Promise<TypeAvailabilityMap>;
}

export async function exportOptimizationCsv(
  payload: OptimizeRequestPayload,
  exportLevel: "package" | "cell" = "package",
  token?: string
): Promise<Blob> {
  const url = `${INTERVENTIONS_BASE_URL}/optimize/export?export_level=${exportLevel}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Failed to export optimization CSV: HTTP ${response.status}`);
  }
  return response.blob();
}
