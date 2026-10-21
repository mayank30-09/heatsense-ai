import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fetchCandidateDetail,
  fetchInterventionCandidates,
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
});
