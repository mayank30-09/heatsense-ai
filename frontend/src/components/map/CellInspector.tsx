import { useEffect, useState } from "react";
import type {
  ActiveLayerMode,
  GridCellScoreItem,
  SeasonName,
} from "../../types/heatPriority";
import type { SceneItem } from "../../services/scenesApi";
import { fetchCellLandCover } from "../../services/interventionsApi";
import type { CellLandCoverData } from "../../types/interventions";
import {
  getConfidenceColor,
  getEligibilityInfo,
  getHPIColor,
  getLSTColor,
  getOpticalImputationLabel,
  getPersistenceBadge,
} from "../../utils/hpiColorScales";

interface CellInspectorProps {
  cell: GridCellScoreItem | null;
  onClose: () => void;
  activeLayerMode?: ActiveLayerMode;
  activeSeason?: SeasonName;
  activeYear?: number;
  selectedScene?: SceneItem | null;
}

const SEASON_LABELS: Record<SeasonName, string> = {
  summer: "Summer",
  winter: "Winter",
  monsoon: "Monsoon",
  post_monsoon: "Post-Monsoon",
};

export default function CellInspector({
  cell,
  onClose,
  activeLayerMode = "hpi",
  activeSeason = "summer",
  activeYear = 2026,
  selectedScene = null,
}: CellInspectorProps) {
  const [showHistory, setShowHistory] = useState(false);
  const [landcoverData, setLandcoverData] = useState<CellLandCoverData | null>(null);
  const [landcoverLoading, setLandcoverLoading] = useState(false);

  useEffect(() => {
    if (!cell?.pixel_id) {
      setLandcoverData(null);
      return;
    }
    let isMounted = true;
    setLandcoverLoading(true);
    fetchCellLandCover(cell.pixel_id, "summer", 2024)
      .then((data) => {
        if (isMounted) {
          setLandcoverData(data);
          setLandcoverLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setLandcoverData(null);
          setLandcoverLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [cell?.pixel_id]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!cell) return null;

  const hpiColor = getHPIColor(cell.heat_priority_score, cell.is_chronic_hotspot);
  const persistenceBadge = getPersistenceBadge(cell.persistence_tier);
  const opticalInfo = getOpticalImputationLabel(cell.optical_imputation_flag);
  const eligibilityInfo = getEligibilityInfo(cell.eligibility_status);
  const isUnavailable = cell.heat_priority_score === null;

  // Resolve current active season label and effective year
  const seasonLabel = SEASON_LABELS[activeSeason] || "Summer";
  const effectiveActiveYear =
    activeSeason === "post_monsoon" && activeYear === 2026 ? 2025 : activeYear;

  // Baseline Summer LST (authoritative baseline for HPI and chronic definition)
  const summerBaselineLst = cell.summer_lst_c ?? (activeSeason === "summer" ? cell.observed_lst_c : null);

  // Active layer observation value
  let activeObsDisplay: {
    title: string;
    value: string;
    color?: string;
    subtext: string;
    isMasked: boolean;
  };

  if (activeLayerMode === "latest_scene") {
    const sceneLst = cell.scene_lst_c ?? (selectedScene ? cell.observed_lst_c : null);
    const sceneDate = selectedScene?.acquisition_date ?? "NRT";
    const sensor = selectedScene?.sensor ?? "Landsat 8/9";
    activeObsDisplay = {
      title: `Observed Scene LST (${sceneDate})`,
      value: sceneLst !== null && sceneLst !== undefined ? `${sceneLst.toFixed(1)}°C` : "N/A",
      color: sceneLst !== null && sceneLst !== undefined ? getLSTColor(sceneLst) : "#64748b",
      subtext: `${sensor} instantaneous overpass`,
      isMasked: sceneLst === null || sceneLst === undefined,
    };
  } else if (activeLayerMode === "lst") {
    const lst = cell.observed_lst_c;
    const isMasked = lst === null || lst === undefined;
    activeObsDisplay = {
      title: `Observed ${seasonLabel} LST (${effectiveActiveYear})`,
      value: !isMasked ? `${lst.toFixed(1)}°C` : `Cloud-masked in ${seasonLabel.toLowerCase()} ${effectiveActiveYear}`,
      color: !isMasked ? getLSTColor(lst) : "#b45309",
      subtext: !isMasked
        ? `Landsat 8/9 seasonal median composite`
        : `QA cloud/cirrus/shadow masked; no clear pixel retrieval`,
      isMasked,
    };
  } else {
    // Default / HPI / Chronic / Confidence mode:
    // Shows authoritative summer baseline LST
    const isMasked = summerBaselineLst === null || summerBaselineLst === undefined;
    activeObsDisplay = {
      title: "Observed Summer LST (2026 Baseline)",
      value: !isMasked ? `${summerBaselineLst.toFixed(1)}°C` : "N/A",
      color: !isMasked ? getLSTColor(summerBaselineLst) : "#64748b",
      subtext: cell.is_chronic_hotspot
        ? "Multi-year persistent extreme summer temperature"
        : "Operational summer 2026 composite defining HPI",
      isMasked,
    };
  }

  // Multi-season observations table data
  const canonicalSeasons = [
    { key: "summer", label: "Summer", year: 2026 },
    { key: "winter", label: "Winter", year: 2026 },
    { key: "post_monsoon", label: "Post-Monsoon", year: 2025 },
    { key: "monsoon", label: "Monsoon", year: 2026 },
  ];

  const seasonalRows = canonicalSeasons.map((cs) => {
    // If backend provided seasonal_observations, look up by key and year
    if (cell.seasonal_observations && cell.seasonal_observations.length > 0) {
      const found = cell.seasonal_observations.find(
        (so) => so.season === cs.key && so.year === cs.year
      );
      if (found) {
        return {
          label: found.season_label,
          year: found.year,
          temp: found.observed_lst_c,
          status: found.status,
          reason: found.reason || (found.observed_lst_c !== null ? "Valid" : `Cloud-masked in ${cs.key} ${cs.year}`),
          obsCount: found.obs_count,
          delta: found.delta_to_summer_c,
        };
      }
    }

    // Fallback if detail not yet populated:
    if (cs.key === "summer") {
      return {
        label: "Summer 2026",
        year: 2026,
        temp: summerBaselineLst,
        status: summerBaselineLst !== null ? "Valid" : "Cloud-masked",
        reason: summerBaselineLst !== null ? "Valid (Summer composite)" : "Cloud-masked in summer 2026",
        obsCount: 10,
        delta: 0.0,
      };
    }
    if (activeSeason === cs.key) {
      const deltaVal =
        cell.observed_lst_c !== null && summerBaselineLst !== null
          ? Math.round((cell.observed_lst_c - summerBaselineLst) * 100) / 100
          : null;
      return {
        label: `${cs.label} ${cs.year}`,
        year: cs.year,
        temp: cell.observed_lst_c,
        status: cell.observed_lst_c !== null ? "Valid" : "Cloud-masked",
        reason: cell.observed_lst_c !== null ? "Valid observation" : `Cloud-masked in ${cs.key} ${cs.year}`,
        obsCount: null,
        delta: deltaVal,
      };
    }
    return {
      label: `${cs.label} ${cs.year}`,
      year: cs.year,
      temp: null,
      status: cs.key === "monsoon" ? "Cloud-masked" : "Unobserved",
      reason: cs.key === "monsoon" ? "Cloud-masked in monsoon 2026" : "Unobserved",
      obsCount: null,
      delta: null,
    };
  });

  return (
    <aside
      className="pointer-events-auto absolute right-3 top-3 z-[900] w-[calc(100vw-24px)] sm:w-96 max-w-sm max-h-[calc(100vh-1.5rem)] sm:max-h-[88vh] flex flex-col rounded-2xl border border-slate-200/90 bg-white/95 shadow-elevated backdrop-blur-md transition-all duration-200 overflow-hidden"
      aria-label="Grid cell details"
    >
      {/* Fixed Header with Pixel ID and Close Button */}
      <div className="shrink-0 p-4 pb-3 border-b border-slate-100 flex items-start justify-between bg-white/50 backdrop-blur-xs">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10.5px] font-bold uppercase tracking-wider text-slate-500 font-mono">
              Analytical Grid Cell
            </span>
            {cell.is_chronic_hotspot && (
              <span className="rounded-full bg-red-600 px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wide text-white shadow-2xs">
                Chronic Hotspot
              </span>
            )}
          </div>
          <h3 className="mt-0.5 text-lg font-bold text-slate-900 font-mono tracking-tight">
            {cell.pixel_id}
          </h3>
          <p className="text-[10.5px] text-slate-500 font-mono leading-snug">
            Nominal 100 m grid (true area: 9,273 m² / 0.927 ha) · Row {cell.row_idx} · Col {cell.col_idx} · {cell.latitude.toFixed(5)}°N, {cell.longitude.toFixed(5)}°E
          </p>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-teal-600 cursor-pointer transition-colors"
          aria-label="Close inspector"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Scrollable Inspector Body */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 pt-3 space-y-3.5 scrollbar-thin">

      {/* Locality & Distance */}
      <div className="mt-2.5 flex items-center justify-between rounded-lg bg-slate-50 border border-slate-100 px-3 py-2 text-xs">
        <span className="text-slate-500 font-medium">Nearest Locality</span>
        <span className="font-semibold text-slate-800">
          {cell.nearest_osm_place_name || "Surat SMC"}
          {cell.nearest_osm_distance_m !== null && (
            <span className="ml-1 text-slate-400 font-normal font-mono">
              ({cell.nearest_osm_distance_m}m)
            </span>
          )}
        </span>
      </div>

      {/* Latest Scene Disclaimer Banner */}
      {activeLayerMode === "latest_scene" && (
        <div className="mt-2.5 rounded-lg border border-teal-200 bg-teal-50/80 p-2.5 text-[10.5px] leading-snug text-teal-950">
          <strong>Single-Scene Overpass:</strong> Single-scene observation, not part of HPI or the 223 chronic hotspots, not comparable to seasonal composites.
        </div>
      )}

      {/* Active Temperature Hero Card */}
      <div className="mt-3 rounded-xl border border-slate-200/80 bg-slate-50/80 p-3 shadow-2xs">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
            {activeObsDisplay.title}
          </span>
          {activeLayerMode === "latest_scene" ? (
            <span className="rounded bg-teal-100 px-1.5 py-0.2 text-[9px] font-bold text-teal-900 font-mono">
              NRT Single Scene
            </span>
          ) : activeLayerMode === "lst" ? (
            <span className="rounded bg-amber-100 px-1.5 py-0.2 text-[9px] font-bold text-amber-900 font-mono">
              {seasonLabel} Layer
            </span>
          ) : (
            <span className="rounded bg-slate-200 px-1.5 py-0.2 text-[9px] font-bold text-slate-700 font-mono">
              HPI Baseline
            </span>
          )}
        </div>

        <div className="mt-1 flex items-baseline gap-2">
          <span
            className={`font-mono font-extrabold tabular-nums ${activeObsDisplay.isMasked && activeLayerMode === "lst" ? "text-sm text-amber-800" : "text-2xl"}`}
            style={{ color: !activeObsDisplay.isMasked ? activeObsDisplay.color : undefined }}
          >
            {activeObsDisplay.value}
          </span>
          {!activeObsDisplay.isMasked && (
            <span className="text-xs text-slate-500">radiant skin temp (T<sub>skin</sub>)</span>
          )}
        </div>
        <div className="mt-0.5 text-[10.5px] text-slate-500 leading-tight">
          {activeObsDisplay.subtext}
        </div>
      </div>

      {/* Main Score Hero Card */}
      <div className="mt-3 rounded-xl border border-slate-200/90 bg-white p-3.5 shadow-2xs">
        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
              Heat Priority Index
            </span>
            {activeLayerMode === "latest_scene" && (
              <span className="text-[10px] font-bold text-amber-800">
                Frozen HPI (multi-year, not from this scene)
              </span>
            )}
          </div>
          <span
            className={`rounded-md border px-2 py-0.5 text-[10px] font-bold ${persistenceBadge.bg} ${persistenceBadge.text} ${persistenceBadge.border}`}
          >
            {persistenceBadge.label}
          </span>
        </div>

        <div className="mt-2 flex items-baseline gap-2">
          {isUnavailable ? (
            <div className="text-2xl font-bold text-slate-400 font-mono">
              UNAVAILABLE
            </div>
          ) : (
            <>
              <span
                className="text-3xl font-extrabold font-mono tabular-nums tracking-tight"
                style={{ color: hpiColor }}
              >
                {cell.heat_priority_score?.toFixed(1)}
              </span>
              <span className="text-sm font-medium text-slate-400 font-mono">/ 100</span>
            </>
          )}
        </div>

        {/* Missing-Data / Exclusion Warning */}
        {isUnavailable && (
          <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-900">
            <div className="flex items-center gap-1.5 font-bold">
              <svg className="h-4 w-4 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>{eligibilityInfo.label}</span>
            </div>
            <p className="mt-1 text-[11px] leading-relaxed text-amber-800">
              {eligibilityInfo.explanation}
            </p>
          </div>
        )}
      </div>

      {/* Component Layers Breakdown */}
      {!isUnavailable && (
        <div className="mt-3 space-y-2 rounded-xl border border-slate-200/90 bg-white p-3 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-500">
            <span>HPI Component Breakdown</span>
            {cell.is_chronic_hotspot && (
              <button
                type="button"
                onClick={() => setShowHistory((prev) => !prev)}
                className="text-[10px] text-teal-700 hover:text-teal-900 font-bold underline cursor-pointer"
              >
                {showHistory ? "Hide 5-Yr History" : "View 5-Yr Summer History"}
              </button>
            )}
          </div>

          {/* 1. Thermal Severity */}
          <div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-600 font-medium">Thermal Severity (40%)</span>
              <span className="font-mono font-bold text-slate-800 tabular-nums">
                {((cell.thermal_severity_component ?? 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full bg-red-600 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, (cell.thermal_severity_component ?? 0) * 100)}%` }}
              />
            </div>
          </div>

          {/* 2. Persistence */}
          <div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-600 font-medium">Persistence (30%)</span>
              <span className="font-mono font-bold text-slate-800 tabular-nums">
                {((cell.persistence_component ?? 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full bg-orange-500 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, (cell.persistence_component ?? 0) * 100)}%` }}
              />
            </div>
          </div>

          {/* 3. Vegetation Deficit */}
          <div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-600 font-medium">Vegetation Deficit (15%)</span>
              <span className="font-mono font-bold text-slate-800 tabular-nums">
                {((cell.vegetation_deficit_component ?? 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full bg-emerald-600 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, (cell.vegetation_deficit_component ?? 0) * 100)}%` }}
              />
            </div>
          </div>

          {/* 4. Built Density */}
          <div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-600 font-medium">Built-Up Density (15%)</span>
              <span className="font-mono font-bold text-slate-800 tabular-nums">
                {((cell.built_density_component ?? 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full bg-amber-600 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, (cell.built_density_component ?? 0) * 100)}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Multi-Year Summer Persistence History Drawer */}
      {(showHistory || cell.is_chronic_hotspot) && cell.summer_history && cell.summer_history.length > 0 && (
        <div className="mt-3 rounded-xl border border-red-200 bg-red-50/60 p-3 text-xs">
          <div className="flex items-center justify-between font-bold text-red-900 border-b border-red-200 pb-1.5 mb-2">
            <span>🔥 Multi-Year Summer Persistence History</span>
            <span className="text-[10px] font-mono text-red-700">2022–2026</span>
          </div>
          <div className="space-y-1">
            {cell.summer_history.map((sh) => (
              <div key={sh.year} className="flex items-center justify-between text-[11px]">
                <span className="font-semibold text-slate-700">Summer {sh.year}</span>
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-slate-900 tabular-nums">
                    {sh.observed_lst_c !== null ? `${sh.observed_lst_c.toFixed(1)}°C` : "N/A"}
                  </span>
                  {sh.is_extreme ? (
                    <span className="rounded bg-red-200 px-1 py-0.2 text-[9px] font-bold text-red-800">
                      Extreme
                    </span>
                  ) : (
                    <span className="rounded bg-slate-200 px-1 py-0.2 text-[9px] font-medium text-slate-600">
                      Normal
                    </span>
                  )}
                  {sh.obs_count && (
                    <span className="text-[9.5px] text-slate-500 font-mono">({sh.obs_count} scenes)</span>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-2 pt-1.5 border-t border-red-200 text-[10px] text-red-800 leading-tight">
            <strong>Chronic Criterion:</strong> Recurrence frequency ≥50% across valid seasons, ≥3 hot seasons, ≥2 distinct years.
          </div>
        </div>
      )}

      {/* 4-Season Observation Table */}
      <div className="mt-3 rounded-xl border border-slate-200/90 bg-white p-2.5 shadow-2xs">
        <div className="flex items-center justify-between pb-1.5 border-b border-slate-100 mb-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
            Seasonal Observations Matrix
          </span>
          <span className="text-[10px] text-slate-400 font-mono">100m grid cell</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-[11px]">
            <thead>
              <tr className="border-b border-slate-100 text-[10px] uppercase font-semibold text-slate-400">
                <th className="py-1">Season</th>
                <th className="py-1 text-right">LST (°C)</th>
                <th className="py-1 text-right">Diff vs Summer</th>
                <th className="py-1 text-right">Quality / Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-sans">
              {seasonalRows.map((row) => {
                const isActive = activeSeason === row.label.split(" ")[0].toLowerCase();
                return (
                  <tr
                    key={row.label}
                    className={isActive ? "bg-amber-50/70 font-semibold" : ""}
                  >
                    <td className="py-1.5 text-slate-800">
                      {row.label}
                      {isActive && (
                        <span className="ml-1 text-[9px] rounded bg-amber-200 px-1 py-0.2 font-bold text-amber-900 font-mono">
                          Active
                        </span>
                      )}
                    </td>
                    <td className="py-1.5 text-right font-mono font-bold tabular-nums">
                      {row.temp !== null ? (
                        <span style={{ color: getLSTColor(row.temp) }}>
                          {row.temp.toFixed(1)}°C
                        </span>
                      ) : (
                        <span className="text-amber-700 text-[10px]">Cloud-masked</span>
                      )}
                    </td>
                    <td className="py-1.5 text-right font-mono text-slate-700 tabular-nums">
                      {row.delta !== undefined && row.delta !== null
                        ? `${row.delta > 0 ? "+" : ""}${row.delta.toFixed(1)}°C`
                        : "—"}
                    </td>
                    <td className="py-1.5 text-right text-[10px] text-slate-500">
                      {row.temp !== null ? (
                        <span className="text-emerald-700 font-medium">
                          {row.obsCount ? `Valid (${row.obsCount} overpasses)` : "Valid"}
                        </span>
                      ) : (
                        <span className="text-amber-700 italic">
                          Cloud-masked
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="mt-1.5 text-[9.5px] text-slate-500 italic border-t border-slate-100 pt-1">
          * latest available composite per season (mixed years: Post-Monsoon 2025). Paired differences shown only where both seasons have valid observations.
        </div>
      </div>

      {/* Observations and Quality Metadata */}
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div
          className="rounded-xl bg-slate-50 border border-slate-100 p-2.5"
          title="Heuristic quality index from QA/observation support, not a probability of correctness"
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-bold tracking-wide text-slate-500">
              Observational Quality
            </span>
            <span className="text-[9px] text-slate-400 italic">Heuristic C_i</span>
          </div>
          <div
            className="mt-0.5 text-sm font-bold"
            style={{ color: getConfidenceColor(cell.confidence_tier) }}
          >
            {cell.confidence_tier || "N/A"}{" "}
            {cell.confidence_index !== null && (
              <span className="text-[11px] font-normal text-slate-500 font-mono tabular-nums">
                (C_i: {cell.confidence_index.toFixed(2)})
              </span>
            )}
          </div>
          <div className="mt-1 text-[9px] text-slate-500 leading-tight">
            Heuristic quality index from QA/observation support, not a probability of correctness
          </div>
        </div>

        <div className="rounded-xl bg-slate-50 border border-slate-100 p-2.5">
          <span className="text-[10px] uppercase font-bold tracking-wide text-slate-500">
            Hotspot Frequency
          </span>
          <div className="mt-0.5 text-sm font-bold text-slate-900 font-mono tabular-nums">
            {cell.hotspot_frequency !== null
              ? `${(cell.hotspot_frequency * 100).toFixed(0)}%`
              : "0%"}
          </div>
          <div className="mt-1 text-[9px] text-slate-500 leading-tight">
            Summer overpass recurrence
          </div>
        </div>

        <div className="rounded-xl bg-slate-50 border border-slate-100 p-2.5 col-span-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-bold tracking-wide text-slate-500">
              Optical Reconstruction Flag
            </span>
            <span className="text-xs font-semibold text-slate-800">
              {opticalInfo.label}
            </span>
          </div>
          {opticalInfo.isImputed && (
            <div className="mt-1 text-[9.5px] text-teal-800">
              {opticalInfo.description}
            </div>
          )}
        </div>
      </div>

      {/* Dynamic World Land Cover Composition & Uncertainty Panel */}
      <div className="mt-3 rounded-xl border border-teal-200/90 bg-teal-50/40 p-3 text-xs shadow-2xs">
        <div className="flex items-center justify-between pb-1.5 border-b border-teal-200/70 mb-2">
          <div className="flex items-center gap-1.5">
            <span className="text-base">🌍</span>
            <span className="text-[11px] font-bold uppercase tracking-wider text-teal-950">
              Dynamic World Land Cover (10m LULC)
            </span>
          </div>
          <span className="rounded bg-teal-100 px-1.5 py-0.5 text-[9.5px] font-semibold text-teal-800">
            Sentinel-2 Model
          </span>
        </div>

        {landcoverLoading && (
          <div className="py-2 text-center text-[11px] text-teal-700 font-medium animate-pulse">
            Loading satellite land-cover observations…
          </div>
        )}

        {!landcoverLoading && !landcoverData && (
          <div className="py-1 text-[11px] text-slate-500 italic">
            No seasonal Dynamic World observations recorded for this cell.
          </div>
        )}

        {!landcoverLoading && landcoverData && (
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div className="rounded-lg bg-white p-2 border border-teal-100">
                <span className="text-[10px] text-slate-500 uppercase font-bold">Top Land Cover</span>
                <div className="mt-0.5 text-sm font-bold capitalize text-slate-900 flex items-center gap-1.5">
                  <span
                    className="inline-block h-3 w-3 rounded-xs shrink-0"
                    style={{
                      backgroundColor:
                        landcoverData.top_class === "built" ? "#C4281B" :
                        landcoverData.top_class === "trees" ? "#397D49" :
                        landcoverData.top_class === "grass" ? "#88B053" :
                        landcoverData.top_class === "crops" ? "#E49635" :
                        landcoverData.top_class === "water" ? "#419BDF" : "#A59B8F",
                    }}
                  />
                  <span>{landcoverData.top_class || "Unclassified"}</span>
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  Confidence: {landcoverData.confidence !== null ? `${(landcoverData.confidence * 100).toFixed(1)}%` : "N/A"}
                </div>
              </div>

              <div className="rounded-lg bg-white p-2 border border-teal-100">
                <span className="text-[10px] text-slate-500 uppercase font-bold">Diagnostics</span>
                <div className="mt-0.5 text-[11px] font-mono text-slate-800 font-semibold">
                  Entropy: {landcoverData.entropy !== null ? landcoverData.entropy.toFixed(3) : "N/A"}
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  {landcoverData.valid_observation_count} valid overpasses
                </div>
              </div>
            </div>

            {/* 9-Class Probability Bars */}
            <div className="rounded-lg bg-white p-2 border border-teal-100 space-y-1.5">
              <span className="text-[10px] text-slate-500 uppercase font-bold">Class Mean Probabilities</span>
              <div className="grid grid-cols-3 gap-1.5 text-[10px]">
                {Object.entries(landcoverData.probabilities || {}).map(([cls, prob]) => {
                  if (prob === null || prob === undefined || prob < 0.01) return null;
                  const colors: Record<string, string> = {
                    built: "#C4281B",
                    trees: "#397D49",
                    grass: "#88B053",
                    crops: "#E49635",
                    shrub_and_scrub: "#DFC35A",
                    water: "#419BDF",
                    bare: "#A59B8F",
                    flooded_vegetation: "#7A87C6",
                    snow_and_ice: "#B39FE1",
                  };
                  return (
                    <div key={cls} className="flex items-center justify-between font-mono bg-slate-50 px-1.5 py-0.5 rounded">
                      <span className="capitalize text-slate-700 truncate mr-1" style={{ color: colors[cls] || "#334155" }}>
                        {cls.replace("_", " ").slice(0, 7)}
                      </span>
                      <span className="font-bold text-slate-900">{(prob * 100).toFixed(0)}%</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Suitability Assessment */}
            {landcoverData.suitability && (
              <div className="rounded-lg bg-emerald-50/80 p-2 border border-emerald-200 text-[10px] space-y-1">
                <div className="flex items-center justify-between font-semibold text-emerald-950">
                  <span>Rule: {landcoverData.suitability.rule_fired}</span>
                  <span className="font-mono text-[9px] px-1 py-0.2 bg-emerald-200 text-emerald-900 rounded">
                    {landcoverData.suitability.screening_status}
                  </span>
                </div>
                <p className="text-emerald-900 leading-snug">
                  {landcoverData.suitability.screening_reason}
                </p>
                <div className="pt-1 border-t border-emerald-200/60 text-[9px] text-emerald-800 font-mono">
                  {landcoverData.suitability.scientific_notice}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Field Survey Prerequisites Section */}
      <div className="rounded-xl border border-amber-200/90 bg-amber-50/50 p-3 text-xs space-y-1.5 shadow-2xs">
        <div className="flex items-center gap-1.5 font-bold text-amber-950 text-[11px] uppercase tracking-wider border-b border-amber-200/60 pb-1">
          <span>📋</span>
          <span>Pre-Implementation Field Verification</span>
        </div>
        <ul className="text-[10px] text-amber-900 list-disc list-inside space-y-0.5 leading-snug">
          <li><strong>Structural Slab Clearance:</strong> Dead/live load test required before roof retrofits.</li>
          <li><strong>Ownership &amp; Legal Tenure:</strong> Unverified via satellite; municipal clearance required.</li>
          <li><strong>Road &amp; Utility Setbacks:</strong> Underground pipes and cables must be surveyed before tree digging.</li>
        </ul>
      </div>

      {/* Satellite Provenance & Sensor Data Section */}
      <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3 text-xs space-y-1.5 shadow-2xs">
        <div className="flex items-center gap-1.5 font-bold text-slate-900 text-[11px] uppercase tracking-wider border-b border-slate-200/60 pb-1">
          <span>🛰️</span>
          <span>Sensor Calibration &amp; Evidence</span>
        </div>
        <div className="grid grid-cols-2 gap-1.5 text-[9.5px] font-mono text-slate-600">
          <div>Thermal: Landsat 8/9 TIRS</div>
          <div>LULC: Sentinel-2 10m</div>
          <div>CRS: EPSG:32643 Planar</div>
          <div>Cell Area: 9,273 m² (0.93 ha)</div>
        </div>
      </div>

      {/* Methodological Context & Physical Distinctions */}
      <div className="border-t border-slate-100 pt-2 text-[10px] leading-tight text-slate-500 space-y-1.5">
        <div>
          <strong>Grid &amp; Resolution:</strong> Nominal 100 m regular grid (0.000898° ≈ 93.2 m × 99.5 m, true planar projected area: mean 9,282 m² / 0.928 ha, range 9,273–9,291 m² in UTM 43N).
        </div>
        <div>
          <strong>Temperature Distinction:</strong> Land Surface Temperature (LST) is radiant surface skin temperature (T<sub>skin</sub>) at ~10:30 local solar time, distinct from ambient 2 m air temperature (T<sub>air</sub>) and indoor temperature. Ambient 2m air cooling is unmodeled.
        </div>
      </div>
    </div>
  </aside>
  );
}
