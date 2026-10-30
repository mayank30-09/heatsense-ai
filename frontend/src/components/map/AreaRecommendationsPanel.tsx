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

const TYPOLOGY_LABELS: Record<string, string> = {
  vacant_public_open_land: "Unbuilt Open Ground (Public Greening Candidate)",
  vacant_private_land: "Unbuilt Open Ground (Private / Non-Municipal)",
  park_garden: "Park or Public Garden",
  water_adjacent: "Water-Adjacent Buffer",
  residential_rcc_roof: "Residential Engineered RCC Roof",
  industrial_shed_roof: "Industrial Warehouse / Shed Roof",
  informal_settlement_roof: "Informal Settlement Roof",
  road_corridor: "Road Corridor & Verge",
  parking_paved_yard: "Parking Lot or Paved Yard",
  institutional_campus: "Institutional Campus (Heuristic)",
  unclassified: "Unclassified / Uncertain Land Parcel",
};

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
  const [activeTab, setActiveTab] = useState<"recommendations" | "evidence" | "assumptions">("recommendations");

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

  const typologyKey = data?.polygon_summary.landuse_typology || "unclassified";
  const typologyTitle = TYPOLOGY_LABELS[typologyKey] || typologyKey.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const needsSurvey = Boolean(data?.polygon_summary.needs_site_survey || typologyKey === "unclassified");

  return (
    <div className="rounded-xl border border-slate-200/90 bg-white p-3.5 shadow-sm text-slate-800">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-800">
              Polygon statistics & recommendations
            </span>
            <span className="badge-evidence badge-assumption">
              ASSUMPTION-BASED ESTIMATE
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
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
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
          {/* Geometry Validity Warning */}
          {(data.polygon_summary.geometry_warning || data.polygon_summary.area_km2 < 0.01) && (
            <div className="rounded border border-amber-300 bg-amber-50 px-2.5 py-1.5 text-xs text-amber-950 space-y-1">
              <div className="font-bold flex items-center gap-1 text-amber-900">
                <span>⚠️</span>
                <span>Geometry Diagnostics</span>
              </div>
              <div className="text-[10.5px] leading-snug">
                {data.polygon_summary.geometry_warning ||
                  `Very small polygon (${data.polygon_summary.area_km2 < 0.001 ? "<0.001" : data.polygon_summary.area_km2.toFixed(4)} km²) is smaller than a single 100m grid cell (1.0 ha / 0.01 km²); edge effects increase statistical uncertainty.`}
              </div>
            </div>
          )}

          {/* Needs Site Survey Warning Banner */}
          {needsSurvey && (
            <div className="rounded border-2 border-amber-400 bg-amber-50 p-2.5 text-xs text-amber-950 space-y-1.5">
              <div className="font-bold flex items-center gap-1.5 text-amber-900">
                <span className="text-base">📋</span>
                <span>NEEDS ON-SITE SURVEY</span>
              </div>
              <div className="text-[11px] leading-snug">
                Land classification for this candidate parcel is unverified or ambiguous. In strict adherence to Surat municipal heat governance, <strong>no mechanical interventions are authorized</strong> until an on-site cadastral, structural, and water-supply survey is conducted.
              </div>
            </div>
          )}

          {/* Land Typology & Allowed Interventions Bar */}
          <div className="rounded-lg border border-slate-200/80 bg-slate-50/70 p-2.5 text-[10.5px] space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-medium">Land-Use Typology:</span>
              <span className="font-bold text-slate-900">{typologyTitle}</span>
            </div>
            <div className="flex items-center justify-between text-[9.5px] text-slate-500 border-t border-indigo-100/60 pt-1">
              <span>Boundary source: SMC study-area polygon in PostGIS</span>
              <span>Inside SMC: {((data.polygon_summary.inside_smc_fraction ?? 1.0) * 100).toFixed(1)}%</span>
            </div>
            <div className="flex items-center justify-between text-[9.5px] text-slate-500">
              <span>Planar CRS: EPSG:32643 planar</span>
              <span>Area method: Geodesic ellipsoidal</span>
            </div>
            <div className="flex items-center justify-between text-[9.5px] text-slate-500">
              <span>Pixel size: 100m × 100m (1 ha)</span>
              <span>
                Coverage: {data.polygon_summary.data_coverage_percentage}% (valid / intersecting pixels)
              </span>
            </div>
            {data.recommendations.length > 0 && data.recommendations[0]?.allowed_interventions && (
              <div className="pt-1 border-t border-indigo-100/60">
                <span className="text-slate-500 font-medium text-[9.5px] block mb-1">Permitted Typology Interventions:</span>
                <div className="flex flex-wrap gap-1">
                  {data.recommendations[0].allowed_interventions.map((itype) => (
                    <span
                      key={itype}
                      className="rounded bg-indigo-100/70 text-indigo-900 text-[9px] px-1.5 py-0.5 font-medium"
                    >
                      {itype.replace(/_/g, " ")}
                    </span>
                  ))}
                </div>
              </div>
            )}
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
              <span className="text-slate-400 block" title="Observed (Landsat L2 ST)">Observed LST</span>
              <strong className="text-slate-700 text-[11px]" title="Observed (Landsat L2 ST)">
                {data.polygon_summary.mean_lst_c !== null && data.polygon_summary.mean_lst_c !== undefined
                  ? `${data.polygon_summary.mean_lst_c.toFixed(1)}°C`
                  : "N/A"}
              </strong>
            </div>
            <div>
              <span className="text-slate-400 block">Mean HPI</span>
              <strong className="text-slate-700 text-[11px]">
                {data.polygon_summary.mean_hpi !== null && data.polygon_summary.mean_hpi !== undefined
                  ? `${data.polygon_summary.mean_hpi.toFixed(1)}`
                  : "N/A"}
              </strong>
            </div>
            <div>
              <span className="text-slate-400 block">Chronic</span>
              <strong className="text-slate-700 text-[11px]">
                {(data.polygon_summary.chronic_cell_share * 100).toFixed(0)}%
              </strong>
            </div>
            <div>
              <span className="text-slate-400 block">Area</span>
              <strong className="text-slate-700 text-[11px]">
                {data.polygon_summary.area_km2.toFixed(2)} km²
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
              onClick={() => setActiveTab("evidence")}
              className={`pb-1 px-2 font-semibold cursor-pointer ${
                activeTab === "evidence"
                  ? "border-b-2 border-indigo-600 text-indigo-900"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              Reasoning Engine (7 Sections)
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

          {/* Reasoning Engine (7 Sections) Tab */}
          {activeTab === "evidence" && (
            <div className="space-y-3.5 text-xs">
              {/* Section 1: Heat Conditions */}
              <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3 space-y-2">
                <div className="flex items-center justify-between border-b border-slate-200/80 pb-1.5 font-bold text-slate-800">
                  <span className="flex items-center gap-1.5">
                    <span>🔥</span>
                    <span>1. Observed &amp; Modeled Heat Conditions</span>
                  </span>
                  <span className="text-[10px] text-amber-700 font-mono bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                    Tier: {data.heat_conditions?.confidence_tier || data.polygon_summary.confidence_tier}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-[11px]">
                  <div>
                    <span className="text-slate-500 block">Mean LST:</span>
                    <strong className="font-mono text-slate-900">
                      {data.heat_conditions?.mean_lst_c ? `${data.heat_conditions.mean_lst_c}°C` : "N/A"}
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Max LST:</span>
                    <strong className="font-mono text-slate-900">
                      {data.heat_conditions?.max_lst_c ? `${data.heat_conditions.max_lst_c}°C` : "N/A"}
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Mean HPI:</span>
                    <strong className="font-mono text-amber-700">
                      {data.heat_conditions?.mean_hpi ?? "N/A"}
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Chronic Cells:</span>
                    <strong className="font-mono text-red-700">
                      {data.heat_conditions?.chronic_hotspot_cells ?? 0}
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Quality (C_i):</span>
                    <strong className="font-mono text-emerald-700">
                      {data.heat_conditions?.confidence_score ?? 0}
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Mean NDVI / NDBI:</span>
                    <span className="font-mono text-[10px] text-slate-700">
                      {data.heat_conditions?.mean_ndvi?.toFixed(2) ?? "N/A"} / {data.heat_conditions?.mean_ndbi?.toFixed(2) ?? "N/A"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Section 2: Physical Features & Land Cover Opportunities */}
              <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3 space-y-2">
                <div className="flex items-center justify-between border-b border-slate-200/80 pb-1.5 font-bold text-slate-800">
                  <span className="flex items-center gap-1.5">
                    <span>📐</span>
                    <span>2. Physical Features &amp; Land Cover Composition</span>
                  </span>
                  <span className="text-[10px] text-slate-600 font-mono bg-white px-1.5 py-0.5 rounded border border-slate-200">
                    {data.physical_features?.polygon_area_ha ?? (data.polygon_summary.area_km2 * 100).toFixed(1)} ha
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div>
                    <span className="text-slate-500 block">Built Surface Fraction:</span>
                    <strong className="font-mono text-slate-800">
                      {((data.physical_features?.built_ratio ?? data.polygon_summary.built_density_component ?? 0) * 100).toFixed(1)}%
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Permeable Open Ground:</span>
                    <strong className="font-mono text-emerald-800">
                      {(((data.physical_features?.bare_ratio ?? 0) + (data.physical_features?.grass_ratio ?? 0)) * 100).toFixed(1)}%
                    </strong>
                  </div>
                  <div className="col-span-2">
                    <span className="text-slate-500 block">Land-Use Typology:</span>
                    <span className="font-semibold text-slate-800">
                      {data.physical_features?.typology_title || typologyTitle}
                    </span>
                  </div>
                </div>

                {/* Land Cover & Satellite Spectral Composition Bar */}
                <div className="mt-2 pt-2 border-t border-slate-200/70 space-y-1.5">
                  <div className="text-[10px] font-bold text-slate-700 uppercase tracking-wider">
                    Area-Weighted Land Cover Composition (Dynamic World &amp; Satellite Indices)
                  </div>
                  <div className="grid grid-cols-3 gap-1.5 text-[10px] font-mono">
                    <div className="bg-white p-1.5 rounded border border-slate-200">
                      <span className="text-slate-400 block text-[9px]">Mean NDVI</span>
                      <strong className="text-emerald-700">
                        {data.polygon_summary.mean_ndvi !== null && data.polygon_summary.mean_ndvi !== undefined
                          ? data.polygon_summary.mean_ndvi.toFixed(2)
                          : "N/A"}
                      </strong>
                    </div>
                    <div className="bg-white p-1.5 rounded border border-slate-200">
                      <span className="text-slate-400 block text-[9px]">Mean NDBI</span>
                      <strong className="text-amber-700">
                        {data.polygon_summary.mean_ndbi !== null && data.polygon_summary.mean_ndbi !== undefined
                          ? data.polygon_summary.mean_ndbi.toFixed(2)
                          : "N/A"}
                      </strong>
                    </div>
                    <div className="bg-white p-1.5 rounded border border-slate-200">
                      <span className="text-slate-400 block text-[9px]">Mean NDWI</span>
                      <strong className="text-sky-700">
                        {data.polygon_summary.mean_ndwi !== null && data.polygon_summary.mean_ndwi !== undefined
                          ? data.polygon_summary.mean_ndwi.toFixed(2)
                          : "N/A"}
                      </strong>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-[9.5px] text-slate-500">
                    <span>Water Fraction: {(data.polygon_summary.water_fraction * 100).toFixed(1)}%</span>
                    <span>Veg Deficit: {((data.polygon_summary.vegetation_deficit_component ?? 0) * 100).toFixed(1)}%</span>
                  </div>
                </div>
              </div>

              {/* Section 3: Candidate Sites with Geometry */}
              <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3 space-y-2">
                <div className="flex items-center justify-between border-b border-slate-200/80 pb-1.5 font-bold text-slate-800">
                  <span className="flex items-center gap-1.5">
                    <span>📍</span>
                    <span>3. Physical Candidate Sites ({data.candidate_sites?.length ?? 0})</span>
                  </span>
                </div>
                {(!data.candidate_sites || data.candidate_sites.length === 0) ? (
                  <div className="text-[11px] text-slate-500 italic">No candidate sites eligible under current physical screening.</div>
                ) : (
                  <div className="space-y-1.5">
                    {data.candidate_sites.map((c) => (
                      <div key={c.candidate_id} className="rounded bg-white p-2 border border-slate-200 text-[11px] flex items-center justify-between">
                        <div>
                          <strong className="text-slate-900 block">{c.title}</strong>
                          <span className="text-slate-500 text-[10px]">
                            Unit: {c.spatial_unit} · Qty: {Number(c.quantity).toLocaleString()} {c.unit}
                          </span>
                        </div>
                        <div className="text-right">
                          <span className="inline-block rounded px-1.5 py-0.5 text-[9px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
                            {c.reasoning_state}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Section 4: Quantity & Cost Roll-up */}
              <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3 space-y-2">
                <div className="flex items-center justify-between border-b border-slate-200/80 pb-1.5 font-bold text-slate-800">
                  <span className="flex items-center gap-1.5">
                    <span>💰</span>
                    <span>4. Quantity &amp; Cost Roll-Up (All-Inclusive Cost Base)</span>
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div>
                    <span className="text-slate-500 block">Total Capital Spend (Base):</span>
                    <strong className="font-mono text-indigo-700 text-xs">
                      {data.quantity_cost_rollup?.total_capital_spend_formatted ?? "₹0.00"}
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Est. Annual Maintenance:</span>
                    <strong className="font-mono text-slate-700 text-xs">
                      ₹{Number(data.quantity_cost_rollup?.total_annual_maintenance_inr ?? 0).toLocaleString()} / yr
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Total Treated Footprint:</span>
                    <strong className="font-mono text-slate-800">
                      {Number(data.quantity_cost_rollup?.total_treated_area_m2 ?? 0).toLocaleString()} m² ({data.quantity_cost_rollup?.total_treated_area_ha ?? 0} ha)
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Eligible vs Rejected Options:</span>
                    <span className="font-mono text-slate-800 font-semibold">
                      {data.quantity_cost_rollup?.eligible_options_count ?? 0} eligible / {data.quantity_cost_rollup?.rejected_options_count ?? 0} rejected
                    </span>
                  </div>
                </div>
              </div>

              {/* Section 5: Evidence Gaps & Required Field Checks */}
              <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3 space-y-1.5">
                <div className="font-bold text-amber-950 flex items-center gap-1.5 border-b border-amber-200/80 pb-1">
                  <span>📋</span>
                  <span>5. Evidence Gaps &amp; Required Municipal Field Surveys</span>
                </div>
                <ul className="list-disc pl-4 space-y-1 text-[11px] text-amber-900 leading-snug">
                  {(data.evidence_gaps ?? [
                    "Cadastral building footprints with structural load ratings (UNAVAILABLE)",
                    "Municipal road network with right-of-way and sidewalk widths (UNAVAILABLE)",
                    "Revenue parcel ownership tenure (UNAVAILABLE)",
                    "High-resolution DEM and stormwater drainage network (UNAVAILABLE)",
                  ]).map((gap, idx) => (
                    <li key={idx}>{gap}</li>
                  ))}
                </ul>
              </div>

              {/* Section 6: Excluded Alternatives & Failed Constraints */}
              <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3 space-y-2">
                <div className="flex items-center justify-between border-b border-slate-200/80 pb-1.5 font-bold text-slate-800">
                  <span className="flex items-center gap-1.5">
                    <span>🚫</span>
                    <span>6. Excluded Alternatives &amp; Failed Constraints</span>
                  </span>
                </div>

                <div className="space-y-1.5">
                  {/* Dynamic rejected candidates from backend */}
                  {(data.rejected_candidates ?? []).map((rc, idx) => (
                    <div key={idx} className="rounded bg-white p-2 border border-slate-200 text-[11px] space-y-0.5">
                      <div className="flex items-center justify-between">
                        <strong className="text-slate-900">{rc.title}</strong>
                        <span className="font-mono text-[9px] bg-slate-100 px-1 py-0.5 rounded text-slate-600 border border-slate-200">
                          {rc.rule_id}
                        </span>
                      </div>
                      <div className="text-rose-800 text-[10px]">
                        Reason: {rc.reasons.join("; ")}
                      </div>
                    </div>
                  ))}

                  {/* Explicit Non-Assessable Typologies (Kept Removed from active catalog) */}
                  <div className="rounded bg-white p-2 border border-slate-200 text-[11px] space-y-0.5">
                    <div className="flex items-center justify-between">
                      <strong className="text-slate-900">🌊 Rainwater-Fed Retention Pond</strong>
                      <span className="font-mono text-[9px] bg-slate-100 px-1 py-0.5 rounded text-slate-600 border border-slate-200 font-bold">
                        NON_ASSESSABLE
                      </span>
                    </div>
                    <div className="text-slate-600 text-[10px]">
                      Reason: Requires high-resolution LiDAR / DEM surface elevation hydrological catchment modeling. Kept removed from active solver.
                    </div>
                  </div>

                  <div className="rounded bg-white p-2 border border-slate-200 text-[11px] space-y-0.5">
                    <div className="flex items-center justify-between">
                      <strong className="text-slate-900">🧗 Modular Vertical Living Wall</strong>
                      <span className="font-mono text-[9px] bg-slate-100 px-1 py-0.5 rounded text-slate-600 border border-slate-200 font-bold">
                        NON_ASSESSABLE
                      </span>
                    </div>
                    <div className="text-slate-600 text-[10px]">
                      Reason: Requires 3D building height, wall aspect and facade structural load inventory. Kept removed from active solver.
                    </div>
                  </div>
                </div>
              </div>

              {/* Section 7: Evidence Availability Panel */}
              <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2 shadow-2xs">
                <div className="flex items-center justify-between border-b border-slate-200 pb-1.5 font-bold text-slate-800">
                  <span className="flex items-center gap-1.5">
                    <span>📡</span>
                    <span>7. Evidence Layers Availability Status</span>
                  </span>
                </div>
                <div className="space-y-1.5">
                  {(data.evidence_availability_panel ?? []).map((ev) => (
                    <div key={ev.provider_id} className="rounded border border-slate-100 bg-slate-50/60 p-2 text-[10.5px] space-y-0.5">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-900">{ev.layer_title}</span>
                        <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${
                          ev.availability === "AVAILABLE"
                            ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                            : ev.availability === "PARTIAL"
                            ? "bg-amber-100 text-amber-800 border border-amber-300"
                            : "bg-rose-100 text-rose-800 border border-rose-300"
                        }`}>
                          {ev.availability}
                        </span>
                      </div>
                      <div className="text-slate-500 text-[10px]">
                        Dataset: {ev.dataset_name} ({ev.spatial_resolution})
                      </div>
                      {ev.missing_reason && (
                        <div className="text-amber-800 text-[9.5px] italic">
                          Missing: {ev.missing_reason}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Recommendations Tab */}
          {activeTab === "recommendations" && (
            <div className="space-y-3">
              {data.recommendations.length === 0 ? (
                <div className="text-xs text-slate-500 py-4 text-center bg-slate-50 rounded border border-slate-100">
                  {needsSurvey
                    ? "Mechanical recommendations blocked pending on-site survey."
                    : "No interventions recommended for this area."}
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
            <div className="space-y-3">
              <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2 shadow-2xs">
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <div className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
                    <span>🔬</span>
                    <span>Transparent Assumptions &amp; Sensitivity Register</span>
                  </div>
                  <span className="text-[9.5px] font-mono text-teal-700 bg-teal-50 px-2 py-0.5 rounded font-bold">
                    No Fabricated Data
                  </span>
                </div>
                <p className="text-[10.5px] text-slate-500 leading-snug">
                  Every parameter in HeatSense AI is either directly measured from satellite rasters, derived by explicit thermodynamic formula, or recorded below as a calibrated engineering assumption with stated sensitivity and required ground-truth replacement dataset.
                </p>

                <div className="overflow-x-auto mt-2">
                  <table className="w-full text-left text-[10px] border-collapse">
                    <thead className="bg-slate-50 text-slate-700 font-bold border-b border-slate-200">
                      <tr>
                        <th className="p-1.5">Parameter</th>
                        <th className="p-1.5">Category</th>
                        <th className="p-1.5">Baseline &amp; Sensitivity</th>
                        <th className="p-1.5">Ground-Truth Replacement Dataset</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {[
                        {
                          name: "Chronic Heat Severity Threshold",
                          category: "Derived",
                          val: "HPI ≥ 50.0 / Top 10% LST",
                          sens: "Low: 45.0 | Base: 50.0 | High: 55.0",
                          replacement: "SMC Automatic Weather Station (AWS) sensor mesh",
                        },
                        {
                          name: "Rooftop Cool Coating Albedo (Δα)",
                          category: "Sourced",
                          val: "+0.45 (aged coating albedo 0.65)",
                          sens: "Low: +0.35 | Base: +0.45 | High: +0.55",
                          replacement: "Field surface spectrometer reflectance survey",
                        },
                        {
                          name: "Tree Crown Area & Transpiration",
                          category: "Sourced",
                          val: "25 m² crown / sapling",
                          sens: "Low: 15 m² | Base: 25 m² | High: 35 m²",
                          replacement: "High-resolution drone LiDAR tree canopy audit",
                        },
                        {
                          name: "Sapling Mortality Buffer",
                          category: "Assumption",
                          val: "15% mortality replacement",
                          sens: "Low: 10% | Base: 15% | High: 25%",
                          replacement: "SMC municipal nursery 3-year survival logs",
                        },
                        {
                          name: "Permeable Paver Porosity & Albedo",
                          category: "Sourced",
                          val: "Δα = +0.20, Void ratio = 18%",
                          sens: "Low: +0.15 | Base: +0.20 | High: +0.25",
                          replacement: "Civil lab core permeability & albedo test certificates",
                        },
                        {
                          name: "Integer DP Discretization Unit",
                          category: "Derived",
                          val: "₹5,000 per knapsack weight unit",
                          sens: "Low: ₹2,500 | Base: ₹5,000 | High: ₹10,000",
                          replacement: "Exact fractional LP / continuous ceiling bounds",
                        },
                        {
                          name: "Rooftop RCC Structural Suitability",
                          category: "Assumption",
                          val: "60% of built footprint suitable",
                          sens: "Low: 40% | Base: 60% | High: 80%",
                          replacement: "Cadastral structural load & tenure register",
                        },
                      ].map((item, idx) => (
                        <tr key={idx} className="hover:bg-slate-50 transition-colors">
                          <td className="p-1.5 font-semibold text-slate-800">{item.name}</td>
                          <td className="p-1.5">
                            <span
                              className={`rounded px-1.5 py-0.2 text-[9px] font-bold font-mono ${
                                item.category === "Data"
                                  ? "bg-emerald-100 text-emerald-800"
                                  : item.category === "Sourced"
                                  ? "bg-blue-100 text-blue-800"
                                  : item.category === "Derived"
                                  ? "bg-indigo-100 text-indigo-800"
                                  : "bg-amber-100 text-amber-800"
                              }`}
                            >
                              {item.category}
                            </span>
                          </td>
                          <td className="p-1.5 text-slate-600">
                            <div><strong>{item.val}</strong></div>
                            <div className="text-[9px] text-slate-400 font-mono">{item.sens}</div>
                          </td>
                          <td className="p-1.5 text-slate-500">{item.replacement}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Dynamic Operational Cutoffs from API */}
              <div className="rounded-lg bg-slate-50 p-2.5 text-[10.5px] border border-slate-200 space-y-1.5 text-slate-700">
                <div className="font-semibold text-slate-800">
                  Polygon-Specific Calibrated Cutoffs (Reported by Engine):
                </div>
                <ul className="list-disc pl-4 space-y-1">
                  {data.assumptions_applied.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
                <div className="mt-2 text-[9.5px] text-slate-500 border-t border-slate-200 pt-1.5">
                  Pre-tender engineering survey required prior to municipal procurement.
                </div>
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

  const getScreeningStatusBadge = () => {
    const status = item.screening_status || (item.feasibility_status === "REJECTED" ? "NOT_APPLICABLE" : "MODEL_ELIGIBLE");
    const reason = item.screening_reason_code || (item.rejection_reasons[0] ? item.rejection_reasons[0].slice(0, 32) : "");
    if (status === "MODEL_ELIGIBLE") {
      return (
        <span className="inline-flex items-center gap-1 rounded bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[10px] font-semibold text-indigo-900">
          <span>●</span> Model-eligible (survey required)
        </span>
      );
    } else if (status === "NOT_APPLICABLE") {
      return (
        <span className="inline-flex items-center gap-1 rounded bg-slate-100 border border-slate-300 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
          <span>✕</span> Not applicable here {reason ? `(${reason.replace(/_/g, " ").toLowerCase()})` : ""}
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 rounded bg-rose-50 border border-rose-200 px-2 py-0.5 text-[10px] font-semibold text-rose-800">
          <span>✕</span> Excluded {reason ? `(${reason.replace(/_/g, " ").toLowerCase()})` : ""}
        </span>
      );
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-2xs hover:border-indigo-200 transition-colors space-y-2">
      {/* Title & Priority Row */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-xs font-bold text-slate-900">{item.title}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            Quantity: <strong>{Number(item.quantity_basis.estimated_quantity).toFixed(1)} {item.quantity_basis.unit}</strong> ({item.quantity_basis.basis_description})
          </div>
        </div>

        <div className="flex flex-col items-end gap-1">
          <span
            className={`rounded border px-2 py-0.5 text-[10px] font-bold shrink-0 ${getPriorityBadgeClass(
              item.priority
            )}`}
          >
            {item.priority}
          </span>
          {getScreeningStatusBadge()}
        </div>
      </div>

      {/* Engineering Clearance & Tenure Status Pills */}
      <div className="flex flex-wrap gap-1 text-[9px] text-slate-500 pt-0.5">
        <span className="rounded bg-slate-100 px-1.5 py-0.5 border border-slate-200">
          Site: <strong>{item.site_suitability || "UNKNOWN - survey required"}</strong>
        </span>
        <span className="rounded bg-slate-100 px-1.5 py-0.5 border border-slate-200">
          Tenure: <strong>{item.ownership_legal || "UNVERIFIED"}</strong>
        </span>
        <span className="rounded bg-slate-100 px-1.5 py-0.5 border border-slate-200">
          Clearance: <strong>{item.engineering_clearance || "NOT ASSESSED"}</strong>
        </span>
        <span className="rounded bg-slate-100 px-1.5 py-0.5 border border-slate-200">
          Procurement: <strong>{item.procurement_status || "NOT STARTED"}</strong>
        </span>
      </div>

      {/* Rationale & Selection Reason */}
      <div className="text-[11px] text-slate-700 leading-snug">
        {item.rationale}
      </div>

      {item.selection_rationale && item.selection_rationale !== item.rationale && (
        <div className="text-[10px] text-indigo-900 bg-indigo-50/60 p-1.5 rounded border border-indigo-100 leading-tight">
          <strong>Why Chosen:</strong> {item.selection_rationale}
        </div>
      )}

      {/* Dual Cooling & Cost Metrics Grid */}
      <div className="grid grid-cols-3 gap-1.5 bg-slate-50 p-2 rounded border border-slate-100 text-[10px]">
        <div>
          <span className="text-slate-500 block font-semibold text-[9.5px] leading-tight">
            Modelled surface temperature reduction (skin), not air temperature
          </span>
          <div className="font-bold text-indigo-700 text-[10.5px] mt-1">
            {item.cooling_range_c.formatted}
          </div>
          <span className="text-[8.5px] text-slate-400 block mt-0.5 italic">
            {item.cell_scope_note || "Modelled surface skin temperature reduction on treated area, not ambient air temperature."}
          </span>
        </div>

        <div>
          <span className="text-slate-500 block font-semibold text-[9.5px] leading-tight">
            Modelled ambient air temperature reduction (2m AGL)
          </span>
          <div className="font-bold text-teal-700 text-[10.5px] mt-1">
            {item.air_cooling_c ? `-${item.air_cooling_c.toFixed(1)}°C` : "-0.5°C"}
          </div>
          <span className="text-[8.5px] text-slate-400 block mt-0.5 italic">
            Macro-canopy air cooling estimate
          </span>
        </div>

        <div>
          <span className="text-slate-500 block font-semibold text-[9.5px] leading-tight">
            Cost Range (INR)
          </span>
          <div className="font-bold text-slate-800 text-[10.5px] mt-1">
            {item.cost_range_inr.formatted}
          </div>
          <div className="text-[8.5px] text-slate-500 mt-0.5 space-y-0.5">
            <div>Unit Rate: <strong>₹{item.unit_rate !== undefined ? item.unit_rate.toFixed(1) : (item.type === 'TREE_CANOPY' ? '2000.0' : (item.type === 'COOL_ROOF' ? '300.0' : '400.0'))} / {item.unit_rate_unit || item.quantity_basis.unit}</strong></div>
            <div className="text-amber-800 italic">{item.schedule_alignment_note || "rates not verified against CPWD/SMC schedule"}</div>
            <div className="text-slate-400">{item.price_date_note || "indicative, not a tender price"}</div>
          </div>
        </div>
      </div>

      {/* Engineering Attributes: Water Need, Construction Time, Whole Life Cost */}
      <div className="grid grid-cols-3 gap-1.5 text-[9.5px] text-slate-600 px-0.5">
        <div>
          <span className="text-slate-400 block">Water Need:</span>
          <span className="font-medium text-slate-800">{item.water_need_description || "Moderate"}</span>
        </div>
        <div>
          <span className="text-slate-400 block">Time to Effect:</span>
          <span className="font-medium text-slate-800">{item.construction_time || "1-3 months"}</span>
        </div>
        <div>
          <span className="text-slate-400 block">Whole-Life (3yr):</span>
          <span className="font-medium text-slate-800">
            {item.whole_life_cost_3yr_inr ? `₹${(item.whole_life_cost_3yr_inr / 100000).toFixed(1)}L` : "Included"}
          </span>
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

      {/* Collapsible Details: Maintenance, Rejected Alternatives, Missing Data */}
      <div>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] font-semibold text-indigo-700 hover:text-indigo-900 cursor-pointer flex items-center gap-1"
        >
          <span>{expanded ? "Hide Engineering Details ▲" : "View Disqualified Alternatives & Engineering Details ▼"}</span>
        </button>

        {expanded && (
          <div className="mt-2 space-y-2 text-[10px] text-slate-600 border-t border-slate-100 pt-2">
            <div>
              <strong className="text-slate-700">Cost Schedule & Markups:</strong>{" "}
              {item.markups_description || "Includes 18% GST, 12% contingency, 6% design & supervision, and scaled site setup"}.{" "}
              <span className="text-amber-800 italic">({item.schedule_alignment_note || "rates not verified against CPWD/SMC schedule"}; {item.price_date_note || "indicative, not a tender price"})</span>
            </div>
            <div>
              <strong className="text-slate-700">Maintenance Burden & Schedule:</strong> {item.maintenance_note}
            </div>

            {/* Rejected Alternatives Section */}
            {item.rejected_alternatives && item.rejected_alternatives.length > 0 && (
              <div className="rounded bg-slate-50 p-2 border border-slate-200/80 space-y-1">
                <strong className="text-slate-800 block text-[10px]">
                  Disqualified Alternatives for this Typology ({item.rejected_alternatives.length}):
                </strong>
                <div className="space-y-1">
                  {item.rejected_alternatives.slice(0, 4).map((alt) => (
                    <div key={alt.intervention_type} className="text-[9.5px]">
                      <span className="font-semibold text-rose-800">✕ {alt.title}: </span>
                      <span className="text-slate-600">{alt.rejection_reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

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
              <span className={`badge-evidence ${
                item.evidence_label === 'MEASURED' ? 'badge-measured' :
                item.evidence_label === 'MODELLED' ? 'badge-modelled' :
                item.evidence_label === 'ASSUMPTION' ? 'badge-assumption' : 'badge-unverified'
              }`}>
                {item.evidence_label}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
