import type { ActiveLayerMode, SeasonName } from "../../types/heatPriority";

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
}: LayerControlsProps) {
  const modes: { id: ActiveLayerMode; label: string; icon: string }[] = [
    { id: "hpi", label: "HPI Priority", icon: "🔥" },
    { id: "lst", label: "Observed LST", icon: "🌡️" },
    { id: "confidence", label: "Confidence / Quality", icon: "🛡️" },
    { id: "chronic", label: "Chronic (223)", icon: "⚠️" },
  ];

  return (
    <div className="pointer-events-none absolute top-3 left-14 z-[1000] flex flex-col gap-2">
      {/* Primary Layer Selector */}
      <div className="pointer-events-auto flex items-center rounded-lg border border-slate-200/90 bg-white/95 p-1 shadow-md backdrop-blur">
        {modes.map((mode) => {
          const isActive = layerMode === mode.id;
          return (
            <button
              key={mode.id}
              type="button"
              onClick={() => onLayerModeChange(mode.id)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
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

      {/* Layer Options / Filter Bar */}
      <div className="pointer-events-auto flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={onToggleRasterTile}
          className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-semibold transition-all backdrop-blur shadow-sm ${
            showRasterTile
              ? "border-blue-300 bg-blue-50 text-blue-800"
              : "border-slate-200 bg-white/95 text-slate-600 hover:bg-slate-50"
          }`}
        >
          <span className={`h-2 w-2 rounded-full ${showRasterTile ? "bg-blue-600" : "bg-slate-300"}`} />
          <span>Thermal Raster</span>
        </button>

        <button
          type="button"
          onClick={onToggleMinHpi}
          className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-semibold transition-all backdrop-blur shadow-sm ${
            minHpiFilter !== undefined
              ? "border-amber-300 bg-amber-50 text-amber-900 font-bold"
              : "border-slate-200 bg-white/95 text-slate-600 hover:bg-slate-50"
          }`}
        >
          <span>🎯</span>
          <span>{minHpiFilter !== undefined ? "HPI ≥ 50 Active" : "Filter: HPI ≥ 50"}</span>
        </button>

        {onSeasonChange && (
          <div className="flex items-center rounded-md border border-slate-200 bg-white/95 p-0.5 shadow-sm">
            <button
              type="button"
              onClick={() => onSeasonChange("summer")}
              className={`rounded px-2 py-1 text-[11px] font-semibold transition-all ${
                season === "summer"
                  ? "bg-amber-600 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              ☀️ Summer
            </button>
            <button
              type="button"
              onClick={() => onSeasonChange("winter")}
              className={`rounded px-2 py-1 text-[11px] font-semibold transition-all ${
                season === "winter"
                  ? "bg-sky-600 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              ❄️ Winter
            </button>
            <button
              type="button"
              onClick={() => onSeasonChange("post_monsoon")}
              className={`rounded px-2 py-1 text-[11px] font-semibold transition-all ${
                season === "post_monsoon"
                  ? "bg-orange-700 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              🍂 Post-Monsoon
            </button>
            <button
              type="button"
              onClick={() => onSeasonChange("monsoon")}
              title="Low reliability: high cloud contamination risk"
              className={`rounded px-2 py-1 text-[11px] font-semibold transition-all flex items-center gap-1 ${
                season === "monsoon"
                  ? "bg-teal-700 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <span>🌧️ Monsoon</span>
              <span className="rounded bg-amber-500/80 px-1 py-0.2 text-[9px] font-bold text-white">⚠️</span>
            </button>
          </div>
        )}

        {onSelectTool && (
          <div className="flex items-center rounded-md border border-slate-200 bg-white/95 p-0.5 shadow-sm">
            <button
              type="button"
              onClick={() => onSelectTool("grid")}
              className={`rounded px-2.5 py-1 text-[11px] font-semibold transition-all ${
                activeTool === "grid"
                  ? "bg-slate-800 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              Grid Cells
            </button>
            <button
              type="button"
              onClick={() => onSelectTool("drawing")}
              className={`rounded px-2.5 py-1 text-[11px] font-semibold transition-all ${
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
    </div>
  );
}
