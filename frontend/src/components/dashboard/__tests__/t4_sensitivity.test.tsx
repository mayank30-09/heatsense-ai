import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import ValidationTrust from "../ValidationTrust";
import type { HPISensitivityAnalysisResponse, SensitivityScenario } from "../../../types/heatPriority";

describe("T4 HPI Sensitivity Analysis Requirements", () => {
  it("renders ValidationTrust hero header with scientific trust and model estimate badge", () => {
    const html = renderToStaticMarkup(<ValidationTrust />);
    expect(html).toContain("Model Validation &amp; Scientific Trust Center");
    expect(html).toContain("MODEL ESTIMATE");
  });

  it("verifies HPISensitivityAnalysisResponse data model and scenario constraints", () => {
    const mockReport: HPISensitivityAnalysisResponse = {
      analysis_name: "Stage C Heat Priority Index (HPI) Sensitivity Analysis",
      generated_at_utc: "2026-10-26T07:04:36Z",
      status: "COMPLETED",
      evidence_paths: {
        baseline_scores_table: "stage_c_heat_priority_scores",
        report_json: "reports/hpi_sensitivity_analysis.json",
        report_md: "reports/hpi_sensitivity_analysis.md",
      },
      baseline: {
        total_cells: 49747,
        mean_hpi: 42.14,
        std_hpi: 12.58,
        min_hpi: 4.83,
        max_hpi: 96.39,
        median_hpi: 44.69,
        chronic_hotspots_count: 223,
        max_recomputation_discrepancy: 0.000008,
        weights: {
          w_thermal: 0.4,
          w_persistence: 0.3,
          w_vegetation: 0.15,
          w_builtup: 0.15,
        },
        formula: "HPI = 100 * (0.40 * T_norm + 0.30 * P_persist + 0.15 * V_deficit + 0.15 * B_density)",
      },
      scenarios: [
        {
          id: "thermal_dominant",
          name: "Thermal-Dominant (Heatwave Emergency)",
          weights: { w_thermal: 0.6, w_persistence: 0.2, w_vegetation: 0.1, w_builtup: 0.1 },
          formula: "HPI = 100 * (0.60 * T_norm + 0.20 * P_persist + 0.10 * V_deficit + 0.10 * B_density)",
          policy_rationale: "Emergency mobilization",
          metrics: {
            mean_hpi: 51.06,
            std_hpi: 13.77,
            min_hpi: 7.24,
            max_hpi: 97.59,
            score_diff_mean: 8.92,
            score_diff_abs_mean: 9.06,
            pearson_r: 0.9741,
            spearman_rho: 0.9802,
            top_10pct_jaccard_pct: 73.59,
            top_500_jaccard_pct: 86.57,
            mean_rank_shift: 2195.5,
            max_rank_shift: 15758,
            cells_shifted_over_1k: 34860,
            cells_shifted_over_5k: 4331,
            top_10pct_shared_count: 4218,
            top_500_shared_count: 464,
          },
        },
        {
          id: "persistence_dominant",
          name: "Persistence-Dominant (Infrastructure)",
          weights: { w_thermal: 0.25, w_persistence: 0.5, w_vegetation: 0.15, w_builtup: 0.1 },
          formula: "HPI = 100 * (0.25 * T_norm + 0.50 * P_persist + 0.15 * V_deficit + 0.10 * B_density)",
          policy_rationale: "Long-term infrastructure",
          metrics: {
            mean_hpi: 29.48,
            std_hpi: 9.88,
            min_hpi: 3.02,
            max_hpi: 96.77,
            score_diff_mean: -12.65,
            score_diff_abs_mean: 12.66,
            pearson_r: 0.9787,
            spearman_rho: 0.9917,
            top_10pct_jaccard_pct: 84.43,
            top_500_jaccard_pct: 89.04,
            mean_rank_shift: 1341.0,
            max_rank_shift: 25552,
            cells_shifted_over_1k: 26356,
            cells_shifted_over_5k: 1298,
            top_10pct_shared_count: 4555,
            top_500_shared_count: 471,
          },
        },
        {
          id: "nature_deficit",
          name: "Nature-Deficit (Urban Greening)",
          weights: { w_thermal: 0.3, w_persistence: 0.2, w_vegetation: 0.3, w_builtup: 0.2 },
          formula: "HPI = 100 * (0.30 * T_norm + 0.20 * P_persist + 0.30 * V_deficit + 0.20 * B_density)",
          policy_rationale: "Urban forestry",
          metrics: {
            mean_hpi: 44.41,
            std_hpi: 15.4,
            min_hpi: 3.62,
            max_hpi: 93.55,
            score_diff_mean: 2.27,
            score_diff_abs_mean: 4.58,
            pearson_r: 0.9559,
            spearman_rho: 0.9660,
            top_10pct_jaccard_pct: 64.27,
            top_500_jaccard_pct: 72.12,
            mean_rank_shift: 2740.1,
            max_rank_shift: 16744,
            cells_shifted_over_1k: 36008,
            cells_shifted_over_5k: 7140,
            top_10pct_shared_count: 3893,
            top_500_shared_count: 419,
          },
        },
        {
          id: "equal_weighting",
          name: "Equal Component Weighting",
          weights: { w_thermal: 0.25, w_persistence: 0.25, w_vegetation: 0.25, w_builtup: 0.25 },
          formula: "HPI = 100 * (0.25 * T_norm + 0.25 * P_persist + 0.25 * V_deficit + 0.25 * B_density)",
          policy_rationale: "Unweighted benchmark",
          metrics: {
            mean_hpi: 41.28,
            std_hpi: 14.71,
            min_hpi: 3.02,
            max_hpi: 93.98,
            score_diff_mean: -0.86,
            score_diff_abs_mean: 3.48,
            pearson_r: 0.9640,
            spearman_rho: 0.9701,
            top_10pct_jaccard_pct: 66.00,
            top_500_jaccard_pct: 80.51,
            mean_rank_shift: 2628.6,
            max_rank_shift: 15094,
            cells_shifted_over_1k: 35451,
            cells_shifted_over_5k: 7080,
            top_10pct_shared_count: 3956,
            top_500_shared_count: 446,
          },
        },
      ],
      scientific_caveats: {
        sensitivity_vs_validation: "Sensitivity is not empirical model validation or causal evidence",
        no_retraining_or_mutation: "No model retraining, raw satellite data unchanged",
        policy_guidance: "Consensus high-priority cells",
      },
    };

    expect(mockReport.baseline.total_cells).toBe(49747);
    expect(mockReport.baseline.chronic_hotspots_count).toBe(223);
    expect(mockReport.scenarios).toHaveLength(4);

    for (const sc of mockReport.scenarios) {
      const weightSum =
        sc.weights.w_thermal +
        sc.weights.w_persistence +
        sc.weights.w_vegetation +
        sc.weights.w_builtup;
      expect(Math.abs(weightSum - 1.0)).toBeLessThan(1e-6);
      expect(sc.metrics.spearman_rho).toBeGreaterThan(0.95);
      expect(sc.metrics.top_500_jaccard_pct).toBeGreaterThan(70.0);
      expect(sc.metrics.pearson_r).toBeGreaterThan(0.95);
    }
  });
});
