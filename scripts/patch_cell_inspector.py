"""Patch CellInspector.tsx to include the Dynamic World Land Cover Composition & Uncertainty panel."""

from pathlib import Path

path = Path("frontend/src/components/map/CellInspector.tsx")
content = path.read_text(encoding="utf-8")

# 1. Add fetchCellLandCover import
import_target = 'import type { SceneItem } from "../../services/scenesApi";'
import_repl = """import type { SceneItem } from "../../services/scenesApi";
import { fetchCellLandCover } from "../../services/interventionsApi";
import type { CellLandCoverData } from "../../types/interventions";"""

if import_target in content and "fetchCellLandCover" not in content:
    content = content.replace(import_target, import_repl, 1)

# 2. Add state and effect in CellInspector
state_target = "  const [showHistory, setShowHistory] = useState(false);"
state_repl = """  const [showHistory, setShowHistory] = useState(false);
  const [landcoverData, setLandcoverData] = useState<CellLandCoverData | null>(null);
  const [landcoverLoading, setLandcoverLoading] = useState(false);

  useEffect(() => {
    if (!cell?.pixel_id) {
      setLandcoverData(null);
      return;
    }
    let isMounted = true;
    setLandcoverLoading(true);
    fetchCellLandCover(cell.pixel_id, "summer", 2024)
      .then((data) => {
        if (isMounted) {
          setLandcoverData(data);
          setLandcoverLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setLandcoverData(null);
          setLandcoverLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [cell?.pixel_id]);"""

if state_target in content and "landcoverData" not in content:
    content = content.replace(state_target, state_repl, 1)

# 3. Add the Land Cover UI block before Methodological Context
panel_target = "      {/* Methodological Context & Physical Distinctions */}"
panel_repl = """      {/* Dynamic World Land Cover Composition & Uncertainty Panel */}
      <div className="mt-3 rounded-xl border border-teal-200/90 bg-teal-50/40 p-3 text-xs shadow-2xs">
        <div className="flex items-center justify-between pb-1.5 border-b border-teal-200/70 mb-2">
          <div className="flex items-center gap-1.5">
            <span className="text-base">🌍</span>
            <span className="text-[11px] font-bold uppercase tracking-wider text-teal-950">
              Dynamic World Land Cover (10m LULC)
            </span>
          </div>
          <span className="rounded bg-teal-100 px-1.5 py-0.5 text-[9.5px] font-semibold text-teal-800">
            Sentinel-2 Model
          </span>
        </div>

        {landcoverLoading && (
          <div className="py-2 text-center text-[11px] text-teal-700 font-medium animate-pulse">
            Loading satellite land-cover observations…
          </div>
        )}

        {!landcoverLoading && !landcoverData && (
          <div className="py-1 text-[11px] text-slate-500 italic">
            No seasonal Dynamic World observations recorded for this cell.
          </div>
        )}

        {!landcoverLoading && landcoverData && (
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div className="rounded-lg bg-white p-2 border border-teal-100">
                <span className="text-[10px] text-slate-500 uppercase font-bold">Top Land Cover</span>
                <div className="mt-0.5 text-sm font-bold capitalize text-slate-900 flex items-center gap-1.5">
                  <span
                    className="inline-block h-3 w-3 rounded-xs shrink-0"
                    style={{
                      backgroundColor:
                        landcoverData.top_class === "built" ? "#C4281B" :
                        landcoverData.top_class === "trees" ? "#397D49" :
                        landcoverData.top_class === "grass" ? "#88B053" :
                        landcoverData.top_class === "crops" ? "#E49635" :
                        landcoverData.top_class === "water" ? "#419BDF" : "#A59B8F",
                    }}
                  />
                  <span>{landcoverData.top_class || "Unclassified"}</span>
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  Confidence: {landcoverData.confidence !== null ? `${(landcoverData.confidence * 100).toFixed(1)}%` : "N/A"}
                </div>
              </div>

              <div className="rounded-lg bg-white p-2 border border-teal-100">
                <span className="text-[10px] text-slate-500 uppercase font-bold">Diagnostics</span>
                <div className="mt-0.5 text-[11px] font-mono text-slate-800 font-semibold">
                  Entropy: {landcoverData.entropy !== null ? landcoverData.entropy.toFixed(3) : "N/A"}
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  {landcoverData.valid_observation_count} valid overpasses
                </div>
              </div>
            </div>

            {/* 9-Class Probability Bars */}
            <div className="rounded-lg bg-white p-2 border border-teal-100 space-y-1.5">
              <span className="text-[10px] text-slate-500 uppercase font-bold">Class Mean Probabilities</span>
              <div className="grid grid-cols-3 gap-1.5 text-[10px]">
                {Object.entries(landcoverData.probabilities || {}).map(([cls, prob]) => {
                  if (prob === null || prob === undefined || prob < 0.01) return null;
                  const colors: Record<string, string> = {
                    built: "#C4281B",
                    trees: "#397D49",
                    grass: "#88B053",
                    crops: "#E49635",
                    shrub_and_scrub: "#DFC35A",
                    water: "#419BDF",
                    bare: "#A59B8F",
                    flooded_vegetation: "#7A87C6",
                    snow_and_ice: "#B39FE1",
                  };
                  return (
                    <div key={cls} className="flex items-center justify-between font-mono bg-slate-50 px-1.5 py-0.5 rounded">
                      <span className="capitalize text-slate-700 truncate mr-1" style={{ color: colors[cls] || "#334155" }}>
                        {cls.replace("_", " ").slice(0, 7)}
                      </span>
                      <span className="font-bold text-slate-900">{(prob * 100).toFixed(0)}%</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Suitability Assessment */}
            {landcoverData.suitability && (
              <div className="rounded-lg bg-emerald-50/80 p-2 border border-emerald-200 text-[10px] space-y-1">
                <div className="flex items-center justify-between font-semibold text-emerald-950">
                  <span>Rule: {landcoverData.suitability.rule_fired}</span>
                  <span className="font-mono text-[9px] px-1 py-0.2 bg-emerald-200 text-emerald-900 rounded">
                    {landcoverData.suitability.screening_status}
                  </span>
                </div>
                <p className="text-emerald-900 leading-snug">
                  {landcoverData.suitability.screening_reason}
                </p>
                <div className="pt-1 border-t border-emerald-200/60 text-[9px] text-emerald-800 font-mono">
                  {landcoverData.suitability.scientific_notice}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Methodological Context & Physical Distinctions */}"""

if panel_target in content and "Dynamic World Land Cover (10m LULC)" not in content:
    content = content.replace(panel_target, panel_repl, 1)

path.write_text(content, encoding="utf-8", newline="\n")
print("Updated CellInspector.tsx successfully")

