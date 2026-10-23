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
  source?: string;
}

export async function fetchScenes(
  signal?: AbortSignal,
  source: string = "landsat_l2"
): Promise<SceneItem[]> {
  const url = `${API_BASE_URL}/scenes?source=${encodeURIComponent(source)}`;
  const response = await fetch(url, { credentials: "omit", signal });

  if (!response.ok) {
    throw new Error(`Failed to fetch scenes catalog: ${response.status}`);
  }

  return response.json() as Promise<SceneItem[]>;
}
