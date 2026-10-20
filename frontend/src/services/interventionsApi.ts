import type {
  CandidateListResponse,
  InterventionCandidateItem,
  InterventionType,
  OptimizationResultResponse,
  OptimizeRequestPayload,
} from "../types/interventions";

const API_BASE_URL = "http://127.0.0.1:8000/api/v1/interventions";

export async function fetchInterventionCandidates(
  filters: {
    bbox?: { min_lon: number; min_lat: number; max_lon: number; max_lat: number };
    intervention_type?: InterventionType;
    feasibility_status?: string;
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
  params.set("limit", (filters.limit ?? 50).toString());
  params.set("offset", (filters.offset ?? 0).toString());

  const url = `${API_BASE_URL}/candidates?${params.toString()}`;
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
  const url = `${API_BASE_URL}/candidates/${encodeURIComponent(candidateId)}`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Failed to load candidate detail: HTTP ${response.status}`);
  }
  return response.json() as Promise<InterventionCandidateItem>;
}

export async function runInterventionOptimization(
  payload: OptimizeRequestPayload,
  signal?: AbortSignal
): Promise<OptimizationResultResponse> {
  const url = `${API_BASE_URL}/optimize`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    throw new Error(`Optimization failed: HTTP ${response.status}`);
  }
  return response.json() as Promise<OptimizationResultResponse>;
}
