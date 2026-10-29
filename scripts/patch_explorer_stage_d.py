from pathlib import Path

path = Path("frontend/src/components/interventions/InterventionExplorer.tsx")
content = path.read_text(encoding="utf-8")

# 1. Add typeAvailability state
state_target = '  // Evidence & Physics Rationale Modal State\n  const [evidenceModalCluster, setEvidenceModalCluster] = useState<ClusterRecommendation | null>(null);'
state_replacement = state_target + """

  // Type availability map (assessable status and package counts)
  const [typeAvailability, setTypeAvailability] = useState<TypeAvailabilityMap | null>(null);

  useEffect(() => {
    let cancelled = false;
    const areaParam = selectedArea === 'All Areas (Overview)' ? undefined : selectedArea;
    fetchTypeAvailability(areaParam, 35.0)
      .then((avail) => {
        if (!cancelled) setTypeAvailability(avail);
      })
      .catch((err) => {
        console.error('Failed to load type availability:', err);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedArea]);"""

assert state_target in content, "state_target not found"
content = content.replace(state_target, state_replacement, 1)

# 2. Update type chips rendering
chips_target = """          {(Object.keys(TYPE_CONFIG) as InterventionType[]).map((itype) => {
            const cfg = TYPE_CONFIG[itype];
            const isSelected = selectedType === itype;
            return (
              <button
                key={itype}
                type="button"
                onClick={() => {
                  setSelectedType(itype);
                  setClusterPage(1);
                }}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
                  isSelected
                    ? "bg-slate-900 text-white shadow-xs"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                <span>{cfg.icon}</span>
                <span>{cfg.label}</span>
              </button>
            );
          })}"""

chips_replacement = """          {(Object.keys(TYPE_CONFIG) as InterventionType[]).map((itype) => {
            const cfg = TYPE_CONFIG[itype];
            const isSelected = selectedType === itype;
            const avail = typeAvailability?.[itype];
            let badgeText: string | null = null;
            let isUnassessable = false;

            if (avail) {
              if (!avail.is_assessable) {
                isUnassessable = true;
                if (itype === "rainwater_fed_pond") {
                  badgeText = "Not assessable: missing DEM/drainage";
                } else if (itype === "green_wall") {
                  badgeText = "Add-on only: missing facade heights";
                } else {
                  badgeText = "Not assessable";
                }
              } else {
                badgeText = `${avail.candidate_packages_count} pkgs`;
              }
            }

            return (
              <button
                key={itype}
                type="button"
                onClick={() => {
                  setSelectedType(itype);
                  setClusterPage(1);
                }}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
                  isSelected
                    ? "bg-slate-900 text-white shadow-xs"
                    : isUnassessable
                    ? "bg-slate-100/70 text-slate-500 hover:bg-slate-200/80 border border-dashed border-slate-300"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                <span>{cfg.icon}</span>
                <span>{cfg.label}</span>
                {badgeText && (
                  <span
                    className={`rounded px-1.5 py-0.2 text-[9.5px] font-mono font-bold ${
                      isUnassessable
                        ? isSelected
                          ? "bg-amber-300 text-amber-950"
                          : "bg-amber-100 text-amber-800 border border-amber-200"
                        : isSelected
                        ? "bg-slate-700 text-slate-100"
                        : "bg-slate-200 text-slate-700"
                    }`}
                  >
                    {badgeText}
                  </span>
                )}
              </button>
            );
          })}"""

assert chips_target in content, "chips_target not found"
content = content.replace(chips_target, chips_replacement, 1)

# 3. Add Unassessable Typology Explanation Banner right below the Filter Bar
banner_target = """        </div>
      </div>

      {/* =====================================================================
          VIEW MODE 1: AREA CLUSTERS (SMC MUNICIPAL RECOMMENDATION PACKAGES)
          ===================================================================== */}"""

banner_replacement = """        </div>
      </div>

      {/* Unassessable Typology Explanation Banner */}
      {selectedType !== "ALL" && typeAvailability?.[selectedType] && !typeAvailability[selectedType].is_assessable && (
        <div className="rounded-2xl border border-amber-300 bg-amber-50/90 p-5 text-xs text-amber-950 shadow-xs">
          <div className="flex items-start gap-3">
            <span className="text-2xl">⚠️</span>
            <div className="flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="rounded-full bg-amber-200/80 px-2.5 py-0.5 text-xs font-bold text-amber-900 font-mono">
                  Biophysical Assessment Unavailable
                </span>
                <span className="text-xs text-amber-800 font-bold">
                  {typeAvailability[selectedType].title}
                </span>
              </div>
              <h4 className="mt-2 text-sm font-extrabold text-amber-950">
                Data Prerequisite Not Met in Local Spatial Catalog
              </h4>
              <p className="mt-1 leading-relaxed text-amber-900">
                {typeAvailability[selectedType].reason}
              </p>
              <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="bg-white/80 p-3 rounded-xl border border-amber-200">
                  <span className="font-bold text-amber-950 block mb-1">Available Local Data:</span>
                  <p className="text-[11px] text-slate-600 leading-normal">
                    {typeAvailability[selectedType].data_available}
                  </p>
                </div>
                <div className="bg-white/80 p-3 rounded-xl border border-amber-200">
                  <span className="font-bold text-amber-950 block mb-1">Required Missing Layer:</span>
                  <p className="text-[11px] text-slate-600 leading-normal">
                    {typeAvailability[selectedType].data_needed}
                  </p>
                </div>
                <div className="bg-white/80 p-3 rounded-xl border border-amber-200">
                  <span className="font-bold text-amber-950 block mb-1">Pre-Tender Field Prerequisite:</span>
                  <p className="text-[11px] text-slate-600 leading-normal">
                    {typeAvailability[selectedType].prerequisites}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          VIEW MODE 1: AREA CLUSTERS (SMC MUNICIPAL RECOMMENDATION PACKAGES)
          ===================================================================== */}"""

assert banner_target in content, "banner_target not found"
content = content.replace(banner_target, banner_replacement, 1)

# 4. Add Evidence Modal sections (Dynamic World sub-pixel, 15% mortality, mature crown vs spacing)
modal_target = """            {/* Physical Assumptions & Pre-Tender Requirements */}
            {evidenceModalCluster.evidence_rationale && (
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5">
                  <span className="font-bold text-slate-700 block mb-1">Modeling Assumptions & Uncertainties</span>
                  <ul className="list-disc pl-4 space-y-1 text-slate-600 text-[11px]">
                    {evidenceModalCluster.evidence_rationale.uncertainties.map((assump: string, idx: number) => (
                      <li key={idx}>{assump}</li>
                    ))}
                  </ul>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-3.5">
                  <span className="font-bold text-amber-900 block mb-1">Mandatory Pre-Tender Field Survey</span>
                  <ul className="list-disc pl-4 space-y-1 text-amber-800 text-[11px]">
                    {evidenceModalCluster.evidence_rationale.survey_requirements.map((req: string, idx: number) => (
                      <li key={idx}>{req}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}"""

modal_replacement = modal_target + """

            {/* Dynamic World 10m LULC Sub-Pixel Continuous Probability & Biophysical Evidence */}
            {evidenceModalCluster.evidence_rationale && (
              <div className="mt-4 rounded-xl border border-teal-200 bg-teal-50/50 p-4 text-xs text-teal-950">
                <div className="flex items-center gap-2 font-bold text-teal-900 mb-1.5">
                  <span>🛰️</span>
                  <span>Dynamic World 10m LULC Sub-Pixel Modeling &amp; Crown Biophysics</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[11px] leading-relaxed text-teal-950 mt-2">
                  <div className="bg-white/80 p-3 rounded-lg border border-teal-100">
                    <strong className="block text-teal-900 font-bold mb-1">Continuous Probability &amp; Margin:</strong>
                    Continuous probabilities across 9 classes (Brown et al., 2022, Sci Data, CC BY 4.0).
                    Candidate parcel boundaries evaluate classification margin (P<sub>top1</sub> − P<sub>top2</sub>) and Shannon entropy (H = −Σ p<sub>i</sub> ln p<sub>i</sub>) rather than fragile binary thresholding.
                  </div>
                  {evidenceModalCluster.intervention_type === "tree_canopy" ? (
                    <div className="bg-white/80 p-3 rounded-lg border border-teal-100">
                      <strong className="block text-teal-900 font-bold mb-1">Crown Geometry &amp; 15% Mortality Buffer:</strong>
                      Mature crown horizontal projection is modeled at <strong>50.3 m²</strong> (π × 4.0² m for 8m mature crown) vs municipal planting grid of <strong>45.0 m²</strong> (6.7m × 6.7m pit spacing).
                      An explicit <strong>15% mortality replacement buffer</strong> is included directly in Capex to guarantee survival during 3-year establishment.
                    </div>
                  ) : (
                    <div className="bg-white/80 p-3 rounded-lg border border-teal-100">
                      <strong className="block text-teal-900 font-bold mb-1">Surface Energy Balance &amp; Albedo:</strong>
                      Direct skin cooling (ΔT<sub>skin</sub> = −Δα·I / h<sub>eff</sub>) modeled under May solar overpass (870 W/m², h<sub>eff</sub> = 45.6 W/(m²·K)).
                      Aged solar reflectance α = 0.65 (ASTM D7897); 2m ambient air temperature is unmodeled.
                    </div>
                  )}
                </div>
              </div>
            )}"""

assert modal_target in content, "modal_target not found"
content = content.replace(modal_target, modal_replacement, 1)

path.write_text(content, encoding="utf-8")
print("Successfully patched InterventionExplorer.tsx!")

