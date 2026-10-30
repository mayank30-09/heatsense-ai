import { API_BASE_URL } from "./api";

export interface SceneItem {
  scene_id: string;
  acquisition_date: string;
  acquisition_time: string;
  acquisition_time_ist?: string | null;
  sensor: string;
  path: number;
  row: number;
  cloud_cover: number | null;
  valid_pixel_fraction: number;
  mean_lst_c: number | null;
  max_lst_c: number | null;
  status: string;
  rejection_reason?: string | null;
  provisional_hotspots_count?: number | null;
  cog_path: string | null;
  source?: string;
}

export interface ExpectedOverpassItem {
  date: string;
  sensor: string;
  status: "PROCESSED" | "REJECTED" | "PENDING_LATENCY" | "OVERDUE";
  label: string;
  rejection_reason?: string | null;
  days_ago: number;
}

export interface PipelineStatus {
  last_checked: string;
  last_checked_ist?: string | null;
  last_checked_relative?: string | null;
  last_ingested_date: string | null;
  next_expected_overpass: string;
  next_expected_sensor?: string | null;
  next_expected_overpass_label?: string | null;
  pipeline_status: "OPERATIONAL" | "DELAYED" | "ERROR" | "IDLE" | "DEGRADED";
  status_detail?: string | null;
  processed_count: number;
  rejected_count: number;
  recent_overpasses?: ExpectedOverpassItem[];
}

export async function fetchScenes(
  signal?: AbortSignal,
  source: string = "landsat_l2",
  includeRejected: boolean = true
): Promise<SceneItem[]> {
  const url = `${API_BASE_URL}/scenes?source=${encodeURIComponent(source)}&include_rejected=${includeRejected}`;
  const response = await fetch(url, { credentials: "omit", signal });

  if (!response.ok) {
    throw new Error(`Failed to fetch scenes catalog: ${response.status}`);
  }

  return response.json() as Promise<SceneItem[]>;
}

export async function fetchPipelineStatus(
  signal?: AbortSignal
): Promise<PipelineStatus> {
  const url = `${API_BASE_URL}/scenes/pipeline-status`;
  const response = await fetch(url, { credentials: "omit", signal });

  if (!response.ok) {
    throw new Error(`Failed to fetch pipeline status: ${response.status}`);
  }

  return response.json() as Promise<PipelineStatus>;
}


export async function triggerPipelineCheck(): Promise<PipelineStatus> {
  const url = `${API_BASE_URL}/scenes/check`;
  const response = await fetch(url, { method: "POST", credentials: "omit" });

  if (!response.ok) {
    throw new Error(`Failed to trigger pipeline check: ${response.status}`);
  }

  return response.json() as Promise<PipelineStatus>;
}
