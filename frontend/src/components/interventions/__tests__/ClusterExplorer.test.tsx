import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import InterventionExplorer from "../InterventionExplorer";
import type { AreaItem, AreaSummary, ClustersListResponse } from "../../../types/interventions";

const { mockAreas, mockSummary, mockClusters } = vi.hoisted(() => {
  const mockAreas: AreaItem[] = [
    {
      area_name: "Udhana",
      total_cells: 1524,
      eligible_cell_count: 1524,
      chronic_hotspot_count: 70,
      mean_hpi: 55.8,
      max_hpi: 88.4,
      is_sufficient: true,
      data_status: "SUFFICIENT",
      insufficient_reason: null,
      top_recommended_type: "cool_roof",
      estimated_portfolio_cost_inr: 843904724.48,
      expected_portfolio_cooling_c: 0.8,
    },
    {
      area_name: "Bhestan",
      total_cells: 2278,
      eligible_cell_count: 2278,
      chronic_hotspot_count: 89,
      mean_hpi: 58.1,
      max_hpi: 91.2,
      is_sufficient: true,
      data_status: "SUFFICIENT",
      insufficient_reason: null,
      top_recommended_type: "cool_roof",
      estimated_portfolio_cost_inr: 1250000000.0,
      expected_portfolio_cooling_c: 1.2,
    },
  ];

  const mockSummary: AreaSummary = {
    area_name: "Udhana",
    is_all_areas: false,
    total_cells: 1524,
    eligible_cells: 1524,
    chronic_cells: 70,
    assigned_cells_count: 1323,
    unassigned_insufficient_surface_count: 201,
    mean_hpi: 55.8,
    mean_baseline_lst_c: 42.4,
    best_option_mean_cooling_c: 0.8,
    best_option_portfolio_cost_inr: 843904724.48,
    full_coverage_bound_inr: 843904724.48,
    total_treated_area_m2: 2286000.0,
    total_geographic_area_ha: 152.4,
    qualifying_candidates_count: 1524,
    clusters_count: 121,
    is_sufficient: true,
    insufficient_reason: null,
    phase1_portfolio: {
      budget_cap_inr: 25000000.0,
      budget_utilized_inr: 24900000.0,
      budget_utilization_pct: 99.6,
      clusters_count: 35,
      cells_count: 88,
      chronic_hotspots_covered: 70,
      mean_cooling_c: 1.82,
      treated_footprint_m2: 85000.0,
    },
    data_confidence_summary: {
      survey_required_percentage: 100.0,
      unverified_roof_percentage: 100.0,
      valid_observations_percentage: 98.5,
    },
  };

  const mockClusters: ClustersListResponse = {
    total_clusters: 121,
    limit: 12,
    offset: 0,
    area_name: "Udhana",
    is_sufficient: true,
    insufficient_reason: null,
    clusters: [
      {
        cluster_id: "CLUST_UDHANA_COOL_ROOF_001",
        area_name: "Udhana",
        intervention_type: "cool_roof",
        title: "Udhana Cluster #1 (16 Contiguous Cells)",
        priority_rank: 1,
        priority_score: 84.5,
        priority_tier: "CRITICAL",
        cell_count: 16,
        treated_footprint_m2: 24000.0,
        geographic_coverage_ha: 1.6,
        expected_cooling_c: 0.58,
        expected_cooling_c_range: [0.4, 0.8],
        indicative_diluted_cooling_c: 0.087,
        estimated_cost_inr: 10060164.0,
        estimated_cost_inr_range: [8000000.0, 12000000.0],
        unit_cost_inr_per_m2: 419.2,
        mean_hpi: 62.4,
        max_hpi: 78.1,
        chronic_hotspot_cells_count: 12,
        mean_baseline_lst_c: 43.1,
        centroid: { latitude: 21.16, longitude: 72.84 },
        bounding_box: { min_lon: 72.83, min_lat: 21.15, max_lon: 72.85, max_lat: 21.17 },
        confidence_rating: "MEDIUM",
        survey_required_cells_count: 16,
        unverified_roof_cells_count: 16,
        caveats_and_warnings: [
          "16/16 cells: roof structural feasibility unverified — engineering survey required.",
        ],
        co_benefits_summary: "Stormwater runoff attenuation, urban heat island mitigation.",
        ranking_factors: {
          hpi_factor: 62.4,
          chronic_factor: 75.0,
          cooling_factor: 58.0,
          cost_effectiveness_factor: 65.0,
        },
      },
    ],
  };

  return { mockAreas, mockSummary, mockClusters };
});

// Mock fetch APIs
vi.mock("../../../services/interventionsApi", () => ({
  fetchInterventionAreas: vi.fn().mockResolvedValue(mockAreas),
  fetchAreaSummary: vi.fn().mockResolvedValue(mockSummary),
  fetchAreaClusters: vi.fn().mockResolvedValue(mockClusters),
  fetchClusterCells: vi.fn().mockResolvedValue({
    cluster_id: "CLUST_UDHANA_COOL_ROOF_001",
    area_name: "Udhana",
    intervention_type: "cool_roof",
    cell_count: 1,
    cells: [],
  }),
  fetchInterventionCandidates: vi.fn().mockResolvedValue({
    total_count: 0,
    limit: 50,
    offset: 0,
    items: [],
  }),
  fetchCandidateDetail: vi.fn(),
}));

describe("InterventionExplorer (Cluster-Level Redesign)", () => {
  it("renders the redesigned area-based explorer hero banner and SMC context", () => {
    const html = renderToStaticMarkup(<InterventionExplorer />);

    expect(html).toContain("Area-Based Intervention Explorer");
    expect(html).toContain("Stage D Prescriptive Action Catalog");
    expect(html).toContain("SMC Locality &amp; Cluster Recommendation Engine");
    expect(html).toContain("Target Locality:");
    expect(html).toContain("Phase 1 Budget:");
  });

  it("renders the 4 primary area KPI cards and mode switcher", () => {
    const html = renderToStaticMarkup(<InterventionExplorer />);

    expect(html).toContain("Phase 1 Capital Outlay");
    expect(html).toContain("Phase 1 Funded Units");
    expect(html).toContain("Phase 1 Mean Cooling");
    expect(html).toContain("Hotspots Mitigated");

    // Mode toggles
    expect(html).toContain("Area Clusters (SMC Recommended)");
    expect(html).toContain("Flat Grid (100m Cells)");
  });

  it("renders the intervention type filter chips and feasibility toggle", () => {
    const html = renderToStaticMarkup(<InterventionExplorer />);

    expect(html).toContain("All Types");
    expect(html).toContain("High-Albedo Cool Roof");
    expect(html).toContain("Native Urban Forestry");
    expect(html).toContain("Model-eligible (FEASIBLE)");
    expect(html).toContain("Not applicable here");
  });
});
