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
      {/* Top Banner */}
      <div className="rounded-xl border border-slate-700/80 bg-slate-900 p-6 text-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-red-500/20 px-2.5 py-0.5 text-xs font-bold text-red-300 border border-red-500/30">
                Stage C Specification
              </span>
              <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Operational Summer 2026 Release
              </span>
            </div>
            <h2 className="mt-2 text-2xl font-bold tracking-tight text-white">
              Surat Municipal Corporation · Heat Priority Index (HPI)
            </h2>
            <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-300">
              Authoritative 100m analytical grid multi-criteria prioritization combining Landsat 8/9 thermal severity,
              multi-year seasonal persistence ({dataRange}), Landsat Level-2 surface reflectance vegetation deficit, and built-up density.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setShowGlossary(true)}
              className="flex items-center gap-1.5 rounded-lg border border-white/20 bg-white/10 px-4 py-2 text-xs font-semibold text-white hover:bg-white/20 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-white/50"
            >
              <span>📖 Science Glossary</span>
            </button>

            <button
              type="button"
              onClick={onSwitchToMap}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-xs font-bold text-white shadow-xs hover:bg-indigo-500 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2 focus:ring-offset-slate-900"
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
            <div key={i} className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="skeleton-box h-3 w-28 mb-3" />
              <div className="skeleton-box h-8 w-36 mb-2" />
              <div className="skeleton-box h-3 w-44" />
            </div>
          ))}
        </div>
      )}

      {/* Error State with Retry Button */}
      {error && !loading && (
        <div className="error-state-panel text-sm">
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
            <div className="decision-card p-5">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Authoritative Grid Cells
              </span>
              <div className="mt-1.5 text-3xl font-extrabold text-slate-900 font-mono tabular-nums">
                {summary.total_grid_cells.toLocaleString()}
              </div>
              <p className="mt-1 text-xs text-slate-600">
                100m resolution · SMC boundary conservation
              </p>
            </div>

            <div className="decision-card p-5">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Mean Heat Priority Score
              </span>
              <div className="mt-1.5 text-3xl font-extrabold text-amber-600 font-mono tabular-nums">
                {summary.mean_hpi?.toFixed(1) ?? "N/A"}
              </div>
              <p className="mt-1 text-xs text-slate-600">
                Range: {summary.min_hpi?.toFixed(1)} to {summary.max_hpi?.toFixed(1)}
              </p>
            </div>

            <div className="decision-card border-red-200 bg-red-50/40 p-5">
              <span className="text-xs font-bold uppercase tracking-wider text-red-700">
                Chronic Hotspots
              </span>
              <div className="mt-1.5 text-3xl font-extrabold text-red-700 font-mono tabular-nums">
                {summary.chronic_hotspots_count}
              </div>
              <p className="mt-1 text-xs text-red-600">
                Persistent multi-year extreme heat zones
              </p>
            </div>

            <div
              className="decision-card p-5"
              title="Heuristic quality index from QA/observation support, not a probability of correctness"
            >
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Observational Quality
              </span>
              <div className="mt-1.5 text-2xl font-extrabold text-emerald-600 font-mono tabular-nums">
                {(summary.confidence_tier_counts["HIGH"] || 0).toLocaleString()} of {summary.total_grid_cells.toLocaleString()}
              </div>
              <p className="mt-1 text-xs text-slate-600" title="Heuristic quality index from QA/observation support, not a probability of correctness">
                Cells meeting observational-quality criteria (C_i &ge; 0.85): {(summary.confidence_tier_counts["HIGH"] || 0).toLocaleString()} of {summary.total_grid_cells.toLocaleString()}
              </p>
            </div>
          </div>

          {/* Component Weights and Persistence Distributions */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* HPI Mathematical Formulation Card */}
            <div className="decision-card p-5">
              <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  Stage C Component Weights & Normalization Bounds
                </h3>
                <span className="font-mono text-xs font-semibold text-slate-500">
                  {overpassTime}
                </span>
              </div>

              <div className="space-y-4 text-xs">
                <div>
                  <div className="flex justify-between font-semibold">
                    <span className="text-slate-700">Thermal Severity (w_T)</span>
                    <span className="font-mono font-bold text-red-600 tabular-nums">40.0%</span>
                  </div>
                  <div className="mt-1 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full bg-red-600 rounded-full" style={{ width: "40%" }} />
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500">
                    Normalized observed summer LST over canonical [{tMin.toFixed(1)}°C, {tMax.toFixed(1)}°C] domain baseline.
                  </p>
                </div>

                <div>
                  <div className="flex justify-between font-semibold">
                    <span className="text-slate-700">Heat Persistence (w_P)</span>
                    <span className="font-mono font-bold text-orange-600 tabular-nums">30.0%</span>
                  </div>
                  <div className="mt-1 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full bg-orange-500 rounded-full" style={{ width: "30%" }} />
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500">
                    Multi-temporal hotspot recurrence frequency across {dataRange}.
                  </p>
                </div>

                <div>
                  <div className="flex justify-between font-semibold">
                    <span className="text-slate-700">Vegetation Deficit (w_V)</span>
                    <span className="font-mono font-bold text-emerald-600 tabular-nums">15.0%</span>
                  </div>
                  <div className="mt-1 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full bg-emerald-600 rounded-full" style={{ width: "15%" }} />
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500">
                    NDVI deficit normalized over [{ndviMin.toFixed(2)}, {ndviTarget.toFixed(2)}] urban canopy target.
                  </p>
                </div>

                <div>
                  <div className="flex justify-between font-semibold">
                    <span className="text-slate-700">Built-Up Density (w_B)</span>
                    <span className="font-mono font-bold text-amber-600 tabular-nums">15.0%</span>
                  </div>
                  <div className="mt-1 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full bg-amber-600 rounded-full" style={{ width: "15%" }} />
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500">
                    NDBI density normalized over [{ndbiMin.toFixed(2)}, {ndbiMax.toFixed(2)}] impervious ceiling.
                  </p>
                </div>
              </div>
            </div>

            {/* Persistence Tiers Breakdown */}
            <div className="decision-card p-5">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-4 pb-2 border-b border-slate-100">
                Multi-Year Persistence Tier Breakdown
              </h3>

              <div className="space-y-3.5 text-xs">
                {Object.entries(summary.persistence_tier_counts).map(([tier, count]) => {
                  const percentage = ((count / summary.total_grid_cells) * 100).toFixed(1);
                  const pctNum = Number(percentage);
                  return (
                    <div key={tier} className="border-b border-slate-100 pb-2.5 last:border-b-0">
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <span
                            className={`h-2.5 w-2.5 rounded-full ${
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
                          />
                          <span className="font-semibold text-slate-800 capitalize">
                            {tier.replace("_", " ")}
                          </span>
                        </div>
                        <div className="text-right tabular-nums">
                          <span className="font-mono font-bold text-slate-900">{count.toLocaleString()}</span>
                          <span className="ml-2 text-slate-500 text-[11px]">({percentage}%)</span>
                        </div>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${
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
