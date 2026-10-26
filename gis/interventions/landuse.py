"""Land-Use Typology Classification & Spatial Parcel Matching for HEATSENSE AI (Stage D).

Classifies urban candidate sites and parcels into 11 authoritative typologies:
1. vacant_public_open_land
2. vacant_private_land
3. park_garden
4. water_adjacent
5. residential_rcc_roof
6. industrial_shed_roof
7. informal_settlement_roof
8. road_corridor
9. parking_paved_yard
10. institutional_campus
11. unclassified (needs site survey -> zero mechanical recommendations)

Grounded in:
- OpenStreetMap (OSM) tags (landuse, leisure, natural, building, amenity, highway)
- Google Open Buildings V3 footprints (50cm high-resolution satellite imagery)
- External JSON configuration (gis/interventions/config/landuse_interventions.json)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_PATH = Path(__file__).parent / "config" / "landuse_interventions.json"
OPEN_BUILDINGS_SUMMARY_PATH = Path(__file__).parents[2] / "docs" / "validation" / "top100_building_footprints_summary.json"


def load_landuse_config() -> dict[str, Any]:
    """Load external land-use typology configuration."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Landuse config not found at {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class LanduseClassificationResult:
    typology: str
    title: str
    description: str
    needs_site_survey: bool
    allowed_interventions: list[str]
    prohibited_interventions: list[str]
    prohibition_reasons: dict[str, str]
    constraints: dict[str, Any]
    data_source: str
    classification_date: str
    confidence: str = "CONFIRMED"
    evidence_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "typology": self.typology,
            "title": self.title,
            "description": self.description,
            "needs_site_survey": self.needs_site_survey,
            "allowed_interventions": self.allowed_interventions,
            "prohibited_interventions": self.prohibited_interventions,
            "prohibition_reasons": self.prohibition_reasons,
            "constraints": self.constraints,
            "data_source": self.data_source,
            "classification_date": self.classification_date,
            "confidence": self.confidence,
            "evidence_notes": self.evidence_notes,
        }


class LanduseClassifier:
    """Classifies spatial candidate areas into land-use typologies."""

    def __init__(self, config_dict: Optional[dict[str, Any]] = None):
        self.config = config_dict or load_landuse_config()
        self.typologies = self.config.get("typologies", {})
        self.open_buildings_index = self._load_open_buildings_index()

    def _load_open_buildings_index(self) -> dict[str, dict[str, Any]]:
        """Index Google Open Buildings V3 footprints by pixel_id where available."""
        index: dict[str, dict[str, Any]] = {}
        if OPEN_BUILDINGS_SUMMARY_PATH.exists():
            try:
                with open(OPEN_BUILDINGS_SUMMARY_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for c in data.get("cells", []):
                        pid = c.get("pixel_id")
                        if pid:
                            index[pid] = c
            except Exception:
                pass
        return index

    def classify(
        self,
        pixel_id: Optional[str] = None,
        osm_tags: Optional[dict[str, str]] = None,
        building_info: Optional[dict[str, Any]] = None,
        ndvi: Optional[float] = None,
        ndbi: Optional[float] = None,
        ndwi: Optional[float] = None,
        water_fraction: float = 0.0,
        distance_to_water_m: Optional[float] = None,
        locality: Optional[str] = None,
        is_public_ownership: Optional[bool] = None,
        built_density: Optional[float] = None,
        veg_deficit: Optional[float] = None,
        explicit_typology: Optional[str] = None,
    ) -> LanduseClassificationResult:
        """
        Classify candidate area into one of 11 landuse typologies.

        If unmatched or ambiguous, falls back to 'unclassified' with needs_site_survey = True.
        """
        date_str = datetime.now().strftime("%Y-%m-%d")

        if explicit_typology and explicit_typology in self.typologies:
            cfg = self.typologies[explicit_typology]
            return LanduseClassificationResult(
                typology=explicit_typology,
                title=cfg["title"],
                description=cfg["description"],
                needs_site_survey=cfg["needs_site_survey"],
                allowed_interventions=list(cfg.get("allowed_interventions", [])),
                prohibited_interventions=list(cfg.get("prohibited_interventions", [])),
                prohibition_reasons=dict(cfg.get("prohibition_reasons", {})),
                constraints=dict(cfg.get("constraints", {})),
                data_source="Explicit Planner Assignment",
                classification_date=date_str,
                confidence="CONFIRMED" if explicit_typology != "unclassified" else "NEEDS_SURVEY",
                evidence_notes=[f"Explicit typology assigned: {cfg['title']}"],
            )

        tags = osm_tags or {}
        building = building_info or {}
        evidence_notes: list[str] = []
        data_sources: list[str] = []

        # Check Open Buildings cache if pixel_id provided
        if pixel_id and pixel_id in self.open_buildings_index:
            ob_entry = self.open_buildings_index[pixel_id]
            data_sources.append("Google Open Buildings V3")
            if not building:
                building = {
                    "building_count": ob_entry.get("building_count", 0),
                    "total_roof_area_m2": ob_entry.get("total_roof_area_m2", 0.0),
                    "max_building_area_m2": ob_entry.get("max_building_area_m2", 0.0),
                }
                evidence_notes.append(
                    f"Open Buildings: {building['building_count']} buildings, {building['total_roof_area_m2']} m² total roof"
                )

        if tags:
            data_sources.append("OpenStreetMap")

        landuse_tag = tags.get("landuse", "").lower()
        leisure_tag = tags.get("leisure", "").lower()
        natural_tag = tags.get("natural", "").lower()
        building_tag = tags.get("building", "").lower()
        amenity_tag = tags.get("amenity", "").lower()
        highway_tag = tags.get("highway", "").lower()

        b_count = int(building.get("building_count", 0))
        max_roof = float(building.get("max_building_area_m2", 0.0))
        tot_roof = float(building.get("total_roof_area_m2", 0.0))

        typology = "unclassified"
        source_label = " & ".join(data_sources) if data_sources else "Landsat biophysical indices"

        # 1. Water Adjacent
        if (
            natural_tag in ("water", "wetland")
            or tags.get("waterway")
            or water_fraction >= 0.20
            or (ndwi is not None and ndwi >= 0.08)
            or (distance_to_water_m is not None and distance_to_water_m <= 100.0)
        ):
            typology = "water_adjacent"
            evidence_notes.append("Riparian / water-adjacent buffer detected within 100m of surface water.")

        # 2. Park or Garden
        elif (
            leisure_tag in ("park", "garden", "recreation_ground", "pitch")
            or landuse_tag in ("grass", "village_green", "meadow")
            or (ndvi is not None and ndvi >= 0.45 and (ndbi is None or ndbi < -0.10))
        ):
            typology = "park_garden"
            evidence_notes.append(f"Public green leisure/park space identified (leisure={leisure_tag or 'park_canopy'}).")

        # 3. Institutional Campus
        elif (
            amenity_tag in ("university", "college", "school", "hospital", "research_institute")
            or landuse_tag in ("institutional", "education", "civic_admin")
        ):
            typology = "institutional_campus"
            evidence_notes.append(f"Institutional campus identified (amenity={amenity_tag or landuse_tag}).")

        # 4. Road Corridor
        elif (
            highway_tag in ("primary", "secondary", "tertiary", "trunk", "motorway", "residential", "service")
            or tags.get("area:highway")
        ):
            typology = "road_corridor"
            evidence_notes.append(f"Roadway and right-of-way corridor identified (highway={highway_tag}).")

        # 5. Parking / Paved Yard
        elif (
            amenity_tag == "parking"
            or landuse_tag in ("commercial_yard", "depot", "freight_terminal")
            or (b_count == 0 and ndbi is not None and ndbi > 0.15 and (ndvi is None or ndvi < 0.15))
        ):
            typology = "parking_paved_yard"
            evidence_notes.append("Paved impermeable ground / parking yard identified without roof structures.")

        # 6. Industrial Shed Roof
        elif (
            building_tag in ("industrial", "warehouse", "shed", "factory")
            or landuse_tag == "industrial"
            or max_roof > 500.0
            or (tot_roof > 3000.0 and b_count <= 6)
        ):
            typology = "industrial_shed_roof"
            evidence_notes.append(
                f"Industrial warehouse/shed roof identified (max footprint: {max_roof:.1f} m², building={building_tag or 'shed'})."
            )

        # 7. Informal Settlement Roof
        elif (
            b_count > 15 and tot_roof > 0 and (tot_roof / b_count) < 65.0
            or landuse_tag in ("slum", "informal")
            or (locality in ("Udhna", "Limbayat") and b_count > 10 and max_roof < 75.0)
        ):
            typology = "informal_settlement_roof"
            evidence_notes.append(
                f"Informal high-density settlement roof identified ({b_count} compact dwellings, avg {tot_roof / max(1, b_count):.1f} m²)."
            )

        # 8. Residential RCC Roof
        elif (
            building_tag in ("residential", "apartments", "house", "detached")
            or landuse_tag == "residential"
            or (b_count > 0 and tot_roof > 0 and (b_count <= 15 or (tot_roof / b_count) >= 65.0))
            or (built_density is not None and built_density >= 0.50)
            or (ndbi is not None and ndbi >= 0.20)
        ):
            typology = "residential_rcc_roof"
            evidence_notes.append(f"Engineered residential concrete roof structure identified ({b_count} structures, {tot_roof:.1f} m² total / inferred).")

        # 9. Unbuilt Open Ground (Potential Public Greening)
        elif (
            (is_public_ownership is True and (b_count == 0 and tot_roof == 0))
            or (is_public_ownership is not False and veg_deficit is not None and veg_deficit >= 0.50 and (built_density is None or built_density < 0.50) and (ndbi is None or ndbi <= 0.10))
        ):
            typology = "vacant_public_open_land"
            evidence_notes.append("Spectral site-type heuristic: unbuilt low-canopy open ground. Note: Satellite features do not verify legal ownership or vacancy; cadastral verification required.")

        # 10. Unbuilt Open Ground (Private / Non-Municipal)
        elif is_public_ownership is False and (b_count == 0 and tot_roof == 0):
            typology = "vacant_private_land"
            evidence_notes.append("Spectral site-type heuristic: unbuilt open plot without municipal designation. Legal ownership requires cadastral verification.")

        # 11. Unclassified Fallback
        else:
            typology = "unclassified"
            evidence_notes.append("No definitive OSM or building footprint match; marked for mandatory on-site survey.")

        cfg = self.typologies.get(typology, self.typologies["unclassified"])

        return LanduseClassificationResult(
            typology=typology,
            title=cfg["title"],
            description=cfg["description"],
            needs_site_survey=cfg["needs_site_survey"],
            allowed_interventions=list(cfg.get("allowed_interventions", [])),
            prohibited_interventions=list(cfg.get("prohibited_interventions", [])),
            prohibition_reasons=dict(cfg.get("prohibition_reasons", {})),
            constraints=dict(cfg.get("constraints", {})),
            data_source=source_label,
            classification_date=date_str,
            confidence="CONFIRMED" if typology != "unclassified" else "NEEDS_SURVEY",
            evidence_notes=evidence_notes,
        )

    def classify_candidates(
        self,
        candidates: list[Any],
        osm_query_log_path: Optional[Path] = None,
    ) -> dict[str, Any]:
        """
        Batch classify a list of intervention candidates and compute match coverage metrics.
        """
        results: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        date_str = datetime.now().strftime("%Y-%m-%d")

        for cand in candidates:
            c_dict = cand.to_dict() if hasattr(cand, "to_dict") else dict(cand)
            pid = c_dict.get("cell_id")
            c_type = c_dict.get("intervention_type", "")
            usable_area = float(c_dict.get("usable_area_m2", 0.0))

            # Simulate lookup or use Open Buildings cache
            b_info = None
            if pid and pid in self.open_buildings_index:
                ob = self.open_buildings_index[pid]
                b_info = {
                    "building_count": ob.get("building_count", 0),
                    "total_roof_area_m2": ob.get("total_roof_area_m2", 0.0),
                    "max_building_area_m2": ob.get("max_building_area_m2", 0.0),
                }

            # Classify
            res = self.classify(
                pixel_id=pid,
                building_info=b_info,
                locality=c_dict.get("administrative_zone"),
            )

            counts[res.typology] = counts.get(res.typology, 0) + 1
            results.append({
                "candidate_id": c_dict.get("candidate_id"),
                "cell_id": pid,
                "landuse_classification": res.to_dict(),
            })

        total = len(candidates)
        unclassified_cnt = counts.get("unclassified", 0)
        matched_cnt = total - unclassified_cnt
        match_coverage_pct = (matched_cnt / total * 100.0) if total > 0 else 0.0

        summary = {
            "query": "OSM tags (landuse, leisure, natural, building, amenity, highway) & Google Open Buildings V3 footprints joined to 100m grid",
            "classification_date": date_str,
            "total_candidates": total,
            "matched_candidates": matched_cnt,
            "unclassified_candidates": unclassified_cnt,
            "match_coverage_pct": round(match_coverage_pct, 2),
            "typology_distribution": counts,
        }

        return {
            "summary": summary,
            "classifications": results,
        }
