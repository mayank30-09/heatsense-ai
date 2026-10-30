import React, { useState, useId } from "react";
import type { PipelineStatus, SceneItem } from "../../services/scenesApi";

interface LatestSceneSidebarProps {
  scenes: SceneItem[];
  selectedSceneId?: string;
  onSelectScene: (sceneId: string) => void;
  showRasterTile: boolean;
  onToggleRasterTile: () => void;
  pipelineStatus?: PipelineStatus | null;
  scenesLoading?: boolean;
  scenesError?: string | null;
  totalCells?: number;
  onTriggerCheck?: () => void;
  isChecking?: boolean;
}

export default function LatestSceneSidebar({
  scenes = [],
  selectedSceneId,
  onSelectScene,
  showRasterTile,
  onToggleRasterTile,
  pipelineStatus,
  scenesLoading = false,
  scenesError,
  totalCells = 49747,
  onTriggerCheck,
  isChecking = false,
}: LatestSceneSidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(() => typeof window !== "undefined" && window.innerWidth < 1024);
  const [copied, setCopied] = useState(false);
  const [showOverpasses, setShowOverpasses] = useState(true);
  const sceneSelectId = useId();

  // Find active scene
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

  const handleCopySceneId = async (id: string) => {
    try {
      await navigator.clipboard.writeText(id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  // When collapsed, show compact toggle chip
  if (isCollapsed) {
    return (
      <aside aria-label="Latest Scene Controls" className="pointer-events-none absolute top-3 left-[56px] z-[900]">
        <button
          type="button"
          onClick={() => setIsCollapsed(false)}
          aria-expanded={false}
          className="pointer-events-auto flex items-center gap-2 rounded-xl border border-indigo-300 bg-white/95 px-3 py-2 text-xs font-bold text-indigo-900 shadow-md backdrop-blur hover:bg-indigo-50 transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
        >
          <span>🛰️</span>
          <span>Show Latest Scene Panel</span>
          <span className="text-[10px] text-indigo-600 bg-indigo-100 px-1.5 py-0.5 rounded font-mono">▶</span>
        </button>
      </aside>
    );
  }

  return (
    <aside
      aria-label="Latest Scene Controls"
      className="pointer-events-none absolute top-3 left-[56px] z-[900] flex flex-col w-[calc(100vw-76px)] max-w-sm sm:w-96 max-h-[calc(100%-24px)] gap-2.5 overflow-y-auto pr-1 pb-4 scrollbar-thin"
    >
      {/* Sidebar Header & Collapse Toggle */}
      <div className="pointer-events-auto flex items-center justify-between rounded-xl border border-indigo-200 bg-white/95 px-3 py-2 shadow-xs backdrop-blur">
        <div className="flex items-center gap-2 text-xs font-bold text-indigo-950">
          <span className="text-base">🛰️</span>
          <span>Landsat NRT Overpass Monitor</span>
        </div>
        <button
          type="button"
          onClick={() => setIsCollapsed(true)}
          aria-expanded={true}
          title="Collapse Latest Scene sidebar"
          className="flex items-center gap-1 rounded bg-slate-100 hover:bg-slate-200 px-2 py-0.5 text-[11px] font-semibold text-slate-600 hover:text-slate-900 transition-colors cursor-pointer"
        >
          <span>◀ Hide</span>
        </button>
      </div>

      {/* Loading State */}
      {scenesLoading && (
        <div className="pointer-events-auto rounded-xl border border-indigo-200 bg-white/95 p-4 shadow-md backdrop-blur text-center space-y-2">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
          <div className="text-xs font-semibold text-indigo-900">
            Fetching Near-Real-Time Landsat catalog...
          </div>
          <div className="text-[11px] text-slate-500">
            Querying Level-2 surface temperature products over Surat WRS 148/45.
          </div>
        </div>
      )}

      {/* Error State */}
      {scenesError && (
        <div className="pointer-events-auto rounded-xl border border-rose-200 bg-rose-50/95 p-3.5 shadow-md backdrop-blur space-y-1.5 text-xs text-rose-900">
          <div className="font-bold flex items-center gap-1.5">
            <span>⚠️</span>
            <span>Failed to load scenes catalog</span>
          </div>
          <p className="text-[11px] text-rose-700">{scenesError}</p>
        </div>
      )}

      {/* Empty State */}
      {!scenesLoading && !scenesError && scenes.length === 0 && (
        <div className="pointer-events-auto rounded-xl border border-slate-200 bg-white/95 p-4 shadow-md backdrop-blur text-center space-y-1.5">
          <div className="text-2xl">📭</div>
          <div className="text-xs font-bold text-slate-800">No scenes processed yet</div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            The automated NRT discovery pipeline has not ingested any Landsat 8/9 Level-2 products yet.
          </p>
        </div>
      )}

      {/* Main Content Sections (Strict Order 1 to 5) */}
      {!scenesLoading && scenes.length > 0 && (
        <>
          {/* =========================================================================
              1. PIPELINE STATUS CARD
             ========================================================================= */}
          <section aria-label="Pipeline Status" className="pointer-events-auto rounded-xl border border-indigo-200 bg-white/95 p-3 shadow-md backdrop-blur space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Pipeline: {pipelineStatus?.pipeline_status ?? "OPERATIONAL"}
              </span>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-bold border ${
                  pipelineStatus?.pipeline_status === "OPERATIONAL"
                    ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                    : pipelineStatus?.pipeline_status === "DELAYED"
                    ? "bg-amber-50 text-amber-800 border-amber-200"
                    : "bg-rose-50 text-rose-800 border-rose-200"
                }`}
                title={pipelineStatus?.status_detail || undefined}
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    pipelineStatus?.pipeline_status === "OPERATIONAL"
                      ? "bg-emerald-500 animate-pulse"
                      : pipelineStatus?.pipeline_status === "DELAYED"
                      ? "bg-amber-500"
                      : "bg-rose-500"
                  }`}
                />
                <span>{pipelineStatus?.pipeline_status ?? "OPERATIONAL"}</span>
              </span>
            </div>

            <div className="space-y-1 text-xs text-slate-700">
              <div className="flex items-start justify-between gap-2">
                <span className="text-slate-500 shrink-0">Last checked:</span>
                <span className="font-medium text-right text-slate-900">
                  {pipelineStatus?.last_checked_ist ||
                    (pipelineStatus?.last_checked
                      ? new Date(pipelineStatus.last_checked).toLocaleString("en-IN", {
                          hour: "2-digit",
                          minute: "2-digit",
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                        }) + " IST"
                      : "Recent")}
                  {pipelineStatus?.last_checked_relative && (
                    <span className="ml-1 text-[11px] font-normal text-slate-500">
                      ({pipelineStatus.last_checked_relative})
                    </span>
                  )}
                </span>
              </div>

              <div className="flex items-start justify-between gap-2">
                <span className="text-slate-500 shrink-0">Next expected overpass:</span>
                <strong className="text-indigo-800 font-mono text-right">
                  {pipelineStatus?.next_expected_overpass_label ??
                    (pipelineStatus?.next_expected_overpass
                      ? `~${pipelineStatus.next_expected_overpass}`
                      : "~8 days")}
                </strong>
              </div>

              {pipelineStatus && (
                <div className="flex items-center justify-between text-[11px] pt-1.5 border-t border-slate-100 text-slate-500">
                  <div>
                    <span>Catalog ledger: </span>
                    <span className="font-semibold text-slate-700">
                      {pipelineStatus.processed_count} processed · {pipelineStatus.rejected_count} rejected
                    </span>
                  </div>
                  {onTriggerCheck && (
                    <button
                      type="button"
                      onClick={onTriggerCheck}
                      disabled={isChecking}
                      aria-label="Check upstream Landsat overpass now"
                      className="flex items-center gap-1 rounded-md bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 px-2 py-0.5 text-[10.5px] font-bold text-indigo-700 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Run live Earth Engine scene discovery check now"
                    >
                      <span className={isChecking ? "inline-block animate-spin" : ""}>🔄</span>
                      <span>{isChecking ? "Checking..." : "Check Now"}</span>
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Overdue/Detail Explanation Banner */}
            {pipelineStatus?.status_detail && pipelineStatus.pipeline_status !== "OPERATIONAL" && (
              <div className="rounded-md border border-amber-200 bg-amber-50/80 p-2 text-[11px] text-amber-900 leading-snug">
                <span>⚠️ {pipelineStatus.status_detail}</span>
              </div>
            )}

            {/* Expandable Recent Overpass Ledger */}
            {pipelineStatus?.recent_overpasses && pipelineStatus.recent_overpasses.length > 0 && (
              <div className="border-t border-slate-100 pt-1.5">
                <button
                  type="button"
                  onClick={() => setShowOverpasses((prev) => !prev)}
                  className="flex w-full items-center justify-between text-[11px] font-semibold text-indigo-700 hover:text-indigo-900 cursor-pointer"
                >
                  <span>Recent overpasses ({pipelineStatus.recent_overpasses.length})</span>
                  <span>{showOverpasses ? "Hide ▲" : "Show ▼"}</span>
                </button>

                {showOverpasses && (
                  <div className="mt-2 space-y-1.5 max-h-36 overflow-y-auto pr-1">
                    {pipelineStatus.recent_overpasses.map((ov) => (
                      <div
                        key={`${ov.date}-${ov.sensor}`}
                        className={`rounded px-2 py-1 text-[10.5px] border flex flex-col gap-0.5 ${
                          ov.status === "PROCESSED"
                            ? "bg-emerald-50/70 border-emerald-200 text-emerald-950"
                            : ov.status === "REJECTED"
                            ? "bg-slate-50 border-slate-200 text-slate-700"
                            : ov.status === "PENDING_LATENCY"
                            ? "bg-blue-50/70 border-blue-200 text-blue-900"
                            : "bg-amber-50 border-amber-200 text-amber-900"
                        }`}
                      >
                        <div className="flex items-center justify-between font-semibold">
                          <span>{ov.label}</span>
                          <span className="font-mono text-[9.5px]">
                            {ov.days_ago === 0 ? "today" : `${ov.days_ago}d ago`}
                          </span>
                        </div>
                        {ov.rejection_reason && (
                          <div className="text-[9.5px] text-slate-500 italic">
                            Reason: {ov.rejection_reason}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>

          {/* =========================================================================
              2. SCENE SELECTOR & CONTROLS CARD
             ========================================================================= */}
          <section aria-label="Scene Selector" className="pointer-events-auto rounded-xl border border-indigo-200 bg-white/95 p-3 shadow-md backdrop-blur space-y-2.5">
            <div className="flex items-center justify-between">
              <label htmlFor={sceneSelectId} className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Selected Overpass
              </label>
              <span className="text-[11px] font-mono font-bold text-indigo-700">
                {selectedScene ? selectedScene.acquisition_date : "N/A"}
              </span>
            </div>

            <select
              id={sceneSelectId}
              value={selectedSceneId || scenes[0]?.scene_id}
              onChange={(e) => onSelectScene(e.target.value)}
              aria-label="Select near-real-time Landsat overpass scene"
              className="w-full rounded-lg border border-indigo-200 bg-indigo-50/60 px-2.5 py-1.5 text-xs font-medium text-slate-900 shadow-2xs focus:border-indigo-500 focus:outline-none cursor-pointer truncate"
            >
              {scenes.map((s) => {
                const isRejected =
                  s.status === "rejected" ||
                  s.status === "REJECTED_CLOUDY" ||
                  s.valid_pixel_fraction < 0.4;
                const clearPct = (s.valid_pixel_fraction * 100).toFixed(0);
                const label = isRejected
                  ? `${s.acquisition_date} (${s.sensor}) — [REJECTED: ${clearPct}% clear - ${s.rejection_reason || "cloud contaminated"}]`
                  : `${s.acquisition_date} (${s.sensor}) — ${clearPct}% clear over SMC`;
                return (
                  <option
                    key={s.scene_id}
                    value={s.scene_id}
                    className={
                      isRejected ? "text-slate-400 bg-slate-50 italic" : "text-slate-900 font-medium"
                    }
                    title={s.rejection_reason || undefined}
                  >
                    {label}
                  </option>
                );
              })}
            </select>

            {/* Scene Badges */}
            {selectedScene && (
              <div className="flex items-center gap-1.5 flex-wrap text-xs">
                <span className="rounded bg-indigo-100/80 px-2 py-0.5 font-bold text-indigo-900 border border-indigo-200 text-[11px]">
                  {selectedScene.sensor}
                </span>
                <span className="rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-700 border border-slate-200 text-[11px]">
                  {daysAgoText}
                </span>
                <span
                  className={`rounded px-2 py-0.5 font-semibold text-[11px] border ${
                    selectedScene.status === "rejected" || selectedScene.status === "REJECTED_CLOUDY"
                      ? "bg-rose-50 text-rose-800 border-rose-200"
                      : "bg-emerald-50 text-emerald-800 border-emerald-200"
                  }`}
                >
                  {(selectedScene.valid_pixel_fraction * 100).toFixed(1)}% clear
                </span>
                <span className="rounded bg-slate-50 px-2 py-0.5 font-mono text-slate-600 border border-slate-200 text-[11px]">
                  {Math.round(selectedScene.valid_pixel_fraction * totalCells).toLocaleString()} cells
                </span>
              </div>
            )}

            {/* Thermal Raster Toggle */}
            <div className="pt-1 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-600 font-medium">Radiant Thermal Raster:</span>
              <button
                type="button"
                aria-pressed={showRasterTile}
                aria-label="Toggle Landsat surface temperature raster layer"
                onClick={onToggleRasterTile}
                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold transition-all shadow-xs cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 ${
                  showRasterTile
                    ? "border-blue-400 bg-blue-50 text-blue-800"
                    : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    showRasterTile ? "bg-blue-600 animate-pulse" : "bg-slate-300"
                  }`}
                />
                <span>Thermal Raster</span>
              </button>
            </div>
          </section>

          {/* =========================================================================
              3. SINGLE-SCENE SCIENTIFIC BANNER (RENDERED EXACTLY ONCE)
             ========================================================================= */}
          <section aria-label="Scientific Invariant Notice" className="pointer-events-auto rounded-xl border border-amber-300 bg-amber-50/95 p-2.5 shadow-sm backdrop-blur text-xs text-amber-950 leading-relaxed space-y-1">
            <div className="flex items-center gap-1.5 font-bold text-amber-900 text-[11px]">
              <span>⚠️</span>
              <span>Instantaneous Single-Scene Overpass</span>
            </div>
            <p className="text-[10.5px] text-amber-800">
              Reflects transient skin temperature (T<sub>skin</sub>) snapshot at ~11:00 AM IST overpass. Strictly excluded from the multi-year HPI composite and the 223 chronic hotspots.
            </p>
          </section>

          {/* =========================================================================
              4. SCENE METADATA & PROVENANCE
             ========================================================================= */}
          <section aria-label="Scene Metadata & Provenance" className="pointer-events-auto rounded-xl border border-slate-200 bg-white/95 p-3 shadow-md backdrop-blur space-y-2 text-xs text-slate-700">
            <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Scene Provenance & Metadata
              </span>
              <span className="font-mono text-[10px] text-indigo-700 font-semibold">
                WRS-2 148/45
              </span>
            </div>

            {/* Scene ID with copy button & wrap */}
            <div className="space-y-1">
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>Product Identifier:</span>
                <button
                  type="button"
                  onClick={() => selectedScene && handleCopySceneId(selectedScene.scene_id)}
                  title="Copy full Landsat Scene ID to clipboard"
                  className="flex items-center gap-1 text-[10px] text-indigo-600 hover:text-indigo-800 cursor-pointer font-medium"
                >
                  <span>{copied ? "✓ Copied" : "📋 Copy ID"}</span>
                </button>
              </div>
              <div
                className="font-mono text-[10px] bg-slate-50 p-1.5 rounded border border-slate-200 text-slate-800 break-all select-all leading-tight"
                title={selectedScene?.scene_id}
              >
                {selectedScene?.scene_id ?? "N/A"}
              </div>
            </div>

            <div className="space-y-1 text-[11px] pt-1">
              <div className="flex justify-between">
                <span className="text-slate-500">Sensor:</span>
                <span className="font-semibold text-slate-900">
                  {selectedScene ? selectedScene.sensor : "Landsat 8/9 Level-2"}
                </span>
              </div>

              <div className="flex justify-between">
                <span className="text-slate-500">Acquisition UTC:</span>
                <span className="font-mono text-slate-800">
                  {selectedScene?.acquisition_time
                    ? selectedScene.acquisition_time.replace("T", " ").replace("Z", " UTC")
                    : "N/A"}
                </span>
              </div>

              {selectedScene?.acquisition_time_ist && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Acquisition IST:</span>
                  <span className="font-mono text-indigo-900 font-medium">
                    {selectedScene.acquisition_time_ist}
                  </span>
                </div>
              )}

              <div className="flex justify-between">
                <span className="text-slate-500">Scene Cloud Cover:</span>
                <span className="font-medium text-slate-900">
                  {selectedScene?.cloud_cover !== null && selectedScene?.cloud_cover !== undefined
                    ? `${selectedScene.cloud_cover.toFixed(2)}%`
                    : "N/A"}
                </span>
              </div>

              <div className="flex justify-between">
                <span className="text-slate-500">Valid SMC Grid Cells:</span>
                <span className="font-semibold text-slate-900">
                  {selectedScene
                    ? `${Math.round(selectedScene.valid_pixel_fraction * totalCells).toLocaleString()} of ${totalCells.toLocaleString()}`
                    : `0 of ${totalCells.toLocaleString()}`}
                </span>
              </div>

              <div className="flex justify-between">
                <span className="text-slate-500">Contributing Scenes:</span>
                <span className="font-semibold text-slate-900">1 (Instantaneous overpass)</span>
              </div>

              <div className="flex justify-between">
                <span className="text-slate-500">Measurement Units:</span>
                <span className="font-medium text-slate-900">
                  Radiant skin temp T<sub>skin</sub> (°C)
                </span>
              </div>

              {/* Observed scene stats */}
              {selectedScene && (selectedScene.mean_lst_c !== null || selectedScene.max_lst_c !== null) && (
                <div className="grid grid-cols-2 gap-2 pt-1.5 mt-1 border-t border-slate-100">
                  <div className="rounded bg-indigo-50/50 p-1.5 border border-indigo-100 text-center">
                    <div className="text-[9px] uppercase tracking-wide text-slate-400">Mean LST</div>
                    <div className="text-sm font-bold text-indigo-700">
                      {selectedScene.mean_lst_c !== null ? `${selectedScene.mean_lst_c.toFixed(1)}°C` : "N/A"}
                    </div>
                  </div>
                  <div className="rounded bg-rose-50/50 p-1.5 border border-rose-100 text-center">
                    <div className="text-[9px] uppercase tracking-wide text-slate-400">Max LST</div>
                    <div className="text-sm font-bold text-rose-700">
                      {selectedScene.max_lst_c !== null ? `${selectedScene.max_lst_c.toFixed(1)}°C` : "N/A"}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* =========================================================================
              5. COLOR RAMP & TICK LEGEND (RENDERED EXACTLY ONCE)
             ========================================================================= */}
          <section aria-label="Thermal Color Ramp Legend" className="pointer-events-auto rounded-xl border border-slate-200 bg-white/95 p-3 shadow-md backdrop-blur space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-600">
                Radiant Skin Temp (T<sub>skin</sub>)
              </span>
              <span className="text-[10px] font-mono text-slate-500">20°C – 60°C</span>
            </div>

            {/* Smooth continuous thermal gradient */}
            <div
              className="h-3 w-full rounded border border-slate-200 shadow-inner"
              style={{
                background:
                  "linear-gradient(to right, #3b82f6 0%, #06b6d4 25%, #eab308 50%, #f97316 75%, #ef4444 90%, #7f1d1d 100%)",
              }}
              title="Continuous temperature ramp from 20°C (cool blue) to 60°C (extreme red)"
            />

            {/* Explicit tick labels */}
            <div className="flex justify-between text-[10px] font-mono text-slate-500 px-0.5">
              <span>20°C</span>
              <span>30°C</span>
              <span>40°C</span>
              <span>50°C</span>
              <span>60°C</span>
            </div>

            <div className="text-[9.5px] leading-tight text-slate-500 pt-1 border-t border-slate-100">
              Skin temperature (T<sub>skin</sub>) measured at ~10:30 local solar time (~11:00 AM IST), distinct from ambient 2 m air temperature (T<sub>air</sub>).
            </div>
          </section>
        </>
      )}
    </aside>
  );
}
