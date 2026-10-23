import { useState, useEffect } from "react";
import type {
  RecommendationsResponse,
  RecommendationItem,
} from "../../services/recommendationsApi";
import {
  fetchPolygonRecommendations,
  exportRecommendationsToCsv,
  exportRecommendationsToJson,
} from "../../services/recommendationsApi";

interface Props {
  areaId: string;
  areaName: string;
  geometry: any;
  season?: string;
  year?: number;
  onClose?: () => void;
}

export default function AreaRecommendationsPanel({
  areaId,
  areaName,
  geometry,
  season = "summer",
  year = 2026,
  onClose,
}: Props) {
  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"recommendations" | "assumptions">("recommendations");

  const loadRecommendations = () => {
    if (!geometry) {
      setError("No polygon geometry available for recommendations analysis.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    const controller = new AbortController();

    fetchPolygonRecommendations(geometry, season, year, controller.signal)
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          setError(err instanceof Error ? err.message : "Failed to load recommendations.");
          setLoading(false);
        }
      });

    return () => controller.abort();
  };

  useEffect(() => {
    const cleanup = loadRecommendations();
    return () => {
      if (cleanup) cleanup();
    };
  }, [areaId, season, year, geometry]);

  const handleExportCsv = () => {
    if (!data) return;
    const safeName = areaName.replace(/[^a-zA-Z0-9_-]/g, "_");
    exportRecommendationsToCsv(data, `recommendations_${safeName}_${season}`);
  };

  const handleExportJson = () => {
    if (!data) return;
    const safeName = areaName.replace(/[^a-zA-Z0-9_-]/g, "_");
    exportRecommendationsToJson(data, `recommendations_${safeName}_${season}`);
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3.5 shadow-sm text-slate-800">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-900">
              Intervention Recommendations
            </span>
            <span className="rounded bg-indigo-50 border border-indigo-200 px-1.5 py-0.2 text-[9.5px] font-semibold text-indigo-700">
              MODELLED
            </span>
          </div>
          <div className="text-xs font-semibold text-slate-700 truncate max-w-[240px]">
            {areaName}
          </div>
        </div>

        <div className="flex items-center gap-1">
          {data && (
            <>
              <button
                type="button"
                onClick={handleExportCsv}
                title="Export recommendations to CSV"
                className="rounded bg-slate-100 hover:bg-slate-200 text-slate-700 text-[10px] font-semibold px-2 py-1 cursor-pointer transition-colors"
              >
                CSV
              </button>
              <button
                type="button"
                onClick={handleExportJson}
                title="Export recommendations to JSON"
                className="rounded bg-slate-100 hover:bg-slate-200 text-slate-700 text-[10px] font-semibold px-2 py-1 cursor-pointer transition-colors"
              >
                JSON
              </button>
            </>
          )}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600 text-xs px-1 cursor-pointer"
              aria-label="Close recommendations"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="py-8 text-center space-y-2">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
          <div className="text-xs font-medium text-slate-500">
            Synthesizing Stage D intervention recommendations...
          </div>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="my-3 rounded-md border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-800 space-y-1.5">
          <div className="font-bold flex items-center gap-1">
            <span>⚠️</span>
            <span>Unable to generate recommendations</span>
          </div>
          <div className="text-[11px] leading-snug">{error}</div>
          <button
            type="button"
            onClick={loadRecommendations}
            className="mt-1 rounded bg-rose-100 hover:bg-rose-200 text-rose-900 px-2 py-0.5 text-[10px] font-semibold cursor-pointer transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loaded Content */}
      {data && !loading && (
        <div className="mt-2.5 space-y-3">
          {/* Scientific Caveat Banner */}
          <div className="rounded border border-amber-300 bg-amber-50 p-2 text-[10px] leading-tight text-amber-900 space-y-1">
            <div className="font-bold flex items-center gap-1">
              <span>⚠️</span>
              <span>Evidence-Based Planning Notice</span>
            </div>
            <div>
              {data.caveats[0]}
            </div>
            <div className="font-medium text-amber-950">
              {data.caveats[1]}
            </div>
          </div>

          {/* Special States */}
          {data.polygon_summary.status === "outside_study_area" && (
            <div className="rounded border border-red-300 bg-red-50 p-2.5 text-xs text-red-900">
              <strong>Outside Study Area:</strong> This polygon falls entirely outside the Surat Municipal Corporation boundary. HeatSense AI interventions only cover the canonical 461.63 km² SMC extent.
            </div>
          )}

          {data.polygon_summary.status === "partially_outside" && (
            <div className="rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-[10.5px] text-amber-900">
              ⚠️ <strong>Partially Outside SMC:</strong> {((1 - data.polygon_summary.inside_smc_fraction) * 100).toFixed(0)}% outside. Recommendations apply strictly to the interior {data.polygon_summary.area_km2.toFixed(2)} km².
            </div>
          )}

          {data.polygon_summary.water_warning && (
            <div className="rounded border border-sky-200 bg-sky-50 px-2 py-1.5 text-[10.5px] text-sky-900">
              🌊 <strong>Water Dominance ({((data.polygon_summary.water_fraction) * 100).toFixed(0)}%):</strong> Open water / wetland detected. Pavement and roof interventions are constrained or rejected.
            </div>
          )}

          {data.polygon_summary.status === "no_valid_observations" && (
            <div className="rounded border border-slate-200 bg-slate-50 p-2.5 text-xs text-slate-700">
              <strong>No Cloud-Free Observations:</strong> Unobserved or cloud-masked in this season.
            </div>
          )}

          {/* Polygon Baseline Context Bar */}
          <div className="grid grid-cols-4 gap-1.5 text-[10px] bg-slate-50 p-2 rounded border border-slate-100">
            <div>
              <span className="text-slate-400 block">Mean LST</span>
              <strong className="text-slate-700 text-[11px]">
                {data.polygon_summary.mean_lst_c !== null ? `${data.polygon_summary.mean_lst_c}°C` : "N/A"}
              </strong>
            </div>
            <div>
              <span className="text-slate-400 block">Mean HPI</span>
              <strong className="text-slate-700 text-[11px]">
                {data.polygon_summary.mean_hpi !== null ? `${data.polygon_summary.mean_hpi}` : "N/A"}
              </strong>
            </div>
            <div>
              <span className="text-slate-400 block">Chronic</span>
              <strong className="text-slate-700 text-[11px]">
                {(data.polygon_summary.chronic_cell_share * 100).toFixed(0)}%
              </strong>
            </div>
            <div>
              <span className="text-slate-400 block">Coverage</span>
              <strong className="text-slate-700 text-[11px]">
                {data.polygon_summary.data_coverage_percentage}%
              </strong>
            </div>
          </div>

          {/* Tab Selector */}
          <div className="flex border-b border-slate-200 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab("recommendations")}
              className={`pb-1 px-2 font-semibold cursor-pointer ${
                activeTab === "recommendations"
                  ? "border-b-2 border-indigo-600 text-indigo-900"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              Recommendations ({data.recommendations.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("assumptions")}
              className={`pb-1 px-2 font-semibold cursor-pointer ${
                activeTab === "assumptions"
                  ? "border-b-2 border-indigo-600 text-indigo-900"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              Assumptions ({data.assumptions_applied.length})
            </button>
          </div>

          {/* Recommendations Tab */}
          {activeTab === "recommendations" && (
            <div className="space-y-3">
              {data.recommendations.length === 0 ? (
                <div className="text-xs text-slate-500 py-3 text-center">
                  No interventions recommended for this area.
                </div>
              ) : (
                data.recommendations.map((rec) => (
                  <RecommendationCard key={rec.type} item={rec} />
                ))
              )}
            </div>
          )}

          {/* Assumptions Tab */}
          {activeTab === "assumptions" && (
            <div className="rounded bg-slate-50 p-2.5 text-[10.5px] border border-slate-200 space-y-1.5 text-slate-700">
              <div className="font-semibold text-slate-800">
                Operational Cutoffs (Explicitly ASSUMED):
              </div>
              <ul className="list-disc pl-4 space-y-1">
                {data.assumptions_applied.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
              <div className="mt-2 text-[9.5px] text-slate-500 border-t border-slate-200 pt-1.5">
                Note: Municipal planner review required before capital allocation.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function RecommendationCard({ item }: { item: RecommendationItem }) {
  const [expanded, setExpanded] = useState(false);

  const getPriorityBadgeClass = (priority: string) => {
    switch (priority) {
      case "HIGH":
        return "bg-rose-100 text-rose-800 border-rose-200";
      case "MEDIUM":
        return "bg-amber-100 text-amber-800 border-amber-200";
      case "LOW":
        return "bg-slate-100 text-slate-700 border-slate-200";
      default:
        return "bg-slate-100 text-slate-400 border-slate-200";
    }
  };

  const getFeasibilityBadge = (status: string) => {
    switch (status) {
      case "FEASIBLE":
        return <span className="text-emerald-700 font-semibold">✓ Feasible</span>;
      case "CONDITIONALLY_FEASIBLE":
        return <span className="text-amber-700 font-semibold">⚠️ Conditional</span>;
      case "REJECTED":
        return <span className="text-rose-700 font-semibold">✕ Rejected</span>;
      default:
        return <span>{status}</span>;
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-2xs hover:border-indigo-200 transition-colors space-y-2">
      {/* Title & Priority Row */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-xs font-bold text-slate-900">{item.title}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {item.quantity_basis.basis_description}
          </div>
        </div>

        <span
          className={`rounded border px-2 py-0.5 text-[10px] font-bold shrink-0 ${getPriorityBadgeClass(
            item.priority
          )}`}
        >
          {item.priority}
        </span>
      </div>

      {/* Rationale */}
      <div className="text-[11px] text-slate-700 leading-snug">
        {item.rationale}
      </div>

      {/* Feasibility & Cost / Cooling Metrics Grid */}
      <div className="grid grid-cols-3 gap-1.5 bg-slate-50 p-2 rounded border border-slate-100 text-[10px]">
        <div>
          <span className="text-slate-400 block">Feasibility</span>
          <div className="text-[10.5px] mt-0.5">{getFeasibilityBadge(item.feasibility_status)}</div>
        </div>

        <div>
          <span className="text-slate-400 block">Cooling Range</span>
          <div className="font-bold text-indigo-700 text-[10.5px] mt-0.5">
            {item.cooling_range_c.formatted}
          </div>
        </div>

        <div>
          <span className="text-slate-400 block">Cost Range (INR)</span>
          <div className="font-bold text-slate-800 text-[10.5px] mt-0.5">
            {item.cost_range_inr.formatted}
          </div>
        </div>
      </div>

      {/* Rejection Reasons if any */}
      {item.rejection_reasons.length > 0 && (
        <div className="rounded bg-rose-50 border border-rose-200 p-1.5 text-[10px] text-rose-800">
          <strong>Constraint Violations:</strong>
          <ul className="list-disc pl-4 mt-0.5 space-y-0.5">
            {item.rejection_reasons.map((r, idx) => (
              <li key={idx}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Collapsible Details: Maintenance & Missing Data Survey Requirements */}
      <div>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] font-semibold text-indigo-700 hover:text-indigo-900 cursor-pointer flex items-center gap-1"
        >
          <span>{expanded ? "Hide Details ▲" : "View Maintenance & Survey Requirements ▼"}</span>
        </button>

        {expanded && (
          <div className="mt-2 space-y-2 text-[10px] text-slate-600 border-t border-slate-100 pt-2">
            <div>
              <strong className="text-slate-700">Maintenance Horizon:</strong> {item.maintenance_note}
            </div>

            <div>
              <strong className="text-slate-700">Missing Data Survey Requirements:</strong>
              <ul className="list-disc pl-4 mt-0.5 space-y-0.5 text-slate-600">
                {item.missing_data_survey_requirements.map((req, idx) => (
                  <li key={idx}>
                    <span className="text-amber-800 font-medium">{req}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex items-center justify-between text-[9px] text-slate-400 pt-1">
              <span>Model Source: {item.cooling_range_c.model_source}</span>
              <span className="rounded bg-slate-100 px-1 py-0.2 font-mono">
                {item.evidence_label}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
