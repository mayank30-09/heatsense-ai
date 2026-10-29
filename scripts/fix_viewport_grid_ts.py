from pathlib import Path

p = Path("frontend/src/components/map/HPIViewportGrid.tsx")
c = p.read_text(encoding="utf-8")

old_str = """    } else if (layerMode === "landcover") {
      const topCls = (cell as any).top_class || (cell.heat_priority_score >= 50 ? "built" : (cell.ndvi && cell.ndvi > 0.3 ? "trees" : "bare"));
      fillColor = DW_CLASS_COLORS[topCls] || "#C4281B";
    }"""

new_str = """    } else if (layerMode === "landcover") {
      const topCls = (cell as any).top_class || ((cell.heat_priority_score ?? 0) >= 50 ? "built" : ((cell.vegetation_deficit_component ?? 0) < 0.4 ? "trees" : "bare"));
      fillColor = DW_CLASS_COLORS[topCls] || "#C4281B";
    }"""

assert old_str in c, "target not found"
p.write_text(c.replace(old_str, new_str, 1), encoding="utf-8", newline="\n")
print("Fixed HPIViewportGrid TypeScript successfully")

