import type {
  CellQueryFilters,
  GridCellScoreItem,
  GridCellsPaginatedResponse,
  HeatPrioritySummary,
  LSTStats,
  SeasonName,
} from "../types/heatPriority";

import { API_BASE_URL } from "./api";

const HEAT_PRIORITY_BASE_URL = `${API_BASE_URL}/heat-priority`;

export async function fetchHeatPrioritySummary(
  scoringPeriod: string = "2026_summer_operational",
  specVersion: string = "v2.0",
  signal?: AbortSignal
): Promise<HeatPrioritySummary> {
  const url = `${HEAT_PRIORITY_BASE_URL}/summary?scoring_period=${encodeURIComponent(
    scoringPeriod
  )}&spec_version=${encodeURIComponent(specVersion)}`;

  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Failed to load HPI summary: HTTP ${response.status}`);
  }
  return response.json() as Promise<HeatPrioritySummary>;
}

export async function fetchGridCells(
  filters: CellQueryFilters = {},
  signal?: AbortSignal
): Promise<GridCellsPaginatedResponse> {
  const params = new URLSearchParams();
  params.set("scoring_period", "2026_summer_operational");
  params.set("spec_version", "v2.0");

  if (filters.bbox) {
    const { min_lon, min_lat, max_lon, max_lat } = filters.bbox;
    params.set("bbox", `${min_lon},${min_lat},${max_lon},${max_lat}`);
  }

  if (filters.min_hpi !== undefined && filters.min_hpi !== null) {
    params.set("min_hpi", filters.min_hpi.toString());
  }

  if (filters.is_chronic_hotspot !== undefined && filters.is_chronic_hotspot !== null) {
    params.set("is_chronic_hotspot", filters.is_chronic_hotspot.toString());
  }

  if (filters.confidence_tier) {
    params.set("confidence_tier", filters.confidence_tier);
  }

  if (filters.persistence_tier) {
    params.set("persistence_tier", filters.persistence_tier);
  }

  if (filters.locality) {
    params.set("locality", filters.locality);
  }

  if (filters.season) {
    params.set("season", filters.season);
  }

  if (filters.year) {
    params.set("year", filters.year.toString());
  }

  params.set("limit", (filters.limit ?? 250).toString());
  params.set("offset", (filters.offset ?? 0).toString());

  const response = await fetch(`${HEAT_PRIORITY_BASE_URL}/cells?${params.toString()}`, { signal });
  if (!response.ok) {
    throw new Error(`Failed to load grid cells: HTTP ${response.status}`);
  }
  return response.json() as Promise<GridCellsPaginatedResponse>;
}

export async function fetchGridCellDetail(
  pixelId: string,
  scoringPeriod: string = "2026_summer_operational",
  specVersion: string = "v2.0",
  signal?: AbortSignal
): Promise<GridCellScoreItem> {
  const url = `${HEAT_PRIORITY_BASE_URL}/cell/${encodeURIComponent(pixelId)}?scoring_period=${encodeURIComponent(
    scoringPeriod
  )}&spec_version=${encodeURIComponent(specVersion)}`;

  const response = await fetch(url, { signal });
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Grid cell '${pixelId}' not found.`);
    }
    throw new Error(`Failed to load cell detail: HTTP ${response.status}`);
  }
  return response.json() as Promise<GridCellScoreItem>;
}

export async function fetchLSTStats(
  season: SeasonName = "summer",
  year?: number,
  signal?: AbortSignal
): Promise<LSTStats> {
  const params = new URLSearchParams();
  params.set("season", season);
  if (year !== undefined && year !== null) {
    params.set("year", year.toString());
  }

  const response = await fetch(`${HEAT_PRIORITY_BASE_URL}/lst-stats?${params.toString()}`, { signal });
  if (!response.ok) {
    throw new Error(`Failed to load LST statistics: HTTP ${response.status}`);
  }
  return response.json() as Promise<LSTStats>;
}
