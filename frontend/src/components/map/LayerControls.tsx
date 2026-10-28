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
  const modes: { id: ActiveLayerMode; label: string; icon: string }[] = [
    { id: "hpi", label: "Heat Priority Index (derived, 0-100)", icon: "🔥" },
    { id: "lst", label: "Observed LST (Landsat Level-2 ST)", icon: "🌡️" },
    { id: "confidence", label: "Confidence / Quality", icon: "🛡️" },
    { id: "chronic", label: "Chronic (223)", icon: "⚠️" },
    { id: "latest_scene", label: "Latest scene", icon: "🛰️" },
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
      className="flex items-center rounded-md border border-slate-200 bg-white/95 p-0.5 shadow-sm"
    >
      <button
        type="button"
        aria-label="Summer season observations"
        aria-pressed={season === "summer"}
        onClick={() => onSeasonChange("summer")}
        className={`rounded px-2 py-1 text-[11px] font-semibold transition-all focus:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500 cursor-pointer ${
          season === "summer"
            ? "bg-amber-600 text-white shadow-sm"
            : "text-slate-600 hover:bg-slate-100"
        }`}
      >
        ☀️ Summer
      </button>
      <button
        type="button"
        aria-label="Winter season observations"
        aria-pressed={season === "winter"}
        onClick={() => onSeasonChange("winter")}
        className={`rounded px-2 py-1 text-[11px] font-semibold transition-all focus:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500 cursor-pointer ${
          season === "winter"
            ? "bg-sky-600 text-white shadow-sm"
            : "text-slate-600 hover:bg-slate-100"
        }`}
      >
        ❄️ Winter
      </button>
      <button
        type="button"
        aria-label="Post-Monsoon season observations"
        aria-pressed={season === "post_monsoon"}
        onClick={() => onSeasonChange("post_monsoon")}
        className={`rounded px-2 py-1 text-[11px] font-semibold transition-all focus:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500 cursor-pointer ${
          season === "post_monsoon"
            ? "bg-orange-700 text-white shadow-sm"
            : "text-slate-600 hover:bg-slate-100"
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
        className={`rounded px-2 py-1 text-[11px] font-semibold transition-all flex items-center gap-1 focus:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500 cursor-pointer ${
          season === "monsoon"
            ? "bg-teal-700 text-white shadow-sm"
            : "text-slate-600 hover:bg-slate-100"
        }`}
      >
        <span>🌧️ Monsoon</span>
        <span className="rounded bg-amber-500/80 px-1 py-0.2 text-[9px] font-bold text-white">⚠️</span>
      </button>
    </div>
  );

  // In Area Analysis mode: render ONLY season selector and thermal-raster toggle
  if (isAreaAnalysis) {
    return (
      <div className="pointer-events-none absolute top-3 left-12 sm:left-14 z-[1000] flex flex-col gap-1.5 max-w-[calc(100vw-60px)] sm:max-w-xl">
        <div className="pointer-events-auto flex items-center gap-2 flex-wrap">
          <button
            type="button"
            aria-pressed={showRasterTile}
            aria-label="Toggle Landsat surface temperature raster layer"
            onClick={onToggleRasterTile}
            className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-semibold transition-all backdrop-blur shadow-xs cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 ${
              showRasterTile
                ? "border-blue-300 bg-blue-50 text-blue-800"
                : "border-slate-200 bg-white/95 text-slate-600 hover:bg-slate-50"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${showRasterTile ? "bg-blue-600" : "bg-slate-300"}`} />
            <span>Thermal Raster</span>
          </button>
          {seasonSelector}
        </div>
      </div>
    );
  }

  return (
    <div className="pointer-events-none absolute top-3 left-12 sm:left-14 z-[1000] flex flex-col gap-2 max-w-[calc(100vw-60px)] sm:max-w-xl">
      {/* Primary Layer Selector */}
      <div
        role="tablist"
        aria-label="Map thermal and priority layer modes"
        className="pointer-events-auto flex items-center rounded-xl border border-slate-200/90 bg-white/95 p-1 shadow-sm backdrop-blur flex-wrap gap-1"
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
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 ${
                isActive
                  ? "bg-slate-900 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              <span>{mode.icon}</span>
              <span>{mode.label}</span>
            </button>
          );
        })}
      </div>

      {/* In Latest Scene Mode, controls and metadata are rendered in the unified LatestSceneSidebar */}
      {layerMode === "latest_scene" ? null : (
        /* Layer Options / Filter Bar for Standard Modes (HPI, LST, Chronic, Confidence) */
        <div className="pointer-events-auto flex items-center gap-2 flex-wrap">
          <button
            type="button"
            aria-pressed={showRasterTile}
            aria-label="Toggle Landsat surface temperature raster layer"
            onClick={onToggleRasterTile}
            className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-semibold transition-all backdrop-blur shadow-sm cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 ${
              showRasterTile
                ? "border-blue-300 bg-blue-50 text-blue-800"
                : "border-slate-200 bg-white/95 text-slate-600 hover:bg-slate-50"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${showRasterTile ? "bg-blue-600" : "bg-slate-300"}`} />
            <span>Thermal Raster</span>
          </button>

          {layerMode !== "chronic" && (
            <button
              type="button"
              aria-pressed={minHpiFilter !== undefined}
              aria-label="Filter grid cells by HPI greater than or equal to 50"
              onClick={onToggleMinHpi}
              className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-semibold transition-all backdrop-blur shadow-sm cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 ${
                minHpiFilter !== undefined
                  ? "border-amber-300 bg-amber-50 text-amber-900 font-bold"
                  : "border-slate-200 bg-white/95 text-slate-600 hover:bg-slate-50"
              }`}
            >
              <span>🎯</span>
              <span>{minHpiFilter !== undefined ? "HPI ≥ 50 Active" : "Filter: HPI ≥ 50"}</span>
            </button>
          )}

          {seasonSelector}

          {isAreaAnalysis && onSelectTool && (
            <div
              role="group"
              aria-label="Map interaction tools"
              className="flex items-center rounded-md border border-slate-200 bg-white/95 p-0.5 shadow-sm"
            >
              <button
                type="button"
                aria-pressed={activeTool === "grid"}
                aria-label="Grid cells inspection tool"
                onClick={() => onSelectTool("grid")}
                className={`rounded px-2.5 py-1 text-[11px] font-semibold transition-all cursor-pointer focus:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500 ${
                  activeTool === "grid"
                    ? "bg-slate-800 text-white"
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
                className={`rounded px-2.5 py-1 text-[11px] font-semibold transition-all cursor-pointer focus:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500 ${
                  activeTool === "drawing"
                    ? "bg-slate-800 text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                Draw Polygon
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
