import { useEffect, useMemo, useState } from "react";
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
    needsRoofSurvey?: boolean;
  }
> = {
  tree_canopy: {
    label: "Native Urban Forestry",
    icon: "🌳",
    badgeClass: "bg-emerald-50 text-emerald-800 border-emerald-300",
    description:
      "Native species (Neem, Peepal, Gulmohar) crown shading and latent evapotranspiration cooling.",
    albedoOrBiomass: "Evaporative Latent Flux (LE) + 85% Solar Attenuation",
    needsRoofSurvey: false,
  },
  cool_roof: {
    label: "High-Albedo Cool Roof",
    icon: "⚪",
    badgeClass: "bg-sky-50 text-sky-800 border-sky-300",
    description:
      "Aged high-reflectance coating (Δα = +0.45, SRI ≥ 78) applied on residential/commercial RCC roofs.",
    albedoOrBiomass: "Solar Reflectance α = 0.65 (Aged ASTM D7897)",
    needsRoofSurvey: true,
  },
  green_roof: {
    label: "Extensive Green Roof",
    icon: "🌿",
    badgeClass: "bg-teal-50 text-teal-800 border-teal-300",
    description:
      "Sedum/succulent vegetative roof on structural RCC concrete with soil moisture buffer.",
    albedoOrBiomass: "Combined Biomass Shading & Evapotranspiration",
    needsRoofSurvey: true,
  },
  cool_pavement: {
    label: "Permeable Cool Pavement",
    icon: "🧱",
    badgeClass: "bg-indigo-50 text-indigo-800 border-indigo-300",
    description:
      "High-albedo porous interlocking pavers and permeable concrete for parking and walkways.",
    albedoOrBiomass: "Solar Reflectance α = 0.40 + Subsurface Moisture Evaporation",
    needsRoofSurvey: false,
  },
  public_park_native_trees: {
    label: "Public Park & Native Trees",
    icon: "🏞️",
    badgeClass: "bg-green-50 text-green-800 border-green-300",
    description: "Multi-tier municipal recreational park with deep-root native tree clusters and turf cover.",
    albedoOrBiomass: "Multi-Tier Canopy Extinction + Transpiration",
    needsRoofSurvey: false,
  },
  dense_miyawaki_plantation: {
    label: "Dense Miyawaki Forest",
    icon: "🌲",
    badgeClass: "bg-emerald-100 text-emerald-900 border-emerald-400",
    description: "Ultra-dense native forest cluster (3-4 saplings/m²) creating microclimatic cool island.",
    albedoOrBiomass: "4-Tier Canopy Solar Extinction (LAI ≥ 5.0)",
    needsRoofSurvey: false,
  },
  bioswale_rain_garden: {
    label: "Bioswale & Rain Garden",
    icon: "🌱",
    badgeClass: "bg-lime-50 text-lime-800 border-lime-300",
    description: "Vegetated infiltration swale and bioretention depression providing evaporative cooling.",
    albedoOrBiomass: "Soil Evaporative Cooling + Runoff Infiltration",
    needsRoofSurvey: false,
  },
  rainwater_fed_pond: {
    label: "Rainwater Retention Pond",
    icon: "💧",
    badgeClass: "bg-blue-50 text-blue-800 border-blue-300",
    description: "Microclimatic water body providing localized evaporative breeze downwind.",
    albedoOrBiomass: "Latent Heat of Vaporization (LE)",
    needsRoofSurvey: false,
  },
  shaded_parking_structure: {
    label: "Shaded Parking Structure",
    icon: "⛱️",
    badgeClass: "bg-amber-50 text-amber-800 border-amber-300",
    description: "High-SRI tensile fabric canopy or solar PV shelter eliminating asphalt direct solar absorption.",
    albedoOrBiomass: "100% Direct Solar Interception (SRI ≥ 85)",
    needsRoofSurvey: false,
  },
  green_wall: {
    label: "Modular Living Green Wall",
    icon: "🧗",
    badgeClass: "bg-teal-100 text-teal-900 border-teal-300",
    description: "Vertical modular climbing facade trellis providing envelope shading and transpiration.",
    albedoOrBiomass: "Vertical Facade Solar Shielding + Evapotranspiration",
    needsRoofSurvey: true,
  },
  permeable_ground_cover: {
    label: "Permeable Ground Cover",
    icon: "🪨",
    badgeClass: "bg-stone-50 text-stone-800 border-stone-300",
    description: "Graded porous crushed aggregate and reinforced gravel eliminating unpaved bare soil heat traps.",
    albedoOrBiomass: "Thermal Inertia & Substrate Porosity",
    needsRoofSurvey: false,
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

const PAGE_SIZE = 24;

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

  // View Mode
  const [viewMode, setViewMode] = useState<"grid" | "grouped">("grid");

  // Pagination
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Comparison Selection (max 3)
  const [selectedForCompare, setSelectedForCompare] = useState<InterventionCandidateItem[]>([]);
  const [showCompareModal, setShowCompareModal] = useState<boolean>(false);

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
          setCurrentPage(1);
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

  const handleToggleCompare = (cand: InterventionCandidateItem) => {
    setSelectedForCompare((prev) => {
      const exists = prev.some((c) => c.candidate_id === cand.candidate_id);
      if (exists) {
        return prev.filter((c) => c.candidate_id !== cand.candidate_id);
      }
      if (prev.length >= 3) {
        return prev;
      }
      return [...prev, cand];
    });
  };

  // Filter candidates by text search
  const filteredCandidates = useMemo(() => {
    return candidates.filter((c) => {
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        c.candidate_id.toLowerCase().includes(q) ||
        c.cell_id.toLowerCase().includes(q) ||
        c.administrative_zone.toLowerCase().includes(q) ||
        c.intervention_type.toLowerCase().includes(q)
      );
    });
  }, [candidates, searchQuery]);

  // Distinct Cell Count & Best-Option Portfolio (1 intervention per cell)
  const { uniqueCellsCount, bestOptionPortfolioCost, bestOptionAvgCooling, groupedByCell } =
    useMemo(() => {
      const map = new Map<string, InterventionCandidateItem[]>();
      filteredCandidates.forEach((cand) => {
        const list = map.get(cand.cell_id) || [];
        list.push(cand);
        map.set(cand.cell_id, list);
      });

      let totalBestCost = 0;
      let totalBestCooling = 0;
      map.forEach((cands) => {
        // Pick best cooling option for each cell
        const best = cands.reduce((prev, curr) =>
          curr.expected_cooling_c > prev.expected_cooling_c ? curr : prev
        );
        totalBestCost += best.cost_inr;
        totalBestCooling += best.expected_cooling_c;
      });

      return {
        uniqueCellsCount: map.size,
        bestOptionPortfolioCost: totalBestCost,
        bestOptionAvgCooling: map.size > 0 ? totalBestCooling / map.size : 0,
        groupedByCell: map,
      };
    }, [filteredCandidates]);

  // Pagination Slice
  const totalPages = Math.max(1, Math.ceil(filteredCandidates.length / PAGE_SIZE));
  const paginatedCandidates = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredCandidates.slice(start, start + PAGE_SIZE);
  }, [filteredCandidates, currentPage]);

  const chronicCount = filteredCandidates.filter((c) => c.is_chronic_hotspot).length;

  return (
    <div className="flex flex-col gap-6">
      {/* Hero Header */}
      <div className="rounded-xl border border-slate-700/80 bg-slate-900 p-6 text-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-indigo-500/20 px-2.5 py-0.5 text-xs font-bold text-indigo-300 border border-indigo-500/30">
                Stage D Specification
              </span>
              <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Surface Energy Balance Cooling Catalog
              </span>
            </div>
            <h2 className="mt-2 text-2xl font-bold tracking-tight text-white">
              Surat Urban Cooling Intervention Explorer
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-300">
              Site-specific candidate cooling interventions calibrated via Surface Energy Balance
              equations (R<sub>n</sub> = H + LE + G) and CPWD/SMC schedule of rates across Surat’s
              highest-vulnerability analytical grid cells.
            </p>
          </div>

          {onSwitchToMap && (
            <button
              type="button"
              onClick={onSwitchToMap}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-indigo-500 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2 focus:ring-offset-slate-900"
            >
              <span>View On Heat Map</span>
              <span aria-hidden="true">→</span>
            </button>
          )}
        </div>
      </div>

      {/* Primary KPI Metrics (Reconciled for Mutual Exclusivity) */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Qualifying Candidates
          </span>
          <div className="mt-1 text-3xl font-extrabold text-slate-900 font-mono">
            {totalCount.toLocaleString()}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Across {uniqueCellsCount} unique 100m grid cells · HPI ≥ 35.0
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Best-Option Mean Cooling
          </span>
          <div className="mt-1 text-3xl font-extrabold text-emerald-600 font-mono">
            -{bestOptionAvgCooling.toFixed(2)}°C
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Direct skin ΔT<sub>skin</sub> for optimal intervention per cell
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Chronic Hotspots Addressed
          </span>
          <div className="mt-1 text-3xl font-extrabold text-orange-600 font-mono">
            {chronicCount} <span className="text-sm font-normal text-slate-500">candidates</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Multi-year persistent heat vulnerability (2021–2026 summer/winter; 2021–2025 post-monsoon)
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Best-Option Portfolio Cost
          </span>
          <div className="mt-1 text-3xl font-extrabold text-indigo-700 font-mono">
            {formatINR(bestOptionPortfolioCost)}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            1 option per cell (mutually exclusive options reconciled)
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
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
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
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
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
          {/* View Mode Toggle */}
          <div className="flex items-center rounded-lg border border-slate-200 bg-slate-50 p-1">
            <button
              type="button"
              onClick={() => setViewMode("grid")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all cursor-pointer ${
                viewMode === "grid"
                  ? "bg-white text-slate-900 shadow-xs font-bold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Flat Grid
            </button>
            <button
              type="button"
              onClick={() => setViewMode("grouped")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all cursor-pointer ${
                viewMode === "grouped"
                  ? "bg-white text-slate-900 shadow-xs font-bold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Group by Cell
            </button>
          </div>

          {/* Feasibility Toggle */}
          <div className="flex items-center rounded-lg border border-slate-200 bg-slate-50 p-1">
            <button
              type="button"
              onClick={() => setFeasibility("FEASIBLE")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all cursor-pointer ${
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
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all cursor-pointer ${
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
              placeholder="Search locality, cell ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-48 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-1.5 text-xs text-slate-400 hover:text-slate-600 cursor-pointer"
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

      {/* Candidate Display: Flat Grid Mode */}
      {!loading && !error && viewMode === "grid" && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {paginatedCandidates.map((cand) => {
              const typeInfo = TYPE_CONFIG[cand.intervention_type] || {
                label: cand.intervention_type,
                icon: "📍",
                badgeClass: "bg-slate-100 text-slate-800 border-slate-300",
                description: "",
                albedoOrBiomass: "",
                needsRoofSurvey: false,
              };

              const isCompareSelected = selectedForCompare.some(
                (c) => c.candidate_id === cand.candidate_id
              );

              return (
                <div
                  key={cand.candidate_id}
                  className={`flex flex-col justify-between rounded-xl border bg-white p-5 shadow-xs transition-all ${
                    isCompareSelected
                      ? "border-indigo-500 ring-2 ring-indigo-500/20 shadow-md"
                      : "border-slate-200 hover:border-indigo-300 hover:shadow-md"
                  }`}
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-bold ${typeInfo.badgeClass}`}
                      >
                        <span>{typeInfo.icon}</span>
                        <span>{typeInfo.label}</span>
                      </span>

                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-slate-500">
                          {cand.cell_id}
                        </span>
                        <input
                          type="checkbox"
                          title="Select to compare (max 3)"
                          checked={isCompareSelected}
                          disabled={!isCompareSelected && selectedForCompare.length >= 3}
                          onChange={() => handleToggleCompare(cand)}
                          className="accent-indigo-600 rounded cursor-pointer h-4 w-4"
                        />
                      </div>
                    </div>

                    <h3 className="mt-3 text-base font-bold text-slate-900">
                      {cand.administrative_zone}
                    </h3>
                    <div className="text-[11px] text-slate-400 font-medium">
                      Nearest OSM Locality
                    </div>

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

                    {/* Roof Survey Caveat */}
                    {typeInfo.needsRoofSurvey && (
                      <div className="mt-2.5 rounded-md border border-amber-200 bg-amber-50/80 px-2 py-1 text-[10.5px] text-amber-800 leading-tight">
                        ⚠️ Roof structure unverified — field survey required for structural feasibility.
                      </div>
                    )}

                    {/* Physics & Cost Preview */}
                    <div className="mt-3 grid grid-cols-2 gap-2 rounded-lg bg-slate-50 p-3 text-xs">
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

                    {/* Cost model attribution */}
                    <div className="mt-2 text-[10px] text-slate-400 italic">
                      Co-benefits & maintenance: from literature, to be verified
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
                      className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-200 transition-colors cursor-pointer"
                    >
                      Inspect Physics →
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
              <div className="text-xs text-slate-500">
                Showing {paginatedCandidates.length} of {filteredCandidates.length} candidate interventions
                (Page {currentPage} of {totalPages})
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={currentPage <= 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-100 disabled:opacity-40 cursor-pointer"
                >
                  ← Previous
                </button>
                <span className="px-2 font-mono text-xs font-bold text-slate-800">
                  {currentPage} / {totalPages}
                </span>
                <button
                  type="button"
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-100 disabled:opacity-40 cursor-pointer"
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Candidate Display: Grouped by Cell Mode */}
      {!loading && !error && viewMode === "grouped" && (
        <div className="flex flex-col gap-6">
          {Array.from(groupedByCell.entries()).map(([cellId, cellCands]) => {
            const first = cellCands[0];
            return (
              <div
                key={cellId}
                className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-extrabold text-slate-900">
                        Cell {cellId}
                      </span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
                        {first.administrative_zone} (Nearest Locality)
                      </span>
                      {first.is_chronic_hotspot && (
                        <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-bold text-orange-800">
                          🔥 Chronic Hotspot
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      Lat: {first.latitude.toFixed(4)}°, Lon: {first.longitude.toFixed(4)}° · Baseline LST:{" "}
                      <strong className="text-red-700">
                        {first.baseline_lst_c ? `${first.baseline_lst_c.toFixed(1)}°C` : "N/A"}
                      </strong>{" "}
                      · HPI:{" "}
                      <strong>
                        {first.baseline_hpi ? (first.baseline_hpi * 100).toFixed(1) : "N/A"}
                      </strong>
                    </div>
                  </div>
                  <span className="text-xs text-slate-400 font-medium">
                    {cellCands.length} competing intervention {cellCands.length === 1 ? "option" : "options"}
                  </span>
                </div>

                {/* Sub-grid of competing options */}
                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {cellCands.map((cand) => {
                    const typeInfo = TYPE_CONFIG[cand.intervention_type] || {
                      label: cand.intervention_type,
                      icon: "📍",
                      badgeClass: "bg-slate-100 text-slate-800 border-slate-300",
                      description: "",
                      albedoOrBiomass: "",
                      needsRoofSurvey: false,
                    };
                    const isCompareSelected = selectedForCompare.some(
                      (c) => c.candidate_id === cand.candidate_id
                    );

                    return (
                      <div
                        key={cand.candidate_id}
                        className="flex flex-col justify-between rounded-lg border border-slate-200 bg-slate-50/50 p-3.5 hover:border-indigo-300 transition-all"
                      >
                        <div>
                          <div className="flex items-center justify-between gap-1">
                            <span
                              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-bold ${typeInfo.badgeClass}`}
                            >
                              <span>{typeInfo.icon}</span>
                              <span>{typeInfo.label}</span>
                            </span>
                            <input
                              type="checkbox"
                              title="Select to compare (max 3)"
                              checked={isCompareSelected}
                              disabled={!isCompareSelected && selectedForCompare.length >= 3}
                              onChange={() => handleToggleCompare(cand)}
                              className="accent-indigo-600 rounded cursor-pointer h-3.5 w-3.5"
                            />
                          </div>

                          {typeInfo.needsRoofSurvey && (
                            <div className="mt-2 rounded bg-amber-50 border border-amber-200 p-1 text-[10px] text-amber-800">
                              ⚠️ Roof survey required
                            </div>
                          )}

                          <div className="mt-3">
                            <div className="text-[10px] uppercase font-bold text-slate-400">
                              Expected Cooling
                            </div>
                            <div className="font-mono text-base font-extrabold text-emerald-600">
                              -{cand.expected_cooling_c.toFixed(2)}°C
                            </div>
                          </div>

                          <div className="mt-2">
                            <div className="text-[10px] uppercase font-bold text-slate-400">
                              Cost & Footprint
                            </div>
                            <div className="font-mono text-xs font-bold text-slate-900">
                              {formatINR(cand.cost_inr)}
                            </div>
                            <div className="text-[10px] text-slate-500">
                              {cand.usable_area_m2.toLocaleString()} m²
                            </div>
                          </div>
                        </div>

                        <div className="mt-3 border-t border-slate-200 pt-2 flex items-center justify-between">
                          <span className="text-[10px] text-slate-400 font-mono">
                            {cand.feasibility_status === "FEASIBLE" ? "✓ Feasible" : "✗ Rejected"}
                          </span>
                          <button
                            type="button"
                            onClick={() => handleOpenDetail(cand)}
                            className="text-xs font-bold text-indigo-600 hover:text-indigo-800 cursor-pointer"
                          >
                            Inspect →
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Floating Comparison Drawer / Bar */}
      {selectedForCompare.length > 0 && (
        <div className="fixed bottom-6 right-6 z-40 flex items-center gap-3 rounded-xl border border-indigo-200 bg-slate-900 px-4 py-3 text-white shadow-xl">
          <div className="text-xs">
            <strong className="text-emerald-400">{selectedForCompare.length}</strong> of 3 candidates selected for side-by-side comparison
          </div>
          <button
            type="button"
            onClick={() => setShowCompareModal(true)}
            className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-indigo-500 transition-colors cursor-pointer"
          >
            Compare Now →
          </button>
          <button
            type="button"
            onClick={() => setSelectedForCompare([])}
            className="rounded-lg bg-white/10 px-2 py-1 text-xs text-slate-300 hover:bg-white/20 transition-colors cursor-pointer"
          >
            Clear
          </button>
        </div>
      )}

      {/* Side-by-Side Comparison Modal */}
      {showCompareModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-xs">
          <div className="relative max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-bold text-indigo-900">
                  Physics & Cost Comparison
                </span>
                <h3 className="mt-1 text-xl font-extrabold text-slate-900">
                  Candidate Interventions Side-by-Side
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowCompareModal(false)}
                className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="mt-6 overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    <th className="p-3 font-bold text-slate-600">Metric / Attribute</th>
                    {selectedForCompare.map((c) => (
                      <th key={c.candidate_id} className="p-3 font-bold text-slate-900 min-w-48">
                        <div className="font-mono text-[11px] text-slate-400">{c.candidate_id}</div>
                        <div className="text-sm font-extrabold text-slate-800">
                          {TYPE_CONFIG[c.intervention_type]?.label || c.intervention_type}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  <tr>
                    <td className="p-3 font-semibold text-slate-500">Nearest Locality</td>
                    {selectedForCompare.map((c) => (
                      <td key={c.candidate_id} className="p-3 text-slate-800">
                        {c.administrative_zone}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-3 font-semibold text-slate-500">Grid Cell ID</td>
                    {selectedForCompare.map((c) => (
                      <td key={c.candidate_id} className="p-3 font-mono font-bold text-slate-900">
                        {c.cell_id}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-3 font-semibold text-slate-500">Modeled Cooling (ΔT_skin)</td>
                    {selectedForCompare.map((c) => (
                      <td key={c.candidate_id} className="p-3 font-mono text-base font-extrabold text-emerald-600">
                        -{c.expected_cooling_c.toFixed(2)}°C
                        <span className="block text-[10px] text-slate-400 font-normal">
                          Range: {c.expected_cooling_c_range[0].toFixed(1)}°–{c.expected_cooling_c_range[1].toFixed(1)}°C
                        </span>
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-3 font-semibold text-slate-500">Estimated Cost (INR)</td>
                    {selectedForCompare.map((c) => (
                      <td key={c.candidate_id} className="p-3 font-mono font-bold text-slate-900">
                        {formatINR(c.cost_inr)}
                        <span className="block text-[10px] text-slate-400 font-normal">
                          {formatINR(c.cost_inr_range[0])} – {formatINR(c.cost_inr_range[1])}
                        </span>
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-3 font-semibold text-slate-500">Treated Footprint</td>
                    {selectedForCompare.map((c) => (
                      <td key={c.candidate_id} className="p-3 text-slate-800">
                        {c.usable_area_m2.toLocaleString()} m²
                        {c.tree_count > 0 && ` (${c.tree_count} trees)`}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="p-3 font-semibold text-slate-500">Cost per °C Cooling</td>
                    {selectedForCompare.map((c) => {
                      const costPerDeg = c.expected_cooling_c > 0 ? c.cost_inr / c.expected_cooling_c : 0;
                      return (
                        <td key={c.candidate_id} className="p-3 font-mono text-slate-700">
                          {formatINR(costPerDeg)} / °C
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td className="p-3 font-semibold text-slate-500">Roof Structural Feasibility</td>
                    {selectedForCompare.map((c) => {
                      const needsSurvey = TYPE_CONFIG[c.intervention_type]?.needsRoofSurvey;
                      return (
                        <td key={c.candidate_id} className="p-3">
                          {needsSurvey ? (
                            <span className="text-amber-700 font-medium">
                              ⚠️ Roof type/structure unverified — field survey required
                            </span>
                          ) : (
                            <span className="text-slate-600">N/A (Ground level / surface)</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td className="p-3 font-semibold text-slate-500">Evidence Standard</td>
                    {selectedForCompare.map((c) => (
                      <td key={c.candidate_id} className="p-3 text-[11px] text-slate-600">
                        {c.evidence_status} (Surface Energy Balance)
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={() => setShowCompareModal(false)}
                className="rounded-lg bg-slate-900 px-4 py-2 text-xs font-bold text-white hover:bg-slate-800 cursor-pointer"
              >
                Close Comparison
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Physics Detail Modal */}
      {selectedCandidate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-xs">
          <div className="relative max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
            <button
              type="button"
              onClick={() => setSelectedCandidate(null)}
              className="absolute right-4 top-4 rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 cursor-pointer"
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
              {selectedCandidate.administrative_zone} (Nearest Locality) · Coordinates:{" "}
              {selectedCandidate.latitude.toFixed(5)}°N, {selectedCandidate.longitude.toFixed(5)}°E
            </p>

            {TYPE_CONFIG[selectedCandidate.intervention_type]?.needsRoofSurvey && (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                <strong>Structural Feasibility Caveat:</strong> Roof type and load-bearing capacity are
                unverified in spatial records. A physical municipal engineering survey is required prior
                to deployment to certify RCC structural load-bearing capacity and waterproofing integrity.
              </div>
            )}

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
                    870 W/m² (May ~10:30 local solar time / ~11:00 IST)
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
              <div className="mt-2 text-[10.5px] text-slate-500 italic">
                * Cost model includes capital costs and 3-year establishment maintenance as cited in cost model, not independently verified.
              </div>
            </div>

            {/* Evidence & Methodology Note */}
            <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/50 p-4 text-xs text-indigo-950">
              <div className="font-bold">Evidence Standard:</div>
              <p className="mt-1 text-indigo-900 leading-relaxed">
                {selectedCandidate.evidence_status} (Akbari 2001, Santamouris 2017, Bowler 2010; qualitative co-benefits from literature, to be verified).
                Calculated strictly via calibrated surface energy balance and microclimate
                dispersion, avoiding machine learning regression coefficient fallacy.
              </p>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setSelectedCandidate(null)}
                className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-100 cursor-pointer"
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
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-500 shadow-sm cursor-pointer"
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
