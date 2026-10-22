import { useEffect, useState } from "react";
import type {
  FeasibilityStatus,
  InterventionCandidateItem,
  InterventionType,
} from "../../types/interventions";
import {
  fetchCandidateDetail,
  fetchInterventionCandidates,
} from "../../services/interventionsApi";

interface InterventionExplorerProps {
  onSwitchToMap?: () => void;
  onSelectCandidateOnMap?: (candidate: InterventionCandidateItem) => void;
}

const TYPE_CONFIG: Record<
  InterventionType,
  {
    label: string;
    icon: string;
    badgeClass: string;
    description: string;
    albedoOrBiomass: string;
  }
> = {
  tree_canopy: {
    label: "Native Urban Forestry",
    icon: "🌳",
    badgeClass: "bg-emerald-50 text-emerald-800 border-emerald-300",
    description:
      "Native species (Neem, Peepal, Gulmohar) crown shading and latent evapotranspiration cooling.",
    albedoOrBiomass: "Evaporative Latent Flux (LE) + 85% Solar Attenuation",
  },
  cool_roof: {
    label: "High-Albedo Cool Roof",
    icon: "⚪",
    badgeClass: "bg-sky-50 text-sky-800 border-sky-300",
    description:
      "Aged high-reflectance coating (Δα = +0.45, SRI ≥ 78) applied on residential/commercial RCC roofs.",
    albedoOrBiomass: "Solar Reflectance α = 0.65 (Aged ASTM D7897)",
  },
  green_roof: {
    label: "Extensive Green Roof",
    icon: "🌿",
    badgeClass: "bg-teal-50 text-teal-800 border-teal-300",
    description:
      "Sedum/succulent vegetative roof on structural RCC concrete with soil moisture buffer.",
    albedoOrBiomass: "Combined Biomass Shading & Evapotranspiration",
  },
  cool_pavement: {
    label: "Permeable Cool Pavement",
    icon: "🧱",
    badgeClass: "bg-indigo-50 text-indigo-800 border-indigo-300",
    description:
      "High-albedo porous interlocking pavers and permeable concrete for parking and walkways.",
    albedoOrBiomass: "Solar Reflectance α = 0.40 + Subsurface Moisture Evaporation",
  },
};

function formatINR(val: number): string {
  if (val >= 10000000) {
    return `₹${(val / 10000000).toFixed(2)} Cr`;
  }
  if (val >= 100000) {
    return `₹${(val / 100000).toFixed(2)} Lakh`;
  }
  return `₹${val.toLocaleString("en-IN")}`;
}

export default function InterventionExplorer({
  onSwitchToMap,
  onSelectCandidateOnMap,
}: InterventionExplorerProps) {
  const [candidates, setCandidates] = useState<InterventionCandidateItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedType, setSelectedType] = useState<InterventionType | "ALL">("ALL");
  const [feasibility, setFeasibility] = useState<FeasibilityStatus>("FEASIBLE");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Detailed Modal Candidate
  const [selectedCandidate, setSelectedCandidate] =
    useState<InterventionCandidateItem | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const filterObj = {
      intervention_type: selectedType === "ALL" ? undefined : selectedType,
      feasibility_status: feasibility,
      limit: 100,
    };

    fetchInterventionCandidates(filterObj)
      .then((res) => {
        if (!cancelled) {
          setCandidates(res.items);
          setTotalCount(res.total_count);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load intervention candidates"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedType, feasibility]);

  const handleOpenDetail = (cand: InterventionCandidateItem) => {
    setDetailLoading(true);
    fetchCandidateDetail(cand.candidate_id)
      .then((fullCand) => {
        setSelectedCandidate(fullCand);
      })
      .catch(() => {
        setSelectedCandidate(cand);
      })
      .finally(() => {
        setDetailLoading(false);
      });
  };

  // Filter candidates by text search
  const filteredCandidates = candidates.filter((c) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      c.candidate_id.toLowerCase().includes(q) ||
      c.cell_id.toLowerCase().includes(q) ||
      c.administrative_zone.toLowerCase().includes(q) ||
      c.intervention_type.toLowerCase().includes(q)
    );
  });

  // KPI Calculations
  const avgCooling =
    filteredCandidates.length > 0
      ? filteredCandidates.reduce((acc, c) => acc + c.expected_cooling_c, 0) /
        filteredCandidates.length
      : 0;

  const totalCost = filteredCandidates.reduce((acc, c) => acc + c.cost_inr, 0);
  const chronicCount = filteredCandidates.filter((c) => c.is_chronic_hotspot).length;

  return (
    <div className="flex flex-col gap-6">
      {/* Hero Header */}
      <div className="rounded-xl border border-slate-200 bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 p-6 text-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-xs font-bold text-emerald-300 border border-emerald-500/30">
                Stage D Verified
              </span>
              <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Physics-Informed Cooling Catalog
              </span>
            </div>
            <h2 className="mt-2 text-2xl font-extrabold text-white">
              Surat Urban Cooling Intervention Explorer
            </h2>
            <p className="mt-1 max-w-3xl text-sm text-slate-300">
              Site-specific candidate cooling interventions calibrated via Surface Energy Balance
              equations (R<sub>n</sub> = H + LE + G) and CPWD/SMC schedule of rates across Surat’s
              highest-vulnerability analytical grid cells.
            </p>
          </div>

          {onSwitchToMap && (
            <button
              type="button"
              onClick={onSwitchToMap}
              className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white shadow hover:bg-emerald-500 transition-all"
            >
              <span>View On Heat Map</span>
              <span>→</span>
            </button>
          )}
        </div>
      </div>

      {/* Primary KPI Metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Qualifying Candidates
          </span>
          <div className="mt-1 text-3xl font-extrabold text-slate-900 font-mono">
            {totalCount.toLocaleString()}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            HPI ≥ 35.0 priority threshold · 100m grid resolution
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Mean Modeled Skin Cooling
          </span>
          <div className="mt-1 text-3xl font-extrabold text-emerald-600 font-mono">
            -{avgCooling.toFixed(2)}°C
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Direct surface ΔT<sub>skin</sub> over treated area footprint
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Chronic Hotspots Addressed
          </span>
          <div className="mt-1 text-3xl font-extrabold text-orange-600 font-mono">
            {chronicCount} <span className="text-sm font-normal text-slate-500">cells</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Multi-year persistent heat vulnerability (2021–2026)
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Catalog Investment Portfolio
          </span>
          <div className="mt-1 text-3xl font-extrabold text-indigo-700 font-mono">
            {formatINR(totalCost)}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Capital + 3-year establishment maintenance
          </p>
        </div>
      </div>

      {/* Filter and Control Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-500">
            <span>Filter Type:</span>
          </div>

          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setSelectedType("ALL")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                selectedType === "ALL"
                  ? "bg-slate-900 text-white shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              All Types
            </button>

            {(Object.keys(TYPE_CONFIG) as InterventionType[]).map((itype) => {
              const cfg = TYPE_CONFIG[itype];
              const isSelected = selectedType === itype;
              return (
                <button
                  key={itype}
                  type="button"
                  onClick={() => setSelectedType(itype)}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                    isSelected
                      ? "bg-slate-900 text-white shadow-xs"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  <span>{cfg.icon}</span>
                  <span>{cfg.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Feasibility Toggle */}
          <div className="flex items-center rounded-lg border border-slate-200 bg-slate-50 p-1">
            <button
              type="button"
              onClick={() => setFeasibility("FEASIBLE")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                feasibility === "FEASIBLE"
                  ? "bg-white text-slate-900 shadow-xs font-bold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Feasible Only
            </button>
            <button
              type="button"
              onClick={() => setFeasibility("REJECTED")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                feasibility === "REJECTED"
                  ? "bg-white text-slate-900 shadow-xs font-bold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Rejected
            </button>
          </div>

          {/* Search Box */}
          <div className="relative">
            <input
              type="text"
              placeholder="Search zone, cell ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-48 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-1.5 text-xs text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Loading & Error States */}
      {loading && (
        <div className="flex items-center justify-center p-12 text-slate-500">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent mr-3" />
          <span>Loading Stage D candidate interventions from catalog…</span>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <div className="font-bold">Error loading candidates:</div>
          <div>{error}</div>
        </div>
      )}

      {/* Candidate Grid */}
      {!loading && !error && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredCandidates.map((cand) => {
            const typeInfo = TYPE_CONFIG[cand.intervention_type] || {
              label: cand.intervention_type,
              icon: "📍",
              badgeClass: "bg-slate-100 text-slate-800 border-slate-300",
              description: "",
              albedoOrBiomass: "",
            };

            return (
              <div
                key={cand.candidate_id}
                className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-xs hover:border-indigo-300 hover:shadow-md transition-all"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-bold ${typeInfo.badgeClass}`}
                    >
                      <span>{typeInfo.icon}</span>
                      <span>{typeInfo.label}</span>
                    </span>

                    <span className="font-mono text-xs font-semibold text-slate-500">
                      {cand.cell_id}
                    </span>
                  </div>

                  <h3 className="mt-3 text-base font-bold text-slate-900">
                    {cand.administrative_zone} Zone
                  </h3>

                  <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                    <span>
                      Lat: {cand.latitude.toFixed(4)}°, Lon: {cand.longitude.toFixed(4)}°
                    </span>
                    {cand.is_chronic_hotspot && (
                      <span className="inline-flex items-center rounded-sm bg-orange-100 px-1.5 py-0.2 text-[10px] font-bold text-orange-800">
                        🔥 Chronic
                      </span>
                    )}
                  </div>

                  {/* Physics & Cost Preview */}
                  <div className="mt-4 grid grid-cols-2 gap-2 rounded-lg bg-slate-50 p-3 text-xs">
                    <div>
                      <div className="text-[11px] font-semibold text-slate-500 uppercase">
                        Expected Cooling
                      </div>
                      <div className="mt-0.5 font-mono text-base font-extrabold text-emerald-600">
                        -{cand.expected_cooling_c.toFixed(2)}°C
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Range: {cand.expected_cooling_c_range[0].toFixed(1)}°–
                        {cand.expected_cooling_c_range[1].toFixed(1)}°C
                      </div>
                    </div>

                    <div>
                      <div className="text-[11px] font-semibold text-slate-500 uppercase">
                        Estimated Cost
                      </div>
                      <div className="mt-0.5 font-mono text-base font-extrabold text-slate-900">
                        {formatINR(cand.cost_inr)}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Footprint: {cand.usable_area_m2.toLocaleString()} m²
                      </div>
                    </div>
                  </div>

                  {/* Baseline Context */}
                  <div className="mt-3 flex items-center justify-between text-xs text-slate-600">
                    <span>
                      Baseline LST:{" "}
                      <strong className="text-red-700">
                        {cand.baseline_lst_c ? `${cand.baseline_lst_c.toFixed(1)}°C` : "N/A"}
                      </strong>
                    </span>
                    <span>
                      HPI Score:{" "}
                      <strong>
                        {cand.baseline_hpi ? (cand.baseline_hpi * 100).toFixed(1) : "N/A"}
                      </strong>
                    </span>
                  </div>
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3">
                  <span className="text-[11px] text-slate-400 font-mono">
                    {cand.feasibility_status === "FEASIBLE" ? (
                      <span className="text-emerald-600 font-semibold">✓ Feasible</span>
                    ) : (
                      <span className="text-red-500 font-semibold">
                        ✗ {cand.rejection_reason}
                      </span>
                    )}
                  </span>

                  <button
                    type="button"
                    onClick={() => handleOpenDetail(cand)}
                    className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-200 transition-colors"
                  >
                    Inspect Physics →
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Physics Detail Modal */}
      {selectedCandidate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-xs">
          <div className="relative max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
            <button
              type="button"
              onClick={() => setSelectedCandidate(null)}
              className="absolute right-4 top-4 rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            >
              ✕
            </button>

            <div className="flex items-center gap-2">
              <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-800">
                Stage D Calibration
              </span>
              <span className="text-xs font-mono text-slate-400">
                {selectedCandidate.candidate_id}
              </span>
            </div>

            <h3 className="mt-2 text-xl font-extrabold text-slate-900">
              {TYPE_CONFIG[selectedCandidate.intervention_type]?.label ||
                selectedCandidate.intervention_type}{" "}
              at Cell {selectedCandidate.cell_id}
            </h3>

            <p className="mt-1 text-xs text-slate-500">
              {selectedCandidate.administrative_zone} Zone · Coordinates:{" "}
              {selectedCandidate.latitude.toFixed(5)}°N, {selectedCandidate.longitude.toFixed(5)}°E
            </p>

            {detailLoading && (
              <div className="my-4 text-xs text-slate-400">Refreshing candidate metrics...</div>
            )}

            {/* Thermodynamics Breakdown Card */}
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                Surface Energy Balance Physics (Surat Summer Overpass)
              </h4>
              <div className="mt-2 grid grid-cols-2 gap-3 text-xs">
                <div className="rounded-lg bg-white p-3 border border-slate-200">
                  <span className="text-slate-400 text-[11px]">Incident Solar Irradiance (K↓)</span>
                  <div className="text-sm font-bold text-slate-800 font-mono">
                    870 W/m² (May 10:30 IST)
                  </div>
                </div>
                <div className="rounded-lg bg-white p-3 border border-slate-200">
                  <span className="text-slate-400 text-[11px]">Effective Conductance (h_eff)</span>
                  <div className="text-sm font-bold text-slate-800 font-mono">
                    45.6 W/(m²·K)
                  </div>
                </div>
                <div className="rounded-lg bg-white p-3 border border-slate-200">
                  <span className="text-slate-400 text-[11px]">Treated Footprint Area</span>
                  <div className="text-sm font-bold text-slate-800 font-mono">
                    {selectedCandidate.usable_area_m2.toLocaleString()} m²
                    {selectedCandidate.tree_count > 0 &&
                      ` (${selectedCandidate.tree_count} trees)`}
                  </div>
                </div>
                <div className="rounded-lg bg-white p-3 border border-slate-200">
                  <span className="text-slate-400 text-[11px]">Modeled Skin Cooling (ΔT_skin)</span>
                  <div className="text-sm font-extrabold text-emerald-600 font-mono">
                    -{selectedCandidate.expected_cooling_c.toFixed(2)}°C
                  </div>
                </div>
              </div>
            </div>

            {/* Cost Breakdown */}
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                Cost Breakdown (CPWD / SMC Schedule of Rates)
              </h4>
              <div className="mt-2 flex items-center justify-between text-xs">
                <span className="text-slate-600">Total Capital + 3-Yr Maintenance:</span>
                <span className="font-mono text-base font-extrabold text-slate-900">
                  {formatINR(selectedCandidate.cost_inr)}
                </span>
              </div>
              <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400">
                <span>Indicative Range:</span>
                <span className="font-mono">
                  {formatINR(selectedCandidate.cost_inr_range[0])} –{" "}
                  {formatINR(selectedCandidate.cost_inr_range[1])}
                </span>
              </div>
            </div>

            {/* Evidence & Methodology Note */}
            <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/50 p-4 text-xs text-indigo-950">
              <div className="font-bold">Evidence Standard:</div>
              <p className="mt-1 text-indigo-900 leading-relaxed">
                {selectedCandidate.evidence_status} (Akbari 2001, Santamouris 2017, Bowler 2010).
                Calculated strictly via calibrated surface energy balance and microclimate
                dispersion, avoiding machine learning regression coefficient fallacy.
              </p>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setSelectedCandidate(null)}
                className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-100"
              >
                Close
              </button>
              {onSelectCandidateOnMap && (
                <button
                  type="button"
                  onClick={() => {
                    const c = selectedCandidate;
                    setSelectedCandidate(null);
                    onSelectCandidateOnMap(c);
                  }}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-500 shadow-sm"
                >
                  Locate On Heat Map
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
