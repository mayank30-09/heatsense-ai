import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchScenes, type SceneItem } from "../scenesApi";

describe("scenesApi", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches scenes list successfully from /api/v1/scenes", async () => {
    const mockScenes: SceneItem[] = [
      {
        scene_id: "LC09_L2SP_148045_20261023_02_T1",
        acquisition_date: "2026-10-23",
        acquisition_time: "2026-10-23T05:43:21+00:00",
        sensor: "LANDSAT_9",
        path: 148,
        row: 45,
        cloud_cover: 12.0,
        valid_pixel_fraction: 0.88,
        mean_lst_c: 45.2,
        max_lst_c: 52.7,
        status: "PROCESSED",
        cog_path: "data/processed/scenes/2026-10-23.tif",
      },
    ];

    (fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockScenes,
    });

    const result = await fetchScenes();

    expect(fetch).toHaveBeenCalledTimes(1);
    const callUrl = (fetch as any).mock.calls[0][0];
    expect(callUrl).toContain("/scenes");
    expect(result).toHaveLength(1);
    expect(result[0].scene_id).toBe("LC09_L2SP_148045_20261023_02_T1");
    expect(result[0].valid_pixel_fraction).toBe(0.88);
  });

  it("handles empty scenes list gracefully", async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => [],
    });

    const result = await fetchScenes();
    expect(result).toEqual([]);
  });

  it("throws descriptive error when server returns failure status", async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    await expect(fetchScenes()).rejects.toThrow("Failed to fetch scenes catalog: 500");
  });
});
