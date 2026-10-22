import { useEffect, useState } from "react";
import type {
  InterventionType,
  OptimizationResultResponse,
  OptimizeRequestPayload,
  ScenarioSolutionItem,
} from "../../types/interventions";
import {
  getDevToken,
  runInterventionOptimization,
} from "../../services/interventionsApi";

interface OptimizationProps {
  initialBudgetInr?: number;
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
  return `₹${val.toLocaleString("en-IN")}`;
}

const BUDGET_PRESETS = [
  { label: "Pilot Hotspots (₹50L)", value: 5000000 },
  { label: "Smart City Phase 1 (₹2.5Cr)", value: 25000000 },
  { label: "UHAP 2026 Citywide (₹10Cr)", value: 100000000 },
];

export default function Optimization({
  initialBudgetInr = 25000000,
  onSwitchToMap,
}: OptimizationProps) {
  // Configuration State
  const [budget, setBudget] = useState<number>(initialBudgetInr);
  const [algorithm, setAlgorithm] = useState<"nsga2" | "greedy">("nsga2");
  const [maxCandidates, setMaxCandidates] = useState<number>(60);
  const [generations, setGenerations] = useState<number>(15);
  const [allowedTypes, setAllowedTypes] = useState<Record<InterventionType, boolean>>({
    tree_canopy: true,
    cool_roof: true,
    cool_pavement: true,
    green_roof: false,
  });

  // Execution State
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OptimizationResultResponse | null>(null);
  const [selectedSolutionIdx, setSelectedSolutionIdx] = useState<number>(0);
  const [authToken, setAuthToken] = useState<string>("");

  // Acquire dev session token on mount
  useEffect(() => {
    let cancelled = false;
    getDevToken("planner")
      .then((token) => {
        if (!cancelled) setAuthToken(token);
      })
      .catch(() => {
        // Fallback: will prompt or retry if needed
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleRunOptimization = async () => {
    setRunning(true);
    setError(null);

    const activeTypes = (Object.keys(allowedTypes) as InterventionType[]).filter(
      (t) => allowedTypes[t]
    );

    const payload: OptimizeRequestPayload = {
      budget_inr: budget,
      algorithm,
      max_candidates: maxCandidates,
      target_types: activeTypes.length > 0 ? activeTypes : undefined,
      generations: algorithm === "nsga2" ? generations : undefined,
    };

    try {
      let token = authToken;
      if (!token) {
        token = await getDevToken("planner");
        setAuthToken(token);
      }
      const res = await runInterventionOptimization(payload, token);
      setResult(res);
      setSelectedSolutionIdx(0);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Optimization execution failed. Check server connectivity."
      );
    } finally {
      setRunning(false);
    }
  };

  const activeSolution: ScenarioSolutionItem | null =
    result && result.solutions.length > 0
      ? result.solutions[selectedSolutionIdx] || result.solutions[0]
      : null;

  return (
    <div className="flex flex-col gap-6">
      {/* Hero Header */}
      <div className="rounded-xl border border-slate-200 bg-gradient-to-r from-slate-900 via-emerald-950 to-slate-900 p-6 text-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-xs font-bold text-emerald-300 border border-emerald-500/30">
                Stage D Multi-Objective Solver
              </span>
              <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Genetic Algorithm & Knapsack Optimization
              </span>
            </div>
            <h2 className="mt-2 text-2xl font-extrabold text-white">
              Surat Urban Cooling Optimization Engine
            </h2>
            <p className="mt-1 max-w-3xl text-sm text-slate-300">
              Pareto-optimal allocation of high-albedo coatings, native forestry, and cool pavements
              under municipal budget constraints. Strictly optimizes physical surface cooling benefit
              and chronic heat hotspot alleviation.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {onSwitchToMap && (
              <button
                type="button"
                onClick={onSwitchToMap}
                className="flex items-center gap-1.5 rounded-lg border border-white/20 bg-white/10 px-3.5 py-2 text-xs font-bold text-white hover:bg-white/20 transition-all"
              >
                <span>View Heat Map</span>
              </button>
            )}

            <button
              type="button"
              disabled={running}
              onClick={handleRunOptimization}
              className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-bold text-white shadow hover:bg-emerald-500 disabled:opacity-50 transition-all cursor-pointer"
            >
              {running ? (
                <>
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Optimizing Frontier…</span>
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

      {/* Configuration & Controls */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Col 1: Budget & Algorithm */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            1. Capital Budget Limit
          </h3>

          <div className="mt-3 flex flex-wrap gap-2">
            {BUDGET_PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => setBudget(p.value)}
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-all ${
                  budget === p.value
                    ? "bg-emerald-600 text-white font-bold shadow-xs"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          <div className="mt-4">
            <div className="flex justify-between text-xs font-semibold text-slate-700">
              <span>Budget Ceiling:</span>
              <span className="font-mono text-sm text-emerald-700 font-extrabold">
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
              className="mt-2 w-full accent-emerald-600 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-400 font-mono">
              <span>₹10 Lakh</span>
              <span>₹2.5 Cr</span>
              <span>₹15 Cr</span>
            </div>
          </div>

          <div className="mt-5 border-t border-slate-100 pt-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              2. Optimization Algorithm
            </h3>

            <div className="mt-2 grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setAlgorithm("nsga2")}
                className={`flex flex-col p-3 rounded-lg border text-left transition-all ${
                  algorithm === "nsga2"
                    ? "border-emerald-600 bg-emerald-50/50 shadow-xs ring-1 ring-emerald-500"
                    : "border-slate-200 bg-white hover:bg-slate-50"
                }`}
              >
                <span className="text-xs font-bold text-slate-900">🧬 NSGA-II</span>
                <span className="mt-1 text-[10px] text-slate-500 leading-tight">
                  Multi-objective Pareto genetic algorithm. Yields frontier of trade-offs.
                </span>
              </button>

              <button
                type="button"
                onClick={() => setAlgorithm("greedy")}
                className={`flex flex-col p-3 rounded-lg border text-left transition-all ${
                  algorithm === "greedy"
                    ? "border-emerald-600 bg-emerald-50/50 shadow-xs ring-1 ring-emerald-500"
                    : "border-slate-200 bg-white hover:bg-slate-50"
                }`}
              >
                <span className="text-xs font-bold text-slate-900">⚡ Greedy Knapsack</span>
                <span className="mt-1 text-[10px] text-slate-500 leading-tight">
                  Fast heuristic allocating highest benefit/cost ratio until budget exhaustion.
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Col 2: Pool & Search Parameters */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            3. Search Pool & Genetic Settings
          </h3>

          <div className="mt-4">
            <div className="flex justify-between text-xs font-semibold text-slate-700">
              <span>Candidate Pool Size:</span>
              <span className="font-mono text-xs font-bold text-slate-900">
                {maxCandidates} candidates
              </span>
            </div>
            <input
              type="range"
              min="20"
              max="150"
              step="10"
              value={maxCandidates}
              onChange={(e) => setMaxCandidates(Number(e.target.value))}
              className="mt-2 w-full accent-slate-800 cursor-pointer"
            />
            <p className="mt-1 text-[10px] text-slate-400">
              Top qualifying Stage C heat cells evaluated as candidate sites.
            </p>
          </div>

          {algorithm === "nsga2" && (
            <div className="mt-5 border-t border-slate-100 pt-4">
              <div className="flex justify-between text-xs font-semibold text-slate-700">
                <span>NSGA-II Generations:</span>
                <span className="font-mono text-xs font-bold text-indigo-700">
                  {generations} generations
                </span>
              </div>
              <input
                type="range"
                min="5"
                max="50"
                step="5"
                value={generations}
                onChange={(e) => setGenerations(Number(e.target.value))}
                className="mt-2 w-full accent-indigo-600 cursor-pointer"
              />
              <p className="mt-1 text-[10px] text-slate-400">
                Genetic crossover & mutation iterations across candidate chromosome population.
              </p>
            </div>
          )}

          <div className="mt-5 border-t border-slate-100 pt-4">
            <span className="text-[11px] font-bold text-slate-500 uppercase">
              Planner Authentication:
            </span>
            <div className="mt-1 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <span className="text-xs text-slate-700 font-medium">
                SMC Town Planning Officer (Authenticated)
              </span>
            </div>
          </div>
        </div>

        {/* Col 3: Allowed Typologies */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            4. Allowed Intervention Typologies
          </h3>

          <div className="mt-3 flex flex-col gap-2">
            {(
              [
                {
                  key: "tree_canopy",
                  label: "🌳 Native Urban Forestry",
                  desc: "Neem, Peepal, Gulmohar crown shading & evapotranspiration",
                },
                {
                  key: "cool_roof",
                  label: "⚪ High-Albedo Cool Roof",
                  desc: "Aged reflective coating (Δα = +0.45) on RCC roofs",
                },
                {
                  key: "cool_pavement",
                  label: "🧱 Permeable Cool Pavers",
                  desc: "Reflective porous pavers for corridors & lots",
                },
                {
                  key: "green_roof",
                  label: "🌿 Extensive Green Roof",
                  desc: "Sedum vegetated buffer (verified load-bearing RCC only)",
                },
              ] as const
            ).map((item) => {
              const isChecked = allowedTypes[item.key];
              return (
                <label
                  key={item.key}
                  className={`flex items-start gap-3 rounded-lg border p-2.5 transition-all cursor-pointer ${
                    isChecked
                      ? "border-emerald-300 bg-emerald-50/30"
                      : "border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() =>
                      setAllowedTypes((prev) => ({
                        ...prev,
                        [item.key]: !prev[item.key],
                      }))
                    }
                    className="mt-0.5 accent-emerald-600 rounded"
                  />
                  <div>
                    <div className="text-xs font-bold text-slate-900">{item.label}</div>
                    <div className="text-[10px] text-slate-500">{item.desc}</div>
                  </div>
                </label>
              );
            })}
          </div>
        </div>
      </div>

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
                <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-800">
                  {result.algorithm} Frontier · {result.solutions_count} Optimal Solutions Found
                </span>
                <h3 className="mt-2 text-xl font-extrabold text-slate-900">
                  Solution {selectedSolutionIdx + 1} of {result.solutions_count}:{" "}
                  {formatINR(activeSolution.total_cost_inr)} Allocated
                </h3>
              </div>

              {/* Solution Picker Chips (for NSGA-II Pareto Frontier) */}
              {result.solutions.length > 1 && (
                <div className="flex items-center gap-1.5 overflow-x-auto max-w-full pb-1">
                  <span className="text-xs font-bold text-slate-500 mr-1">Pareto Set:</span>
                  {result.solutions.map((sol, idx) => (
                    <button
                      key={sol.solution_id || idx}
                      type="button"
                      onClick={() => setSelectedSolutionIdx(idx)}
                      className={`rounded-lg px-2.5 py-1 text-xs font-mono font-bold transition-all ${
                        selectedSolutionIdx === idx
                          ? "bg-slate-900 text-white shadow-xs"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                    >
                      #{idx + 1} ({formatINR(sol.total_cost_inr)})
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* KPI Cards for Active Solution */}
            <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              <div className="rounded-lg bg-slate-50 p-3 border border-slate-200/60">
                <span className="text-[10px] text-slate-400 uppercase font-bold">
                  Total Expenditure
                </span>
                <div className="mt-1 font-mono text-base font-extrabold text-slate-900">
                  {formatINR(activeSolution.total_cost_inr)}
                </div>
                <div className="text-[10px] text-slate-500">
                  {activeSolution.budget_utilized_percent.toFixed(1)}% of budget cap
                </div>
              </div>

              <div className="rounded-lg bg-slate-50 p-3 border border-slate-200/60">
                <span className="text-[10px] text-slate-400 uppercase font-bold">
                  Interventions Selected
                </span>
                <div className="mt-1 font-mono text-base font-extrabold text-slate-900">
                  {activeSolution.interventions_count} sites
                </div>
                <div className="text-[10px] text-slate-500">
                  Across 100m grid cells
                </div>
              </div>

              <div className="rounded-lg bg-slate-50 p-3 border border-slate-200/60">
                <span className="text-[10px] text-slate-400 uppercase font-bold">
                  Mean Local Cooling
                </span>
                <div className="mt-1 font-mono text-base font-extrabold text-emerald-600">
                  -{activeSolution.mean_local_cooling_c.toFixed(2)}°C
                </div>
                <div className="text-[10px] text-slate-500">
                  Direct treated skin ΔT
                </div>
              </div>

              <div className="rounded-lg bg-slate-50 p-3 border border-slate-200/60">
                <span className="text-[10px] text-slate-400 uppercase font-bold">
                  Treated Footprint
                </span>
                <div className="mt-1 font-mono text-base font-extrabold text-slate-900">
                  {(activeSolution.treated_area_m2 / 10000).toFixed(1)} ha
                </div>
                <div className="text-[10px] text-slate-500">
                  {activeSolution.treated_area_m2.toLocaleString()} m² footprint
                </div>
              </div>

              <div className="rounded-lg bg-slate-50 p-3 border border-slate-200/60">
                <span className="text-[10px] text-slate-400 uppercase font-bold">
                  Thermal Benefit (ΔT·m²)
                </span>
                <div className="mt-1 font-mono text-base font-extrabold text-indigo-700">
                  {activeSolution.portfolio_thermal_benefit_c_m2.toLocaleString(undefined, {
                    maximumFractionDigits: 0,
                  })}
                </div>
                <div className="text-[10px] text-slate-500">
                  Extensive cooling sum
                </div>
              </div>

              <div className="rounded-lg bg-slate-50 p-3 border border-slate-200/60">
                <span className="text-[10px] text-slate-400 uppercase font-bold">
                  Hotspots Mitigated
                </span>
                <div className="mt-1 font-mono text-base font-extrabold text-orange-600">
                  {activeSolution.chronic_hotspots_count} cells
                </div>
                <div className="text-[10px] text-slate-500">
                  🔥 Persistent heat stress
                </div>
              </div>
            </div>
          </div>

          {/* Selected Candidates Deployment List */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h4 className="text-sm font-bold uppercase tracking-wider text-slate-700">
                Allocated Candidate Deployments ({activeSolution.selected_candidate_ids.length} sites)
              </h4>
              <span className="text-xs text-slate-400 font-mono">
                Pareto Rank: {activeSolution.pareto_rank} · Feasible:{" "}
                {activeSolution.is_feasible ? "✓ Strictly Constrained" : "✗ Overbudget"}
              </span>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {activeSolution.selected_candidate_ids.map((candId) => {
                const parts = candId.split("_");
                const cellTag = parts.slice(-2).join("_");
                const isTree = candId.includes("TREE");
                const isRoof = candId.includes("ROOF");
                const isPaver = candId.includes("PAVEMENT");

                return (
                  <div
                    key={candId}
                    className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs hover:border-emerald-300 transition-colors"
                  >
                    <span>{isTree ? "🌳" : isRoof ? "⚪" : isPaver ? "🧱" : "🌿"}</span>
                    <span className="font-mono font-bold text-slate-800">{cellTag}</span>
                    <span className="text-[10px] text-slate-400">
                      {isTree ? "Tree Canopy" : isRoof ? "Cool Roof" : "Cool Paver"}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Mathematical Grounding & Physics Note */}
          <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-5 text-xs text-indigo-950">
            <h4 className="font-bold">Physical Energy Balance & Metric Clarification:</h4>
            <p className="mt-1 leading-relaxed text-indigo-900">
              Mean local cooling (-{activeSolution.mean_local_cooling_c.toFixed(2)}°C) represents the direct
              footprint-weighted reduction in surface skin temperature over the treated areas during
              morning overpass. The citywide average (
              {activeSolution.citywide_cooling_c.toFixed(6)}°C) reflects extensive dilution across Surat’s
              complete municipal domain (461.63 km²), preserving physical conservation of energy and
              strictly avoiding additive temperature summation.
            </p>
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
            Configure your capital budget ceiling and optimization algorithm above, then click
            &ldquo;Execute Optimization&rdquo; to compute Pareto-optimal candidate allocations across Surat.
          </p>
          <button
            type="button"
            onClick={handleRunOptimization}
            className="mt-4 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-500 shadow-sm transition-all"
          >
            Run With Current Settings ({formatINR(budget)}) →
          </button>
        </div>
      )}
    </div>
  );
}
