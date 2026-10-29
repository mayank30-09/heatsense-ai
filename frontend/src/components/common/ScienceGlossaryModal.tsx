import { useEffect, useMemo, useState } from "react";

interface ScienceGlossaryModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface GlossaryEntry {
  term: string;
  abbreviation?: string;
  category: "Remote Sensing" | "Index Formulation" | "Climatology" | "Intervention Physics";
  summary: string;
  details: string;
  reference?: string;
}

const GLOSSARY_ENTRIES: GlossaryEntry[] = [
  {
    term: "Land Surface Temperature vs. 2m Ambient Air Temperature",
    abbreviation: "LST (T_skin) vs. T_air",
    category: "Remote Sensing",
    summary:
      "Radiant radiometric skin temperature of physical ground surfaces (~10:30 local solar time, about 11:00 IST) is physically distinct from ambient 2 m air temperature.",
    details:
      "Landsat 8/9 TIRS-2 measures thermal infrared radiation emitted by surfaces (asphalt, concrete RCC roofs, vegetative canopy, water). During morning summer overpasses in Surat (~10:30 local solar time / ~11:00 IST), dark dry impervious surfaces often reach 48°C–54°C. In contrast, standard weather stations measure ambient air temperature at 2 m above ground, which is moderated by atmospheric convective mixing and typically measures 8°C–12°C cooler than sunlit surfaces during peak solar irradiance.",
    reference: "Voogt & Oke (2003); USGS Landsat Collection 2 Level-2 Surface Temperature",
  },
  {
    term: "Heat Priority Index",
    abbreviation: "HPI (Stage C)",
    category: "Index Formulation",
    summary:
      "Canonical 0–100 composite prioritization score combining four transparent physical layers without opaque black-box collapse.",
    details:
      "HPI = 100 × (0.40 × T_norm + 0.30 × P_persist + 0.15 × V_deficit + 0.15 × B_density). Normalized using verified baseline constants: LST normalized over [30.0°C, 50.0°C], Vegetation Deficit over NDVI [0.05, 0.45], Built-Up Density over NDBI [-0.25, 0.15], and Multi-Year Heat Persistence [0.0, 1.0]. Missing summer LST results in strict NULL score to prevent synthetic imputation.",
    reference: "SMC Urban Heat Action Plan (UHAP 2026); gis/heat_priority/scoring.py",
  },
  {
    term: "Multi-Year Heat Persistence",
    abbreviation: "P_persist",
    category: "Climatology",
    summary:
      "Fraction of observed summer seasons where a 100m grid cell ranks among the citywide upper thermal deciles.",
    details:
      "Calculated across multi-year validated satellite overpasses across Surat. Categorized into four persistence tiers: Chronic Hotspot (frequency ≥ 0.50 with multi-year recurrence), Frequent Hotspot (0.35–0.50), Occasional Hotspot (0.20–0.35), and Transient Extreme (< 0.20). Distinguishes persistent structural microclimate traps from transient meteorological heat spikes.",
    reference: "gis/heat_priority/persistence.py",
  },
  {
    term: "Chronic Heat Hotspots",
    abbreviation: "223 Cells (SMC)",
    category: "Index Formulation",
    summary:
      "Highest-priority 100m analytical grid cells exhibiting persistent extreme heat vulnerability across consecutive years.",
    details:
      "In Surat, exactly 223 cells satisfy the strict multi-year chronic criteria: hotspot frequency ≥ 0.50, at least 3 hot seasons, at least 2 distinct observation years, and at least 4 qualifying observation seasons. These 223 cells receive top priority for Stage D municipal cooling interventions.",
    reference: "Stage C Verified Catalog; Table stage_c_hpi_scores",
  },
  {
    term: "Quality & Confidence Index",
    abbreviation: "C_i (Quality Tier)",
    category: "Remote Sensing",
    summary:
      "Observational reliability rating [0.0, 1.0] reflecting QA saturation masks, cloud contamination distance, and clear-sky pass frequency.",
    details:
      "Derived from Landsat QA_PIXEL cloud/shadow masks and QA_RADSAT thermal radiometric saturation flags. Classified into four operational tiers: HIGH (C_i ≥ 0.85, primary policy grade), MODERATE (0.70 ≤ C_i < 0.85), LOW (0.50 ≤ C_i < 0.70), and INSUFFICIENT (C_i < 0.50, excluded from municipal intervention prioritization).",
    reference: "gis/heat_priority/quality.py",
  },
  {
    term: "Seasonal Composite vs. Single Scene",
    abbreviation: "Composite vs. Single Overpass",
    category: "Remote Sensing",
    summary:
      "Multi-scene pixel-wise median composites provide stable baseline climatology; single scenes provide near-real-time snapshots.",
    details:
      "Seasonal composites aggregate multiple cloud-free overpasses over a 3-month seasonal window (e.g., 22 scenes for Summer 2026, 14 scenes for Post-Monsoon 2025) using pixel-wise median filtering to eliminate transient cloud shadows and smoke anomalies. In contrast, single scenes capture an instantaneous snapshot (~10:30 local solar time / ~11:00 IST) for rapid post-event inspection.",
    reference: "gis/gee/seasonal_features.py; backend/app/api/v1/rasters.py",
  },
  {
    term: "Linearized Microclimate Heat Dissipation Model",
    abbreviation: "Linearized Energy Balance (h_eff = 45.6 W/m²·K)",
    category: "Intervention Physics",
    summary:
      "First-order linearized heat dissipation model governed by empirical aerodynamic and radiative conductance, not numerical PDE or CFD solvers.",
    details:
      "Stage D estimates local skin cooling using a simplified, uncalibrated heat dissipation equation (ΔT_cell = f_treated · |ΔT_skin| · C_attenuation · η_cell) with effective conductance h_eff = 45.6 W/(m²·K) and solar irradiance (870 W/m²). Direct coating skin drop is ~8.59°C, while cell-scale cooling incorporates 15% footprint fraction and empirical attenuation (0.372) yielding ~0.57°C. Not field-validated with in-situ sensors in Surat. This empirical formulation enforces physical saturation caps (e.g. tree canopy -3.5°C, cool roof -2.5°C, max combined -4.5°C) and sub-additive attenuation, but is not a full numerical CFD or PDE surface-energy-balance solver.",
    reference: "Akbari et al. (2001); Santamouris (2017); Bowler et al. (2010)",
  },
  {
    term: "Canonical 100m Analytical Grid & Resolution",
    abbreviation: "100m Grid",
    category: "Remote Sensing",
    summary:
      "100 m is the analysis/reporting grid. Landsat TIRS native thermal sampling is about 100 m (distributed at 30 m); 30 m optical indices are aggregated to the grid. Cells are not building- or street-level measurements.",
    details:
      "100 m is the analysis/reporting grid. Landsat TIRS native thermal sampling is about 100 m (distributed at 30 m); 30 m optical indices are aggregated to the grid. Cells are not building- or street-level measurements.",
    reference: "USGS Landsat 8/9 Level-2 Science Product Guide; SMC Analytical Domain",
  },
];

export default function ScienceGlossaryModal({
  isOpen,
  onClose,
}: ScienceGlossaryModalProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [searchTerm, setSearchTerm] = useState<string>("");

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const categories = useMemo(() => {
    return ["ALL", "Remote Sensing", "Index Formulation", "Climatology", "Intervention Physics"];
  }, []);

  const filteredEntries = useMemo(() => {
    return GLOSSARY_ENTRIES.filter((entry) => {
      const matchesCategory = selectedCategory === "ALL" || entry.category === selectedCategory;
      const matchesSearch =
        !searchTerm.trim() ||
        entry.term.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (entry.abbreviation && entry.abbreviation.toLowerCase().includes(searchTerm.toLowerCase())) ||
        entry.summary.toLowerCase().includes(searchTerm.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [selectedCategory, searchTerm]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="glossary-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-xs"
    >
      <div className="relative max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-7 shadow-2xl scrollbar-thin">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-teal-50 px-2.5 py-0.5 text-xs font-bold text-teal-800 border border-teal-200 font-mono">
                Scientific Reference
              </span>
              <span className="text-xs text-slate-400 font-mono">HEATSENSE AI Standards</span>
            </div>
            <h2 id="glossary-modal-title" className="mt-1 text-2xl font-extrabold text-slate-900 tracking-tight">
              Science &amp; Metric Glossary
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Authoritative definitions, thermodynamic grounding, and remote sensing standards for Surat Municipal Corporation.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close glossary modal"
            className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 cursor-pointer focus:outline-none focus:ring-2 focus:ring-teal-600 transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Filter & Search Bar */}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-1">
            {categories.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setSelectedCategory(cat)}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-all cursor-pointer ${
                  selectedCategory === cat
                    ? "bg-slate-900 text-white shadow-2xs font-bold"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {cat === "ALL" ? "All Categories" : cat}
              </button>
            ))}
          </div>

          <div className="relative">
            <input
              type="text"
              placeholder="Search concepts, terms..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-48 sm:w-56 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm("")}
                className="absolute right-2 top-1.5 text-xs text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Entry List */}
        <div className="mt-5 space-y-4">
          {filteredEntries.map((entry) => (
            <div
              key={entry.term}
              className="rounded-xl border border-slate-200/90 bg-slate-50/60 p-4 transition-all hover:border-teal-300 hover:bg-white hover:shadow-xs"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-sm font-extrabold text-slate-900">
                    {entry.term}
                  </h3>
                  {entry.abbreviation && (
                    <span className="rounded-md bg-slate-200/80 px-2 py-0.5 font-mono text-[11px] font-bold text-slate-700">
                      {entry.abbreviation}
                    </span>
                  )}
                </div>

                <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-bold text-teal-800 border border-teal-200">
                  {entry.category}
                </span>
              </div>

              <p className="mt-2 text-xs font-semibold text-slate-900 leading-relaxed">
                {entry.summary}
              </p>

              <p className="mt-1.5 text-xs text-slate-600 leading-relaxed">
                {entry.details}
              </p>

              {entry.reference && (
                <div className="mt-2 text-[10px] text-slate-400 italic">
                  Reference: {entry.reference}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="mt-6 flex justify-end border-t border-slate-100 pt-4">
          <button
            type="button"
            onClick={onClose}
            className="btn-primary text-xs"
          >
            Close Glossary
          </button>
        </div>
      </div>
    </div>
  );
}
