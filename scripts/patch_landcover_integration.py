"""Helper script to integrate Dynamic World land cover into candidates, clustering, and API."""

import re

# 1. Update gis/interventions/__init__.py
with open("gis/interventions/__init__.py", "r", encoding="utf-8") as f:
    init_code = f.read()

target1 = """    unit_rate: float = 0.0
    unit_rate_unit: str = ""
    markups_description: str = "Includes 18% GST, 12% contingency, 6% design & supervision, and scaled site setup" """
# handle any trailing space/crlf
pattern1 = r'(\s+markups_description: str = [^\n]+)'
replacement1 = r"""\1
    landcover_assessment: dict[str, Any] | None = None
    landcover_rule_fired: str = "NONE"
    landcover_disclosure: str = "ASSUMPTION: UNCALIBRATED_HEURISTIC"
    landcover_version: str = "v1.0"
    landcover_top_class: str | None = None
    landcover_confidence: float | None = None
    landcover_entropy: float | None = None"""

pattern2 = r'(\s+"survey_prerequisites": self\.survey_prerequisites,)'
replacement2 = r"""\1
            "landcover_assessment": self.landcover_assessment,
            "landcover_rule_fired": self.landcover_rule_fired,
            "landcover_disclosure": self.landcover_disclosure,
            "landcover_version": self.landcover_version,
            "landcover_top_class": self.landcover_top_class,
            "landcover_confidence": self.landcover_confidence,
            "landcover_entropy": self.landcover_entropy,"""

new_init = re.sub(pattern1, replacement1, init_code, count=1)
new_init = re.sub(pattern2, replacement2, new_init, count=1)

with open("gis/interventions/__init__.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(new_init)

print("Updated gis/interventions/__init__.py successfully.")

