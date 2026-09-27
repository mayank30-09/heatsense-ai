from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point


# ---------------------------------------------------------------------------
# INPUTS
# ---------------------------------------------------------------------------

PLACES_FILE = Path(
    "data/raw/place_names/surat_osm_place_points.geojson"
)

SMC_BOUNDARY_FILE = Path(
    "data/raw/boundaries/surat_smc_boundary.geojson"
)


# ---------------------------------------------------------------------------
# OUTPUTS
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(
    "data/processed/place_names"
)

ALL_PLACES_OUTPUT = (
    OUTPUT_DIR / "surat_osm_places_validated.geojson"
)

SMC_PLACES_OUTPUT = (
    OUTPUT_DIR / "surat_smc_locality_candidates.geojson"
)

REPORT_OUTPUT = (
    OUTPUT_DIR / "surat_osm_places_validation_report.json"
)


# ---------------------------------------------------------------------------
# PLACE CLASSIFICATION
# ---------------------------------------------------------------------------

def classify_place(place_type: str) -> str:
    """
    Preserve the original OSM place type while assigning a HEATSENSE
    interpretation class.

    This does NOT modify the source OSM classification.
    """

    if place_type == "town":
        return "settlement"

    if place_type == "village":
        return "settlement"

    if place_type == "suburb":
        return "urban_locality"

    if place_type == "locality":
        return "urban_locality"

    if place_type == "neighbourhood":
        return "micro_locality"

    return "other"


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("HEATSENSE AI - Surat OSM Place Validation")
    print("=" * 70)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -----------------------------------------------------------------------
    # LOAD PLACE DATA
    # -----------------------------------------------------------------------

    print()
    print("Loading OSM place points...")

    places = gpd.read_file(
        PLACES_FILE
    )

    print(
        f"Loaded OSM places: "
        f"{len(places)}"
    )

    # -----------------------------------------------------------------------
    # BASIC GEOMETRY VALIDATION
    # -----------------------------------------------------------------------

    if places.empty:
        raise RuntimeError(
            "OSM place dataset is empty."
        )

    if places.crs is None:
        raise RuntimeError(
            "OSM place dataset has no CRS."
        )

    print(
        f"Place CRS: {places.crs}"
    )

    # The extraction is expected to be EPSG:4326.
    places = places.to_crs(
        "EPSG:4326"
    )

    invalid_geometry_count = int(
        (~places.geometry.is_valid).sum()
    )

    empty_geometry_count = int(
        places.geometry.is_empty.sum()
    )

    non_point_count = int(
        (
            places.geometry.geom_type
            != "Point"
        ).sum()
    )

    print(
        f"Invalid geometries: "
        f"{invalid_geometry_count}"
    )

    print(
        f"Empty geometries: "
        f"{empty_geometry_count}"
    )

    print(
        f"Non-point geometries: "
        f"{non_point_count}"
    )

    # -----------------------------------------------------------------------
    # LOAD SMC BOUNDARY
    # -----------------------------------------------------------------------

    print()
    print("Loading Surat SMC boundary...")

    smc = gpd.read_file(
        SMC_BOUNDARY_FILE
    )

    if smc.empty:
        raise RuntimeError(
            "Surat SMC boundary is empty."
        )

    if smc.crs is None:
        raise RuntimeError(
            "Surat SMC boundary has no CRS."
        )

    smc = smc.to_crs(
        "EPSG:4326"
    )

    smc_geometry = smc.geometry.union_all()

    print(
        f"SMC boundary CRS: {smc.crs}"
    )

    # -----------------------------------------------------------------------
    # CLASSIFY PLACES
    # -----------------------------------------------------------------------

    places["place_type"] = (
        places["place"]
        .fillna("")
        .astype(str)
        .str.lower()
    )

    places["candidate_class"] = (
        places["place_type"]
        .apply(classify_place)
    )

    places["inside_smc"] = (
        places.geometry
        .within(smc_geometry)
    )

    # -----------------------------------------------------------------------
    # DUPLICATE NAME CHECK
    # -----------------------------------------------------------------------

    name_counts = Counter(
        places["name"]
        .fillna("")
        .astype(str)
    )

    places["duplicate_name"] = (
        places["name"]
        .map(name_counts)
        .fillna(0)
        .astype(int)
        > 1
    )

    # -----------------------------------------------------------------------
    # SOURCE METADATA
    # -----------------------------------------------------------------------

    places["source"] = (
        "OpenStreetMap"
    )

    places["source_dataset"] = (
        "Surat OSM place extraction"
    )

    # -----------------------------------------------------------------------
    # SAVE ALL VALIDATED PLACES
    # -----------------------------------------------------------------------

    places.to_file(
        ALL_PLACES_OUTPUT,
        driver="GeoJSON",
    )

    # -----------------------------------------------------------------------
    # FILTER SMC LOCALITY CANDIDATES
    # -----------------------------------------------------------------------

    locality_types = {
        "town",
        "suburb",
        "neighbourhood",
        "locality",
        "village",
    }

    smc_places = places[
        places["inside_smc"]
        & places["place_type"].isin(
            locality_types
        )
    ].copy()

    smc_places = smc_places.sort_values(
        by=[
            "place_type",
            "name",
        ]
    )

    smc_places.to_file(
        SMC_PLACES_OUTPUT,
        driver="GeoJSON",
    )

    # -----------------------------------------------------------------------
    # TYPE COUNTS
    # -----------------------------------------------------------------------

    all_type_counts = {
        str(key): int(value)
        for key, value in (
            places["place_type"]
            .value_counts()
            .to_dict()
            .items()
        )
    }

    smc_type_counts = {
        str(key): int(value)
        for key, value in (
            smc_places["place_type"]
            .value_counts()
            .to_dict()
            .items()
        )
    }

    # -----------------------------------------------------------------------
    # REPORT
    # -----------------------------------------------------------------------

    report = {
        "input": str(
            PLACES_FILE
        ),
        "smc_boundary": str(
            SMC_BOUNDARY_FILE
        ),
        "total_places": int(
            len(places)
        ),
        "places_inside_smc": int(
            len(smc_places)
        ),
        "invalid_geometries": (
            invalid_geometry_count
        ),
        "empty_geometries": (
            empty_geometry_count
        ),
        "non_point_geometries": (
            non_point_count
        ),
        "all_place_type_counts": (
            all_type_counts
        ),
        "smc_place_type_counts": (
            smc_type_counts
        ),
        "duplicate_name_count": int(
            places["duplicate_name"].sum()
        ),
    }

    REPORT_OUTPUT.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # -----------------------------------------------------------------------
    # TERMINAL SUMMARY
    # -----------------------------------------------------------------------

    print()
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    print()
    print(
        f"Total OSM places: "
        f"{len(places)}"
    )

    print(
        f"Places inside SMC: "
        f"{len(smc_places)}"
    )

    print()
    print("All OSM place types:")

    for place_type, count in sorted(
        all_type_counts.items()
    ):
        print(
            f"  {place_type}: {count}"
        )

    print()
    print(
        "SMC locality candidate types:"
    )

    for place_type, count in sorted(
        smc_type_counts.items()
    ):
        print(
            f"  {place_type}: {count}"
        )

    print()
    print(
        "SMC locality candidates:"
    )

    for _, row in smc_places.iterrows():
        print(
            f"  - {row['name']} "
            f"| {row['place_type']} "
            f"| {row['candidate_class']}"
        )

    print()
    print(
        f"Validated dataset:\n"
        f"  {ALL_PLACES_OUTPUT}"
    )

    print(
        f"SMC locality candidates:\n"
        f"  {SMC_PLACES_OUTPUT}"
    )

    print(
        f"Validation report:\n"
        f"  {REPORT_OUTPUT}"
    )

    print()
    print("=" * 70)
    print("OSM PLACE VALIDATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()