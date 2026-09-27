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
                "linear-gradient(to right, rgb(0,0,255), rgb(0,255,255), rgb(0,255,0), rgb(255,255,0), rgb(255,0,0))",
            }}
          />

          <div className="mt-1 flex justify-between text-[11px] font-medium text-slate-600">
            <span>20°C</span>
            <span>35°C</span>
            <span>50°C</span>
          </div>

          <div className="mt-2 border-t border-slate-100 pt-2 text-[10px] leading-4 text-slate-500">
            Landsat-derived surface temperature.
            <br />
            Visualization range: 20–50°C.
          </div>
        </div>
      </div>
    </>
  );
}