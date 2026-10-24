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

  const [isCollapsed, setIsCollapsed] = useState(false);

  const getLegendTitle = () => {
    switch (layerMode) {
      case "hpi":
        return "Heat Priority Index";
      case "lst":
        return `Observed LST (${fallback.label} ${displayYear})`;
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
    <div className="pointer-events-none absolute bottom-3 sm:bottom-6 left-3 z-[1000] w-[calc(100vw-24px)] max-w-[300px] sm:max-w-xs">
      <div className="pointer-events-auto rounded-lg border border-slate-200/90 bg-white/95 p-3 shadow-md backdrop-blur">
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
          <div className="max-h-[38vh] sm:max-h-[46vh] overflow-y-auto pr-1 space-y-3">
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

            {!hasRecentScene && (
              <div className="mt-2 flex items-center gap-1.5 rounded border border-amber-300 bg-amber-50 px-2 py-1 text-[10px] font-semibold text-amber-900">
                <span>⚠️</span>
                <span>No clear scene in the last {recentDayThreshold} days.</span>
              </div>
            )}
          </div>
        ) : (
          <div className="mb-3 rounded-md border border-slate-200 bg-slate-50 p-2.5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Active Layer
              </span>
              <span className="rounded bg-slate-200/80 px-2 py-0.5 font-mono text-[11px] font-bold text-slate-800">
                {fallback.label} / {displayYear}
              </span>
            </div>

            <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
              <div className="rounded bg-white p-1.5 border border-slate-100 shadow-2xs">
                <div className="text-[9px] uppercase tracking-wide text-slate-400">Mean LST</div>
                <div className="text-sm font-bold text-blue-700">
                  {meanLst.toFixed(1)}°C
                </div>
              </div>
              <div className="rounded bg-white p-1.5 border border-slate-100 shadow-2xs">
                <div className="text-[9px] uppercase tracking-wide text-slate-400">Max LST</div>
                <div className="text-sm font-bold text-red-700">
                  {maxLst.toFixed(1)}°C
                </div>
              </div>
            </div>

            {/* Seasonal Scene Provenance */}
            <div className="mt-2 rounded bg-white p-1.5 border border-slate-100 text-[10px] space-y-0.5 text-slate-600">
              <div className="flex justify-between">
                <span className="text-slate-500">Composite:</span>
                <span className="font-semibold">{stats?.n_scenes ?? fallback.sceneCount} contributing scenes</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Date Window:</span>
                <span className="font-mono text-[9px]">{stats?.date_window ?? fallback.dateWindow}</span>
              </div>
            </div>

            {isPostMonsoonNotice && (
              <div className="mt-2 flex items-center gap-1.5 rounded border border-blue-200 bg-blue-50 px-2 py-1 text-[10px] font-medium text-blue-800">
                <span>ℹ️</span>
                <span>Year 2026 incomplete; validated 2025 observation data is shown.</span>
              </div>
            )}

            {isMonsoonPartial && (
              <div className="mt-2 flex items-center gap-1.5 rounded border border-amber-300 bg-amber-50 px-2 py-1 text-[10px] font-semibold text-amber-900">
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
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                Heat Priority Index (HPI)
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

            <div className="mt-1 flex justify-between text-[10px] font-semibold text-slate-600">
              <span>0 (Low)</span>
              <span>30 (Mod)</span>
              <span>60 (High)</span>
              <span>100 (Critical)</span>
            </div>

            <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-2 text-[11px]">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-slate-600">
                  <span className="inline-block h-3 w-3 rounded-full border-2 border-red-600 bg-red-800 shadow-sm" />
                  Chronic Hotspot (Citywide)
                </span>
                <span className="font-bold text-red-700">{chronicCount} cells</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-slate-600">
                  <span className="inline-block h-3 w-3 rounded-sm border border-slate-400 bg-slate-400" />
                  Unavailable / Excluded
                </span>
                <span className="font-medium text-slate-500">SQL NULL</span>
              </div>
            </div>

            <div className="mt-2.5 rounded bg-slate-50 p-2 border border-slate-200 text-[9.5px] leading-tight text-slate-600">
              <span className="font-bold">HPI Baseline:</span> The HPI composite score represents baseline Summer 2026 heat vulnerability and is invariant to the seasonal LST layer selector.
            </div>
          </div>
        )}

        {/* Layer Mode: Observed LST */}
        {layerMode === "lst" && (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                Observed {fallback.label} LST
              </span>
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
                Landsat 8/9 · ~10:30 LST (~11:00 IST)
              </span>
            </div>

            {/* Unified 20°C - 60°C standard thermal gradient */}
            <div
              className="mt-2 h-3.5 w-full rounded"
              style={{
                background:
                  "linear-gradient(to right, rgb(59,130,246), rgb(16,185,129), rgb(245,158,11), rgb(234,88,12), rgb(127,29,29))",
              }}
            />

            <div className="mt-1 flex justify-between text-[10px] font-semibold text-slate-600">
              <span>20°C</span>
              <span>30°C</span>
              <span>40°C</span>
              <span>50°C</span>
              <span>60°C</span>
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
            </div>

            <div className="mt-2 rounded bg-amber-50/90 p-2 border border-amber-200/70 text-[9.5px] leading-snug text-amber-900">
              <span className="font-bold">Physical Note:</span> Landsat-derived Land Surface Temperature (LST) measures radiant skin temperature (T<sub>skin</sub>) at the satellite overpass (~10:30 local solar time, about 11:00 IST), distinct from ambient 2 m air temperature (T<sub>air</sub>).
            </div>
          </div>
        )}

        {/* Layer Mode: Confidence & Quality */}
        {layerMode === "confidence" && (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                Confidence & Quality Tier
              </span>
              <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800">
                Stage C QC
              </span>
            </div>

            <div className="mt-2.5 grid grid-cols-2 gap-1.5 text-[11px]">
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-emerald-600" />
                <span className="font-medium text-slate-700">HIGH (≥0.85)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-blue-600" />
                <span className="font-medium text-slate-700">MODERATE (0.70-0.85)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-amber-600" />
                <span className="font-medium text-slate-700">LOW (0.50-0.70)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-rose-600" />
                <span className="font-medium text-slate-700">INSUFFICIENT (&lt;0.50)</span>
              </div>
            </div>

            <div className="mt-2.5 border-t border-slate-100 pt-2 text-[10px] text-slate-500">
              Optical Imputation: 8-Connected Median, Boundary Mean, or Neutral Climatological Fallback.
            </div>

            <div className="mt-2 text-[10px] text-amber-800 italic bg-amber-50 rounded p-1.5 border border-amber-200">
              Notice: Confidence index is a heuristic, not a calibrated probability.
            </div>
          </div>
        )}

        {/* Layer Mode: Chronic Hotspots */}
        {layerMode === "chronic" && (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-red-800">
                Chronic Hotspots Only
              </span>
              <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-800">
                {chronicCount} Persistent Hotspots
              </span>
            </div>

            <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-700">
              <span className="inline-block h-4 w-4 rounded-full border-2 border-red-600 bg-red-800" />
              <span>Multi-year persistent extreme heat cells</span>
            </div>

            <p className="mt-2 text-[10px] leading-tight text-slate-500">
              Criterion: Hotspot frequency ≥50%, ≥3 hot seasons, ≥2 distinct years, and ≥4 qualifying seasons.
            </p>
          </div>
        )}

        {/* Layer Mode: Latest Scene */}
        {layerMode === "latest_scene" && (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                Observed Single Scene LST
              </span>
              <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-800">
                20°C – 60°C
              </span>
            </div>

            <div
              className="mt-2 h-3.5 w-full rounded"
              style={{
                background:
                  "linear-gradient(to right, rgb(59,130,246), rgb(16,185,129), rgb(245,158,11), rgb(234,88,12), rgb(127,29,29))",
              }}
            />

            <div className="mt-1 flex justify-between text-[10px] font-medium text-slate-500">
              <span>20°C</span>
              <span>30°C</span>
              <span>40°C</span>
              <span>50°C</span>
              <span>60°C</span>
            </div>

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
                  <span className="text-slate-500">Cloud Cover:</span>
                  <span className="font-semibold">
                    {selectedScene.cloud_cover !== null ? `${selectedScene.cloud_cover.toFixed(1)}%` : "N/A"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Clear Pixels (SMC):</span>
                  <span className="font-semibold text-emerald-700">
                    {(selectedScene.valid_pixel_fraction * 100).toFixed(1)}%
                  </span>
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
                  <span className="text-slate-500">Units:</span>
                  <span className="font-semibold">°C (Celsius)</span>
                </div>
              </div>
            )}

            <div className="mt-2.5 border-t border-slate-100 pt-2 text-[10px] font-medium text-slate-700 leading-4">
              Skin temperature at ~10:30 local solar time (about 11:00 IST), single scene, not a seasonal composite.
            </div>

            <div className="mt-1 text-[9px] font-medium text-amber-700 bg-amber-50 rounded p-1 border border-amber-200">
              ⚠️ NRT scenes use a different QA mask from the frozen seasonal composites and are not comparable.
            </div>

            <div className="mt-1 text-[9px] text-slate-400">
              Cloud-masked or unobserved pixels render transparent (nodata). Single-scene values do not flow into HPI, predictions, or recommendations.
            </div>
          </div>
        )}
      </div>
    )}
  </div>
</div>
);
}
