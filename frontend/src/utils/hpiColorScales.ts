/**
 * Scientific color scales and formatters for Stage C Heat Priority layers.
 */

export function getHPIColor(score: number | null, isChronic: boolean = false): string {
  if (score === null || isNaN(score)) {
    return "#94a3b8"; // Muted slate gray for missing/insufficient data
  }
  if (isChronic) {
    return "#991b1b"; // Deep crimson for chronic hotspot
  }
  if (score >= 75) return "#dc2626"; // Extreme priority: Red
  if (score >= 60) return "#ea580c"; // High priority: Orange
  if (score >= 45) return "#f59e0b"; // Moderate-High: Amber
  if (score >= 30) return "#eab308"; // Moderate: Yellow
  if (score >= 15) return "#84cc16"; // Low-Moderate: Lime
  return "#22c55e"; // Low priority: Green
}

export function getLSTColor(tempC: number | null): string {
  if (tempC === null || isNaN(tempC)) {
    return "#94a3b8";
  }
  // Standardized 20°C - 60°C thermal scale
  if (tempC >= 55.0) return "#7f1d1d"; // >= 55°C: Deep Crimson
  if (tempC >= 45.0) return "#ea580c"; // 45°C - 55°C: Burnt Orange / Red
  if (tempC >= 35.0) return "#f59e0b"; // 35°C - 45°C: Yellow / Amber
  if (tempC >= 25.0) return "#10b981"; // 25°C - 35°C: Cyan / Emerald
  return "#3b82f6"; // < 25°C: Deep Blue
}

export function getConfidenceColor(tier: string | null): string {
  switch (tier?.toUpperCase()) {
    case "HIGH":
      return "#059669"; // Emerald
    case "MODERATE":
      return "#2563eb"; // Blue
    case "LOW":
      return "#d97706"; // Amber
    case "INSUFFICIENT":
      return "#e11d48"; // Rose/Red
    default:
      return "#64748b"; // Neutral gray
  }
}

export function getPersistenceBadge(tier: string | null): {
  label: string;
  bg: string;
  text: string;
  border: string;
} {
  switch (tier) {
    case "chronic_hotspot":
      return {
        label: "Chronic Hotspot",
        bg: "bg-red-100",
        text: "text-red-800",
        border: "border-red-300",
      };
    case "frequent_hotspot":
      return {
        label: "Frequent Hotspot",
        bg: "bg-orange-100",
        text: "text-orange-800",
        border: "border-orange-300",
      };
    case "occasional_hotspot":
      return {
        label: "Occasional Hotspot",
        bg: "bg-amber-100",
        text: "text-amber-800",
        border: "border-amber-300",
      };
    case "transient_extreme":
      return {
        label: "Transient Extreme",
        bg: "bg-purple-100",
        text: "text-purple-800",
        border: "border-purple-300",
      };
    case "non_hotspot":
    default:
      return {
        label: "Non-Hotspot",
        bg: "bg-slate-100",
        text: "text-slate-700",
        border: "border-slate-200",
      };
  }
}

export function getOpticalImputationLabel(flag: string | null): {
  label: string;
  description: string;
  isImputed: boolean;
} {
  switch (flag) {
    case "OPTICAL_IMPUTED_MEDIAN":
      return {
        label: "Median Imputed",
        description: "Reconstructed from 8-connected spatial neighbor median (≥4 valid neighbors)",
        isImputed: true,
      };
    case "OPTICAL_IMPUTED_BOUNDARY":
      return {
        label: "Boundary Imputed",
        description: "Reconstructed from boundary neighbor mean (1-3 valid neighbors)",
        isImputed: true,
      };
    case "OPTICAL_FALLBACK_NEUTRAL":
      return {
        label: "Neutral Fallback",
        description: "Assigned climatological neutral median (isolated cell with 0 valid neighbors)",
        isImputed: true,
      };
    case "NONE":
    default:
      return {
        label: "Clean Optical",
        description: "Authoritative direct Landsat 8/9 observation with zero nodata corruption",
        isImputed: false,
      };
  }
}

export function getEligibilityInfo(status: string | null): {
  label: string;
  isExcluded: boolean;
  explanation: string;
} {
  switch (status) {
    case "ACCEPT":
      return {
        label: "Eligible & Scored",
        isExcluded: false,
        explanation: "Passed all Stage C QC filters with valid summer thermal evidence.",
      };
    case "FLAG":
      return {
        label: "Flagged / Marginal Quality",
        isExcluded: false,
        explanation: "Accepted with confidence penalty due to high QA uncertainty or boundary effect.",
      };
    case "INSUFFICIENT_THERMAL_EVIDENCE":
      return {
        label: "Insufficient Thermal Evidence",
        isExcluded: true,
        explanation: "Zero valid Landsat thermal observations in summer 2026. HPI score is unavailable (SQL NULL).",
      };
    case "EXCLUDE":
      return {
        label: "Excluded from Scoring",
        isExcluded: true,
        explanation: "Disqualified due to cloud cover, persistent water, or sub-threshold confidence.",
      };
    default:
      return {
        label: status || "Unknown",
        isExcluded: status !== "ACCEPT" && status !== "FLAG",
        explanation: "Cell status unclassified.",
      };
  }
}
