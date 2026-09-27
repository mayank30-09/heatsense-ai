from __future__ import annotations

import json
from pathlib import Path

from geoalchemy2.shape import from_shape
from shapely.geometry import shape
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.models.osm_place import OSMPlace


SOURCE = Path(
    "data/processed/place_names/surat_osm_places_validated.geojson"
)


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Validated OSM dataset not found: {SOURCE}"
        )

    with SOURCE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    features = data.get("features", [])

    if not features:
        raise ValueError("Validated OSM GeoJSON contains no features.")

    engine = create_engine(get_settings().database_url)

    inserted = 0
    updated = 0
    skipped = 0

    with Session(engine) as session:
        for feature in features:
            properties = feature.get("properties", {})
            geometry = feature.get("geometry")

            if not geometry:
                skipped += 1
                continue

            osm_id = properties.get("osm_id")
            osm_type = properties.get("osm_type")
            name = properties.get("name")

            if osm_id is None or not osm_type or not name:
                skipped += 1
                continue

            geom = shape(geometry)

            if geom.is_empty or not geom.is_valid:
                skipped += 1
                continue

            existing = session.scalar(
                select(OSMPlace).where(
                    OSMPlace.osm_id == osm_id,
                    OSMPlace.osm_type == osm_type,
                )
            )

            values = {
                "osm_id": osm_id,
                "osm_type": osm_type,
                "name": name,
                "place_type": properties.get(
                    "place_type",
                    "unknown",
                ),
                "candidate_class": properties.get(
                    "candidate_class",
                    "unknown",
                ),
                "inside_smc": bool(
                    properties.get("inside_smc", False)
                ),
                "duplicate_name": bool(
                    properties.get("duplicate_name", False)
                ),
                "source": properties.get(
                    "source",
                    "OpenStreetMap",
                ),
                "source_dataset": properties.get(
                    "source_dataset",
                    "surat_osm_places_validated",
                ),
                "geometry": from_shape(
                    geom,
                    srid=4326,
                ),
            }

            if existing:
                for key, value in values.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                session.add(OSMPlace(**values))
                inserted += 1

        session.commit()

    print("OSM PLACE IMPORT COMPLETE")
    print(f"FEATURES  = {len(features)}")
    print(f"INSERTED  = {inserted}")
    print(f"UPDATED   = {updated}")
    print(f"SKIPPED   = {skipped}")


if __name__ == "__main__":
    main()
