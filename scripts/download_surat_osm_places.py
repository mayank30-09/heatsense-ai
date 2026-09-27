from __future__ import annotations

import json
import time
from pathlib import Path

import requests
import osm2geojson


# ---------------------------------------------------------------------------
# STUDY AREA
# ---------------------------------------------------------------------------

# Slightly larger than the Surat SMC boundary so that locality boundaries
# touching the study-area edge are also captured.

SOUTH = 21.00
WEST = 72.65
NORTH = 21.36
EAST = 73.00


# ---------------------------------------------------------------------------
# OUTPUT PATHS
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("data/raw/place_names")

RAW_JSON = (
    OUTPUT_DIR / "surat_osm_places_raw.json"
)

BOUNDARIES_GEOJSON = (
    OUTPUT_DIR / "surat_osm_place_boundaries.geojson"
)

POINTS_GEOJSON = (
    OUTPUT_DIR / "surat_osm_place_points.geojson"
)


# ---------------------------------------------------------------------------
# OVERPASS QUERY
# ---------------------------------------------------------------------------

OVERPASS_QUERY = f"""
[out:json][timeout:120];

(
    relation
        ["boundary"="place"]
        ["place"~"^(suburb|quarter|neighbourhood|village|town|locality)$"]
        ({SOUTH},{WEST},{NORTH},{EAST});

    way
        ["boundary"="place"]
        ["place"~"^(suburb|quarter|neighbourhood|village|town|locality)$"]
        ({SOUTH},{WEST},{NORTH},{EAST});

    way
        ["place"~"^(suburb|quarter|quarter|neighbourhood|village|town|locality)$"]
        ({SOUTH},{WEST},{NORTH},{EAST})
        (if:is_closed());

    node
        ["place"~"^(suburb|quarter|neighbourhood|village|town|locality)$"]
        ({SOUTH},{WEST},{NORTH},{EAST});
);

out body geom;
"""


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 70)
    print("HEATSENSE AI - Surat OSM Place Dataset")
    print("=" * 70)

    print()
    print("Study bounding box:")
    print(
        f"South={SOUTH}, "
        f"West={WEST}, "
        f"North={NORTH}, "
        f"East={EAST}"
    )

    print()
    print("Querying OpenStreetMap Overpass...")
    print("This is a one-time data acquisition step.")
    print()

    # -----------------------------------------------------------------------
    # OVERPASS REQUEST
    # -----------------------------------------------------------------------

    OVERPASS_ENDPOINT = (
        "https://overpass-api.de/api/interpreter"
    )

    headers = {
        "User-Agent": (
            "HEATSENSE-AI/0.1 "
            "(academic GIS project; "
            "OpenStreetMap place-data acquisition)"
        )
    }

    response = None

    for attempt in range(1, 4):
        try:
            print(
                f"Overpass request attempt "
                f"{attempt}/3..."
            )

            response = requests.post(
                OVERPASS_ENDPOINT,
                data={
                    "data": OVERPASS_QUERY,
                },
                headers=headers,
                timeout=180,
            )

            response.raise_for_status()

            print(
                f"Overpass request successful "
                f"(HTTP {response.status_code})."
            )

            break

        except requests.RequestException as exc:
            print(
                f"Overpass request failed: {exc}"
            )

            if attempt == 3:
                raise RuntimeError(
                    "Overpass request failed after "
                    "3 attempts."
                ) from exc

            print(
                "Waiting 10 seconds before retrying..."
            )

            time.sleep(10)

    if response is None:
        raise RuntimeError(
            "No response received from Overpass."
        )

    # -----------------------------------------------------------------------
    # READ OVERPASS RESPONSE
    # -----------------------------------------------------------------------

    raw_text = response.text
    raw_data = response.json()

    RAW_JSON.write_text(
        raw_text,
        encoding="utf-8",
    )

    print(
        f"Raw Overpass data saved to:\n  {RAW_JSON}"
    )

    elements = raw_data.get(
        "elements",
        [],
    )

    print()
    print(
        f"OSM elements received: "
        f"{len(elements)}"
    )

    # -----------------------------------------------------------------------
    # CONVERT OSM JSON TO GEOJSON
    # -----------------------------------------------------------------------

    print()
    print(
        "Converting OSM geometries to GeoJSON..."
    )

    geojson = osm2geojson.json2geojson(
        raw_data
    )

    features = geojson.get(
        "features",
        []
    )

    # -----------------------------------------------------------------------
    # CLASSIFY FEATURES
    # -----------------------------------------------------------------------

    boundary_features = []
    point_features = []

    for feature in features:
        geometry = feature.get(
            "geometry"
        )

        properties = feature.get(
            "properties",
            {}
        )

        tags = properties.get(
            "tags",
            {}
        )

        name = tags.get(
            "name"
        )

        place_type = tags.get(
            "place"
        )

        # Ignore unnamed features.
        if not name or not place_type:
            continue

        geometry_type = (
            geometry.get("type")
            if geometry
            else None
        )

        # Keep only the information we need.
        cleaned_properties = {
            "osm_id": properties.get("id"),
            "osm_type": properties.get("type"),
            "name": name,
            "place": place_type,
            "boundary": tags.get("boundary"),
        }

        feature["properties"] = (
            cleaned_properties
        )

        if geometry_type in {
            "Polygon",
            "MultiPolygon",
        }:
            boundary_features.append(
                feature
            )

        elif geometry_type == "Point":
            point_features.append(
                feature
            )

    # -----------------------------------------------------------------------
    # BUILD GEOJSON FEATURE COLLECTIONS
    # -----------------------------------------------------------------------

    boundary_collection = {
        "type": "FeatureCollection",
        "features": boundary_features,
    }

    point_collection = {
        "type": "FeatureCollection",
        "features": point_features,
    }

    # -----------------------------------------------------------------------
    # SAVE BOUNDARIES
    # -----------------------------------------------------------------------

    BOUNDARIES_GEOJSON.write_text(
        json.dumps(
            boundary_collection,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # -----------------------------------------------------------------------
    # SAVE POINTS
    # -----------------------------------------------------------------------

    POINTS_GEOJSON.write_text(
        json.dumps(
            point_collection,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # -----------------------------------------------------------------------
    # PRINT SUMMARY
    # -----------------------------------------------------------------------

    print()
    print(
        f"Place boundary features: "
        f"{len(boundary_features)}"
    )

    print(
        f"Place point features: "
        f"{len(point_features)}"
    )

    # -----------------------------------------------------------------------
    # PRINT BOUNDARY NAMES
    # -----------------------------------------------------------------------

    print()
    print("Boundary names:")

    boundary_names = sorted(
        {
            feature["properties"]["name"]
            for feature in boundary_features
        }
    )

    if boundary_names:
        for name in boundary_names:
            print(f"  - {name}")
    else:
        print("  (none)")

    # -----------------------------------------------------------------------
    # PRINT POINT NAMES
    # -----------------------------------------------------------------------

    print()
    print("Point names:")

    point_names = sorted(
        {
            feature["properties"]["name"]
            for feature in point_features
        }
    )

    if point_names:
        for name in point_names:
            print(f"  - {name}")
    else:
        print("  (none)")

    # -----------------------------------------------------------------------
    # COMPLETE
    # -----------------------------------------------------------------------

    print()
    print("=" * 70)
    print("OSM PLACE DATA ACQUISITION COMPLETE")
    print("=" * 70)

    print()
    print(
        f"Boundary GeoJSON:\n"
        f"  {BOUNDARIES_GEOJSON}"
    )

    print(
        f"Point GeoJSON:\n"
        f"  {POINTS_GEOJSON}"
    )

    print()
    print(
        "Next stage: inspect the dataset before "
        "importing anything into PostGIS."
    )


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()