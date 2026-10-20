import { describe, expect, it } from "vitest";
import {
  getConfidenceColor,
  getEligibilityInfo,
  getHPIColor,
  getLSTColor,
  getOpticalImputationLabel,
  getPersistenceBadge,
} from "../hpiColorScales";

describe("hpiColorScales", () => {
  describe("getHPIColor", () => {
    it("returns gray for null or undefined scores (missing / excluded data)", () => {
      expect(getHPIColor(null)).toBe("#94a3b8");
      expect(getHPIColor(NaN)).toBe("#94a3b8");
    });

    it("returns chronic hotspot crimson when scored and isChronic is true", () => {
      expect(getHPIColor(45, true)).toBe("#991b1b");
      expect(getHPIColor(null, true)).toBe("#94a3b8");
    });

    it("returns correct color stops across the HPI gradient", () => {
      // Score >= 75: Extreme Priority (Red)
      expect(getHPIColor(85)).toBe("#dc2626");

      // Score 60 - 75: High Priority (Orange)
      expect(getHPIColor(62)).toBe("#ea580c");

      // Score 45 - 60: Moderate-High (Amber)
      expect(getHPIColor(50)).toBe("#f59e0b");

      // Score 30 - 45: Moderate (Yellow)
      expect(getHPIColor(35)).toBe("#eab308");

      // Score 15 - 30: Low-Moderate (Lime)
      expect(getHPIColor(20)).toBe("#84cc16");

      // Score < 15: Low Priority (Green)
      expect(getHPIColor(10)).toBe("#22c55e");
    });
  });

  describe("getLSTColor", () => {
    it("returns neutral gray when LST is null or non-finite", () => {
      expect(getLSTColor(null)).toBe("#94a3b8");
      expect(getLSTColor(NaN)).toBe("#94a3b8");
    });

    it("returns thermal color gradient correctly across 28°C to 48°C", () => {
      // Extreme heat >= 46°C
      expect(getLSTColor(47)).toBe("#7f1d1d");

      // Very Hot >= 43°C
      expect(getLSTColor(44)).toBe("#b91c1c");

      // Hot >= 40°C
      expect(getLSTColor(41)).toBe("#c2410c");

      // Warm >= 34°C
      expect(getLSTColor(35)).toBe("#f59e0b");

      // Moderate >= 30°C
      expect(getLSTColor(31)).toBe("#eab308");

      // Coolest < 30°C
      expect(getLSTColor(28)).toBe("#3b82f6");
    });
  });

  describe("getConfidenceColor", () => {
    it("maps all confidence tiers to distinct palette colors", () => {
      expect(getConfidenceColor("HIGH")).toBe("#059669");
      expect(getConfidenceColor("MODERATE")).toBe("#2563eb");
      expect(getConfidenceColor("LOW")).toBe("#d97706");
      expect(getConfidenceColor("INSUFFICIENT")).toBe("#e11d48");
      expect(getConfidenceColor(null)).toBe("#64748b");
    });
  });

  describe("getPersistenceBadge", () => {
    it("maps persistence tiers to distinct UI badges", () => {
      const chronic = getPersistenceBadge("chronic_hotspot");
      expect(chronic.label).toBe("Chronic Hotspot");
      expect(chronic.bg).toBe("bg-red-100");
      expect(chronic.text).toBe("text-red-800");

      const frequent = getPersistenceBadge("frequent_hotspot");
      expect(frequent.label).toBe("Frequent Hotspot");
      expect(frequent.bg).toBe("bg-orange-100");

      const occasional = getPersistenceBadge("occasional_hotspot");
      expect(occasional.label).toBe("Occasional Hotspot");
      expect(occasional.bg).toBe("bg-amber-100");

      const transient = getPersistenceBadge("transient_extreme");
      expect(transient.label).toBe("Transient Extreme");
      expect(transient.bg).toBe("bg-purple-100");

      const nonHotspot = getPersistenceBadge("non_hotspot");
      expect(nonHotspot.label).toBe("Non-Hotspot");
      expect(nonHotspot.bg).toBe("bg-slate-100");
    });
  });

  describe("getEligibilityInfo", () => {
    it("provides scientific explanations for missing-data and exclusion states", () => {
      const eligible = getEligibilityInfo("ACCEPT");
      expect(eligible.isExcluded).toBe(false);
      expect(eligible.label).toBe("Eligible & Scored");

      const flagged = getEligibilityInfo("FLAG");
      expect(flagged.isExcluded).toBe(false);
      expect(flagged.label).toContain("Flagged");

      const insufficient = getEligibilityInfo("INSUFFICIENT_THERMAL_EVIDENCE");
      expect(insufficient.isExcluded).toBe(true);
      expect(insufficient.label).toBe("Insufficient Thermal Evidence");
      expect(insufficient.explanation).toContain("SQL NULL");

      const exclude = getEligibilityInfo("EXCLUDE");
      expect(exclude.isExcluded).toBe(true);
      expect(exclude.label).toContain("Excluded");
    });
  });

  describe("getOpticalImputationLabel", () => {
    it("distinguishes pure observations from reconstructed / imputed optical signals", () => {
      const clean = getOpticalImputationLabel("NONE");
      expect(clean.isImputed).toBe(false);
      expect(clean.label).toBe("Clean Optical");

      const median = getOpticalImputationLabel("OPTICAL_IMPUTED_MEDIAN");
      expect(median.isImputed).toBe(true);
      expect(median.label).toBe("Median Imputed");

      const boundary = getOpticalImputationLabel("OPTICAL_IMPUTED_BOUNDARY");
      expect(boundary.isImputed).toBe(true);
      expect(boundary.label).toBe("Boundary Imputed");

      const neutral = getOpticalImputationLabel("OPTICAL_FALLBACK_NEUTRAL");
      expect(neutral.isImputed).toBe(true);
      expect(neutral.label).toBe("Neutral Fallback");
    });
  });
});
