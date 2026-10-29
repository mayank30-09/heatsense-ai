import type { ActiveLayerMode, SeasonName } from "../../types/heatPriority";
import type { PipelineStatus, SceneItem } from "../../services/scenesApi";

interface LayerControlsProps {
  layerMode: ActiveLayerMode;
  onLayerModeChange: (mode: ActiveLayerMode) => void;
  showRasterTile: boolean;
  onToggleRasterTile: () => void;
  minHpiFilter: number | undefined;
  onToggleMinHpi: () => void;
  season?: SeasonName;
  onSeasonChange?: (season: SeasonName) => void;
  activeTool?: "grid" | "drawing";
  onSelectTool?: (tool: "grid" | "drawing") => void;
  scenes?: SceneItem[];
  selectedSceneId?: string;
  onSelectScene?: (sceneId: string) => void;
  recentDayThreshold?: number;
  isAreaAnalysis?: boolean;
  pipelineStatus?: PipelineStatus | null;
  scenesLoading?: boolean;
  scenesError?: string | null;
}

export default function LayerControls({
  layerMode,
  onLayerModeChange,
  showRasterTile,
  onToggleRasterTile,
  minHpiFilter,
  onToggleMinHpi,
  season = "summer",
  onSeasonChange,
  activeTool = "grid",
  onSelectTool,
  scenes = [],
  selectedSceneId,
  onSelectScene,
  isAreaAnalysis = false,
  pipelineStatus,
  scenesLoading = false,
  scenesError,
}: LayerControlsProps) {
  const modes: { id: ActiveLayerMode; label: string; icon: string; shortLabel: string }[] = [
    { id: "hpi", label: "Heat Priority Index (derived, 0-100)", shortLabel: "HPI (0-100)", icon: "🔥" },
    { id: "lst", label: "Observed LST (Landsat Level-2 ST)", shortLabel: "Observed LST", icon: "🌡️" },
    { id: "confidence", label: "Confidence / Quality", shortLabel: "Confidence (QA)", icon: "🛡️" },
    { id: "chronic", label: "Chronic (223)", shortLabel: "Chronic Hotspots", icon: "⚠️" },
    { id: "latest_scene", label: "Latest scene", shortLabel: "NRT Scene", icon: "🛰️" },
  ];

  const selectedScene = scenes.find((s) => s.scene_id === selectedSceneId) || scenes[0];

  // Calculate days since acquisition
  let daysAgoText = "Recent";
  if (selectedScene?.acquisition_date) {
    const acqTime = new Date(selectedScene.acquisition_date).getTime();
    const now = new Date().getTime();
    const diffDays = Math.floor((now - acqTime) / (1000 * 60 * 60 * 24));
    if (diffDays >= 0) {
      daysAgoText = diffDays === 0 ? "Today" : diffDays === 1 ? "1 day ago" : `${diffDays} days ago`;
    }
  }

  const seasonSelector = onSeasonChange && (
    <div
      role="group"
      aria-label="Observation season selection"
      className="flex items-center rounded-lg border border-slate-200/90 bg-white/95 p-0.5 shadow-xs backdrop-blur-md"
    >
      <button
        type="button"
        aria-label="Summer season observations"
        aria-pressed={season === "summer"}
        onClick={() => onSeasonChange("summer")}
        className={`rounded-md px-2.5 py-1 text-[11px] font-semibold transition-all focus:outline-none focus-visible:ring-1 focus-visible:ring-teal-600 cursor-pointer ${
          season === "summer"
            ? "bg-amber-600 text-white shadow-xs font-bold"
            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        }`}
      >
        ☀️ Summer
      </button>
      <button
        type="button"
        aria-label="Winter season observations"
        aria-pressed={season === "winter"}
        onClick={() => onSeasonChange("winter")}
        className={`rounded-md px-2.5 py-1 text-[11px] font-semibold transition-all focus:outline-none focus-visible:ring-1 focus-visible:ring-teal-600 cursor-pointer ${
          season === "winter"
            ? "bg-sky-600 text-white shadow-xs font-bold"
            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        }`}
      >
        ❄️ Winter
      </button>
      <button
        type="button"
        aria-label="Post-Monsoon season observations"
        aria-pressed={season === "post_monsoon"}
        onClick={() => onSeasonChange("post_monsoon")}
        className={`rounded-md px-2.5 py-1 text-[11px] font-semibold transition-all focus:outline-none focus-visible:ring-1 focus-visible:ring-teal-600 cursor-pointer ${
          season === "post_monsoon"
            ? "bg-orange-700 text-white shadow-xs font-bold"
            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        }`}
      >
        🍂 Post-Monsoon
      </button>
      <button
        type="button"
        aria-label="Monsoon season observations"
        aria-pressed={season === "monsoon"}
        onClick={() => onSeasonChange("monsoon")}
        title="Low reliability: high cloud contamination risk"
        className={`rounded-md px-2.5 py-1 text-[11px] font-semibold transition-all flex items-center gap-1 focus:outline-none focus-visible:ring-1 focus-visible:ring-teal-600 cursor-pointer ${
          season === "monsoon"
            ? "bg-teal-700 text-white shadow-xs font-bold"
            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        }`}
      >
        <span>🌧️ Monsoon</span>
        <span className="rounded bg-amber-500/90 px-1 py-0.2 text-[9px] font-bold text-white leading-none">⚠️</span>
      </button>
    </div>
  );

  // In Area Analysis mode: render fixed single-period baseline notice and thermal-raster toggle
  if (isAreaAnalysis) {
    return (
      <div
        className="map-toolbar w-full rounded-xl border border-slate-200/90 bg-white/95 px-3 py-2 shadow-xs mb-2 transition-all"
        aria-label="Map Controls Toolbar"
      >
        <div className="flex flex-wrap items-center gap-2 md:gap-2.5 max-md:overflow-x-auto max-md:flex-nowrap max-md:scrollbar-none max-md:pb-1">
          <div className="flex items-center gap-2 rounded-lg bg-amber-50/80 border border-amber-200/80 px-2.5 py-1 text-[11px] text-amber-950 font-mono shadow-2xs shrink-0">
            <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse shrink-0" />
            <span>Analysis Baseline: <strong>Summer 2026 (Authoritative HPI Composite)</strong></span>
            <span className="text-[10px] text-amber-800/80 italic hidden md:inline">· Multi-season comparisons available in Heat Map</span>
          </div>

          <div className="ml-auto flex items-center gap-2 shrink-0">
            <button
              type="button"
              aria-pressed={showRasterTile}
              aria-label="Toggle Landsat surface temperature raster layer"
              onClick={onToggleRasterTile}
              className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-semibold transition-all shadow-xs cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 ${
                showRasterTile
                  ? "border-teal-400 bg-teal-50 text-teal-900 font-bold ring-1 ring-teal-200"
                  : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              <span className={`h-2 w-2 rounded-full transition-colors ${showRasterTile ? "bg-teal-600" : "bg-slate-300"}`} />
              <span>Thermal Raster</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="map-toolbar w-full rounded-xl border border-slate-200/90 bg-white/95 px-3 py-2 shadow-xs mb-2 transition-all"
      aria-label="Map Controls Toolbar"
    >
      <div className="flex flex-wrap items-center gap-2 md:gap-2.5 max-md:overflow-x-auto max-md:flex-nowrap max-md:scrollbar-none max-md:pb-1">
        {/* Primary Layer Mode Selector Pill */}
        <div
          role="tablist"
          aria-label="Map thermal and priority layer modes"
          className="flex items-center rounded-lg border border-slate-200/90 bg-slate-50/80 p-0.5 shrink-0 shadow-2xs"
        >
          {modes.map((mode) => {
            const isActive = layerMode === mode.id;
            return (
              <button
                key={mode.id}
                role="tab"
                aria-selected={isActive}
                aria-label={`${mode.label} layer`}
                type="button"
                onClick={() => onLayerModeChange(mode.id)}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all cursor-pointer whitespace-nowrap focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 ${
                  isActive
                    ? "bg-slate-900 text-white shadow-xs font-bold"
                    : "text-slate-600 hover:bg-slate-200/70 hover:text-slate-900"
                }`}
              >
                <span className="text-xs leading-none">{mode.icon}</span>
                <span>{mode.label}</span>
              </button>
            );
          })}
        </div>

        {/* Season Selector Pills (for standard modes when not in latest_scene) */}
        {layerMode !== "latest_scene" && seasonSelector && (
          <div className="shrink-0">
            {seasonSelector}
          </div>
        )}

        {/* Right-aligned Toggles & Filters (ml-auto) */}
        <div className="ml-auto flex items-center gap-2 shrink-0">
          <button
            type="button"
            aria-pressed={showRasterTile}
            aria-label="Toggle Landsat surface temperature raster layer"
            onClick={onToggleRasterTile}
            className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-semibold transition-all shadow-xs cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 ${
              showRasterTile
                ? "border-teal-400 bg-teal-50 text-teal-900 font-bold ring-1 ring-teal-200"
                : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900"
            }`}
          >
            <span className={`h-2 w-2 rounded-full transition-colors ${showRasterTile ? "bg-teal-600" : "bg-slate-300"}`} />
            <span>Thermal Raster</span>
          </button>

          {layerMode !== "chronic" && layerMode !== "latest_scene" && (
            <button
              type="button"
              aria-pressed={minHpiFilter !== undefined}
              aria-label="Filter grid cells by HPI greater than or equal to 50"
              onClick={onToggleMinHpi}
              className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-semibold transition-all shadow-xs cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 ${
                minHpiFilter !== undefined
                  ? "border-amber-400 bg-amber-50 text-amber-950 font-bold ring-1 ring-amber-300"
                  : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              <span>🎯</span>
              <span>{minHpiFilter !== undefined ? "HPI ≥ 50 Active" : "Filter: HPI ≥ 50"}</span>
            </button>
          )}

          {isAreaAnalysis && onSelectTool && (
            <div
              role="group"
              aria-label="Map interaction tools"
              className="flex items-center rounded-lg border border-slate-200/90 bg-slate-50 p-0.5 shadow-xs"
            >
              <button
                type="button"
                aria-pressed={activeTool === "grid"}
                aria-label="Grid cells inspection tool"
                onClick={() => onSelectTool("grid")}
                className={`rounded px-2.5 py-1 text-[11px] font-semibold transition-all cursor-pointer focus:outline-none focus-visible:ring-1 focus-visible:ring-teal-600 ${
                  activeTool === "grid"
                    ? "bg-slate-800 text-white font-bold"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                Grid Cells
              </button>
              <button
                type="button"
                aria-pressed={activeTool === "drawing"}
                aria-label="Custom polygon drawing tool"
                onClick={() => onSelectTool("drawing")}
                className={`rounded px-2.5 py-1 text-[11px] font-semibold transition-all cursor-pointer focus:outline-none focus-visible:ring-1 focus-visible:ring-teal-600 ${
                  activeTool === "drawing"
                    ? "bg-slate-800 text-white font-bold"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                Draw Polygon
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
