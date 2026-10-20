import type { ActiveLayerMode } from "../../types/heatPriority";

interface HPILegendProps {
  layerMode: ActiveLayerMode;
  chronicCount?: number;
  totalCells?: number;
}

export default function HPILegend({
  layerMode,
  chronicCount = 223,
  totalCells = 49747,
}: HPILegendProps) {
  return (
    <div className="pointer-events-none absolute bottom-8 left-3 z-[1000] w-72">
      <div className="pointer-events-auto rounded-lg border border-slate-200/90 bg-white/95 p-3.5 shadow-md backdrop-blur">
        {/* Layer Mode: HPI Priority */}
        {layerMode === "hpi" && (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                Heat Priority Index (HPI)
              </span>
              <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-800">
                0 – 100
              </span>
            </div>

            <div
              className="mt-2 h-3.5 w-full rounded"
              style={{
                background:
                  "linear-gradient(to right, #22c55e, #84cc16, #eab308, #f59e0b, #ea580c, #dc2626)",
              }}
            />

            <div className="mt-1 flex justify-between text-[10px] font-semibold text-slate-600">
              <span>0 (Low)</span>
              <span>30 (Mod)</span>
              <span>60 (High)</span>
              <span>100 (Critical)</span>
            </div>

            <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-2 text-[11px]">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-slate-600">
                  <span className="inline-block h-3 w-3 rounded-full border-2 border-red-600 bg-red-800 shadow-sm" />
                  Chronic Hotspot (Citywide)
                </span>
                <span className="font-bold text-red-700">{chronicCount} cells</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-slate-600">
                  <span className="inline-block h-3 w-3 rounded-sm border border-slate-400 bg-slate-400" />
                  Unavailable / Excluded
                </span>
                <span className="font-medium text-slate-500">SQL NULL</span>
              </div>
            </div>

            <p className="mt-2.5 text-[10px] leading-tight text-slate-500">
              Composite score: Thermal (40%) + Persistence (30%) + Veg Deficit (15%) + Built Density (15%).
            </p>
          </div>
        )}

        {/* Layer Mode: Observed LST */}
        {layerMode === "lst" && (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                Observed Summer LST
              </span>
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
                Landsat 8/9
              </span>
            </div>

            <div
              className="mt-2 h-3.5 w-full rounded"
              style={{
                background:
                  "linear-gradient(to right, #3b82f6, #eab308, #ea580c, #c2410c, #b91c1c, #7f1d1d)",
              }}
            />

            <div className="mt-1 flex justify-between text-[10px] font-semibold text-slate-600">
              <span>&lt;32°C</span>
              <span>38°C</span>
              <span>42°C</span>
              <span>&gt;46°C</span>
            </div>

            <div className="mt-2.5 space-y-1 border-t border-slate-100 pt-2 text-[10px] text-slate-600">
              <div className="flex justify-between">
                <span>Normalization Baseline:</span>
                <span className="font-medium text-slate-800">28.0°C – 48.0°C</span>
              </div>
              <div className="flex justify-between">
                <span>Study Area Extent:</span>
                <span className="font-medium text-slate-800">{totalCells.toLocaleString()} cells (100m)</span>
              </div>
            </div>
          </div>
        )}

        {/* Layer Mode: Confidence & Quality */}
        {layerMode === "confidence" && (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
                Confidence & Quality Tier
              </span>
              <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800">
                Stage C QC
              </span>
            </div>

            <div className="mt-2.5 grid grid-cols-2 gap-1.5 text-[11px]">
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-emerald-600" />
                <span className="font-medium text-slate-700">HIGH (≥0.85)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-blue-600" />
                <span className="font-medium text-slate-700">MODERATE (0.70-0.85)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-amber-600" />
                <span className="font-medium text-slate-700">LOW (0.50-0.70)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-rose-600" />
                <span className="font-medium text-slate-700">INSUFFICIENT (&lt;0.50)</span>
              </div>
            </div>

            <div className="mt-2.5 border-t border-slate-100 pt-2 text-[10px] text-slate-500">
              Optical Imputation: 8-Connected Median, Boundary Mean, or Neutral Climatological Fallback.
            </div>
          </div>
        )}

        {/* Layer Mode: Chronic Hotspots */}
        {layerMode === "chronic" && (
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-red-800">
                Chronic Hotspots Only
              </span>
              <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-800">
                {chronicCount} Verified
              </span>
            </div>

            <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-700">
              <span className="inline-block h-4 w-4 rounded-full border-2 border-red-600 bg-red-800" />
              <span>Multi-year persistent extreme heat cells</span>
            </div>

            <p className="mt-2 text-[10px] leading-tight text-slate-500">
              Criterion: Hotspot frequency ≥50%, ≥3 hot seasons, ≥2 distinct years, and ≥4 qualifying seasons.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
