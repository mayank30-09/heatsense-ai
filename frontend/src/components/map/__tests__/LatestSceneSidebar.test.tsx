import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import LatestSceneSidebar from "../LatestSceneSidebar";
import type { PipelineStatus, SceneItem } from "../../../services/scenesApi";

describe("LatestSceneSidebar Component", () => {
  const mockScenes: SceneItem[] = [
    {
      scene_id: "LC09_L2SP_148045_20261014_02_T1",
      acquisition_date: "2026-10-14",
      acquisition_time: "2026-10-14T05:42:10Z",
      acquisition_time_ist: "11:12:10 AM IST, 14 Oct 2026",
      sensor: "Landsat 9",
      path: 148,
      row: 45,
      cloud_cover: 0.8,
      valid_pixel_fraction: 0.942,
      mean_lst_c: 41.5,
      max_lst_c: 54.2,
      status: "PROCESSED",
      rejection_reason: null,
      provisional_hotspots_count: 14,
      cog_path: null,
    },
    {
      scene_id: "LC09_L2SP_148045_20260928_02_T1",
      acquisition_date: "2026-09-28",
      acquisition_time: "2026-09-28T05:42:10Z",
      acquisition_time_ist: "11:12:10 AM IST, 28 Sep 2026",
      sensor: "Landsat 9",
      path: 148,
      row: 45,
      cloud_cover: 88.5,
      valid_pixel_fraction: 0.115,
      mean_lst_c: null,
      max_lst_c: null,
      status: "REJECTED_CLOUDY",
      rejection_reason: "Valid pixel fraction 11.5% below 40% threshold (cloud contamination: 88.5%)",
      provisional_hotspots_count: null,
      cog_path: null,
    },
  ];

  const mockPipelineStatus: PipelineStatus = {
    pipeline_status: "OPERATIONAL",
    last_checked: "2026-10-27T08:30:00Z",
    last_checked_ist: "02:00 PM IST, 27 Oct 2026",
    last_checked_relative: "1 hour ago",
    last_ingested_date: "2026-10-14",
    next_expected_overpass: "2026-10-30",
    next_expected_sensor: "Landsat 9",
    next_expected_overpass_label: "~Oct 30 (Landsat 9)",
    processed_count: 2,
    rejected_count: 1,
    recent_overpasses: [
      {
        date: "2026-10-22",
        sensor: "Landsat 8",
        status: "OVERDUE",
        label: "Oct 22 (Landsat 8): no scene found / overdue in GEE (> 3 days)",
        days_ago: 5,
      },
      {
        date: "2026-10-14",
        sensor: "Landsat 9",
        status: "PROCESSED",
        label: "Oct 14 (Landsat 9): processed (94% clear)",
        days_ago: 13,
      },
    ],
  };

  it("renders the 5 main blocks in strict top-to-bottom order without duplication", () => {
    const html = renderToStaticMarkup(
      <LatestSceneSidebar
        scenes={mockScenes}
        selectedSceneId="LC09_L2SP_148045_20261014_02_T1"
        onSelectScene={vi.fn()}
        showRasterTile={true}
        onToggleRasterTile={vi.fn()}
        pipelineStatus={mockPipelineStatus}
      />
    );

    // Block 1: Pipeline status
    const posBlock1 = html.indexOf('aria-label="Pipeline Status"');
    expect(posBlock1).toBeGreaterThan(-1);
    expect(html).toContain("Pipeline: OPERATIONAL");
    expect(html).toContain("02:00 PM IST, 27 Oct 2026");
    expect(html).toContain("1 hour ago");
    expect(html).toContain("~Oct 30 (Landsat 9)");

    // Block 2: Scene selector + badges
    const posBlock2 = html.indexOf('aria-label="Scene Selector"');
    expect(posBlock2).toBeGreaterThan(posBlock1);
    expect(html).toContain("Thermal Raster");

    // Block 3: Single-scene scientific banner (rendered once)
    const posBlock3 = html.indexOf('aria-label="Scientific Invariant Notice"');
    expect(posBlock3).toBeGreaterThan(posBlock2);

    // Verify banner text is not repeated
    const firstBanner = html.indexOf("Instantaneous Single-Scene Overpass");
    const lastBanner = html.lastIndexOf("Instantaneous Single-Scene Overpass");
    expect(firstBanner).toBe(lastBanner);

    // Block 4: Scene metadata & provenance
    const posBlock4 = html.indexOf('aria-label="Scene Metadata &amp; Provenance"');
    expect(posBlock4).toBeGreaterThan(posBlock3);
    expect(html).toContain("LC09_L2SP_148045_20261014_02_T1");
    expect(html).toContain("Copy ID");
    expect(html).toContain("Valid SMC Grid Cells:");

    // Block 5: Color ramp legend
    const posBlock5 = html.indexOf('aria-label="Thermal Color Ramp Legend"');
    expect(posBlock5).toBeGreaterThan(posBlock4);
    expect(html).toContain("20°C");
    expect(html).toContain("60°C");
  });

  it("lists processed AND rejected scenes with clear rejection reasons in the selector", () => {
    const html = renderToStaticMarkup(
      <LatestSceneSidebar
        scenes={mockScenes}
        selectedSceneId="LC09_L2SP_148045_20261014_02_T1"
        onSelectScene={vi.fn()}
        showRasterTile={true}
        onToggleRasterTile={vi.fn()}
        pipelineStatus={mockPipelineStatus}
      />
    );

    expect(html).toContain("2026-10-14 (Landsat 9) — 94% clear over SMC");
    expect(html).toContain("REJECTED: 12% clear - Valid pixel fraction 11.5% below 40% threshold");
  });

  it("displays proper loading state when fetching scenes catalog", () => {
    const html = renderToStaticMarkup(
      <LatestSceneSidebar
        scenes={[]}
        onSelectScene={vi.fn()}
        showRasterTile={false}
        onToggleRasterTile={vi.fn()}
        scenesLoading={true}
      />
    );

    expect(html).toContain("Fetching Near-Real-Time Landsat catalog...");
  });

  it("displays proper error state when scene catalog fails to load", () => {
    const html = renderToStaticMarkup(
      <LatestSceneSidebar
        scenes={[]}
        onSelectScene={vi.fn()}
        showRasterTile={false}
        onToggleRasterTile={vi.fn()}
        scenesError="Network connection lost to scenes endpoint"
      />
    );

    expect(html).toContain("Failed to load scenes catalog");
    expect(html).toContain("Network connection lost to scenes endpoint");
  });

  it("displays empty state when no scenes have been processed yet", () => {
    const html = renderToStaticMarkup(
      <LatestSceneSidebar
        scenes={[]}
        onSelectScene={vi.fn()}
        showRasterTile={false}
        onToggleRasterTile={vi.fn()}
        scenesLoading={false}
        scenesError={null}
      />
    );

    expect(html).toContain("No scenes processed yet");
  });

  it("shows explicit status for missed or overdue overpasses", () => {
    const html = renderToStaticMarkup(
      <LatestSceneSidebar
        scenes={mockScenes}
        selectedSceneId="LC09_L2SP_148045_20261014_02_T1"
        onSelectScene={vi.fn()}
        showRasterTile={true}
        onToggleRasterTile={vi.fn()}
        pipelineStatus={mockPipelineStatus}
      />
    );

    expect(html).toContain("Oct 22 (Landsat 8): no scene found / overdue in GEE (&gt; 3 days)");
  });


  it("renders Check Now button and reflects checking state when provided", () => {
    const htmlNormal = renderToStaticMarkup(
      <LatestSceneSidebar
        scenes={mockScenes}
        selectedSceneId="LC09_L2SP_148045_20261014_02_T1"
        onSelectScene={vi.fn()}
        showRasterTile={true}
        onToggleRasterTile={vi.fn()}
        pipelineStatus={mockPipelineStatus}
        onTriggerCheck={vi.fn()}
        isChecking={false}
      />
    );
    expect(htmlNormal).toContain("Check Now");
    expect(htmlNormal).toContain('aria-label="Check upstream Landsat overpass now"');

    const htmlChecking = renderToStaticMarkup(
      <LatestSceneSidebar
        scenes={mockScenes}
        selectedSceneId="LC09_L2SP_148045_20261014_02_T1"
        onSelectScene={vi.fn()}
        showRasterTile={true}
        onToggleRasterTile={vi.fn()}
        pipelineStatus={mockPipelineStatus}
        onTriggerCheck={vi.fn()}
        isChecking={true}
      />
    );
    expect(htmlChecking).toContain("Checking...");
  });
});
