import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fetchGridCellDetail,
  fetchGridCells,
  fetchHeatPrioritySummary,
  fetchModelValidation,
  fetchHPISensitivityAnalysis,
} from "../heatPriorityApi";

describe("heatPriorityApi", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("fetchHeatPrioritySummary", () => {
    it("fetches HPI summary with encoded scoring period and spec version", async () => {
      const mockSummary = {
        scoring_period: "2026_summer_operational",
        spec_version: "v2.0",
        total_grid_cells: 49747,
        scored_cells_count: 49747,
        mean_hpi: 52.4,
        min_hpi: 10.2,
        max_hpi: 98.6,
        chronic_hotspots_count: 223,
        confidence_tier_counts: { HIGH: 49100, MODERATE: 647 },
        persistence_tier_counts: { chronic_hotspot: 223 },
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockSummary,
      });

      const result = await fetchHeatPrioritySummary();

      expect(fetch).toHaveBeenCalledTimes(1);
      const callUrl = (fetch as any).mock.calls[0][0];
      expect(callUrl).toContain("/api/v1/heat-priority/summary");
      expect(callUrl).toContain("scoring_period=2026_summer_operational");
      expect(callUrl).toContain("spec_version=v2.0");
      expect(result.total_grid_cells).toBe(49747);
      expect(result.chronic_hotspots_count).toBe(223);
    });

    it("throws when server returns error response", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 503,
      });

      await expect(fetchHeatPrioritySummary()).rejects.toThrow("HTTP 503");
    });
  });

  describe("fetchGridCells", () => {
    it("formats bounding box and filter query parameters correctly", async () => {
      const mockResponse = {
        total: 15,
        offset: 0,
        limit: 350,
        items: [
          {
            pixel_id: "R100_C200",
            row_idx: 100,
            col_idx: 200,
            latitude: 21.17,
            longitude: 72.83,
            heat_priority_score: 82.5,
            is_chronic_hotspot: true,
            confidence_tier: "HIGH",
            persistence_tier: "chronic_hotspot",
          },
        ],
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const result = await fetchGridCells({
        bbox: { min_lon: 72.8, min_lat: 21.1, max_lon: 72.9, max_lat: 21.2 },
        min_hpi: 50,
        is_chronic_hotspot: true,
        limit: 350,
      });

      expect(fetch).toHaveBeenCalledTimes(1);
      const callUrl = (fetch as any).mock.calls[0][0];
      expect(callUrl).toContain("bbox=72.8%2C21.1%2C72.9%2C21.2");
      expect(callUrl).toContain("min_hpi=50");
      expect(callUrl).toContain("is_chronic_hotspot=true");
      expect(callUrl).toContain("limit=350");
      expect(result.items).toHaveLength(1);
      expect(result.items[0].pixel_id).toBe("R100_C200");
    });
  });

  describe("fetchGridCellDetail", () => {
    it("fetches single cell detail and handles 404 cleanly", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      await expect(fetchGridCellDetail("UNKNOWN_CELL")).rejects.toThrow(
        "Grid cell 'UNKNOWN_CELL' not found."
      );
    });
  });

  describe("fetchModelValidation", () => {
    it("fetches model validation and qc summary successfully", async () => {
      const mockValidation = {
        qc_summary: {
          status: "PASS",
          holdout_evaluation: {
            test_rows: 203758,
            mae: 1.27,
            rmse: 1.76,
            r2: 0.9006,
          },
        },
        model_metadata: {
          model_id: "surat_operational_rf_v2",
        },
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockValidation,
      });

      const result = await fetchModelValidation();

      expect(fetch).toHaveBeenCalledTimes(1);
      const callUrl = (fetch as any).mock.calls[0][0];
      expect(callUrl).toContain("/api/v1/heat-priority/model-validation");
      expect(result.qc_summary.status).toBe("PASS");
      expect(result.qc_summary.holdout_evaluation.test_rows).toBe(203758);
    });

    it("throws when server returns error response", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await expect(fetchModelValidation()).rejects.toThrow(
        "Failed to load model validation metadata: HTTP 500"
      );
    });
  });

  describe("fetchHPISensitivityAnalysis", () => {
    it("fetches HPI sensitivity analysis payload", async () => {
      const mockSensitivity = {
        analysis_name: "Stage C Heat Priority Index (HPI) Sensitivity Analysis",
        status: "COMPLETED",
        baseline: { total_cells: 49747, mean_hpi: 42.14 },
        scenarios: [
          {
            id: "thermal_dominant",
            name: "Thermal-Dominant (Heatwave Emergency)",
            weights: { w_thermal: 0.6, w_persistence: 0.2, w_vegetation: 0.1, w_builtup: 0.1 },
            metrics: { mean_hpi: 51.06, spearman_rho: 0.9802 },
          },
        ],
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockSensitivity,
      });

      const result = await fetchHPISensitivityAnalysis();
      expect(fetch).toHaveBeenCalledTimes(1);
      const callUrl = (fetch as any).mock.calls[0][0];
      expect(callUrl).toContain("/api/v1/heat-priority/sensitivity-analysis");
      expect(result.status).toBe("COMPLETED");
      expect(result.baseline.total_cells).toBe(49747);
      expect(result.scenarios[0].metrics.spearman_rho).toBe(0.9802);
    });

    it("throws when server returns error response", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await expect(fetchHPISensitivityAnalysis()).rejects.toThrow(
        "Failed to load HPI sensitivity analysis: HTTP 500"
      );
    });
  });
});

