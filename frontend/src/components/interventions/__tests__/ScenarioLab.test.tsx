import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import ScenarioLab from "../ScenarioLab";
import { AuthContext, type AuthContextType } from "../../../context/AuthContext";
import type { PlanningScenario } from "../../../types/interventions";

const { mockScenarios } = vi.hoisted(() => {
  const mockScenarios: PlanningScenario[] = [
    {
      scenario_name: "SMC Neighborhood Cool Corridors (Pilot Tier)",
      tier: "low",
      budget_inr: 5000000.0,
      target_focus: "Targeted pilot cooling for extreme chronic hotspots",
      recommended_types: ["tree_canopy", "cool_roof"],
      treated_cells: 39,
      total_treated_m2: 36915.0,
      mean_dlst_treated: [-0.5, -0.73, -1.0],
      peak_hotspot_dlst: [-0.54, -0.78, -1.07],
      breakdown: {
        cool_roof_m2: 7500.0,
        cool_paver_m2: 0.0,
        green_roof_m2: 0.0,
        trees_count: 585,
      },
    },
  ];
  return { mockScenarios };
});

// Mock fetch APIs
vi.mock("../../../services/interventionsApi", () => ({
  fetchScenarios: vi.fn().mockResolvedValue(mockScenarios),
  fetchDiminishingReturns: vi.fn().mockResolvedValue({
    curve_points: [
      {
        budget_inr: 5000000,
        treated_cells_count: 39,
        treated_area_m2: 36915,
        mean_local_cooling_c: 0.73,
        citywide_cooling_c: 0.058,
        heat_priority_weighted_benefit_c_m2: 26948,
        marginal_cooling_per_cr_inr: 0.146,
        trees_count: 585,
        cool_roof_m2: 7500,
        cool_paver_m2: 0,
        green_roof_m2: 0,
      },
    ],
  }),
}));

function createMockAuth(overrides: Partial<AuthContextType> = {}): AuthContextType {
  return {
    token: null,
    user: null,
    role: null,
    isAuthenticated: false,
    isPlannerOrAdmin: false,
    loginError: null,
    sessionMessage: null,
    isLoading: false,
    login: vi.fn().mockResolvedValue(true),
    logout: vi.fn(),
    clearSession: vi.fn(),
    ...overrides,
  };
}

describe("ScenarioLab Authentication & Diminishing Returns Protection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows login prompt and clear explanation when logged out instead of an error", () => {
    const mockAuth = createMockAuth({
      isAuthenticated: false,
      isPlannerOrAdmin: false,
    });

    const html = renderToStaticMarkup(
      <AuthContext.Provider value={mockAuth}>
        <ScenarioLab initialScenarios={mockScenarios} />
      </AuthContext.Provider>
    );

    // 1. Shows "Logged Out" status badge in header
    expect(html).toContain("Logged Out");

    // 2. Shows clear message for diminishing returns requirement
    expect(html).toContain("Stage D Diminishing Returns");
    expect(html).toContain("Physical Diminishing Returns &amp; Custom Simulator");
    expect(html).toContain(
      "Accessing the live Stage D knapsack diminishing returns curve and dynamic budget simulation requires"
    );
    expect(html).toContain("Planner");
    expect(html).toContain("Admin");

    // 3. Shows login prompt (LoginPanel)
    expect(html).toContain("Scenario Lab Planner Authentication");
    expect(html).toContain("Sign in with an authorized municipal account");
    expect(html).toContain("Username");
    expect(html).toContain("Password");

    // 4. Does NOT show an error message
    expect(html).not.toContain("Error loading scenarios");
    expect(html).not.toContain("Failed to load diminishing returns curve");
  });

  it("shows restricted privileges notice when signed in as researcher without planner/admin role", () => {
    const mockAuth = createMockAuth({
      token: "mock-researcher-token",
      user: {
        id: "usr_res_01",
        username: "heat_researcher",
        email: "research@surat.gov.in",
        role: "researcher",
        is_active: true,
      },
      role: "researcher",
      isAuthenticated: true,
      isPlannerOrAdmin: false,
    });

    const html = renderToStaticMarkup(
      <AuthContext.Provider value={mockAuth}>
        <ScenarioLab initialScenarios={mockScenarios} />
      </AuthContext.Provider>
    );

    // Header displays researcher role
    expect(html).toContain("heat_researcher");
    expect(html).toContain("researcher");

    // LoginPanel indicates restricted privileges
    expect(html).toContain("Restricted Privileges");
    expect(html).toContain("Role &#x27;researcher&#x27; is not authorized for budget optimization");
    expect(html).toContain("Municipal optimization requires");
  });

  it("renders interactive simulator and omits login prompt when signed in as planner or admin", () => {
    const mockAuth = createMockAuth({
      token: "mock-planner-token",
      user: {
        id: "usr_plan_01",
        username: "planner_officer",
        email: "planner@surat.gov.in",
        role: "planner",
        is_active: true,
      },
      role: "planner",
      isAuthenticated: true,
      isPlannerOrAdmin: true,
    });

    const html = renderToStaticMarkup(
      <AuthContext.Provider value={mockAuth}>
        <ScenarioLab initialScenarios={mockScenarios} />
      </AuthContext.Provider>
    );

    // Header displays planner details
    expect(html).toContain("planner_officer");
    expect(html).toContain("planner");

    // Login prompt is omitted
    expect(html).not.toContain("Scenario Lab Planner Authentication");

    // Simulator controls are rendered
    expect(html).toContain("Physics Simulator");
    expect(html).toContain("Custom Budget Optimization Projections");
    expect(html).toContain("Municipal Budget Ceiling:");
  });
});

