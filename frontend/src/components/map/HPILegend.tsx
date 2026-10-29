import { useEffect, useState } from "react";
import type { ActiveLayerMode, LSTStats, SeasonName } from "../../types/heatPriority";
import { fetchLSTStats } from "../../services/heatPriorityApi";
import type { SceneItem } from "../../services/scenesApi";

interface HPILegendProps {
  layerMode: ActiveLayerMode;
  season?: SeasonName;
  year?: number;
  chronicCount?: number;
  totalCells?: number;
  selectedScene?: SceneItem | null;
  recentDayThreshold?: number;
  hasRecentScene?: boolean;
}

interface SeasonalStats {
  label: string;
  year: number;
  meanLst: number;
  minLst: number;
  maxLst: number;
  p90Lst: number;
  sceneCount?: number;
  dateWindow?: string;
  isFlagged?: boolean;
  flagMessage?: string;
}

const SEASON_FALLBACKS: Record<SeasonName, SeasonalStats> = {
  summer: {
    label: "Summer",
    year: 2026,
    meanLst: 43.8,
    minLst: 29.6,
    maxLst: 58.6,
    p90Lst: 47.4,
    sceneCount: 22,
    dateWindow: "2026-03-04 to 2026-05-31",
  },
  winter: {
    label: "Winter",
    year: 2026,
    meanLst: 31.3,
    minLst: 23.7,
    maxLst: 44.4,
    p90Lst: 33.5,
    sceneCount: 20,
    dateWindow: "2025-12-06 to 2026-02-24",
  },
  post_monsoon: {
    label: "Post-Monsoon",
    year: 2025,
    meanLst: 33.5,
    minLst: 26.3,
    maxLst: 46.5,
    p90Lst: 35.9,
    sceneCount: 14,
    dateWindow: "2025-10-03 to 2025-11-28",
    isFlagged: true,
    flagMessage: "Year 2026 incomplete; validated 2025 observation data is shown.",
  },
  monsoon: {
    label: "Monsoon",
    year: 2026,
    meanLst: 43.0,
    minLst: 27.1,
    maxLst: 59.0,
    p90Lst: 47.2,
    sceneCount: 6,
    dateWindow: "2026-06-08 to 2026-09-28",
    isFlagged: true,
    flagMessage: "Partial coverage due to persistent monsoon cloud masking.",
  },
};

export default function HPILegend({
  layerMode,
  season = "summer",
  year,
  chronicCount = 223,
  totalCells = 49747,
  selectedScene = null,
  recentDayThreshold = 30,
  hasRecentScene = true,
}: HPILegendProps) {
  const fallback = SEASON_FALLBACKS[season] || SEASON_FALLBACKS.summer;
  const [stats, setStats] = useState<LSTStats | null>(null);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    fetchLSTStats(season, year, controller.signal)
      .then((data) => {
        if (mounted) setStats(data);
      })
      .catch(() => {
        // Fallback remains active on network error
      });

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [season, year]);

  const displayYear = stats?.effective_year ?? year ?? fallback.year;
  const meanLst = stats?.mean_c ?? fallback.meanLst;
  const minLst = stats?.min_c ?? fallback.minLst;
  const maxLst = stats?.max_c ?? fallback.maxLst;

  const isPostMonsoonNotice = season === "post_monsoon";
  const isMonsoonPartial = season === "monsoon" || (stats?.is_partial ?? false);

  const [isCollapsed, setIsCollapsed] = useState(() => typeof window !== "undefined" && window.innerWidth < 1024);
  const [showSceneList, setShowSceneList] = useState(false);

  const getLegendTitle = () => {
    switch (layerMode) {
      case "hpi":
        return "Heat Priority Index (derived, 0-100)";
      case "lst":
        return `Observed LST (Landsat Level-2 ST) (${fallback.label} ${displayYear})`;
      case "confidence":
        return "Confidence & Quality";
      case "chronic":
        return "Chronic Hotspots (223)";
      case "latest_scene":
        return `Latest Scene (${selectedScene?.acquisition_date ?? "NRT"})`;
      default:
        return "Map Legend";
    }
  };

  return (
    <div className="pointer-events-none absolute top-3 left-[56px] z-[900] w-[calc(100vw-76px)] max-w-[300px] max-h-[calc(100%-24px)] flex flex-col">
      <div className="pointer-events-auto rounded-xl border border-slate-200/90 bg-white/95 p-3 shadow-md backdrop-blur">
        {/* Header with Collapse/Expand Toggle */}
        <div className="flex items-center justify-between pb-1.5 border-b border-slate-200/80 mb-2">
          <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5 truncate">
            <span>🗺️</span>
            <span className="truncate">{getLegendTitle()}</span>
          </span>
          <button
            type="button"
            onClick={() => setIsCollapsed((prev) => !prev)}
            aria-expanded={!isCollapsed}
            aria-label={isCollapsed ? "Expand map legend" : "Collapse map legend"}
            className="text-[10px] font-semibold text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-2 py-0.5 rounded cursor-pointer transition-colors shrink-0"
          >
            {isCollapsed ? "Expand ▲" : "Collapse ▼"}
          </button>
        </div>

        {!isCollapsed && (
          <div className="max-h-[38vh] sm:max-h-[58vh] md:max-h-[66vh] overflow-y-auto pr-1 space-y-3 pb-2 scrollbar-thin">
            {/* Visible Season / Year or Scene LST Statistics Card */}
        {layerMode === "latest_scene" ? (
          <div className="mb-3 rounded-md border border-indigo-200 bg-indigo-50/70 p-2.5 shadow-sm">
            {/* Clear banner */}
            <div className="mb-2 rounded bg-amber-100/90 border border-amber-300 px-2 py-1 text-[10px] font-bold text-amber-900 flex items-center gap-1.5">
              <span>⚠️</span>
              <span>single scene, not a seasonal composite, not used in HPI</span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-800">
                Satellite Overpass
              </span>
              <span className="rounded bg-indigo-200/80 px-2 py-0.5 font-mono text-[11px] font-bold text-indigo-900">
                {selectedScene ? selectedScene.acquisition_date : "No Scene"}
              </span>
            </div>

            {selectedScene ? (
              <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
                <div className="rounded bg-white p-1.5 border border-indigo-100 shadow-2xs">
                  <div className="text-[9px] uppercase tracking-wide text-slate-400">Mean LST</div>
                  <div className="text-sm font-bold text-indigo-700">
                    {selectedScene.mean_lst_c !== null ? `${selectedScene.mean_lst_c.toFixed(1)}°C` : "N/A"}
                  </div>
                </div>
                <div className="rounded bg-white p-1.5 border border-indigo-100 shadow-2xs">
                  <div className="text-[9px] uppercase tracking-wide text-slate-400">Max LST</div>
                  <div className="text-sm font-bold text-red-700">
                    {selectedScene.max_lst_c !== null ? `${selectedScene.max_lst_c.toFixed(1)}°C` : "N/A"}
                  </div>
                </div>
              </div>
            ) : null}

            {/* T1(b) Provenance Strip for Latest Scene */}
            <div className="mt-2 rounded bg-white p-2 border border-slate-200/90 text-[10px] space-y-1 text-slate-700">
              <div className="flex justify-between items-center font-bold text-slate-800 border-b border-slate-100 pb-1">
                <span>Provenance Strip</span>
                <span className="font-mono text-[9px] text-indigo-700">Single scene</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Source:</span>
                <span className="font-medium text-right text-slate-800">
                  {selectedScene ? selectedScene.sensor : "Landsat 8/9 Collection 2 Level-2 ST_B10 (LST)"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Composite Window:</span>
                <span className="font-mono text-[9px] text-slate-800">
                  {selectedScene?.acquisition_date ?? "Instantaneous Overpass"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Contributing Scenes:</span>
                <span className="font-semibold text-slate-800">1</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Valid Cells:</span>
                <span className="font-semibold text-slate-800">
                  {selectedScene
                    ? `${Math.round(selectedScene.valid_pixel_fraction * totalCells).toLocaleString()} of ${totalCells.toLocaleString()}`
                    : `0 of ${totalCells.toLocaleString()}`}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Compositing Statistic:</span>
                <span className="font-medium text-slate-800 text-right">Instantaneous clear-pixel</span>
              </div>
            </div>

            {!hasRecentScene && (
              <div className="mt-2 flex items-center gap-1.5 rounded border border-amber-300 bg-amber-50 px-2 py-1 text-[10px] font-semibold text-amber-900">
                <span>⚠️</span>
                <span>No clear scene in the last {recentDayThreshold} days.</span>
              </div>
            )}
          </div>
        ) : (
          <div className="mb-3 rounded-md border border-slate-200 bg-slate-50 p-2.5 shadow-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-700">
                City-wide layer statistics
              </span>
              <span className="rounded bg-indigo-100 px-2 py-0.5 font-mono text-[11px] font-bold text-indigo-900 border border-indigo-200">
                {fallback.label} {displayYear}
              </span>
            </div>
            <div className="text-[9.5px] text-slate-500">
              Active Season & Year: {fallback.label} {displayYear} (city-wide SMC extent)
            </div>

            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div className="rounded bg-white p-1.5 border border-slate-100 shadow-2xs">
                <div className="text-[9px] uppercase tracking-wide text-slate-500">
                  City-wide Mean LST ({fallback.label} {displayYear})
                </div>
                <div className="text-sm font-bold text-blue-700">
                  {meanLst.toFixed(1)}°C
                </div>
              </div>
              <div className="rounded bg-white p-1.5 border border-slate-100 shadow-2xs">
                <div className="text-[9px] uppercase tracking-wide text-slate-500">
                  City-wide Max LST ({fallback.label} {displayYear})
                </div>
                <div className="text-sm font-bold text-red-700">
                  {maxLst.toFixed(1)}°C
                </div>
              </div>
            </div>

            {/* T1(b) Provenance Strip */}
            <div className="rounded bg-white p-2 border border-slate-200/90 text-[10px] space-y-1 text-slate-700">
              <div className="flex justify-between items-center font-bold text-slate-800 border-b border-slate-100 pb-1">
                <span>Provenance Strip</span>
                <span className="font-mono text-[9px] text-indigo-700">
                  {layerMode === "lst"
                    ? (stats?.layer_type ?? "Observed seasonal composite")
                    : layerMode === "hpi"
                    ? "HPI baseline"
                    : "Stage C QC / Analysis"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Source:</span>
                <span className="font-medium text-right text-slate-800">
                  {stats?.sensor_source ?? "Landsat 8/9 Collection 2 Level-2 ST_B10 (LST)"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Composite Window:</span>
                <span className="font-mono text-[9px] text-slate-800">
                  {stats?.date_window ?? fallback.dateWindow}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500">Contributing Scenes:</span>
                <div className="flex items-center gap-1.5">
                  <span className="font-semibold text-slate-800">
                    {stats?.n_scenes ?? fallback.sceneCount}
                  </span>
                  {stats?.scenes && stats.scenes.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setShowSceneList((prev) => !prev)}
                      aria-expanded={showSceneList}
                      aria-label="Toggle contributing scenes list"
                      className="text-[9px] text-indigo-600 hover:text-indigo-800 underline font-medium cursor-pointer"
                    >
                      {showSceneList ? "Hide list" : "View scene list"}
                    </button>
                  )}
                </div>
              </div>
              {showSceneList && stats?.scenes && stats.scenes.length > 0 && (
                <div className="mt-1 p-2 rounded border border-indigo-200 bg-indigo-50/70 text-[9px] space-y-1.5 max-h-40 overflow-y-auto">
                  <div className="flex justify-between items-center font-bold text-slate-700 pb-0.5 border-b border-indigo-100">
                    <span>Contributing Scenes ({stats.scenes.length})</span>
                    <button
                      type="button"
                      onClick={() => setShowSceneList(false)}
                      className="text-slate-400 hover:text-slate-700 font-bold px-1"
                      aria-label="Close scene list"
                    >
                      ×
                    </button>
                  </div>
                  <div className="space-y-1 divide-y divide-indigo-100/60 font-mono">
                    {stats.scenes.map((sc) => (
                      <div key={sc.scene_id} className="pt-1 first:pt-0">
                        <div className="font-semibold text-indigo-950 truncate" title={sc.scene_id}>
                          {sc.scene_id}
                        </div>
                        <div className="flex justify-between text-slate-500 text-[8px] font-sans">
                          <span>{sc.date} • {sc.sensor.replace("Landsat ", "L")}</span>
                          <span>WRS {sc.path}/{sc.row} • Cloud: {typeof sc.cloud_cover === 'number' ? sc.cloud_cover.toFixed(1) : sc.cloud_cover}%</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-500">Valid Cells:</span>
                <span className="font-semibold text-slate-800">
                  {stats?.n_valid
                    ? `${stats.n_valid.toLocaleString()} of ${totalCells.toLocaleString()}`
                    : `${totalCells.toLocaleString()} of ${totalCells.toLocaleString()}`}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Compositing Statistic:</span>
                <span className="font-medium text-slate-800 text-right">
                  {stats?.compositing_statistic ?? "pixel-wise seasonal median (median)"}
                </span>
              </div>
            </div>

            {isPostMonsoonNotice && (
              <div className="flex items-center gap-1.5 rounded border border-blue-200 bg-blue-50 px-2 py-1 text-[10px] font-medium text-blue-800">
                <span>ℹ️</span>
                <span>Year 2026 incomplete; validated 2025 observation data is shown.</span>
              </div>
            )}

            {isMonsoonPartial && (
              <div className="flex items-center gap-1.5 rounded border border-amber-300 bg-amber-50 px-2 py-1 text-[10px] font-semibold text-amber-900">
                <span>⚠️</span>
                <span>
                  {stats?.n_valid
                    ? `Partial coverage: cloud masked (${stats.n_valid.toLocaleString()} of ${totalCells.toLocaleString()} valid cells, ${(stats.valid_fraction ? stats.valid_fraction * 100 : (stats.n_valid / totalCells) * 100).toFixed(1)}%)`
                    : "Partial coverage due to persistent monsoon cloud masking."}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Layer Mode: HPI Priority */}
        {layerMode === "hpi" && (
          <div>
            {/* T1(d) Prominent HPI Baseline Notice */}
            <div className="mb-2.5 rounded bg-amber-50 p-2 border border-amber-200 text-[10px] font-semibold text-amber-900 leading-snug">
              <span>ℹ️ <strong>HPI Baseline:</strong> HPI is a fixed Summer 2026 baseline and does not change with the season selector.</span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                Heat Priority Index (derived, 0-100)
              </span>
              <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-800">
                0 – 100
              </span>
            </div>

            <div
              className="mt-2 h-3.5 w-full rounded"
              style={{
                background:
                  "linear-gradient(to right, #22c55e, #84cc16, #eab308, #f59e0b, #ea580c, #dc2626)",
              }}
            />

            {/* T1(c) Class thresholds defined in code (hpiColorScales.ts) */}
            <div className="mt-1 grid grid-cols-3 gap-1 text-[9.5px] font-medium text-slate-600">
              <span>&lt;15 (Low)</span>
              <span>15–30 (Low-Mod)</span>
              <span>30–45 (Mod)</span>
              <span>45–60 (Mod-High)</span>
              <span>60–75 (High)</span>
              <span>≥75 (Extreme)</span>
            </div>

            <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-2 text-[11px]">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-slate-600">
                  <span className="inline-flex items-center justify-center h-3.5 w-3.5 rounded-full border-2 border-red-600 bg-red-800 shadow-xs text-center text-[9px] leading-[11px] text-white font-bold">
                    ◎
                  </span>
                  Chronic Hotspot (symbol + outline)
                </span>
                <span className="font-bold text-red-700">{chronicCount} cells</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-slate-600">
                  <span
                    className="inline-block h-3.5 w-3.5 rounded-xs border border-slate-400 bg-slate-300"
                    style={{
                      backgroundImage:
                        "repeating-linear-gradient(45deg, #cbd5e1 0, #cbd5e1 2px, transparent 0, transparent 4px)",
                    }}
                  />
                  <span>NoData / cloud-masked (no valid observation)</span>
                </span>
                <span className="font-medium text-slate-500">Transparent / Hatched</span>
              </div>
            </div>
          </div>
        )}

        {/* Layer Mode: Observed LST */}
        {layerMode === "lst" && (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                Observed LST (Landsat Level-2 ST)
              </span>
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
                Observed (Landsat L2 ST)
              </span>
            </div>

            {/* T1(c) Fixed 20°C - 60°C standard thermal gradient */}
            <div
              className="mt-2 h-3.5 w-full rounded"
              style={{
                background:
                  "linear-gradient(to right, rgb(59,130,246), rgb(16,185,129), rgb(245,158,11), rgb(234,88,12), rgb(127,29,29))",
              }}
            />

            <div className="mt-1 flex justify-between px-1 text-[10px] font-semibold text-slate-600">
              <span>20°C</span>
              <span>30°C</span>
              <span>40°C</span>
              <span>50°C</span>
              <span>60°C</span>
            </div>

            <div className="mt-1 text-[9.5px] text-slate-500 text-center">
              Fixed 20–60°C rendering range with out-of-range clipping (&lt;20°C clipped to 20°C, &gt;60°C clipped to 60°C).
            </div>

            <div className="mt-2.5 space-y-1 border-t border-slate-100 pt-2 text-[10px] text-slate-600">
              <div className="flex justify-between">
                <span>Observed Range:</span>
                <span className="font-medium text-slate-800">
                  {minLst.toFixed(1)}°C – {maxLst.toFixed(1)}°C
                </span>
              </div>
              <div className="flex justify-between">
                <span>Study Area Extent:</span>
                <span className="font-medium text-slate-800">{totalCells.toLocaleString()} cells (100m)</span>
              </div>
              <div className="flex items-center justify-between pt-1 border-t border-slate-100">
                <span className="flex items-center gap-1.5 text-slate-600">
                  <span
                    className="inline-block h-3.5 w-3.5 rounded-xs border border-slate-400 bg-slate-300"
                    style={{
                      backgroundImage:
                        "repeating-linear-gradient(45deg, #cbd5e1 0, #cbd5e1 2px, transparent 0, transparent 4px)",
                    }}
                  />
                  <span>NoData / cloud-masked (no valid observation)</span>
                </span>
                <span className="font-medium text-slate-500">Transparent / Hatched</span>
              </div>
            </div>

            <div className="mt-2 rounded bg-amber-50/90 p-2 border border-amber-200/70 text-[9.5px] leading-snug text-amber-900">
              <span className="font-bold">Physical Distinction:</span> Land Surface Temperature (LST) is surface temperature (skin), not air temperature. Measured by Landsat TIRS at satellite overpass (~10:30 local solar time, ~11:00 IST), distinct from ambient 2 m air temperature (T<sub>air</sub>).
            </div>
          </div>
        )}

        {/* Layer Mode: Confidence & Quality */}
        {layerMode === "confidence" && (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                Observational Quality Tier
              </span>
              <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800">
                Stage C QC
              </span>
            </div>

            {/* T1(c) Quality tiers with symbols + text, not colour alone */}
            <div className="mt-2.5 space-y-1.5 text-[11px]">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center justify-center h-4 w-4 rounded-full bg-emerald-600 text-white text-[10px] font-bold">
                  ✓
                </span>
                <span className="font-medium text-slate-800">HIGH (C_i ≥ 0.85)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center justify-center h-4 w-4 rounded-xs bg-blue-600 text-white text-[10px] font-bold">
                  ▲
                </span>
                <span className="font-medium text-slate-800">MODERATE (0.70 ≤ C_i &lt; 0.85)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center justify-center h-4 w-4 rounded-xs bg-amber-600 text-white text-[10px] font-bold">
                  ◆
                </span>
                <span className="font-medium text-slate-800">LOW (0.50 ≤ C_i &lt; 0.70)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center justify-center h-4 w-4 rounded-xs bg-rose-600 text-white text-[10px] font-bold">
                  ✕
                </span>
                <span className="font-medium text-slate-800">INSUFFICIENT (C_i &lt; 0.50)</span>
              </div>
              <div className="flex items-center gap-2 pt-1 border-t border-slate-100">
                <span
                  className="inline-block h-4 w-4 rounded-xs border border-slate-400 bg-slate-300"
                  style={{
                    backgroundImage:
                      "repeating-linear-gradient(45deg, #cbd5e1 0, #cbd5e1 2px, transparent 0, transparent 4px)",
                  }}
                />
                <span className="font-medium text-slate-600">NoData / cloud-masked (no valid observation)</span>
              </div>
            </div>

            <div className="mt-2.5 border-t border-slate-100 pt-2 text-[10px] text-slate-500">
              Optical Imputation: 8-Connected Median, Boundary Mean, or Neutral Climatological Fallback.
            </div>

            <div className="mt-2 text-[10px] text-amber-800 italic bg-amber-50 rounded p-1.5 border border-amber-200">
              Notice: Heuristic quality index from QA/observation support, not a probability of correctness.
            </div>
          </div>
        )}

        {/* Layer Mode: Chronic Hotspots */}
        {layerMode === "chronic" && (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-red-800">
                Chronic Hotspots
              </span>
              <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-800">
                {chronicCount} Hotspots
              </span>
            </div>

            <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-700">
              <span className="inline-flex items-center justify-center h-4 w-4 rounded-full border-2 border-red-600 bg-red-800 text-white text-[10px] font-bold">
                ◎
              </span>
              <span>Persistent extreme heat cells (symbol + outline)</span>
            </div>

            <div className="mt-2 flex items-center gap-2 pt-1 border-t border-slate-100 text-[11px]">
              <span
                className="inline-block h-4 w-4 rounded-xs border border-slate-400 bg-slate-300"
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(45deg, #cbd5e1 0, #cbd5e1 2px, transparent 0, transparent 4px)",
                }}
              />
              <span className="font-medium text-slate-600">NoData / cloud-masked (no valid observation)</span>
            </div>

            <p className="mt-2 text-[10px] leading-tight text-slate-500">
              Criterion: Hotspot recurrence frequency ≥ 50% across valid seasons, ≥ 3 hot seasons, ≥ 2 distinct years.
            </p>
          </div>
        )}

        {/* Layer Mode: Latest Scene */}
        {layerMode === "latest_scene" && (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                Observed LST (Landsat Level-2 ST) - Single Scene
              </span>
              <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-800">
                Observed (Landsat L2 ST)
              </span>
            </div>

            <div
              className="mt-2 h-3.5 w-full rounded"
              style={{
                background:
                  "linear-gradient(to right, rgb(59,130,246), rgb(16,185,129), rgb(245,158,11), rgb(234,88,12), rgb(127,29,29))",
              }}
            />

            <div className="mt-1 flex justify-between px-1 text-[10px] font-medium text-slate-500">
              <span>20°C</span>
              <span>30°C</span>
              <span>40°C</span>
              <span>50°C</span>
              <span>60°C</span>
            </div>

            <div className="mt-1 text-[9.5px] text-slate-500 text-center">
              Fixed 20–60°C rendering range with out-of-range clipping (&lt;20°C clipped to 20°C, &gt;60°C clipped to 60°C).
            </div>

            {/* T1(g) Latest Scene panel */}
            {selectedScene && (
              <div className="mt-2.5 rounded bg-slate-50 p-2 text-[11px] text-slate-700 space-y-1">
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Scene ID:</span>
                  <span className="font-mono text-[9px] truncate max-w-[170px]" title={selectedScene.scene_id}>
                    {selectedScene.scene_id}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Sensor:</span>
                  <span className="font-semibold">{selectedScene.sensor}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Acquisition (UTC):</span>
                  <span className="font-mono text-[9.5px]">{selectedScene.acquisition_time}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Acquisition (IST):</span>
                  <span className="font-mono text-[9.5px]">
                    {selectedScene.acquisition_time_ist ||
                      `${new Date(selectedScene.acquisition_time).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" })} IST`}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Cloud Cover:</span>
                  <span className="font-semibold">
                    {selectedScene.cloud_cover !== null ? `${selectedScene.cloud_cover.toFixed(1)}%` : "N/A"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Valid Pixels inside SMC:</span>
                  <span className="font-semibold text-emerald-700">
                    {(selectedScene.valid_pixel_fraction * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Units:</span>
                  <span className="font-semibold">°C (Celsius)</span>
                </div>
              </div>
            )}

            <div className="mt-2 flex items-center gap-2 pt-1 border-t border-slate-100 text-[11px]">
              <span
                className="inline-block h-4 w-4 rounded-xs border border-slate-400 bg-slate-300"
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(45deg, #cbd5e1 0, #cbd5e1 2px, transparent 0, transparent 4px)",
                }}
              />
              <span className="font-medium text-slate-600">NoData / cloud-masked (no valid observation)</span>
            </div>

            <div className="mt-2.5 border-t border-slate-100 pt-2 text-[10px] font-medium text-slate-700 leading-4">
              Land Surface Temperature (LST) is surface temperature (skin), not air temperature. Single overpass (~10:30 local solar time, about 11:00 IST), not a seasonal composite.
            </div>

            <div className="mt-1 text-[9px] font-medium text-amber-700 bg-amber-50 rounded p-1 border border-amber-200">
              ⚠️ NRT scenes use a different QA mask from the frozen seasonal composites and are not comparable.
            </div>
          </div>
        )}

        {/* Layer Mode: Dynamic World Land Cover */}
        {layerMode === "landcover" && (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                Dynamic World Land Cover (10m LULC)
              </span>
              <span className="rounded bg-teal-100 px-1.5 py-0.5 text-[10px] font-semibold text-teal-800">
                Sentinel-2 Model
              </span>
            </div>

            <div className="mt-2 text-[10px] text-slate-600">
              9-class near-real-time global land use land cover at 10 m resolution:
            </div>

            <div className="mt-2 grid grid-cols-3 gap-1.5 text-[10px]">
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-xs shrink-0" style={{ backgroundColor: "#C4281B" }} />
                <span className="font-medium text-slate-700">Built</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-xs shrink-0" style={{ backgroundColor: "#397D49" }} />
                <span className="font-medium text-slate-700">Trees</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-xs shrink-0" style={{ backgroundColor: "#88B053" }} />
                <span className="font-medium text-slate-700">Grass</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-xs shrink-0" style={{ backgroundColor: "#E49635" }} />
                <span className="font-medium text-slate-700">Crops</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-xs shrink-0" style={{ backgroundColor: "#DFC35A" }} />
                <span className="font-medium text-slate-700">Shrub</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-xs shrink-0" style={{ backgroundColor: "#419BDF" }} />
                <span className="font-medium text-slate-700">Water</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-xs shrink-0" style={{ backgroundColor: "#7A87C6" }} />
                <span className="font-medium text-slate-700">Wetland</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-xs shrink-0" style={{ backgroundColor: "#A59B8F" }} />
                <span className="font-medium text-slate-700">Bare</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-xs shrink-0" style={{ backgroundColor: "#B39FE1" }} />
                <span className="font-medium text-slate-700">Snow/Ice</span>
              </div>
            </div>

            <div className="mt-2.5 rounded bg-teal-50 p-2 border border-teal-200 text-[9.5px] leading-relaxed text-teal-900">
              <strong>Scientific Disclosure:</strong> Dynamic World outputs are deep learning model predictions from Sentinel-2 TOA reflectance (CC BY 4.0; Brown et al. 2022, Sci Data). Not empirical in-situ ground truth. Physical surveys remain required for structural suitability and tenure.
            </div>
          </div>
        )}

        {/* T1(e) Resolution Note */}
        <div className="mt-2.5 rounded bg-slate-100/90 p-2 border border-slate-200 text-[9px] leading-relaxed text-slate-600">
          <strong>Resolution Note:</strong> 100 m is the analysis/reporting grid. Landsat TIRS native thermal sampling is about 100 m (distributed at 30 m); 30 m optical indices are aggregated to the grid. Cells are not building- or street-level measurements.
        </div>
      </div>
    )}
  </div>
</div>
);
}
