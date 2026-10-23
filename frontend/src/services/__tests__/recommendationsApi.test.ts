import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fetchPolygonRecommendations,
  exportRecommendationsToCsv,
  exportRecommendationsToJson,
  type RecommendationsResponse,
} from "../recommendationsApi";

const mockResponse: RecommendationsResponse = {
  polygon_summary: {
    status: "ok",
    area_km2: 1.25,
    inside_smc_fraction: 1.0,
    season: "summer",
    effective_year: 2026,
    mean_lst_c: 41.5,
    max_lst_c: 44.2,
    min_lst_c: 38.0,
    mean_hpi: 62.4,
    max_hpi: 78.1,
    mean_ndvi: 0.12,
    mean_ndbi: 0.35,
    mean_ndwi: -0.15,
    water_fraction: 0.0,
    water_warning: false,
    cell_count: 5,
    chronic_cell_count: 2,
    chronic_cell_share: 0.4,
    frequent_cell_share: 0.6,
    data_coverage_percentage: 98.5,
    confidence_score: 85.0,
    confidence_tier: "HIGH",
  },
  recommendations: [
    {
      type: "cool_roofs",
      title: "High-Albedo Cool Roof Coating",
      priority: "HIGH",
      rationale: "Elevated mean surface temperature of 41.5°C and built-up index NDBI 0.35.",
      quantity_basis: {
        estimated_quantity: 125000,
        unit: "sq.m of roof surface",
        basis_description: "Estimated 10% built-up roof density over 1.25 km².",
        missing_data_survey_note: "not available - field survey required",
      },
      cost_range_inr: {
        base: 25000000,
        min: 20000000,
        max: 30000000,
        formatted: "₹2.00 Cr - ₹3.00 Cr",
        maintenance_horizon: "Recoting cycle: 5 years",
      },
      cooling_range_c: {
        expected: 2.1,
        min: 1.5,
        max: 3.2,
        formatted: "1.5°C - 3.2°C",
        model_source: "Stage D Cool Roof Energy Model",
      },
      feasibility_status: "FEASIBLE",
      rejection_reasons: [],
      feasibility_notes: ["High solar exposure"],
      maintenance_note: "Routine annual washing and inspection.",
      evidence_label: "MODELLED",
      missing_data_survey_requirements: [
        "not available - field survey required (roof area)",
      ],
    },
    {
      type: "urban_greening",
      title: "Urban Tree Canopy & Vegetative Buffer",
      priority: "HIGH",
      rationale: "Severe vegetation deficit (NDVI 0.12) and 40.0% chronic heat cells.",
      quantity_basis: {
        estimated_quantity: 2500,
        unit: "native canopy trees",
        basis_description: "Targeting 20 trees per hectare over permeable fractions.",
        missing_data_survey_note: "not available - field survey required",
      },
      cost_range_inr: {
        base: 8750000,
        min: 7500000,
        max: 10500000,
        formatted: "₹75.00 L - ₹1.05 Cr",
        maintenance_horizon: "Initial 3-year establishment watering",
      },
      cooling_range_c: {
        expected: 1.8,
        min: 1.2,
        max: 2.5,
        formatted: "1.2°C - 2.5°C",
        model_source: "Stage D Urban Forestry Cooling Model",
      },
      feasibility_status: "FEASIBLE",
      rejection_reasons: [],
      feasibility_notes: ["Requires root barrier protection"],
      maintenance_note: "Regular drip irrigation for first 36 months.",
      evidence_label: "MODELLED",
      missing_data_survey_requirements: [
        "not available - field survey required (permeable ground)",
      ],
    },
  ],
  caveats: [
    "Interventions are preliminary modelled estimates.",
    "Field survey is required before capital outlay.",
  ],
  assumptions_applied: [
    "ASSUMPTION_COOL_ROOF_LST_MIN_C: 38.0°C",
    "ASSUMPTION_GREENING_NDVI_MAX: 0.25",
  ],
  evidence_label: "MODELLED",
};

describe("recommendationsApi", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches polygon recommendations successfully", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as any);

    const testGeo = {
      type: "Polygon",
      coordinates: [
        [
          [72.82, 21.18],
          [72.84, 21.18],
          [72.84, 21.2],
          [72.82, 21.2],
          [72.82, 21.18],
        ],
      ],
    };

    const result = await fetchPolygonRecommendations(testGeo, "summer", 2026);

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, options] = fetchSpy.mock.calls[0];
    expect(url).toContain("/analysis/recommendations");
    expect(options?.method).toBe("POST");
    expect(JSON.parse(options?.body as string)).toEqual({
      geometry: testGeo,
      season: "summer",
      year: 2026,
    });
    expect(result.recommendations.length).toBe(2);
    expect(result.recommendations[0].type).toBe("cool_roofs");
  });

  it("handles backend API error gracefully", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ detail: "Invalid polygon geometry" }),
    } as any);

    await expect(
      fetchPolygonRecommendations({ type: "Point" }, "summer", 2026)
    ).rejects.toThrow("Invalid polygon geometry");
  });

  it("generates CSV export and triggers download", () => {
    let capturedFilename = "";
    const mockAnchor = {
      href: "",
      download: "",
      click: vi.fn(() => {
        capturedFilename = mockAnchor.download;
      }),
    };

    const originalDocument = (globalThis as any).document;
    const originalUrl = (globalThis as any).URL;

    (globalThis as any).document = {
      body: {
        appendChild: vi.fn(),
        removeChild: vi.fn(),
      },
      createElement: vi.fn((tag: string) => {
        if (tag === "a") return mockAnchor;
        return {};
      }),
    };
    (globalThis as any).URL = {
      createObjectURL: vi.fn(() => "blob:mock-url"),
      revokeObjectURL: vi.fn(),
    };

    try {
      exportRecommendationsToCsv(mockResponse, "test_recommendations");
      expect(capturedFilename).toBe("test_recommendations.csv");
      expect(mockAnchor.click).toHaveBeenCalled();
      expect((globalThis as any).URL.createObjectURL).toHaveBeenCalled();
      expect((globalThis as any).document.body.appendChild).toHaveBeenCalled();
      expect((globalThis as any).document.body.removeChild).toHaveBeenCalled();
    } finally {
      (globalThis as any).document = originalDocument;
      (globalThis as any).URL = originalUrl;
    }
  });

  it("generates JSON export and triggers download", () => {
    let capturedFilename = "";
    const mockAnchor = {
      href: "",
      download: "",
      click: vi.fn(() => {
        capturedFilename = mockAnchor.download;
      }),
    };

    const originalDocument = (globalThis as any).document;
    const originalUrl = (globalThis as any).URL;

    (globalThis as any).document = {
      body: {
        appendChild: vi.fn(),
        removeChild: vi.fn(),
      },
      createElement: vi.fn((tag: string) => {
        if (tag === "a") return mockAnchor;
        return {};
      }),
    };
    (globalThis as any).URL = {
      createObjectURL: vi.fn(() => "blob:mock-url"),
      revokeObjectURL: vi.fn(),
    };

    try {
      exportRecommendationsToJson(mockResponse, "test_recommendations");
      expect(capturedFilename).toBe("test_recommendations.json");
      expect(mockAnchor.click).toHaveBeenCalled();
      expect((globalThis as any).URL.createObjectURL).toHaveBeenCalled();
      expect((globalThis as any).document.body.appendChild).toHaveBeenCalled();
      expect((globalThis as any).document.body.removeChild).toHaveBeenCalled();
    } finally {
      (globalThis as any).document = originalDocument;
      (globalThis as any).URL = originalUrl;
    }
  });
});
