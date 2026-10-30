import { useState, useMemo, useEffect, useRef } from "react";
import type {
  InterventionType,
  OptimizationResultResponse,
  OptimizeRequestPayload,
  ScenarioSolutionItem,
  DeploymentDetail,
  PackageItem,
  LocalityRollupItem,
  StrategyComparison,
  BudgetCurvePoint,
  AreaItem,
} from "../../types/interventions";
import {
  runInterventionOptimization,
  exportOptimizationCsv,
  fetchInterventionAreas,
} from "../../services/interventionsApi";
import { useAuth } from "../../context/AuthContext";
import LoginPanel from "../auth/LoginPanel";

interface OptimizationProps {
  initialBudgetInr?: number;
  initialConfig?: {
    budgetInr?: number;
    algorithm?: "exact" | "nsga2";
    strategy?: "hotspot_first" | "max_benefit" | "cost_effective";
    targetTypes?: Record<InterventionType, boolean>;
    scope?: string;
    autoRun?: boolean;
    source?: string;
  };
  onSwitchToMap?: () => void;
  onSelectCandidateOnMap?: (candidateId: string) => void;
}

function formatINR(val: number): string {
  if (val >= 10000000) {
    return `₹${(val / 10000000).toFixed(2)} Cr`;
  }
  if (val >= 100000) {
    return `₹${(val / 100000).toFixed(2)} Lakh`;
  }
  return `₹${Math.round(val).toLocaleString("en-IN")}`;
}

const BUDGET_PRESETS = [
  { label: "Pilot Hotspots (₹50L)", value: 5000000 },
  { label: "Smart City Phase 1 (₹2.5Cr)", value: 25000000 },
  { label: "Ward Annual (₹5.0Cr)", value: 50000000 },
  { label: "UHAP 2026 Citywide (₹10Cr)", value: 100000000 },
];

export default function Optimization({
  initialBudgetInr = 25000000,
  initialConfig,
  onSwitchToMap,
  onSelectCandidateOnMap,
}: OptimizationProps) {
  // Authentication State
  const {
    token,
    user,
    role,
    isPlannerOrAdmin,
    logout,
    clearSession,
  } = useAuth();

  // Scope & Available Localities
  const [areas, setAreas] = useState<AreaItem[]>([]);
  const [scope, setScope] = useState<string>("all");
  const [areasLoading, setAreasLoading] = useState<boolean>(true);

  // Configuration State
  const [budget, setBudget] = useState<number>(initialConfig?.budgetInr ?? initialBudgetInr);
  const [algorithm, setAlgorithm] = useState<"exact" | "nsga2">(
    initialConfig?.algorithm === "nsga2" ? "nsga2" : "exact"
  );
  const [strategy, setStrategy] = useState<"hotspot_first" | "max_benefit" | "cost_effective">(initialConfig?.strategy ?? "hotspot_first");
  const [generations, setGenerations] = useState<number>(20);
  const [allowedTypes, setAllowedTypes] = useState<Record<InterventionType, boolean>>(
    initialConfig?.targetTypes ?? {
    tree_canopy: true,
    cool_roof: true,
    cool_pavement: true,
    green_roof: false,
    public_park_native_trees: true,
    dense_miyawaki_plantation: true,
    bioswale_rain_garden: true,
    rainwater_fed_pond: false,
    shaded_parking_structure: true,
    green_wall: false,
    permeable_ground_cover: true,
  });

  // Execution & Results State
  const [running, setRunning] = useState<boolean>(false);
  const [exportingCsv, setExportingCsv] = useState<"packages" | "cells" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OptimizationResultResponse | null>(null);
  const [selectedSolutionIdx, setSelectedSolutionIdx] = useState<number>(0);
  const [executionDurationMs, setExecutionDurationMs] = useState<number | null>(null);

  // Drilldown drawer / modal for package contributing cells
  const [selectedPackageForCells, setSelectedPackageForCells] = useState<PackageItem | null>(null);

  // Deployment / package search & filter
  const [searchFilter, setSearchFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [showDefinitions, setShowDefinitions] = useState<boolean>(false);
  const [showParetoSection, setShowParetoSection] = useState<boolean>(false);

  // Load available localities on mount
  useEffect(() => {
    let cancelled = false;
    fetchInterventionAreas(35.0)
      .then((data) => {
        if (!cancelled) {
          setAreas(data);
          setAreasLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("Failed to load intervention areas:", err);
          setAreasLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Stale Configuration Detection
  const isStale = useMemo(() => {
    if (!result?.config) return false;
    const cfg = result.config;
    if (cfg.budget_inr !== budget) return true;
    if (cfg.algorithm !== algorithm) return true;
    if (algorithm === "nsga2" && cfg.generations !== generations) return true;
    const activeTypes = (Object.keys(allowedTypes) as InterventionType[]).filter(
      (t) => allowedTypes[t]
    );
    if (cfg.target_types && cfg.target_types.length !== activeTypes.length) return true;
    return false;
  }, [result, budget, algorithm, generations, allowedTypes]);

  const hasAutoRunRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (initialConfig?.autoRun && !hasAutoRunRef.current && token) {
      hasAutoRunRef.current = true;
      handleRunOptimization();
    }
  }, [initialConfig, token]);

  const handleCancelOptimization = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setRunning(false);
      setError("Optimization execution cancelled by user.");
    }
  };

  const handleRunOptimization = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    setRunning(true);
    setError(null);
    const startTime = performance.now();

    const activeTypes = (Object.keys(allowedTypes) as InterventionType[]).filter(
      (t) => allowedTypes[t]
    );

    const payload: OptimizeRequestPayload = {
      budget_inr: budget,
      algorithm,
      strategy: algorithm === "exact" ? strategy : undefined,
      scope: scope === "all" ? undefined : scope,
      target_types: activeTypes.length > 0 ? activeTypes : undefined,
      generations: algorithm === "nsga2" ? generations : undefined,
    };

    try {
      if (!token) {
        clearSession("Authentication required to run optimization.");
        return;
      }
      const res = await runInterventionOptimization(payload, token, abortController.signal);
      const endTime = performance.now();
      setExecutionDurationMs(Math.round(endTime - startTime));
      setResult(res);
      setSelectedSolutionIdx(0);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setError("Optimization execution cancelled by user.");
        return;
      }
      const errMsg =
        err instanceof Error
          ? err.message
          : "Optimization execution failed. Check server connectivity.";
      if (errMsg.includes("401")) {
        clearSession("Session expired or unauthorized (401). Please sign in again.");
      } else {
        setError(errMsg);
      }
    } finally {
      setRunning(false);
      abortControllerRef.current = null;
    }
  };

  // CSV Export Handler: Package-level or Cell-level directly from server
  const handleExportCsv = async (level: "packages" | "cells") => {
    if (!token) {
      clearSession("Authentication required to export CSV.");
      return;
    }
    setExportingCsv(level);
    try {
      const activeTypes = (Object.keys(allowedTypes) as InterventionType[]).filter(
        (t) => allowedTypes[t]
      );
      const payload: OptimizeRequestPayload = {
        budget_inr: budget,
        algorithm,
        strategy: algorithm === "exact" ? strategy : undefined,
        scope: scope === "all" ? undefined : scope,
        target_types: activeTypes.length > 0 ? activeTypes : undefined,
        generations: algorithm === "nsga2" ? generations : undefined,
      };

      const blob = await exportOptimizationCsv(
        payload,
        level === "packages" ? "package" : "cell",
        token
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.setAttribute("href", url);
      link.setAttribute(
        "download",
        `surat_optimization_${scope}_${level}_${Math.round(budget / 100000)}L.csv`
      );
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      console.error("CSV Export failed:", err);
      setError(
        err instanceof Error
          ? err.message
          : "Failed to download export CSV from server."
      );
    } finally {
      setExportingCsv(null);
    }
  };

  const activeSolution: ScenarioSolutionItem | null =
    result && result.solutions.length > 0
      ? result.solutions[selectedSolutionIdx] || result.solutions[0]
      : null;

  const solvedBudgetCap = result?.config?.budget_inr || activeSolution?.budget_limit_inr || budget;
  const utilizationAgainstSolved = activeSolution
    ? (activeSolution.total_cost_inr / solvedBudgetCap) * 100
    : 0;

  // Filtered packages
  const filteredPackages: PackageItem[] = useMemo(() => {
    if (!activeSolution?.selected_packages) return [];
    return activeSolution.selected_packages.filter((pkg) => {
      const matchesSearch =
        pkg.package_id.toLowerCase().includes(searchFilter.toLowerCase()) ||
        pkg.cluster_id.toLowerCase().includes(searchFilter.toLowerCase()) ||
        pkg.locality.toLowerCase().includes(searchFilter.toLowerCase()) ||
        pkg.cell_ids.some((cid) => cid.toLowerCase().includes(searchFilter.toLowerCase()));
      const matchesType =
        typeFilter === "ALL" ||
        (typeFilter === "CHRONIC" && pkg.chronic_hotspot_cells_count > 0) ||
        pkg.intervention_type.toLowerCase().includes(typeFilter.toLowerCase());
      return matchesSearch && matchesType;
    });
  }, [activeSolution, searchFilter, typeFilter]);

  // Fallback deployments if legacy
  const filteredDeployments: DeploymentDetail[] = useMemo(() => {
    if (!activeSolution?.deployments) return [];
    return activeSolution.deployments.filter((d) => {
      const matchesSearch =
        d.cell_id.toLowerCase().includes(searchFilter.toLowerCase()) ||
        d.intervention_type.toLowerCase().includes(searchFilter.toLowerCase()) ||
        d.administrative_zone.toLowerCase().includes(searchFilter.toLowerCase());
      const matchesType =
        typeFilter === "ALL" ||
        (typeFilter === "CHRONIC" && d.is_chronic_hotspot) ||
        d.intervention_type.toLowerCase().includes(typeFilter.toLowerCase());
      return matchesSearch && matchesType;
    });
  }, [activeSolution, searchFilter, typeFilter]);

  // Unauthenticated / Insufficient Permissions
  if (!isPlannerOrAdmin) {
    return (
      <div className="py-6">
        <LoginPanel
          title="Optimization Authentication Required"
          subtitle="Stage D budget optimization and intervention selection require Planner or Admin privileges."
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Hero Header */}
      <div className="rounded-2xl border border-slate-800/90 bg-slate-900 p-7 text-white shadow-elevated relative overflow-hidden">
        <div
          className="absolute inset-0 opacity-[0.03] pointer-events-none"
          style={{
            backgroundImage:
              "radial-gradient(#2dd4bf 1px, transparent 1px), radial-gradient(#2dd4bf 1px, #0f172a 1px)",
            backgroundSize: "24px 24px",
            backgroundPosition: "0 0, 12px 12px",
          }}
        />

        <div className="relative flex flex-wrap items-center justify-between gap-6 z-10">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="rounded-full bg-teal-500/15 px-3 py-0.5 text-xs font-bold text-teal-300 border border-teal-500/30 font-mono">
                Stage D Multi-Objective Solver
              </span>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
                Exact 0/1 Integer Knapsack DP · Queen Contiguous Packages (≤ 4 cells)
              </span>
            </div>
            <h2 className="mt-3 text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Surat Urban Cooling Optimization Engine
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">
              Allocates implementation packages across municipal localities under capital budget ceilings.
              Every package is guaranteed Queen contiguous (max 4 cells), mutually exclusive (zero duplicate cells),
              and scientifically grounded in surface skin cooling (ΔT<sub>skin</sub>). 2m ambient air temperature is unmodeled.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0 flex-wrap">
            <div className="text-right">
              <div className="text-xs text-slate-300">
                Logged in: <strong className="text-white">{user?.username}</strong>
              </div>
              <span className="inline-block mt-0.5 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-teal-500/20 text-teal-300 border border-teal-500/40 font-mono">
                {role}
              </span>
            </div>

            <button
              type="button"
              onClick={() => setShowDefinitions((prev) => !prev)}
              className="rounded-xl border border-slate-700 bg-slate-800/80 px-3 py-2 text-xs font-semibold text-teal-300 hover:bg-slate-700/80 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              📖 Terminology &amp; Units
            </button>

            <button
              type="button"
              onClick={logout}
              className="rounded-xl border border-slate-700 bg-slate-800/80 px-3.5 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700/80 hover:text-white transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              Sign Out
            </button>

            {onSwitchToMap && (
              <button
                type="button"
                onClick={onSwitchToMap}
                className="flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800/80 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700/80 hover:text-white transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-teal-500"
              >
                <span>View Heat Map</span>
              </button>
            )}

            {running && (
              <button
                type="button"
                onClick={handleCancelOptimization}
                className="flex items-center gap-1.5 rounded-xl border border-rose-500/50 bg-rose-600/20 px-3.5 py-2 text-xs font-bold text-rose-200 hover:bg-rose-600/30 transition-all cursor-pointer"
              >
                <span>✕</span>
                <span>Cancel</span>
              </button>
            )}

            <button
              type="button"
              disabled={running}
              onClick={handleRunOptimization}
              className="flex items-center gap-2 rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-bold text-white shadow-md hover:bg-teal-500 disabled:opacity-50 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-teal-400 focus:ring-offset-2 focus:ring-offset-slate-900"
            >
              {running ? (
                <>
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Optimizing Packages…</span>
                </>
              ) : (
                <>
                  <span>Execute Optimization</span>
                  <span>⚡</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Terminology & Units Callout (collapsible) */}
      {showDefinitions && (
        <div className="rounded-xl border border-teal-200 bg-teal-50/70 p-5 text-xs text-slate-800 shadow-xs">
          <div className="flex items-center justify-between border-b border-teal-200 pb-2 mb-3">
            <h4 className="font-extrabold uppercase tracking-wider text-teal-950 flex items-center gap-1.5">
              <span>📖</span>
              <span>Scientific Definitions, Footprint Reconciliations &amp; Unit Conventions</span>
            </h4>
            <button
              type="button"
              onClick={() => setShowDefinitions(false)}
              className="text-slate-400 hover:text-slate-700 text-sm font-bold cursor-pointer"
            >
              ✕
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white/80 p-3 rounded-lg border border-teal-100">
              <span className="font-bold text-teal-900 block mb-1">1. Canonical Package Units</span>
              <p className="text-[11px] leading-relaxed text-slate-600">
                <strong>Package:</strong> Queen contiguous block of ≤ 4 cells (up to 4.0 ha), representing an actionable municipal procurement unit.<br />
                <strong>Cell-Exclusivity:</strong> Exactly 1 primary intervention per cell across all clusters and packages. Zero duplicate cells.<br />
                <strong>Cost Invariance:</strong> Σ(cell cost) = package cost = cluster cost = sum of engineering line items.
              </p>
            </div>
            <div className="bg-white/80 p-3 rounded-lg border border-teal-100">
              <span className="font-bold text-teal-900 block mb-1">2. Local vs Extensive Cooling</span>
              <p className="text-[11px] leading-relaxed text-slate-600">
                <strong>Surface Skin Cooling (ΔT<sub>skin</sub>):</strong> Direct physical skin temperature reduction over treated footprints during May clear-sky noon (870 W/m², h<sub>eff</sub> = 45.6 W/(m²·K)).<br />
                <strong>Extensive Thermal Benefit:</strong> Conserved energy benefit measured in <strong>K·m²</strong> (replaces °C·cell). Ambient 2m air temperature is unmodeled.
              </p>
            </div>
            <div className="bg-white/80 p-3 rounded-lg border border-teal-100">
              <span className="font-bold text-teal-900 block mb-1">3. Pre-Tender Field Surveys</span>
              <p className="text-[11px] leading-relaxed text-slate-600">
                All allocations are classified <strong>FEASIBLE_SUBJECT_TO_SURVEY</strong>.
                Structural load capacity (RCC dead load), rooftop tenure rights, and underground utility clearances
                are unverified at remote sensing scale and require mandatory on-site engineering surveys prior to tender.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Stale Configuration Warning Banner */}
      {isStale && activeSolution && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-xs text-amber-900 flex flex-wrap items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center gap-2.5">
            <span className="text-xl">⚠️</span>
            <div>
              <strong className="font-bold text-amber-950">Configuration Modified (Stale Results Displayed):</strong>
              <div className="mt-0.5 text-amber-800">
                Controls changed (Budget: {formatINR(budget)}, Scope: {scope.toUpperCase()}), but the active solution was computed with{" "}
                <strong>Budget: {formatINR(solvedBudgetCap)}</strong> ({result?.algorithm}). Click &ldquo;Re-execute Optimization&rdquo; to solve under new parameters.
              </div>
            </div>
          </div>
          <button
            type="button"
            disabled={running}
            onClick={handleRunOptimization}
            className="rounded-lg bg-amber-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-amber-700 transition-colors shadow-xs cursor-pointer shrink-0"
          >
            Re-execute Optimization ({formatINR(budget)}) →
          </button>
        </div>
      )}

      {initialConfig?.source && (
        <div className="flex items-center justify-between rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 text-xs text-teal-900 shadow-xs">
          <div className="flex items-center gap-2">
            <span className="text-base">⚡</span>
            <span>
              <strong>Configured from Scenario Lab (Scenario: {initialConfig.source}):</strong> Budget {formatINR(budget)}, Strategy {strategy.replace("_", " ")}, Algorithm {algorithm.toUpperCase()}.
            </span>
          </div>
          <span className="font-mono text-[10px] text-teal-700 font-bold bg-teal-100/70 px-2 py-0.5 rounded">
            AUTO-CONFIGURED
          </span>
        </div>
      )}

      {/* Configuration & Controls */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Col 1: Scope & Budget Limit */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs flex flex-col justify-between">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              1. Geographic Scope &amp; Budget Ceiling
            </h3>

            {/* Scope Selector */}
            <div className="mt-3">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Geographic Scope (Locality):
              </label>
              <select
                value={scope}
                onChange={(e) => setScope(e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 shadow-xs focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 cursor-pointer"
              >
                <option value="all">🌐 All Areas (Citywide Municipal Domain)</option>
                {areas.map((a) => (
                  <option key={a.area_name} value={a.area_name}>
                    📍 {a.area_name} ({a.chronic_hotspot_count} chronic hotspots · {a.eligible_cell_count} cells)
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[10px] text-slate-400">
                {areasLoading ? "Loading localities..." : `Evaluates all candidate packages in ${scope === "all" ? "citywide domain" : scope}.`}
              </p>
            </div>

            {/* Budget Presets */}
            <div className="mt-4 flex flex-wrap gap-2">
              {BUDGET_PRESETS.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => setBudget(p.value)}
                  className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-all cursor-pointer ${
                    budget === p.value
                      ? "bg-teal-600 text-white font-bold shadow-xs"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            {/* Budget Slider */}
            <div className="mt-4">
              <div className="flex justify-between text-xs font-semibold text-slate-700">
                <span>Capital Budget Limit:</span>
                <span className="font-mono text-sm text-teal-700 font-extrabold">
                  {formatINR(budget)}
                </span>
              </div>
              <input
                type="range"
                min="1000000"
                max="150000000"
                step="1000000"
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
                className="mt-2 w-full accent-teal-600 cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-slate-400 font-mono">
                <span>₹10 Lakh</span>
                <span>₹2.5 Cr</span>
                <span>₹15 Cr</span>
              </div>
            </div>
          </div>
        </div>

        {/* Col 2: Optimization Algorithm & Strategy */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs flex flex-col justify-between">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              2. Solver &amp; Prioritization Strategy
            </h3>

            {/* Algorithm Selector */}
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setAlgorithm("exact")}
                className={`p-2.5 rounded-lg border text-left transition-all cursor-pointer ${
                  algorithm === "exact"
                    ? "border-teal-600 bg-teal-50/50 shadow-xs ring-1 ring-teal-500"
                    : "border-slate-200 bg-white hover:bg-slate-50"
                }`}
              >
                <div className="text-xs font-bold text-slate-900 flex items-center justify-between">
                  <span>🎯 Exact DP Knapsack</span>
                  <span className="text-[9px] bg-teal-100 text-teal-800 font-bold px-1.5 py-0.5 rounded font-mono">Optimal</span>
                </div>
                <div className="text-[9.5px] text-slate-500 mt-1 leading-tight">
                  Integer 0/1 knapsack via dynamic programming; provably optimal under budget ceiling.
                </div>
              </button>

              <button
                type="button"
                onClick={() => setAlgorithm("nsga2")}
                className={`p-2.5 rounded-lg border text-left transition-all cursor-pointer ${
                  algorithm === "nsga2"
                    ? "border-teal-600 bg-teal-50/50 shadow-xs ring-1 ring-teal-500"
                    : "border-slate-200 bg-white hover:bg-slate-50"
                }`}
              >
                <div className="text-xs font-bold text-slate-900 flex items-center justify-between">
                  <span>🧬 NSGA-II Genetic</span>
                  <span className="text-[9px] bg-indigo-100 text-indigo-800 font-bold px-1.5 py-0.5 rounded font-mono">Pareto</span>
                </div>
                <div className="text-[9.5px] text-slate-500 mt-1 leading-tight">
                  Multi-objective Pareto frontier trading off cost, thermal benefit (K·m²), and hotspot coverage.
                </div>
              </button>
            </div>

            {/* Exact Strategy Selector (if Exact DP selected) */}
            {algorithm === "exact" && (
              <div className="mt-4 border-t border-slate-100 pt-3">
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Exact Knapsack Objective:
                </label>
                <div className="flex flex-col gap-1.5">
                  {[
                    {
                      key: "hotspot_first",
                      label: "Strategy A: Hotspot-First (Recommended)",
                      desc: "Lexicographically prioritizes chronic heat islands, then maximum extensive thermal benefit (K·m²).",
                    },
                    {
                      key: "max_benefit",
                      label: "Strategy B: Maximum Thermal Benefit",
                      desc: "Maximizes aggregate extensive cooling (K·m²) across citywide domain without vulnerability weighting.",
                    },
                    {
                      key: "cost_effective",
                      label: "Strategy C: Cost-Effectiveness Ratio",
                      desc: "Prioritizes benefit per rupee (K·m²/INR) across municipal packages.",
                    },
                  ].map((s) => (
                    <label
                      key={s.key}
                      className={`flex items-start gap-2.5 p-2 rounded-lg border cursor-pointer transition-all ${
                        strategy === s.key
                          ? "border-teal-400 bg-teal-50/40"
                          : "border-slate-200 bg-white hover:bg-slate-50"
                      }`}
                    >
                      <input
                        type="radio"
                        name="exact_strategy"
                        checked={strategy === s.key}
                        onChange={() => setStrategy(s.key as typeof strategy)}
                        className="mt-0.5 accent-teal-600 cursor-pointer"
                      />
                      <div>
                        <div className="text-xs font-bold text-slate-900">{s.label}</div>
                        <div className="text-[10px] text-slate-500 leading-tight">{s.desc}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* NSGA-II Generations (if NSGA-II selected) */}
            {algorithm === "nsga2" && (
              <div className="mt-4 border-t border-slate-100 pt-3">
                <div className="flex justify-between text-xs font-semibold text-slate-700">
                  <span>NSGA-II Generations:</span>
                  <span className="font-mono text-xs font-bold text-teal-700">
                    {generations} iterations
                  </span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="50"
                  step="5"
                  value={generations}
                  onChange={(e) => setGenerations(Number(e.target.value))}
                  className="mt-2 w-full accent-teal-600 cursor-pointer"
                />
                <p className="mt-1 text-[10px] text-slate-400">
                  Crossover &amp; mutation iterations across candidate package chromosomes.
                </p>
              </div>
            )}
          </div>

          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Discretization: <strong>₹5,000 unit</strong></span>
            {executionDurationMs !== null && (
              <span className="font-mono font-bold text-emerald-600">
                Runtime: {executionDurationMs} ms
              </span>
            )}
          </div>
        </div>

        {/* Col 3: Allowed Typologies */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                3. Eligible Typologies &amp; Prerequisites
              </h3>
              <span className="text-[10px] font-mono text-teal-700 bg-teal-50 px-2 py-0.5 rounded font-bold">
                9 Active In Catalog
              </span>
            </div>

            <div className="mt-3 flex flex-col gap-2 max-h-64 overflow-y-auto pr-1">
              {[
                {
                  key: "cool_roof",
                  label: "⚪ High-Albedo Cool Roof",
                  status: "Eligible",
                  surface: "RCC roofs / concrete decks",
                  prereq: "Structural survey, aged coating (Δα = +0.45)",
                },
                {
                  key: "tree_canopy",
                  label: "🌳 Native Urban Forestry",
                  status: "Eligible",
                  surface: "Open ground, roadside verges",
                  prereq: "Soil depth ≥ 1.0m, unpaved buffer, 15% mortality buffer",
                },
                {
                  key: "cool_pavement",
                  label: "🧱 Permeable Cool Pavers",
                  status: "Eligible",
                  surface: "Pedestrian plazas, light parking",
                  prereq: "Permeable sub-base, high solar reflectance",
                },
                {
                  key: "green_roof",
                  label: "🌿 Extensive Green Roof",
                  status: "Provisional",
                  surface: "Load-bearing RCC flat roofs",
                  prereq: "RCC dead load survey (≥ 150 kg/m²), drainage membrane",
                },
                {
                  key: "public_park_native_trees",
                  label: "🏞️ Public Park & Trees",
                  status: "Eligible",
                  surface: "Municipal open spaces / parks",
                  prereq: "Native species, water tanker access, ground plot ≥ 400 m²",
                },
                {
                  key: "dense_miyawaki_plantation",
                  label: "🌲 Miyawaki Forest",
                  status: "Eligible",
                  surface: "Contiguous urban plots",
                  prereq: "Ultra-dense planting (3-4 saplings/m²), organic soil prep",
                },
                {
                  key: "bioswale_rain_garden",
                  label: "💧 Bioswale & Rain Garden",
                  status: "Eligible",
                  surface: "Stormwater runoff corridors",
                  prereq: "Natural drainage swale, engineered bioretention soil",
                },
                {
                  key: "shaded_parking_structure",
                  label: "🅿️ Shaded Parking Canopy",
                  status: "Eligible",
                  surface: "Commercial & municipal parking",
                  prereq: "Solar / high-reflectance overhead shade canopy",
                },
                {
                  key: "permeable_ground_cover",
                  label: "🟩 Permeable Ground Cover",
                  status: "Eligible",
                  surface: "Unpaved vacant lots & medians",
                  prereq: "Gravel / porous turf pavers, erosion control",
                },
              ].map((item) => {
                const isChecked = allowedTypes[item.key as InterventionType];
                return (
                  <label
                    key={item.key}
                    className={`flex items-start gap-2.5 rounded-lg border p-2 transition-all cursor-pointer ${
                      isChecked
                        ? "border-teal-300 bg-teal-50/30"
                        : "border-slate-200 bg-white hover:bg-slate-50 opacity-60"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() =>
                        setAllowedTypes((prev) => ({
                          ...prev,
                          [item.key]: !prev[item.key as InterventionType],
                        }))
                      }
                      className="mt-0.5 accent-teal-600 rounded cursor-pointer"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-xs font-bold text-slate-900 truncate">{item.label}</span>
                        <span
                          className={`text-[9px] font-bold px-1.5 py-0.2 rounded font-mono ${
                            item.status === "Eligible"
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {item.status}
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-500 leading-tight mt-0.5">
                        <strong className="text-slate-600">Req:</strong> {item.surface} · {item.prereq}
                      </div>
                    </div>
                  </label>
                );
              })}

              {/* Explicitly Non-Assessable Typologies (Kept Removed) */}
              <div className="mt-2 pt-2 border-t border-slate-100 flex flex-col gap-1.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Non-Assessable Typologies (Excluded from Active Solver)
                </span>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-2 text-[10px] text-slate-500">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-700">🌊 Rainwater-Fed Retention Pond</span>
                    <span className="font-mono text-[9px] bg-slate-200 text-slate-700 px-1.5 py-0.2 rounded font-bold">
                      Not assessable
                    </span>
                  </div>
                  <div className="text-[9.5px] text-slate-400 mt-0.5">
                    Requires high-resolution LiDAR / DEM surface elevation hydrological catchment modeling. Kept removed.
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-2 text-[10px] text-slate-500">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-700">🧗 Modular Green Living Wall</span>
                    <span className="font-mono text-[9px] bg-slate-200 text-slate-700 px-1.5 py-0.2 rounded font-bold">
                      Not assessable
                    </span>
                  </div>
                  <div className="text-[9.5px] text-slate-400 mt-0.5">
                    Requires 3D building height, wall aspect &amp; facade structural load inventory. Kept removed.
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-3 pt-2 border-t border-slate-100 text-[10px] text-slate-400 flex justify-between items-center">
            <span>Pre-tender structural survey required for all rooftop interventions.</span>
            <span className="font-mono text-teal-700 font-semibold">
              {(Object.keys(allowedTypes) as InterventionType[]).filter((t) => allowedTypes[t]).length} selected
            </span>
          </div>
        </div>
      </div>

      {/* Specific Informative Banners for Empty / Over-Budget Outcomes */}
      {result && result.status === "CHEAPEST_EXCEEDS_BUDGET" && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-5 text-amber-900 shadow-xs">
          <div className="flex items-start gap-3">
            <span className="text-2xl">⚠️</span>
            <div>
              <h4 className="text-sm font-bold text-amber-950">
                Budget Ceiling Exceeded by Minimum Package Unit
              </h4>
              <p className="mt-1 text-xs text-amber-800 leading-relaxed">
                {result.reason || "The allocated budget cap is smaller than the lowest-cost implementation package available in the selected scope."}
              </p>
              <div className="mt-2 text-xs font-semibold text-amber-900">
                Recommendation: Increase budget limit to at least ₹15 Lakh, or expand scope to include localities with lower-cost per-cell deployments.
              </div>
            </div>
          </div>
        </div>
      )}

      {result && result.status === "NO_CANDIDATES" && (
        <div className="rounded-xl border border-blue-300 bg-blue-50 p-5 text-blue-900 shadow-xs">
          <div className="flex items-start gap-3">
            <span className="text-2xl">ℹ️</span>
            <div>
              <h4 className="text-sm font-bold text-blue-950">
                No Eligible Candidate Packages Found
              </h4>
              <p className="mt-1 text-xs text-blue-800 leading-relaxed">
                {result.reason || "No packages matched the selected scope and intervention typology filters."}
              </p>
              <div className="mt-2 text-xs font-semibold text-blue-900">
                Recommendation: Select additional intervention typologies or set scope to &ldquo;All Areas&rdquo;.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Error Callout */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <div className="font-bold">Optimization Error:</div>
          <div>{error}</div>
        </div>
      )}

      {/* Results Section */}
      {result && result.solutions.length > 0 && activeSolution && (
        <div className="flex flex-col gap-6">
          {/* Solution Selector Header */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="rounded-full bg-teal-100 px-2.5 py-0.5 text-xs font-bold text-teal-800 font-mono">
                    {result.algorithm.toUpperCase()} · {activeSolution.solution_id}
                  </span>
                  <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-800 font-mono">
                    {activeSolution.optimality_gap_percent === 0 || activeSolution.optimality_gap_percent === undefined
                      ? "✓ Exact DP Optimal (0.00% Gap)"
                      : `Heuristic Gap: ${activeSolution.optimality_gap_percent.toFixed(2)}%`}
                  </span>
                  <span className="text-xs text-slate-500 font-mono">
                    Scope: <strong>{scope === "all" ? "Citywide" : scope}</strong>
                  </span>
                </div>
                <h3 className="mt-2 text-xl font-extrabold text-slate-900">
                  Recommended Municipal Allocation Plan: {formatINR(activeSolution.total_cost_inr)}
                </h3>
              </div>

              {/* Action Buttons: CSV Exports */}
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  disabled={exportingCsv !== null}
                  onClick={() => handleExportCsv("packages")}
                  className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 shadow-xs cursor-pointer disabled:opacity-50"
                  title="Download CSV of implementation packages (≤ 4 cells each) with capex and extensive cooling"
                >
                  <span>📥 Export Packages (CSV)</span>
                </button>

                <button
                  type="button"
                  disabled={exportingCsv !== null}
                  onClick={() => handleExportCsv("cells")}
                  className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 shadow-xs cursor-pointer disabled:opacity-50"
                  title="Download CSV of all individual contributing 100m cells with coordinates and HPI"
                >
                  <span>📥 Export Contributing Cells (CSV)</span>
                </button>
              </div>
            </div>

            {/* Summary KPI Strip: 9 Key Indicators */}
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {/* Spend */}
              <div className="rounded-lg bg-slate-50 p-3 border border-slate-200/60">
                <span className="text-[10px] text-slate-400 uppercase font-bold">
                  Capital Spend
                </span>
                <div className="mt-1 font-mono text-base font-extrabold text-slate-900">
                  {formatINR(activeSolution.total_cost_inr)}
                </div>
                <div className="text-[10px] text-slate-500">
                  {utilizationAgainstSolved.toFixed(1)}% of {formatINR(solvedBudgetCap)} cap
                </div>
              </div>

              {/* Thermal Benefit */}
              <div className="rounded-lg bg-slate-50 p-3 border border-slate-200/60">
                <span className="text-[10px] text-slate-400 uppercase font-bold">
                  Extensive Thermal Benefit
                </span>
                <div className="mt-1 font-mono text-base font-extrabold text-indigo-700">
                  {Math.round(activeSolution.portfolio_thermal_benefit_c_m2).toLocaleString()} K·m²
                </div>
                <div className="text-[10px] text-slate-500">
                  Conserved extensive cooling sum
                </div>
              </div>

              {/* Mean Local Skin Cooling */}
              <div className="rounded-lg bg-slate-50 p-3 border border-slate-200/60">
                <span className="text-[10px] text-slate-400 uppercase font-bold">
                  Mean Local Skin ΔT
                </span>
                <div className="mt-1 font-mono text-base font-extrabold text-emerald-600">
                  -{activeSolution.mean_local_cooling_c.toFixed(2)}°C
                </div>
                <div className="text-[10px] text-slate-500">
                  Footprint surface skin drop
                </div>
              </div>

              {/* Packages & Cells */}
              <div className="rounded-lg bg-slate-50 p-3 border border-slate-200/60">
                <span className="text-[10px] text-slate-400 uppercase font-bold">
                  Packages &amp; Cells
                </span>
                <div className="mt-1 font-mono text-base font-extrabold text-teal-800">
                  {activeSolution.packages_count ?? activeSolution.selected_packages?.length ?? activeSolution.interventions_count} pkgs · {activeSolution.cells_count ?? activeSolution.interventions_count} cells
                </div>
                <div className="text-[10px] text-slate-500">
                  Queen contiguous · 0 duplicate cells
                </div>
              </div>

              {/* Chronic Hotspots Mitigated */}
              <div className="rounded-lg bg-slate-50 p-3 border border-slate-200/60">
                <span className="text-[10px] text-slate-400 uppercase font-bold">
                  Chronic Hotspots
                </span>
                <div className="mt-1 font-mono text-base font-extrabold text-orange-600">
                  {activeSolution.chronic_hotspots_count} cells
                </div>
                <div className="text-[10px] text-slate-500">
                  🔥 Persistent thermal vulnerability
                </div>
              </div>
            </div>
          </div>

          {/* 3-Strategy Comparison Cards (if available) */}
          {result.strategy_comparison && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center justify-between mb-3 border-b border-slate-100 pb-2">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    ⚖️ 3-Strategy Comparative Analysis (Same Discretization &amp; Budget Ceiling)
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Compare the recommended Hotspot-First strategy against unconstrained benefit maximization and the greedy heuristic.
                  </p>
                </div>
                <span className="text-xs font-mono font-bold text-teal-700 bg-teal-50 px-2.5 py-1 rounded-md border border-teal-200">
                  Recommended: {result.strategy_comparison.recommended_strategy.replace(/_/g, " ").toUpperCase()}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Strategy A */}
                <div
                  className={`rounded-xl p-4 border transition-all ${
                    result.strategy_comparison.recommended_strategy === "strategy_a_hotspot_first"
                      ? "border-teal-400 bg-teal-50/30 ring-1 ring-teal-400"
                      : "border-slate-200 bg-slate-50/50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-teal-900">
                      {result.strategy_comparison.strategy_a_hotspot_first.title}
                    </span>
                    <span className="text-[10px] font-bold bg-teal-600 text-white rounded px-1.5 py-0.5">
                      Exact DP
                    </span>
                  </div>
                  <p className="mt-1 text-[10px] text-slate-600 leading-tight">
                    {result.strategy_comparison.strategy_a_hotspot_first.description}
                  </p>
                  <div className="mt-3 space-y-1.5 font-mono text-xs border-t border-teal-100 pt-2">
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-sans text-[11px]">Spend:</span>
                      <strong className="text-slate-900">
                        {formatINR(result.strategy_comparison.strategy_a_hotspot_first.spend_inr)}
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-sans text-[11px]">Packages / Cells:</span>
                      <strong className="text-slate-800">
                        {result.strategy_comparison.strategy_a_hotspot_first.packages_count} pkgs · {result.strategy_comparison.strategy_a_hotspot_first.cells_count} cells
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-sans text-[11px]">Chronic Hotspots:</span>
                      <strong className="text-orange-600">
                        {result.strategy_comparison.strategy_a_hotspot_first.chronic_hotspots_count} cells
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-sans text-[11px]">Thermal Benefit:</span>
                      <strong className="text-indigo-700">
                        {Math.round(result.strategy_comparison.strategy_a_hotspot_first.thermal_benefit_k_m2).toLocaleString()} K·m²
                      </strong>
                    </div>
                  </div>
                </div>

                {/* Strategy B */}
                <div className="rounded-xl p-4 border border-slate-200 bg-slate-50/50">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-slate-900">
                      {result.strategy_comparison.strategy_b_max_benefit.title}
                    </span>
                    <span className="text-[10px] font-bold bg-slate-700 text-white rounded px-1.5 py-0.5">
                      Exact DP
                    </span>
                  </div>
                  <p className="mt-1 text-[10px] text-slate-600 leading-tight">
                    {result.strategy_comparison.strategy_b_max_benefit.description}
                  </p>
                  <div className="mt-3 space-y-1.5 font-mono text-xs border-t border-slate-200 pt-2">
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-sans text-[11px]">Spend:</span>
                      <strong className="text-slate-900">
                        {formatINR(result.strategy_comparison.strategy_b_max_benefit.spend_inr)}
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-sans text-[11px]">Packages / Cells:</span>
                      <strong className="text-slate-800">
                        {result.strategy_comparison.strategy_b_max_benefit.packages_count} pkgs · {result.strategy_comparison.strategy_b_max_benefit.cells_count} cells
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-sans text-[11px]">Chronic Hotspots:</span>
                      <strong className="text-orange-600">
                        {result.strategy_comparison.strategy_b_max_benefit.chronic_hotspots_count} cells
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-sans text-[11px]">Thermal Benefit:</span>
                      <strong className="text-indigo-700">
                        {Math.round(result.strategy_comparison.strategy_b_max_benefit.thermal_benefit_k_m2).toLocaleString()} K·m²
                      </strong>
                    </div>
                  </div>
                </div>

                {/* Strategy C */}
                <div className="rounded-xl p-4 border border-slate-200 bg-slate-50/50">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-slate-900">
                      {result.strategy_comparison.strategy_c_greedy_baseline.title}
                    </span>
                    <span className="text-[10px] font-bold bg-amber-600 text-white rounded px-1.5 py-0.5">
                      Greedy Heuristic
                    </span>
                  </div>
                  <p className="mt-1 text-[10px] text-slate-600 leading-tight">
                    {result.strategy_comparison.strategy_c_greedy_baseline.description}
                  </p>
                  <div className="mt-3 space-y-1.5 font-mono text-xs border-t border-slate-200 pt-2">
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-sans text-[11px]">Spend:</span>
                      <strong className="text-slate-900">
                        {formatINR(result.strategy_comparison.strategy_c_greedy_baseline.spend_inr)}
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-sans text-[11px]">Packages / Cells:</span>
                      <strong className="text-slate-800">
                        {result.strategy_comparison.strategy_c_greedy_baseline.packages_count} pkgs · {result.strategy_comparison.strategy_c_greedy_baseline.cells_count} cells
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-sans text-[11px]">Optimality Gap:</span>
                      <strong className="text-amber-700">
                        {(result.strategy_comparison.strategy_c_greedy_baseline.optimality_gap_percent ?? 0).toFixed(2)}% vs Exact DP
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-sans text-[11px]">Thermal Benefit:</span>
                      <strong className="text-indigo-700">
                        {Math.round(result.strategy_comparison.strategy_c_greedy_baseline.thermal_benefit_k_m2).toLocaleString()} K·m²
                      </strong>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Locality Roll-up Table (if multiple localities) */}
          {result.locality_rollup && result.locality_rollup.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center justify-between mb-3 border-b border-slate-100 pb-2">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    🏛️ Municipal Locality Roll-Up (Administrative Wards in Scope)
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Aggregated capital outlay and thermal return by municipal ward.
                  </p>
                </div>
                <span className="text-xs font-mono text-slate-400">
                  {result.locality_rollup.length} Localities Funded
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-50 text-slate-700 font-bold border-b border-slate-200">
                    <tr>
                      <th className="p-2.5">Locality Name</th>
                      <th className="p-2.5 text-right">Packages</th>
                      <th className="p-2.5 text-right">Cells</th>
                      <th className="p-2.5 text-right">Capital Spend</th>
                      <th className="p-2.5 text-right">Treated Area</th>
                      <th className="p-2.5 text-right">Thermal Benefit</th>
                      <th className="p-2.5 text-right">Chronic Hotspots</th>
                      <th className="p-2.5">Typologies</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    {result.locality_rollup.map((loc) => (
                      <tr key={loc.locality} className="hover:bg-slate-50 transition-colors">
                        <td className="p-2.5 font-bold text-slate-900 font-sans">{loc.locality}</td>
                        <td className="p-2.5 text-right">{loc.packages_count}</td>
                        <td className="p-2.5 text-right">{loc.cells_count}</td>
                        <td className="p-2.5 text-right font-bold text-slate-900">{formatINR(loc.spend_inr)}</td>
                        <td className="p-2.5 text-right text-slate-600">{Math.round(loc.treated_area_m2).toLocaleString()} m²</td>
                        <td className="p-2.5 text-right font-bold text-indigo-700">
                          {Math.round(loc.thermal_benefit_k_m2).toLocaleString()} K·m²
                        </td>
                        <td className="p-2.5 text-right text-orange-600 font-bold">{loc.chronic_hotspot_cells_count}</td>
                        <td className="p-2.5 font-sans">
                          <div className="flex flex-wrap gap-1">
                            {loc.intervention_types.map((t) => (
                              <span
                                key={t}
                                className="text-[9.5px] rounded px-1.5 py-0.5 bg-slate-100 text-slate-700 font-semibold"
                              >
                                {t.replace(/_/g, " ")}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="border-t-2 border-slate-300 bg-slate-100 font-bold text-slate-900 font-mono">
                    <tr>
                      <td className="p-2.5 font-sans">Total Municipal Portfolio</td>
                      <td className="p-2.5 text-right">
                        {result.locality_rollup.reduce((acc, l) => acc + l.packages_count, 0)}
                      </td>
                      <td className="p-2.5 text-right">
                        {result.locality_rollup.reduce((acc, l) => acc + l.cells_count, 0)}
                      </td>
                      <td className="p-2.5 text-right text-base text-slate-900">
                        {formatINR(result.locality_rollup.reduce((acc, l) => acc + l.spend_inr, 0))}
                      </td>
                      <td className="p-2.5 text-right">
                        {Math.round(result.locality_rollup.reduce((acc, l) => acc + l.treated_area_m2, 0)).toLocaleString()} m²
                      </td>
                      <td className="p-2.5 text-right text-indigo-800">
                        {Math.round(result.locality_rollup.reduce((acc, l) => acc + l.thermal_benefit_k_m2, 0)).toLocaleString()} K·m²
                      </td>
                      <td className="p-2.5 text-right text-orange-600">
                        {result.locality_rollup.reduce((acc, l) => acc + l.chronic_hotspot_cells_count, 0)}
                      </td>
                      <td className="p-2.5 font-sans text-xs text-slate-500 font-normal">All qualifying types</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          )}

          {/* 10-Point Budget-vs-Benefit Curve (Diminishing Returns) */}
          {result.budget_curve && result.budget_curve.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center justify-between mb-3 border-b border-slate-100 pb-2">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    📈 10-Point Budget-vs-Benefit Curve (Diminishing Returns Profile)
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Sampled from the Exact 0/1 Knapsack dynamic programming table across 10 budget levels (10% to 100% of cap).
                  </p>
                </div>
                <span className="text-xs font-mono font-bold text-teal-700">
                  Exact DP Integer State Space
                </span>
              </div>

              {/* Curve Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-50 text-slate-700 font-bold border-b border-slate-200">
                    <tr>
                      <th className="p-2">Step</th>
                      <th className="p-2">Fraction</th>
                      <th className="p-2">Budget Cap</th>
                      <th className="p-2">Actual Spend</th>
                      <th className="p-2">Utilization</th>
                      <th className="p-2 text-right">Packages</th>
                      <th className="p-2 text-right">Cells</th>
                      <th className="p-2 text-right">Chronic Hotspots</th>
                      <th className="p-2 text-right">Thermal Benefit (K·m²)</th>
                      <th className="p-2 text-right">Marginal (K·m²/₹ Lakh)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    {result.budget_curve.map((pt, idx) => {
                      const prevPt = idx > 0 ? result.budget_curve![idx - 1] : null;
                      const dSpendLakh = prevPt ? (pt.actual_spend_inr - prevPt.actual_spend_inr) / 100000 : pt.actual_spend_inr / 100000;
                      const dBen = prevPt ? pt.thermal_benefit_k_m2 - prevPt.thermal_benefit_k_m2 : pt.thermal_benefit_k_m2;
                      const marginalRatio = dSpendLakh > 0 ? (dBen / dSpendLakh).toFixed(1) : "—";

                      return (
                        <tr
                          key={pt.step}
                          className={`hover:bg-slate-50 transition-colors ${
                            pt.step === 10 ? "bg-teal-50/30 font-bold" : ""
                          }`}
                        >
                          <td className="p-2">#{pt.step}</td>
                          <td className="p-2">{(pt.budget_fraction * 100).toFixed(0)}%</td>
                          <td className="p-2 text-slate-500">{formatINR(pt.budget_cap_inr)}</td>
                          <td className="p-2 font-bold text-slate-900">{formatINR(pt.actual_spend_inr)}</td>
                          <td className="p-2 text-slate-600">{pt.spend_utilized_percent.toFixed(1)}%</td>
                          <td className="p-2 text-right">{pt.packages_count}</td>
                          <td className="p-2 text-right">{pt.cells_count}</td>
                          <td className="p-2 text-right text-orange-600 font-bold">{pt.chronic_hotspots_count}</td>
                          <td className="p-2 text-right font-bold text-indigo-700">
                            {Math.round(pt.thermal_benefit_k_m2).toLocaleString()}
                          </td>
                          <td className="p-2 text-right text-emerald-700">{marginalRatio}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Ranked Selected Packages List & Cell Drill-Down Drawer */}
          {activeSolution.selected_packages && activeSolution.selected_packages.length > 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-3">
                <div>
                  <h4 className="text-sm font-bold uppercase tracking-wider text-slate-700">
                    Allocated Implementation Packages ({activeSolution.selected_packages.length} packages · {activeSolution.cells_count} cells)
                  </h4>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Every package is Queen contiguous (≤ 4 cells) and represents an actionable municipal procurement unit.
                  </p>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <input
                    type="text"
                    placeholder="Filter package ID / locality..."
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                    className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500"
                  />

                  <select
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                    className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-teal-500"
                  >
                    <option value="ALL">All Typologies</option>
                    <option value="CHRONIC">🔥 Chronic Hotspots Only</option>
                    <option value="tree">🌳 Tree Canopy</option>
                    <option value="roof">⚪ Cool Roof</option>
                    <option value="pavement">🧱 Cool Pavers</option>
                  </select>
                </div>
              </div>

              {/* Packages Table */}
              <div className="mt-4 overflow-x-auto max-h-96">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="sticky top-0 bg-slate-100 text-slate-700 font-bold z-10 border-b border-slate-200">
                    <tr>
                      <th className="p-2.5">Package ID &amp; Locality</th>
                      <th className="p-2.5">Typology</th>
                      <th className="p-2.5 text-right">Cells</th>
                      <th className="p-2.5 text-right">Footprint</th>
                      <th className="p-2.5 text-right">Capital Outlay</th>
                      <th className="p-2.5 text-right">3-Yr Opex</th>
                      <th className="p-2.5 text-right">Skin ΔT</th>
                      <th className="p-2.5 text-right">Thermal Benefit</th>
                      <th className="p-2.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    {filteredPackages.map((pkg) => (
                      <tr key={pkg.package_id} className="hover:bg-slate-50 transition-colors">
                        <td className="p-2.5">
                          <div className="font-bold text-slate-900">{pkg.package_id}</div>
                          <div className="text-[10px] text-slate-400 font-sans">
                            {pkg.locality} · Cluster: {pkg.cluster_id}
                          </div>
                        </td>
                        <td className="p-2.5 font-sans">
                          <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold bg-slate-100 text-slate-800">
                            {pkg.intervention_type.includes("tree")
                              ? "🌳 Forestry"
                              : pkg.intervention_type.includes("roof")
                              ? "⚪ Cool Roof"
                              : "🧱 Pavers"}
                          </span>
                          {pkg.chronic_hotspot_cells_count > 0 && (
                            <span className="ml-1 text-[10px] text-orange-600 font-bold">
                              🔥 {pkg.chronic_hotspot_cells_count} chronic
                            </span>
                          )}
                        </td>
                        <td className="p-2.5 text-right font-bold text-slate-800">
                          {pkg.cell_count} cells
                        </td>
                        <td className="p-2.5 text-right text-slate-600">
                          {Math.round(pkg.treated_footprint_m2).toLocaleString()} m²
                        </td>
                        <td className="p-2.5 text-right font-bold text-slate-900">
                          {formatINR(pkg.estimated_cost_inr)}
                        </td>
                        <td className="p-2.5 text-right text-slate-500">
                          {formatINR(pkg.opex_3yr_inr)}
                        </td>
                        <td className="p-2.5 text-right text-emerald-600 font-bold">
                          -{pkg.expected_cooling_c.toFixed(2)}°C
                        </td>
                        <td className="p-2.5 text-right font-bold text-indigo-700">
                          {Math.round(pkg.thermal_benefit_k_m2).toLocaleString()} K·m²
                        </td>
                        <td className="p-2.5 text-right font-sans">
                          <button
                            type="button"
                            onClick={() => setSelectedPackageForCells(pkg)}
                            className="rounded bg-teal-50 px-2.5 py-1 text-[11px] font-bold text-teal-700 hover:bg-teal-100 transition-colors cursor-pointer"
                          >
                            Inspect Cells ({pkg.cell_count}) →
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : activeSolution.deployments && activeSolution.deployments.length > 0 ? (
            /* Fallback to legacy deployments if packages array missing */
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <h4 className="text-sm font-bold uppercase tracking-wider text-slate-700 mb-3">
                Allocated Candidate Deployments ({activeSolution.interventions_count} sites)
              </h4>
              <div className="overflow-x-auto max-h-96">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="sticky top-0 bg-slate-100 text-slate-700 font-bold z-10 border-b border-slate-200">
                    <tr>
                      <th className="p-2.5">Cell ID</th>
                      <th className="p-2.5">Typology</th>
                      <th className="p-2.5">Coordinates</th>
                      <th className="p-2.5 text-right">Site Cost</th>
                      <th className="p-2.5 text-right">Treated Area</th>
                      <th className="p-2.5 text-right">Skin ΔT</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    {filteredDeployments.map((d) => (
                      <tr key={d.candidate_id} className="hover:bg-slate-50 transition-colors">
                        <td className="p-2.5 font-bold text-slate-900">{d.cell_id}</td>
                        <td className="p-2.5 font-sans">{d.intervention_type}</td>
                        <td className="p-2.5 text-slate-500">{d.latitude.toFixed(4)}, {d.longitude.toFixed(4)}</td>
                        <td className="p-2.5 text-right font-bold text-slate-900">{formatINR(d.cost_inr)}</td>
                        <td className="p-2.5 text-right text-slate-600">{d.usable_area_m2.toLocaleString()} m²</td>
                        <td className="p-2.5 text-right text-emerald-600 font-bold">-{d.expected_cooling_c.toFixed(2)}°C</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          {/* Collapsible Advanced Pareto Frontier Explorer (when NSGA-II chosen or multiple solutions) */}
          {result.solutions.length > 1 && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                    🧬 Advanced Multi-Objective Pareto Frontier ({result.solutions_count} Non-Dominated Trade-Off Solutions)
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Explore genetic trade-offs between capital expenditure, extensive thermal benefit, and chronic hotspot remediation.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowParetoSection((prev) => !prev)}
                  className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-100 cursor-pointer"
                >
                  {showParetoSection ? "Collapse Frontier ▲" : "Expand Frontier ▼"}
                </button>
              </div>

              {showParetoSection && (
                <div className="mt-4 border-t border-slate-100 pt-4">
                  {/* Solution Picker Chips (Representative non-dominated solutions) */}
                  <div className="flex items-center gap-1.5 overflow-x-auto pb-2 mb-3">
                    <span className="text-xs font-bold text-slate-500 mr-1">Representative Solutions:</span>
                    {result.solutions.slice(0, 5).map((sol, idx) => (
                      <button
                        key={sol.solution_id || idx}
                        type="button"
                        onClick={() => setSelectedSolutionIdx(idx)}
                        className={`rounded-lg px-2.5 py-1 text-xs font-mono font-bold transition-all cursor-pointer ${
                          selectedSolutionIdx === idx
                            ? "bg-slate-900 text-white shadow-xs"
                            : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                        }`}
                      >
                        #{idx + 1} ({formatINR(sol.total_cost_inr)})
                      </button>
                    ))}
                  </div>

                  {/* Pareto Trade-Off Interactive SVG Chart */}
                  <div className="rounded-lg bg-slate-50 border border-slate-200 p-4">
                    {(() => {
                      const sols = [...result.solutions].sort((a, b) => a.total_cost_inr - b.total_cost_inr);
                      const minCost = Math.min(...sols.map((s) => s.total_cost_inr));
                      const maxCost = Math.max(...sols.map((s) => s.total_cost_inr));
                      const minBen = Math.min(...sols.map((s) => s.portfolio_thermal_benefit_c_m2));
                      const maxBen = Math.max(...sols.map((s) => s.portfolio_thermal_benefit_c_m2));

                      const costRange = maxCost - minCost || 1;
                      const benRange = maxBen - minBen || 1;

                      const width = 600;
                      const height = 140;
                      const padX = 40;
                      const padY = 20;

                      const points = sols.map((s) => {
                        const x = padX + ((s.total_cost_inr - minCost) / costRange) * (width - 2 * padX);
                        const y = height - padY - ((s.portfolio_thermal_benefit_c_m2 - minBen) / benRange) * (height - 2 * padY);
                        return { s, x, y };
                      });

                      const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");

                      return (
                        <div className="relative">
                          <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-36 overflow-visible">
                            <line x1={padX} y1={padY} x2={padX} y2={height - padY} stroke="#cbd5e1" strokeWidth="1" />
                            <line x1={padX} y1={height - padY} x2={width - padX} y2={height - padY} stroke="#cbd5e1" strokeWidth="1" />
                            <path d={pathD} fill="none" stroke="#0d9488" strokeWidth="2.5" strokeDasharray="3 3" />
                            {points.map((pt) => {
                              const origIdx = result.solutions.indexOf(pt.s);
                              const isSelected = selectedSolutionIdx === origIdx;
                              return (
                                <g
                                  key={pt.s.solution_id}
                                  className="cursor-pointer"
                                  onClick={() => setSelectedSolutionIdx(origIdx)}
                                >
                                  {isSelected && (
                                    <circle cx={pt.x} cy={pt.y} r="10" fill="#2dd4bf" opacity="0.3" />
                                  )}
                                  <circle
                                    cx={pt.x}
                                    cy={pt.y}
                                    r={isSelected ? "6" : "4.5"}
                                    fill={isSelected ? "#0f766e" : "#0d9488"}
                                    stroke="#ffffff"
                                    strokeWidth="2"
                                  />
                                </g>
                              );
                            })}
                          </svg>
                          <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1 px-4">
                            <span>Min Spend: {formatINR(minCost)}</span>
                            <span className="text-teal-700 font-bold">← Lower Cost · Higher Thermal Benefit (Pareto Frontier) →</span>
                            <span>Max Spend: {formatINR(maxCost)}</span>
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Climatological & Biophysical Notice */}
          <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-5 text-xs text-indigo-950">
            <h4 className="font-bold">Physical Energy Balance &amp; Climatological Grounding:</h4>
            <p className="mt-1 leading-relaxed text-indigo-900">
              Mean local cooling (-{activeSolution.mean_local_cooling_c.toFixed(2)}°C) represents the direct
              footprint-weighted reduction in surface skin temperature (ΔT<sub>skin</sub>) over treated parcel areas
              under morning overpass conditions (870 W/m² irradiance, h<sub>eff</sub> = 45.6 W/(m²·K)).
              Extensive thermal benefit is conserved in <strong>K·m²</strong> across all interventions.
              2m ambient atmospheric air temperature is unmodeled due to convective advection complexity.
            </p>
            <div className="mt-2 text-[11px] text-indigo-800 flex items-center justify-between flex-wrap gap-2">
              <div>
                <strong>Municipal Palette:</strong> High-albedo reflective coatings, porous permeable pavers, and native shade trees (Neem, Peepal, Gulmohar).
              </div>
              <div className="font-mono text-[10px] text-indigo-600 font-bold">
                Status: Modeled Biophysical Physics · Subject to Structural &amp; Tenure Field Survey
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Package Contributing Cells Drill-Down Drawer / Modal */}
      {selectedPackageForCells && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-xs">
          <div className="relative max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
            {/* Header */}
            <div className="flex items-start justify-between border-b border-slate-100 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-teal-100 px-2.5 py-0.5 text-xs font-bold text-teal-800 font-mono">
                    Queen Contiguous Package (≤ 4 cells)
                  </span>
                  <span className="font-mono text-xs text-slate-400">
                    {selectedPackageForCells.package_id}
                  </span>
                </div>
                <h3 className="mt-1 text-xl font-extrabold text-slate-900">
                  Contributing 100m Cells in {selectedPackageForCells.package_id}
                </h3>
                <p className="mt-0.5 text-xs text-slate-500">
                  {selectedPackageForCells.locality} · Cluster: {selectedPackageForCells.cluster_id} · Typology: {selectedPackageForCells.intervention_type}
                </p>
              </div>

              <button
                type="button"
                onClick={() => setSelectedPackageForCells(null)}
                className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Package KPI strip */}
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 text-xs font-mono">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 font-sans block">Capital Outlay</span>
                <span className="text-sm font-extrabold text-slate-900">{formatINR(selectedPackageForCells.estimated_cost_inr)}</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 font-sans block">Treated Footprint</span>
                <span className="text-sm font-extrabold text-slate-800">{Math.round(selectedPackageForCells.treated_footprint_m2).toLocaleString()} m²</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 font-sans block">Skin ΔT</span>
                <span className="text-sm font-extrabold text-emerald-600">-{selectedPackageForCells.expected_cooling_c.toFixed(2)}°C</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-400 font-sans block">Thermal Benefit</span>
                <span className="text-sm font-extrabold text-indigo-700">{Math.round(selectedPackageForCells.thermal_benefit_k_m2).toLocaleString()} K·m²</span>
              </div>
            </div>

            {/* Contributing Cells Table */}
            <div className="mt-5">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
                Contributing Spatial Cells ({selectedPackageForCells.cells?.length ?? selectedPackageForCells.cell_count} cells)
              </h4>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200">
                    <tr>
                      <th className="p-2.5">Cell ID</th>
                      <th className="p-2.5">Coordinates (Lat, Lon)</th>
                      <th className="p-2.5 text-right">Baseline HPI</th>
                      <th className="p-2.5 text-right">Baseline LST</th>
                      <th className="p-2.5 text-right">Treated Area</th>
                      <th className="p-2.5 text-right">Cell Capex</th>
                      <th className="p-2.5 text-right">Skin ΔT</th>
                      <th className="p-2.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    {selectedPackageForCells.cells && selectedPackageForCells.cells.length > 0 ? (
                      selectedPackageForCells.cells.map((cell: any) => (
                        <tr key={cell.cell_id || cell.candidate_id} className="hover:bg-slate-50 transition-colors">
                          <td className="p-2.5 font-bold text-slate-900">
                            {cell.cell_id}
                            {cell.is_chronic_hotspot && (
                              <span className="ml-1 text-[10px] text-orange-600 font-bold font-sans">🔥 Chronic</span>
                            )}
                          </td>
                          <td className="p-2.5 text-slate-500">
                            {cell.latitude?.toFixed(4)}, {cell.longitude?.toFixed(4)}
                          </td>
                          <td className="p-2.5 text-right">
                            {cell.baseline_hpi !== null && cell.baseline_hpi !== undefined
                              ? cell.baseline_hpi.toFixed(1)
                              : "—"}
                          </td>
                          <td className="p-2.5 text-right">
                            {cell.baseline_lst_c !== null && cell.baseline_lst_c !== undefined
                              ? `${cell.baseline_lst_c.toFixed(1)}°C`
                              : "—"}
                          </td>
                          <td className="p-2.5 text-right text-slate-700">
                            {Math.round(cell.usable_area_m2 || 0).toLocaleString()} m²
                          </td>
                          <td className="p-2.5 text-right font-bold text-slate-900">
                            {formatINR(cell.cost_inr || 0)}
                          </td>
                          <td className="p-2.5 text-right text-emerald-600 font-bold">
                            -{(cell.expected_cooling_c || 0).toFixed(2)}°C
                          </td>
                          <td className="p-2.5 text-right font-sans">
                            {onSwitchToMap && (
                              <button
                                type="button"
                                onClick={() => {
                                  if (onSelectCandidateOnMap) {
                                    onSelectCandidateOnMap(cell.candidate_id || cell.cell_id);
                                  }
                                  setSelectedPackageForCells(null);
                                  onSwitchToMap();
                                }}
                                className="rounded bg-teal-50 px-2 py-1 text-[10px] font-bold text-teal-700 hover:bg-teal-100 cursor-pointer"
                              >
                                View Map →
                              </button>
                            )}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={8} className="p-4 text-center text-slate-400">
                          {selectedPackageForCells.cell_ids.join(", ")}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedPackageForCells(null)}
                className="rounded-xl bg-slate-900 px-5 py-2 text-xs font-bold text-white hover:bg-slate-800 cursor-pointer"
              >
                Close Cell Inspector
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Initial Empty State before running */}
      {!result && !running && !error && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
          <div className="text-4xl">⚡</div>
          <h3 className="mt-3 text-base font-bold text-slate-900">
            Optimizer Ready for Execution
          </h3>
          <p className="mt-1 max-w-md text-xs text-slate-500">
            Configure your geographic scope and capital budget ceiling above, then click
            &ldquo;Execute Optimization&rdquo; to compute provably optimal implementation packages across Surat.
          </p>
          <button
            type="button"
            onClick={handleRunOptimization}
            className="mt-4 rounded-xl bg-teal-600 px-5 py-2.5 text-xs font-bold text-white hover:bg-teal-500 shadow-sm transition-all cursor-pointer"
          >
            Run With Current Settings ({formatINR(budget)}) →
          </button>
        </div>
      )}
    </div>
  );
}
