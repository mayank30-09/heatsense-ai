"""Patch HPIViewportGrid.tsx for landcover."""

from pathlib import Path

p = Path("frontend/src/components/map/HPIViewportGrid.tsx")
content = p.read_text(encoding="utf-8")

target = """    } else if (layerMode === "chronic") {
      fillColor = "#b91c1c";
    }"""

replacement = """    } else if (layerMode === "chronic") {
      fillColor = "#b91c1c";
    } else if (layerMode === "landcover") {
      const topCls = (cell as any).top_class || (cell.heat_priority_score >= 50 ? "built" : (cell.ndvi && cell.ndvi > 0.3 ? "trees" : "bare"));
      fillColor = DW_CLASS_COLORS[topCls] || "#C4281B";
    }"""

if target in content:
    content = content.replace(target, replacement, 1)
    p.write_text(content, encoding="utf-8", newline="\n")
    print("Updated HPIViewportGrid.tsx successfully")
else:
    print("Target not found in HPIViewportGrid.tsx")

