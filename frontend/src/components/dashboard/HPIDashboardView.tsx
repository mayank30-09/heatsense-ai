import { useEffect, useState } from "react";
import type { HeatPrioritySummary } from "../../types/heatPriority";
import { fetchHeatPrioritySummary } from "../../services/heatPriorityApi";
import ScienceGlossaryModal from "../common/ScienceGlossaryModal";

interface HPIDashboardViewProps {
  onSwitchToMap: () => void;
}

export default function HPIDashboardView({ onSwitchToMap }: HPIDashboardViewProps) {
  const [summary, setSummary] = useState<HeatPrioritySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showGlossary, setShowGlossary] = useState(false);

  const loadSummary = () => {
    setLoading(true);
    fetchHeatPrioritySummary()
      .then((data) => {
        setSummary(data);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load summary statistics");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    loadSummary();
  }, []);

  const norm = summary?.normalization_constants;
  const tMin = norm?.t_min_c ?? 30.0;
  const tMax = norm?.t_max_c ?? 50.0;
  const ndviMin = norm?.ndvi_min ?? 0.05;
  const ndviTarget = norm?.ndvi_target ?? 0.45;
  const ndbiMin = norm?.ndbi_min ?? -0.25;
  const ndbiMax = norm?.ndbi_max ?? 0.15;
  const dataRange = norm?.data_observation_years ?? "2021–2026 (Summer, Winter, Monsoon); 2021–2025 (Post-Monsoon)";
  const overpassTime = norm?.overpass_solar_time ?? "~10:30 local solar time (about 11:00 IST)";

  return (
    <div className="flex flex-col gap-6">
      {/* Executive Hero Banner */}
      <div className="rounded-2xl border border-slate-800/90 bg-slate-900 p-7 text-white shadow-elevated relative overflow-hidden">
        {/* Subtle background geospatial grid lines */}
        <div
          className="absolute inset-0 opacity-[0.03] pointer-events-none"
          style={{
            backgroundImage: "radial-gradient(#2dd4bf 1px, transparent 1px), radial-gradient(#2dd4bf 1px, #0f172a 1px)",
            backgroundSize: "24px 24px",
            backgroundPosition: "0 0, 12px 12px",
          }}
        />

        <div className="relative flex flex-wrap items-center justify-between gap-6 z-10">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="rounded-full bg-teal-500/15 px-3 py-0.5 text-xs font-bold text-teal-300 border border-teal-500/30 font-mono">
                Stage C Specification
              </span>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
                Operational Summer 2026 Release
              </span>
              <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-[11px] font-mono text-slate-300 border border-slate-700">
                Surat WRS 148/45
              </span>
            </div>
            <h2 className="mt-3 text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Surat Municipal Corporation · Heat Priority Index (HPI)
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-300">
              Authoritative 100m analytical grid multi-criteria prioritization combining Landsat 8/9 thermal severity,
              multi-year seasonal persistence ({dataRange}), Landsat Level-2 surface reflectance vegetation deficit, and built-up density.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0 flex-wrap">
            <button
              type="button"
              onClick={() => setShowGlossary(true)}
              className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 px-4 py-2.5 text-xs font-semibold text-slate-200 hover:bg-slate-700/80 hover:text-white transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              <span>📖</span>
              <span>Science Glossary</span>
            </button>

            <button
              type="button"
              onClick={onSwitchToMap}
              className="flex items-center gap-2 rounded-xl bg-teal-600 px-5 py-2.5 text-xs font-bold text-white shadow-md hover:bg-teal-500 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-teal-400 focus:ring-offset-2 focus:ring-offset-slate-900"
            >
              <span>Explore Interactive Heat Map</span>
              <span aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      </div>

      {/* Loading Skeleton */}
      {loading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
              <div className="skeleton-box h-3 w-28" />
              <div className="skeleton-box h-9 w-36" />
              <div className="skeleton-box h-3 w-48" />
            </div>
          ))}
        </div>
      )}

      {/* Error State with Retry Button */}
      {error && !loading && (
        <div className="error-state-panel text-sm p-8">
          <div className="font-bold text-base text-red-900 mb-1">Failed to Load Dashboard Data</div>
          <p className="text-red-700 max-w-md">{error}</p>
          <button
            type="button"
            onClick={loadSummary}
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-red-700 px-4 py-2 text-xs font-bold text-white hover:bg-red-800 cursor-pointer shadow-xs transition-all focus:outline-none focus:ring-2 focus:ring-red-500"
          >
            <span>↻</span>
            <span>Retry Connection</span>
          </button>
        </div>
      )}

      {/* Primary KPI Grid */}
      {summary && !loading && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* 1. Total Grid Cells */}
            <div className="decision-card p-5 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Authoritative Grid Cells
                </span>
                <span className="h-2 w-2 rounded-full bg-teal-500" />
              </div>
              <div className="mt-2 text-3xl font-extrabold text-slate-900 font-mono tabular-nums tracking-tight">
                {summary.total_grid_cells.toLocaleString()}
              </div>
              <p className="mt-1.5 text-xs text-slate-600">
                100m planar grid (93.25m × 99.54m = 9,282 m²) · 461.77 km² (99.55% boundary coverage)
              </p>
            </div>

            {/* 2. Mean HPI Score */}
            <div className="decision-card p-5 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Mean Heat Priority Score
                </span>
                <span className="text-xs font-bold text-amber-600 bg-amber-50 px-2 py-0.5 rounded font-mono">
                  Scale 0–100
                </span>
              </div>
              <div className="mt-2 text-3xl font-extrabold text-amber-600 font-mono tabular-nums tracking-tight">
                {summary.mean_hpi?.toFixed(1) ?? "N/A"}
              </div>
              <p className="mt-1.5 text-xs text-slate-600 font-mono">
                Range: {summary.min_hpi?.toFixed(1)} to {summary.max_hpi?.toFixed(1)}
              </p>
            </div>

            {/* 3. Chronic Hotspots */}
            <div className="decision-card border-red-200/90 bg-red-50/30 p-5 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-red-700">
                  Chronic Hotspots
                </span>
                <span className="inline-flex items-center justify-center h-4 w-4 rounded-full bg-red-600 text-white text-[10px] font-bold">
                  ◎
                </span>
              </div>
              <div className="mt-2 text-3xl font-extrabold text-red-700 font-mono tabular-nums tracking-tight">
                {summary.chronic_hotspots_count}
              </div>
              <p className="mt-1.5 text-xs text-red-700/80 font-medium">
                Persistent multi-year extreme heat zones
              </p>
            </div>

            {/* 4. Observational Quality */}
            <div
              className="decision-card p-5 relative overflow-hidden"
              title="Heuristic quality index from QA/observation support, not a probability of correctness"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Observational Quality
                </span>
                <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded font-mono">
                  Tier: HIGH
                </span>
              </div>
              <div className="mt-2 text-2xl font-extrabold text-emerald-700 font-mono tabular-nums tracking-tight">
                {(summary.confidence_tier_counts["HIGH"] || 0).toLocaleString()} of {summary.total_grid_cells.toLocaleString()}
              </div>
              <p className="mt-1.5 text-xs text-slate-600 leading-snug" title="Heuristic quality index from QA/observation support, not a probability of correctness">
                Cells meeting observational-quality criteria (C_i &ge; 0.85): {(summary.confidence_tier_counts["HIGH"] || 0).toLocaleString()} of {summary.total_grid_cells.toLocaleString()}
              </p>
            </div>
          </div>

          {/* Component Weights and Persistence Distributions */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* HPI Mathematical Formulation Card */}
            <div className="decision-card p-6">
              <div className="flex items-center justify-between mb-5 pb-3 border-b border-slate-100">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 font-mono">
                    Stage C Component Weights &amp; Normalization Bounds
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Additive linear multi-criteria score (0–100 scale)
                  </p>
                </div>
                <span className="font-mono text-xs font-semibold text-slate-500 bg-slate-50 border border-slate-200 px-2 py-1 rounded">
                  {overpassTime}
                </span>
              </div>

              <div className="space-y-4 text-xs">
                {/* Thermal Severity */}
                <div className="rounded-xl bg-slate-50/70 border border-slate-100 p-3">
                  <div className="flex justify-between font-semibold">
                    <span className="text-slate-800">Thermal Severity (w_T)</span>
                    <span className="font-mono font-bold text-red-600 tabular-nums">40.0%</span>
                  </div>
                  <div className="mt-2 h-2 w-full rounded-full bg-slate-200 overflow-hidden">
                    <div className="h-full bg-red-600 rounded-full transition-all duration-500" style={{ width: "40%" }} />
                  </div>
                  <p className="mt-2 text-[11px] text-slate-500 leading-relaxed">
                    Normalized observed summer LST over canonical [{tMin.toFixed(1)}°C, {tMax.toFixed(1)}°C] domain baseline.
                  </p>
                </div>

                {/* Heat Persistence */}
                <div className="rounded-xl bg-slate-50/70 border border-slate-100 p-3">
                  <div className="flex justify-between font-semibold">
                    <span className="text-slate-800">Heat Persistence (w_P)</span>
                    <span className="font-mono font-bold text-orange-600 tabular-nums">30.0%</span>
                  </div>
                  <div className="mt-2 h-2 w-full rounded-full bg-slate-200 overflow-hidden">
                    <div className="h-full bg-orange-500 rounded-full transition-all duration-500" style={{ width: "30%" }} />
                  </div>
                  <p className="mt-2 text-[11px] text-slate-500 leading-relaxed">
                    Multi-temporal hotspot recurrence frequency across {dataRange}.
                  </p>
                </div>

                {/* Vegetation Deficit */}
                <div className="rounded-xl bg-slate-50/70 border border-slate-100 p-3">
                  <div className="flex justify-between font-semibold">
                    <span className="text-slate-800">Vegetation Deficit (w_V)</span>
                    <span className="font-mono font-bold text-emerald-600 tabular-nums">15.0%</span>
                  </div>
                  <div className="mt-2 h-2 w-full rounded-full bg-slate-200 overflow-hidden">
                    <div className="h-full bg-emerald-600 rounded-full transition-all duration-500" style={{ width: "15%" }} />
                  </div>
                  <p className="mt-2 text-[11px] text-slate-500 leading-relaxed">
                    NDVI deficit normalized over [{ndviMin.toFixed(2)}, {ndviTarget.toFixed(2)}] urban canopy target.
                  </p>
                </div>

                {/* Built-Up Density */}
                <div className="rounded-xl bg-slate-50/70 border border-slate-100 p-3">
                  <div className="flex justify-between font-semibold">
                    <span className="text-slate-800">Built-Up Density (w_B)</span>
                    <span className="font-mono font-bold text-amber-600 tabular-nums">15.0%</span>
                  </div>
                  <div className="mt-2 h-2 w-full rounded-full bg-slate-200 overflow-hidden">
                    <div className="h-full bg-amber-600 rounded-full transition-all duration-500" style={{ width: "15%" }} />
                  </div>
                  <p className="mt-2 text-[11px] text-slate-500 leading-relaxed">
                    NDBI density normalized over [{ndbiMin.toFixed(2)}, {ndbiMax.toFixed(2)}] impervious ceiling.
                  </p>
                </div>
              </div>
            </div>

            {/* Persistence Tiers Breakdown */}
            <div className="decision-card p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-5 pb-3 border-b border-slate-100">
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 font-mono">
                      Multi-Year Persistence Tier Breakdown
                    </h3>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      Recurrence frequency across multi-season Landsat overpasses
                    </p>
                  </div>
                  <span className="font-mono text-xs font-semibold text-slate-500 bg-slate-50 border border-slate-200 px-2 py-1 rounded">
                    {summary.total_grid_cells.toLocaleString()} Cells
                  </span>
                </div>

                <div className="space-y-4 text-xs">
                  {Object.entries(summary.persistence_tier_counts).map(([tier, count]) => {
                    const percentage = ((count / summary.total_grid_cells) * 100).toFixed(1);
                    const pctNum = Number(percentage);
                    return (
                      <div key={tier} className="border-b border-slate-100 pb-3 last:border-b-0 last:pb-0">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2.5">
                            <span
                              className={`h-3 w-3 rounded-full ${
                                tier === "chronic_hotspot"
                                  ? "bg-red-600 ring-2 ring-red-100"
                                  : tier === "frequent_hotspot"
                                  ? "bg-orange-500 ring-2 ring-orange-100"
                                  : tier === "occasional_hotspot"
                                  ? "bg-amber-500 ring-2 ring-amber-100"
                                  : tier === "transient_extreme"
                                  ? "bg-purple-500 ring-2 ring-purple-100"
                                  : "bg-slate-400 ring-2 ring-slate-100"
                              }`}
                            />
                            <span className="font-semibold text-slate-800 capitalize text-[13px]">
                              {tier.replace("_", " ")}
                            </span>
                          </div>
                          <div className="text-right tabular-nums">
                            <span className="font-mono font-bold text-slate-900 text-sm">{count.toLocaleString()}</span>
                            <span className="ml-2 text-slate-500 text-xs font-mono">({percentage}%)</span>
                          </div>
                        </div>
                        <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              tier === "chronic_hotspot"
                                ? "bg-red-600"
                                : tier === "frequent_hotspot"
                                ? "bg-orange-500"
                                : tier === "occasional_hotspot"
                                ? "bg-amber-500"
                                : tier === "transient_extreme"
                                ? "bg-purple-500"
                                : "bg-slate-400"
                            }`}
                            style={{ width: `${Math.min(100, Math.max(1, pctNum))}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="mt-5 pt-3 border-t border-slate-100 text-[11px] text-slate-500 flex items-center justify-between">
                <span>Methodology: Pixel-wise frequency thresholding</span>
                <span className="font-mono text-teal-700 font-semibold">SMC Surat Domain</span>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Science Glossary Modal */}
      <ScienceGlossaryModal
        isOpen={showGlossary}
        onClose={() => setShowGlossary(false)}
      />
    </div>
  );
}
