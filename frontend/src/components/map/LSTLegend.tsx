export default function LSTLegend() {
  return (
    <>
      {/* Active layer label */}
      <div className="pointer-events-none absolute right-3 top-3 z-[1000]">
        <div className="rounded-md border border-slate-200 bg-white/95 px-3 py-2 shadow-sm backdrop-blur">
          <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
            Active Layer
          </div>

          <div className="mt-0.5 text-sm font-semibold text-slate-900">
            Land Surface Temperature
          </div>

          <div className="mt-0.5 text-[11px] text-slate-500">
            Landsat LST · ~100 m thermal-scale output
          </div>
        </div>
      </div>

      {/* LST legend */}
      <div className="pointer-events-none absolute bottom-8 left-3 z-[1000] w-64">
        <div className="rounded-md border border-slate-200 bg-white/95 p-3 shadow-sm backdrop-blur">
          <div className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-slate-600">
            Land Surface Temperature
          </div>

          <div
            className="h-3 w-full rounded-sm"
            style={{
              background:
                "linear-gradient(to right, rgb(59,130,246), rgb(16,185,129), rgb(245,158,11), rgb(234,88,12), rgb(127,29,29))",
            }}
          />

          <div className="mt-1 flex justify-between text-[11px] font-medium text-slate-600">
            <span>20°C</span>
            <span>30°C</span>
            <span>40°C</span>
            <span>50°C</span>
            <span>60°C</span>
          </div>

          <div className="mt-2 flex items-center justify-between border-t border-slate-100 pt-2 text-[10px] text-slate-600">
            <span className="flex items-center gap-1.5">
              <span
                className="inline-block h-3.5 w-3.5 rounded-xs border border-slate-400 bg-slate-300"
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(45deg, #cbd5e1 0, #cbd5e1 2px, transparent 0, transparent 4px)",
                }}
              />
              <span>NoData / cloud-masked</span>
            </span>
            <span className="font-medium text-slate-400">Transparent</span>
          </div>

          <div className="mt-2 border-t border-slate-100 pt-2 text-[10px] leading-4 text-slate-500">
            Fixed 20–60°C rendering range with out-of-range clipping.
            <br />
            <strong>Physical Distinction:</strong> Land Surface Temperature (LST) is radiometric surface (skin) temperature, not 2 m ambient air temperature.
          </div>
        </div>
      </div>
    </>
  );
}