"""Patch gis/interventions/optimization.py to carry landcover fields in deployments."""

from pathlib import Path

path = Path("gis/interventions/optimization.py")
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

target = """                "prerequisites_status": getattr(c, "prerequisites_status", "FEASIBLE_SUBJECT_TO_SURVEY"),
                "survey_prerequisites": prereqs,
            })"""

replacement = """                "prerequisites_status": getattr(c, "prerequisites_status", "FEASIBLE_SUBJECT_TO_SURVEY"),
                "survey_prerequisites": prereqs,
                "landcover_rule_fired": getattr(c, "landcover_rule_fired", "NONE"),
                "landcover_top_class": getattr(c, "landcover_top_class", None),
                "landcover_confidence": getattr(c, "landcover_confidence", None),
                "landcover_entropy": getattr(c, "landcover_entropy", None),
                "landcover_disclosure": getattr(c, "landcover_disclosure", "ASSUMPTION: UNCALIBRATED_HEURISTIC"),
            })"""

if target in code:
    code = code.replace(target, replacement)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    print("Patched gis/interventions/optimization.py successfully")
else:
    print("Target not found in gis/interventions/optimization.py")

