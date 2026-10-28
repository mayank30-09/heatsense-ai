import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import LayerControls from "../LayerControls";
import HPILegend from "../HPILegend";

describe("LayerControls Navigation & Mode Isolation", () => {
  it("renders only season selector and thermal raster toggle in Area Analysis mode", () => {
    const html = renderToStaticMarkup(
      <LayerControls
        isAreaAnalysis={true}
        layerMode="lst"
        onLayerModeChange={() => {}}
        showRasterTile={true}
        onToggleRasterTile={() => {}}
        minHpiFilter={undefined}
        onToggleMinHpi={() => {}}
        season="summer"
        onSeasonChange={() => {}}
      />
    );
    expect(html).toContain("Thermal Raster");
    expect(html).toContain("☀️ Summer");
    expect(html).toContain("❄️ Winter");
    expect(html).toContain("🍂 Post-Monsoon");
    expect(html).toContain("🌧️ Monsoon");

    // Mode tablist and minHpi filter must be omitted in Area Analysis
    expect(html).not.toContain("Heat Priority Index (derived, 0-100)");
    expect(html).not.toContain("Observed LST (Landsat Level-2 ST)");
    expect(html).not.toContain("Confidence / Quality");
    expect(html).not.toContain("Chronic (223)");
    expect(html).not.toContain("Filter: HPI ≥ 50");
    // Draw polygon button is omitted
    expect(html).not.toContain("Draw Polygon");
  });

  it("does not render Draw Polygon toggle in Heat Map mode when onSelectTool is omitted", () => {
    const html = renderToStaticMarkup(
      <LayerControls
        isAreaAnalysis={false}
        layerMode="hpi"
        onLayerModeChange={() => {}}
        showRasterTile={true}
        onToggleRasterTile={() => {}}
        minHpiFilter={undefined}
        onToggleMinHpi={() => {}}
        season="summer"
        onSeasonChange={() => {}}
      />
    );
    expect(html).toContain("Heat Priority Index (derived, 0-100)");
    expect(html).toContain("Observed LST (Landsat Level-2 ST)");
    expect(html).toContain("Thermal Raster");
    expect(html).toContain("Filter: HPI ≥ 50");
    expect(html).not.toContain("Draw Polygon");
    expect(html).not.toContain("Grid Cells");
  });
});

describe("HPILegend Responsive & Collapsible Structure", () => {
  it("renders collapse/expand toggle button and max-height scrolling wrapper", () => {
    const html = renderToStaticMarkup(
      <HPILegend layerMode="hpi" season="summer" year={2026} />
    );
    expect(html).toContain("Collapse ▼");
    expect(html).toContain("Heat Priority Index");
    expect(html).toContain("max-h-[38vh]");
    expect(html).toContain("max-w-[300px]");
  });

  it("renders correct title for observed LST mode", () => {
    const html = renderToStaticMarkup(
      <HPILegend layerMode="lst" season="winter" year={2026} />
    );
    expect(html).toContain("Observed LST (Landsat Level-2 ST) (Winter 2026)");
  });
});
