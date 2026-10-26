import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import HPILegend from "../HPILegend";
import type { LSTStats, SceneProvenanceItem } from "../../../types/heatPriority";

describe("T2 Scene Provenance Reconciliation Requirements", () => {
  it("renders contributing scenes count and provenance metadata in HPILegend", () => {
    const html = renderToStaticMarkup(
      <HPILegend layerMode="lst" season="summer" year={2026} />
    );
    expect(html).toContain("Contributing Scenes:");
    expect(html).toContain("22");
    expect(html).toContain("2026-03-04 to 2026-05-31");
    expect(html).toContain("Landsat 8/9 Collection 2 Level-2 ST_B10 (LST)");
  });

  it("renders winter, monsoon, and post-monsoon provenance scene counts", () => {
    const winterHtml = renderToStaticMarkup(
      <HPILegend layerMode="lst" season="winter" year={2026} />
    );
    expect(winterHtml).toContain("20");

    const monsoonHtml = renderToStaticMarkup(
      <HPILegend layerMode="lst" season="monsoon" year={2026} />
    );
    expect(monsoonHtml).toContain("6");

    const postMonsoonHtml = renderToStaticMarkup(
      <HPILegend layerMode="lst" season="post_monsoon" year={2026} />
    );
    expect(postMonsoonHtml).toContain("14");
    expect(postMonsoonHtml).toContain("2025");
  });

  it("verifies SceneProvenanceItem type structure conforms to manifest schema", () => {
    const testScene: SceneProvenanceItem = {
      collection: "LANDSAT/LC09/C02/T1_L2",
      sensor: "Landsat 9 OLI-2/TIRS-2",
      scene_id: "LC09_L2SP_148045_20260304_20260305_02_T1",
      date: "2026-03-04",
      time_utc: "05:33:19.6464820Z",
      cloud_cover: 0.02,
      path: 148,
      row: 45,
      passes_cloud_80: true,
    };

    const stats: LSTStats = {
      season: "summer",
      year: 2026,
      effective_year: 2026,
      n_cells: 49747,
      n_valid: 49747,
      valid_fraction: 1.0,
      mean_c: 43.1,
      min_c: 24.2,
      max_c: 58.7,
      p90_c: 47.3,
      source: "stage_c_grid_observations",
      is_partial: false,
      n_scenes: 1,
      first_acquisition_date: "2026-03-04",
      last_acquisition_date: "2026-03-04",
      date_window: "2026-03-04 to 2026-03-04",
      scenes: [testScene],
    };

    expect(stats.scenes).toHaveLength(1);
    expect(stats.scenes?.[0].scene_id).toBe("LC09_L2SP_148045_20260304_20260305_02_T1");
    expect(stats.scenes?.[0].path).toBe(148);
    expect(stats.scenes?.[0].row).toBe(45);
    expect(stats.scenes?.[0].cloud_cover).toBeLessThanOrEqual(80.0);
  });
});
