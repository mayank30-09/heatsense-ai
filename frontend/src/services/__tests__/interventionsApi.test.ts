import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fetchAreaClusters,
  fetchAreaSummary,
  fetchCandidateDetail,
  fetchClusterCells,
  fetchCellLandCover,
  fetchLandCoverSummary,
  fetchDiminishingReturns,
  fetchInterventionAreas,
  fetchInterventionCandidates,
  fetchScenarios,
  optimizeInterventions,
  runInterventionOptimization,
} from "../interventionsApi";
import type { OptimizeRequestPayload } from "../../types/interventions";

describe("interventionsApi", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("fetchInterventionCandidates", () => {
    it("fetches candidates with query parameters", async () => {
      const mockResponse = {
        total_candidates: 1,
        candidates: [],
        limit: 10,
        offset: 0,
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const result = await fetchInterventionCandidates({
        bbox: { min_lon: 72.8, min_lat: 21.1, max_lon: 72.9, max_lat: 21.2 },
        intervention_type: "cool_roof",
        limit: 10,
      });

      expect(fetch).toHaveBeenCalledTimes(1);
      const [url] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/candidates");
      expect(url).toContain("bbox=72.8%2C21.1%2C72.9%2C21.2");
      expect(url).toContain("intervention_type=cool_roof");
      expect(url).toContain("limit=10");
      expect(result).toEqual(mockResponse);
    });

    it("fetches candidates with feasibility_status and offset filters", async () => {
      const mockResponse = {
        total_count: 5,
        limit: 25,
        offset: 10,
        items: [],
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const result = await fetchInterventionCandidates({
        feasibility_status: "FEASIBLE",
        limit: 25,
        offset: 10,
      });

      expect(fetch).toHaveBeenCalledTimes(1);
      const [url] = (fetch as any).mock.calls[0];
      expect(url).toContain("feasibility_status=FEASIBLE");
      expect(url).toContain("limit=25");
      expect(url).toContain("offset=10");
      expect(result).toEqual(mockResponse);
    });

    it("throws error when candidate listing request fails", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await expect(fetchInterventionCandidates()).rejects.toThrow(
        "Failed to load intervention candidates: HTTP 500"
      );
    });
  });

  describe("fetchCandidateDetail", () => {
    it("fetches candidate detail with encoded id", async () => {
      const mockCandidate = {
        candidate_id: "SURAT_ROOF_001",
        intervention_type: "cool_roof",
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockCandidate,
      });

      const result = await fetchCandidateDetail("SURAT_ROOF_001");

      expect(fetch).toHaveBeenCalledTimes(1);
      const [url] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/candidates/SURAT_ROOF_001");
      expect(result).toEqual(mockCandidate);
    });

    it("throws error when candidate detail fails", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      await expect(fetchCandidateDetail("NON_EXISTENT_ID")).rejects.toThrow(
        "Failed to load candidate detail: HTTP 404"
      );
    });
  });

  describe("runInterventionOptimization", () => {
    const payload: OptimizeRequestPayload = {
      budget_inr: 5000000,
      algorithm: "greedy",
      target_types: ["cool_roof"],
    };

    it("submits optimization request without auth token when omitted", async () => {
      const mockResult = {
        method: "greedy",
        budget_allocated: 4500000,
        selected_count: 2,
        solutions: [],
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResult,
      });

      const result = await runInterventionOptimization(payload);

      expect(fetch).toHaveBeenCalledTimes(1);
      const [url, init] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/optimize");
      expect(init.method).toBe("POST");
      expect(init.headers["Content-Type"]).toBe("application/json");
      expect(init.headers["Authorization"]).toBeUndefined();
      expect(JSON.parse(init.body)).toEqual(payload);
      expect(result).toEqual(mockResult);
    });

    it("attaches Bearer authorization header when token is supplied", async () => {
      const mockResult = {
        method: "nsga2",
        budget_allocated: 4800000,
        selected_count: 3,
        solutions: [],
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResult,
      });

      const token = "mock-jwt-token-xyz";
      const result = await runInterventionOptimization(payload, token);

      expect(fetch).toHaveBeenCalledTimes(1);
      const [url, init] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/optimize");
      expect(init.headers["Authorization"]).toBe("Bearer mock-jwt-token-xyz");
      expect(result).toEqual(mockResult);
    });

    it("verifies optimizeInterventions alias function works identically", async () => {
      const mockResult = {
        method: "greedy",
        budget_allocated: 1000000,
        selected_count: 1,
        solutions: [],
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResult,
      });

      const token = "mock-admin-token";
      const result = await optimizeInterventions(payload, token);

      expect(result).toEqual(mockResult);
      const [, init] = (fetch as any).mock.calls[0];
      expect(init.headers["Authorization"]).toBe("Bearer mock-admin-token");
    });

    it("throws error when optimization fails", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      await expect(runInterventionOptimization(payload)).rejects.toThrow(
        "Optimization failed: HTTP 401"
      );
    });
  });

  describe("fetchScenarios", () => {
    it("fetches reference planning scenarios", async () => {
      const mockScenarios = [
        {
          scenario_name: "SMC Neighborhood Cool Corridors",
          budget_inr: 5000000,
          target_focus: "Pilot cooling",
          recommended_types: ["tree_canopy", "cool_roof"],
        },
      ];

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockScenarios,
      });

      const result = await fetchScenarios();

      expect(fetch).toHaveBeenCalledTimes(1);
      const [url] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/scenarios");
      expect(result).toEqual(mockScenarios);
    });

    it("throws error when fetching scenarios fails", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await expect(fetchScenarios()).rejects.toThrow(
        "Failed to load planning scenarios: HTTP 500"
      );
    });
  });

  describe("fetchDiminishingReturns", () => {
    it("posts request to diminishing-returns endpoint and returns curve points", async () => {
      const mockCurve = {
        algorithm: "GREEDY_KNAPSACK",
        curve_points: [
          { budget_inr: 5000000, total_cost_inr: 4950000, treated_cells_count: 35 },
          { budget_inr: 25000000, total_cost_inr: 24800000, treated_cells_count: 120 },
        ],
        parameters: { max_candidates: 40 },
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockCurve,
      });

      const result = await fetchDiminishingReturns({ max_candidates: 40 }, "test-token");
      expect(fetch).toHaveBeenCalledTimes(1);
      const [url, options] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/diminishing-returns");
      expect(options.method).toBe("POST");
      expect(options.headers["Authorization"]).toBe("Bearer test-token");
      expect(result).toEqual(mockCurve);
    });

    it("throws error when diminishing-returns request fails", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await expect(fetchDiminishingReturns()).rejects.toThrow(
        "Failed to load diminishing returns curve: HTTP 500"
      );
    });
  });

  describe("fetchInterventionAreas", () => {
    it("fetches areas list with min_hpi parameter", async () => {
      const mockAreas = [
        { area_name: "Udhana", total_cells: 1524, eligible_cell_count: 1524, is_sufficient: true },
        { area_name: "Bhestan", total_cells: 2278, eligible_cell_count: 2278, is_sufficient: true },
      ];

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockAreas,
      });

      const res = await fetchInterventionAreas(40.0);
      expect(fetch).toHaveBeenCalledTimes(1);
      const [url] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/areas?min_hpi=40");
      expect(res).toEqual(mockAreas);
    });
  });

  describe("fetchAreaSummary", () => {
    it("fetches locality summary with query params", async () => {
      const mockSummary = {
        area_name: "Udhana",
        is_sufficient: true,
        best_option_mean_cooling_c: 0.8,
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockSummary,
      });

      const res = await fetchAreaSummary("Udhana", { min_hpi: 35, intervention_type: "cool_roof" });
      expect(fetch).toHaveBeenCalledTimes(1);
      const [url] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/areas/Udhana/summary");
      expect(url).toContain("min_hpi=35");
      expect(url).toContain("intervention_type=cool_roof");
      expect(res).toEqual(mockSummary);
    });
  });

  describe("fetchAreaClusters", () => {
    it("fetches ranked clusters with pagination and sorting", async () => {
      const mockClusters = {
        total_clusters: 12,
        clusters: [{ cluster_id: "CLUST_001", priority_score: 85 }],
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockClusters,
      });

      const res = await fetchAreaClusters("Udhana", { sort_by: "cooling_desc", limit: 5 });
      expect(fetch).toHaveBeenCalledTimes(1);
      const [url] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/areas/Udhana/clusters");
      expect(url).toContain("sort_by=cooling_desc");
      expect(url).toContain("limit=5");
      expect(res).toEqual(mockClusters);
    });
  });

  describe("fetchClusterCells", () => {
    it("fetches contributing cells for cluster", async () => {
      const mockDetail = {
        cluster_id: "CLUST_001",
        cell_count: 3,
        cells: [{ cell_id: "R100_C200" }],
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockDetail,
      });

      const res = await fetchClusterCells("CLUST_001");
      expect(fetch).toHaveBeenCalledTimes(1);
      const [url] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/clusters/CLUST_001/cells");
      expect(res).toEqual(mockDetail);
    });
  });

  describe("Dynamic World Land Cover API", () => {
    it("fetches cell land cover with 9-class probabilities and suitability", async () => {
      const mockDw = {
        cell_id: "R000_C249",
        top_class: "built",
        confidence: 0.6346,
        probabilities: { built: 0.6346, bare: 0.0396 },
        suitability: { rule_fired: "RULE_DW_BUILT_DENSE" },
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockDw,
      });

      const res = await fetchCellLandCover("R000_C249", "summer", 2024);
      expect(fetch).toHaveBeenCalledTimes(1);
      const [url] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/landcover/R000_C249?season=summer&year=2024");
      expect(res).toEqual(mockDw);
    });

    it("fetches land cover summary", async () => {
      const mockSummary = {
        total_cells_recorded: 330,
        cells_sufficient: 330,
        class_distribution: { built: 302 },
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockSummary,
      });

      const res = await fetchLandCoverSummary("summer", 2024);
      expect(fetch).toHaveBeenCalledTimes(1);
      const [url] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/landcover/summary?season=summer&year=2024");
      expect(res).toEqual(mockSummary);
    });
  });
});
