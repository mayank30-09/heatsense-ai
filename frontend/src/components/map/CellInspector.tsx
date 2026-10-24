import { useEffect } from "react";
import type { GridCellScoreItem } from "../../types/heatPriority";
import {
  getConfidenceColor,
  getEligibilityInfo,
  getHPIColor,
  getOpticalImputationLabel,
  getPersistenceBadge,
} from "../../utils/hpiColorScales";

interface CellInspectorProps {
  cell: GridCellScoreItem | null;
  onClose: () => void;
}

export default function CellInspector({ cell, onClose }: CellInspectorProps) {
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

  return (
    <aside
      className="pointer-events-auto absolute right-3 top-3 z-[1000] w-88 max-h-[85vh] overflow-y-auto rounded-xl border border-slate-200/90 bg-white/95 p-4 shadow-xl backdrop-blur transition-all duration-200"
      aria-label="Grid cell details"
    >
      {/* Header with Pixel ID and Close Button */}
      <div className="flex items-start justify-between border-b border-slate-100 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Analytical Grid Cell
            </span>
            {cell.is_chronic_hotspot && (
              <span className="rounded-full bg-red-600 px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wide text-white shadow-sm">
                Chronic Hotspot
              </span>
            )}
          </div>
          <h3 className="mt-0.5 text-lg font-bold text-slate-900 font-mono">
            {cell.pixel_id}
          </h3>
          <p className="text-[11px] text-slate-500">
            Row {cell.row_idx} · Col {cell.col_idx} · {cell.latitude.toFixed(5)}°N, {cell.longitude.toFixed(5)}°E
          </p>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
          aria-label="Close inspector"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Locality & Distance */}
      <div className="mt-3 flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs">
        <span className="text-slate-500">Nearest Locality</span>
        <span className="font-semibold text-slate-800">
          {cell.nearest_osm_place_name || "Surat SMC"}
          {cell.nearest_osm_distance_m !== null && (
            <span className="ml-1 text-slate-400 font-normal">
              ({cell.nearest_osm_distance_m}m)
            </span>
          )}
        </span>
      </div>

      {/* Main Score Hero Card */}
      <div className="mt-3 rounded-lg border border-slate-100 p-3.5 shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
            Heat Priority Index
          </span>
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
                className="text-3xl font-extrabold font-mono"
                style={{ color: hpiColor }}
              >
                {cell.heat_priority_score?.toFixed(1)}
              </span>
              <span className="text-sm font-medium text-slate-400">/ 100</span>
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
        <div className="mt-3 space-y-2 rounded-lg border border-slate-100 p-3 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            HPI Component Breakdown
          </div>

          {/* 1. Thermal Severity */}
          <div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-600 font-medium">Thermal Severity (40%)</span>
              <span className="font-mono font-bold text-slate-800">
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
              <span className="font-mono font-bold text-slate-800">
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
              <span className="font-mono font-bold text-slate-800">
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
              <span className="font-mono font-bold text-slate-800">
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

      {/* Observations and Quality Metadata */}
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg bg-slate-50 p-2.5">
          <span className="text-[10px] uppercase font-bold tracking-wide text-slate-400">
            Observed Summer LST
          </span>
          <div className="mt-0.5 text-sm font-bold text-slate-900 font-mono">
            {cell.observed_lst_c !== null ? `${cell.observed_lst_c.toFixed(1)}°C` : "N/A"}
          </div>
        </div>

        <div className="rounded-lg bg-slate-50 p-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-bold tracking-wide text-slate-400">
              Confidence Tier
            </span>
            <span className="text-[9px] text-slate-400 italic">Heuristic</span>
          </div>
          <div
            className="mt-0.5 text-sm font-bold"
            style={{ color: getConfidenceColor(cell.confidence_tier) }}
          >
            {cell.confidence_tier || "N/A"}{" "}
            {cell.confidence_index !== null && (
              <span className="text-[11px] font-normal text-slate-500 font-mono">
                ({cell.confidence_index.toFixed(2)})
              </span>
            )}
          </div>
          <div className="mt-1 text-[9px] text-slate-400 italic leading-tight">
            Confidence index is a heuristic, not a calibrated probability.
          </div>
        </div>

        <div className="rounded-lg bg-slate-50 p-2.5">
          <span className="text-[10px] uppercase font-bold tracking-wide text-slate-400">
            Hotspot Frequency
          </span>
          <div className="mt-0.5 text-sm font-bold text-slate-900 font-mono">
            {cell.hotspot_frequency !== null
              ? `${(cell.hotspot_frequency * 100).toFixed(0)}%`
              : "0%"}
          </div>
        </div>

        <div className="rounded-lg bg-slate-50 p-2.5">
          <span className="text-[10px] uppercase font-bold tracking-wide text-slate-400">
            Optical Flag
          </span>
          <div className="mt-0.5 text-xs font-semibold text-slate-800">
            {opticalInfo.label}
          </div>
        </div>
      </div>

      {/* Footnote on Optical Reconstruction if Imputed */}
      {opticalInfo.isImputed && (
        <div className="mt-2.5 rounded border border-blue-100 bg-blue-50/60 p-2 text-[10px] text-blue-900">
          <strong>Quality Notice:</strong> {opticalInfo.description}.
        </div>
      )}
    </aside>
  );
}
