import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import HPILegend from "../HPILegend";
import CellInspector from "../CellInspector";
import AreaRecommendationsPanel from "../AreaRecommendationsPanel";
import ValidationTrust from "../../dashboard/ValidationTrust";
import ScienceGlossaryModal from "../../common/ScienceGlossaryModal";
import type { GridCellScoreItem } from "../../../types/heatPriority";
import type { SceneItem } from "../../../services/scenesApi";

describe("T1 UI Labelling & Provenance Requirements", () => {
  const mockScene: SceneItem = {
    scene_id: "LC09_L2SP_148045_20260415_02_T1",
    acquisition_date: "2026-04-15",
    acquisition_time: "2026-04-15T05:42:10Z",
    acquisition_time_ist: "11:12:10 IST",
    sensor: "Landsat 9 TIRS-2",
    path: 148,
    row: 45,
    cloud_cover: 1.2,
    valid_pixel_fraction: 0.985,
    mean_lst_c: 44.2,
    max_lst_c: 55.8,
    status: "PROCESSED",
    cog_path: null,
  };

  const mockCell: GridCellScoreItem = {
    pixel_id: "1234",
    row_idx: 10,
    col_idx: 20,
    latitude: 21.1700,
    longitude: 72.8300,
    nearest_osm_place_name: "Adajan",
    nearest_osm_distance_m: 50,
    heat_priority_score: 75.5,
    thermal_severity_component: 0.8,
    persistence_component: 0.9,
    vegetation_deficit_component: 0.5,
    built_density_component: 0.6,
    confidence_index: 0.92,
    confidence_tier: "HIGH",
    persistence_tier: "chronic",
    is_chronic_hotspot: true,
    hotspot_frequency: 0.95,
    eligibility_status: "ELIGIBLE",
    observed_lst_c: 44.5,
    optical_imputation_flag: null,
  };

  it("T1(b) renders complete provenance strip in HPILegend", () => {
    const html = renderToStaticMarkup(
      <HPILegend layerMode="lst" season="summer" year={2026} />
    );
    expect(html).toContain("Provenance Strip");
    expect(html).toContain("Observed seasonal composite");
    expect(html).toContain("Landsat 8/9 Collection 2 Level-2 ST_B10 (LST)");
    expect(html).toContain("2026-03-04 to 2026-05-31");
    expect(html).toContain("22");
    expect(html).toContain("49,747 of 49,747");
    expect(html).toContain("pixel-wise seasonal median (median)");
  });

  it("T1(c) renders accurate legends per active layer with missing data swatches", () => {
    // LST: fixed 20-60 C scale and 'no valid observation' swatch
    const lstHtml = renderToStaticMarkup(
      <HPILegend layerMode="lst" season="summer" year={2026} />
    );
    expect(lstHtml).toContain("20°C");
    expect(lstHtml).toContain("30°C");
    expect(lstHtml).toContain("40°C");
    expect(lstHtml).toContain("50°C");
    expect(lstHtml).toContain("60°C");
    expect(lstHtml).toContain("no valid observation");
    expect(lstHtml).toContain("Observed (Landsat L2 ST)");

    // HPI: 0-100 with class thresholds, chronic symbol outline, and no valid observation
    const hpiHtml = renderToStaticMarkup(
      <HPILegend layerMode="hpi" season="summer" year={2026} />
    );
    expect(hpiHtml).toContain("&lt;15 (Low)");
    expect(hpiHtml).toContain("15–30 (Low-Mod)");
    expect(hpiHtml).toContain("30–45 (Mod)");
    expect(hpiHtml).toContain("45–60 (Mod-High)");
    expect(hpiHtml).toContain("60–75 (High)");
    expect(hpiHtml).toContain("≥75 (Extreme)");
    expect(hpiHtml).toContain("◎");
    expect(hpiHtml).toContain("Chronic Hotspot");
    expect(hpiHtml).toContain("no valid observation");

    // Quality tier: symbols + text, not colour alone
    const qualityHtml = renderToStaticMarkup(
      <HPILegend layerMode="confidence" season="summer" year={2026} />
    );
    expect(qualityHtml).toContain("HIGH (C_i ≥ 0.85)");
    expect(qualityHtml).toContain("MODERATE (0.70 ≤ C_i &lt; 0.85)");
    expect(qualityHtml).toContain("LOW (0.50 ≤ C_i &lt; 0.70)");
    expect(qualityHtml).toContain("INSUFFICIENT (C_i &lt; 0.50)");
    expect(qualityHtml).toContain("no valid observation");
  });

  it("T1(d) shows active season/year banner and HPI baseline notice", () => {
    const hpiHtml = renderToStaticMarkup(
      <HPILegend layerMode="hpi" season="summer" year={2026} />
    );
    expect(hpiHtml).toContain("Active Season &amp; Year");
    expect(hpiHtml).toContain("Summer 2026");
    expect(hpiHtml).toContain("HPI is a fixed Summer 2026 baseline and does not change with the season selector");
  });

  it("T1(e) renders resolution note in HPILegend and ScienceGlossaryModal", () => {
    const note = "100 m is the analysis/reporting grid. Landsat TIRS native thermal sampling is about 100 m (distributed at 30 m); 30 m optical indices are aggregated to the grid. Cells are not building- or street-level measurements.";
    
    const legendHtml = renderToStaticMarkup(
      <HPILegend layerMode="lst" season="summer" year={2026} />
    );
    expect(legendHtml).toContain(note);

    const glossaryHtml = renderToStaticMarkup(
      <ScienceGlossaryModal isOpen={true} onClose={() => {}} />
    );
    expect(glossaryHtml).toContain(note);
  });

  it("T1(f) labels Observed vs Model estimate vs Assumption-based estimate", () => {
    const panelHtml = renderToStaticMarkup(
      <AreaRecommendationsPanel
        areaId="area_1"
        areaName="Test Ward"
        geometry={{ type: "Polygon", coordinates: [] }}
      />
    );
    expect(panelHtml).toContain("ASSUMPTION-BASED ESTIMATE");

    const trustHtml = renderToStaticMarkup(<ValidationTrust />);
    expect(trustHtml).toContain("MODEL ESTIMATE");
  });

  it("T1(g) renders Latest Scene panel with UTC/IST time and SMC valid pixel %", () => {
    const sceneHtml = renderToStaticMarkup(
      <HPILegend layerMode="latest_scene" season="summer" year={2026} selectedScene={mockScene} />
    );
    expect(sceneHtml).toContain("LC09_L2SP_148045_20260415_02_T1");
    expect(sceneHtml).toContain("Landsat 9 TIRS-2");
    expect(sceneHtml).toContain("2026-04-15T05:42:10Z");
    expect(sceneHtml).toContain("11:12:10 IST");
    expect(sceneHtml).toContain("1.2%");
    expect(sceneHtml).toContain("Valid Pixels inside SMC:");
    expect(sceneHtml).toContain("98.5%");
  });

  it("T1(a) CellInspector displays observational quality heuristic wording", () => {
    const cellHtml = renderToStaticMarkup(
      <CellInspector cell={mockCell} onClose={() => {}} />
    );
    expect(cellHtml).toContain("Observational Quality");
    expect(cellHtml).toContain("Heuristic C_i");
    expect(cellHtml).toContain("Heuristic quality index from QA/observation support, not a probability of correctness");
  });
});
