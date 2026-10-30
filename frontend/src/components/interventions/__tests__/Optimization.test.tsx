import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import Optimization from "../Optimization";
import { AuthContext, type AuthContextType } from "../../../context/AuthContext";
import type { OptimizationResultResponse } from "../../../types/interventions";

const { mockOptimizationResult } = vi.hoisted(() => {
  const mockOptimizationResult: OptimizationResultResponse = {
    run_id: "RUN_OPT_TEST1234",
    algorithm: "NSGA_II_PARETO",
    budget_inr: 25000000.0,
    solutions_count: 2,
    config: {
      run_id: "RUN_OPT_TEST1234",
      budget_inr: 25000000.0,
      algorithm: "nsga2",
      max_candidates: 60,
      generations: 15,
      random_seed: 42,
    },
    solutions: [
      {
        solution_id: "PARETO_NSGA2_SOL_01",
        run_id: "RUN_OPT_TEST1234",
        algorithm: "NSGA_II_PARETO",
        total_cost_inr: 24241246.38,
        portfolio_thermal_benefit_c_m2: 109860.14,
        treated_area_m2: 90000.0,
        mean_local_cooling_c: 1.221,
        citywide_cooling_c: 0.000238,
        domain_area_m2: 461630791.0,
        heat_priority_weighted_benefit_c_m2: 98234.7,
        population_exposure_benefit: null,
        population_exposure_status: "POPULATION_DATA_UNAVAILABLE",
        chronic_hotspots_count: 60,
        interventions_count: 60,
        budget_limit_inr: 25000000.0,
        budget_utilized_percent: 96.96,
        is_feasible: true,
        pareto_rank: 1,
        crowding_distance: 0.0,
        selected_candidate_ids: ["CAND_TREE_CANOPY_R206_C168", "CAND_COOL_ROOF_R207_C169"],
        unresolved_prerequisites_count: 2,
        deployments: [
          {
            candidate_id: "CAND_TREE_CANOPY_R206_C168",
            cell_id: "R206_C168",
            intervention_type: "tree_canopy",
            cost_inr: 143406.92,
            usable_area_m2: 1500.0,
            expected_cooling_c: 1.85,
            baseline_hpi: 0.72,
            baseline_lst_c: 43.76,
            is_chronic_hotspot: true,
            administrative_zone: "Udhana",
            latitude: 21.165,
            longitude: 72.845,
            landuse_typology: "vacant_public_open_land",
            feasibility_status: "FEASIBLE",
            prerequisites_status: "FEASIBLE_SUBJECT_TO_SURVEY",
            survey_prerequisites: ["UNDERGROUND_UTILITIES_CLEARANCE", "MUNICIPAL_RIGHT_OF_WAY_TENURE"],
          },
        ],
      },
    ],
  };
  return { mockOptimizationResult };
});

vi.mock("../../../services/interventionsApi", () => ({
  runInterventionOptimization: vi.fn().mockResolvedValue(mockOptimizationResult),
}));

function createMockAuth(overrides: Partial<AuthContextType> = {}): AuthContextType {
  return {
    token: "mock-token-xyz",
    user: { id: "1", username: "planner_surat", role: "planner", email: "planner@smc.gov.in", is_active: true },
    role: "planner",
    isAuthenticated: true,
    isPlannerOrAdmin: true,
    loginError: null,
    sessionMessage: null,
    isLoading: false,
    login: vi.fn().mockResolvedValue(true),
    logout: vi.fn(),
    clearSession: vi.fn(),
    ...overrides,
  };
}

describe("Optimization Component Audit & Verification", () => {
  it("renders configuration controls, budget presets and terminology button for planner", () => {
    const mockAuth = createMockAuth();
    const html = renderToStaticMarkup(
      <AuthContext.Provider value={mockAuth}>
        <Optimization initialBudgetInr={25000000} />
      </AuthContext.Provider>
    );

    // 1. Check title and headers
    expect(html).toContain("Surat Urban Cooling Optimization Engine");
    expect(html).toContain("Stage D Multi-Objective Solver");

    // 2. Check budget presets
    expect(html).toContain("Pilot Hotspots (₹50L)");
    expect(html).toContain("Smart City Phase 1 (₹2.5Cr)");
    expect(html).toContain("UHAP 2026 Citywide (₹10Cr)");

    // 3. Check algorithm controls
    expect(html).toContain("NSGA-II");
    expect(html).toContain("Exact DP Knapsack");

    // 4. Check Terminology button
    expect(html).toContain("Terminology &amp; Units");
  });

  it("shows login prompt and denies unauthenticated access", () => {
    const unauth = createMockAuth({
      isAuthenticated: false,
      isPlannerOrAdmin: false,
    });
    const html = renderToStaticMarkup(
      <AuthContext.Provider value={unauth}>
        <Optimization initialBudgetInr={25000000} />
      </AuthContext.Provider>
    );

    expect(html).toContain("Optimization Authentication Required");
    expect(html).toContain("Stage D budget optimization and intervention selection require Planner or Admin privileges");
  });
});
