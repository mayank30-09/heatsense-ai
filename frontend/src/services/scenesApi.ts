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
  cog_path: string | null;
}

export async function fetchScenes(signal?: AbortSignal): Promise<SceneItem[]> {
  const response = await fetch(`${API_BASE_URL}/scenes`, { credentials: "omit", signal });

  if (!response.ok) {
    throw new Error(`Failed to fetch scenes catalog: ${response.status}`);
  }

  return response.json() as Promise<SceneItem[]>;
}
