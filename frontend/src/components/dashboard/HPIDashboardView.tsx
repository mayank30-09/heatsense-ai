import { useEffect, useState } from "react";
import type { HeatPrioritySummary } from "../../types/heatPriority";
import { fetchHeatPrioritySummary } from "../../services/heatPriorityApi";

interface HPIDashboardViewProps {
  onSwitchToMap: () => void;
}

export default function HPIDashboardView({ onSwitchToMap }: HPIDashboardViewProps) {
  const [summary, setSummary] = useState<HeatPrioritySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchHeatPrioritySummary()
      .then((data) => {
        if (!cancelled) {
          setSummary(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load summary statistics");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-6">
      {/* Top Banner */}
      <div className="rounded-xl border border-slate-200 bg-gradient-to-r from-slate-900 to-slate-800 p-6 text-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-red-400">
              Stage C Verified Release · Operational Summer 2026
            </div>
            <h2 className="mt-1 text-2xl font-extrabold text-white">
              Surat Municipal Corporation · Heat Priority Index (HPI)
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-slate-300">
              Authoritative 100m analytical grid multi-criteria prioritization combining Landsat 8/9 thermal severity,
              5-year multi-seasonal persistence, Landsat Level-2 surface reflectance vegetation deficit, and built-up density.
            </p>
          </div>

          <button
            type="button"
            onClick={onSwitchToMap}
            className="flex items-center gap-2 rounded-lg bg-red-600 px-5 py-2.5 text-sm font-bold text-white shadow hover:bg-red-500 transition-all focus:outline-none focus:ring-2 focus:ring-red-400"
          >
            <span>Explore Interactive Heat Map</span>
            <span>→</span>
          </button>
        </div>
      </div>

      {/* Loading & Error States */}
      {loading && (
        <div className="flex items-center justify-center p-12 text-slate-500">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-red-600 border-t-transparent mr-3" />
          <span>Loading Stage C authoritative statistics from PostgreSQL…</span>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <div className="font-bold">Error loading summary:</div>
          <div>{error}</div>
        </div>
      )}

      {/* Primary KPI Grid */}
      {summary && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Authoritative Grid Cells
              </span>
              <div className="mt-1 text-3xl font-extrabold text-slate-900 font-mono">
                {summary.total_grid_cells.toLocaleString()}
              </div>
              <p className="mt-1 text-xs text-slate-500">
                100m resolution · SMC boundary conservation
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Mean Heat Priority Score
              </span>
              <div className="mt-1 text-3xl font-extrabold text-amber-600 font-mono">
                {summary.mean_hpi?.toFixed(1) ?? "N/A"}
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Range: {summary.min_hpi?.toFixed(1)} to {summary.max_hpi?.toFixed(1)}
              </p>
            </div>

            <div className="rounded-xl border border-red-200 bg-red-50/70 p-5 shadow-sm">
              <span className="text-xs font-bold uppercase tracking-wider text-red-700">
                Chronic Hotspots
              </span>
              <div className="mt-1 text-3xl font-extrabold text-red-700 font-mono">
                {summary.chronic_hotspots_count}
              </div>
              <p className="mt-1 text-xs text-red-600">
                Persistent multi-year extreme heat zones
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                High Confidence Rating
              </span>
              <div className="mt-1 text-3xl font-extrabold text-emerald-600 font-mono">
                {((summary.confidence_tier_counts["HIGH"] || 0) / summary.total_grid_cells * 100).toFixed(1)}%
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {(summary.confidence_tier_counts["HIGH"] || 0).toLocaleString()} cells with C_i ≥ 0.85
              </p>
            </div>
          </div>

          {/* Component Weights and Persistence Distributions */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* HPI Mathematical Formulation Card */}
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700 mb-4">
                Stage C Composite Weight Specification
              </h3>

              <div className="space-y-4 text-xs">
                <div>
                  <div className="flex justify-between font-semibold">
                    <span className="text-slate-700">Thermal Severity (w_T)</span>
                    <span className="font-mono text-red-600">40.0%</span>
                  </div>
                  <div className="mt-1 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full bg-red-600 rounded-full" style={{ width: "40%" }} />
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500">Normalized LST over [28°C, 48°C] domain baseline.</p>
                </div>

                <div>
                  <div className="flex justify-between font-semibold">
                    <span className="text-slate-700">Heat Persistence (w_P)</span>
                    <span className="font-mono text-orange-600">30.0%</span>
                  </div>
                  <div className="mt-1 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full bg-orange-500 rounded-full" style={{ width: "30%" }} />
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500">Multi-temporal hotspot frequency across 19 valid seasons.</p>
                </div>

                <div>
                  <div className="flex justify-between font-semibold">
                    <span className="text-slate-700">Vegetation Deficit (w_V)</span>
                    <span className="font-mono text-emerald-600">15.0%</span>
                  </div>
                  <div className="mt-1 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full bg-emerald-600 rounded-full" style={{ width: "15%" }} />
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500">NDVI cooling deficit relative to target threshold.</p>
                </div>

                <div>
                  <div className="flex justify-between font-semibold">
                    <span className="text-slate-700">Built-Up Density (w_B)</span>
                    <span className="font-mono text-amber-600">15.0%</span>
                  </div>
                  <div className="mt-1 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full bg-amber-600 rounded-full" style={{ width: "15%" }} />
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500">NDBI impervious surface heat trap potential.</p>
                </div>
              </div>
            </div>

            {/* Persistence Tiers Breakdown */}
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700 mb-4">
                Multi-Year Persistence Tier Breakdown
              </h3>

              <div className="space-y-3 text-xs">
                {Object.entries(summary.persistence_tier_counts).map(([tier, count]) => {
                  const percentage = ((count / summary.total_grid_cells) * 100).toFixed(1);
                  return (
                    <div key={tier} className="flex items-center justify-between border-b border-slate-50 pb-2">
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
                      <div className="text-right">
                        <span className="font-mono font-bold text-slate-900">{count.toLocaleString()}</span>
                        <span className="ml-2 text-slate-400 text-[11px]">({percentage}%)</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
